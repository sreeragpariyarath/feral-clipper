# Feral Clipper — product plan

A local, single-user app that turns a finished stream (Twitch VOD link or a video file on disk) into
ready-to-post 9:16 clips, fully automatically, with every step visible in a modern web UI.

Not commercial software and not published. It runs on this PC only (backend + frontend started locally).

---

## 1. Goal

Paste a URL or a file path → press Start → the app does everything below on its own and shows live
progress for each step:

1. Download the video and audio (or use the local file), with %, size, speed and time left.
2. Extract the audio.
3. Transcribe the whole stream (Whisper, local GPU).
4. Find loud / active parts (audio loudness, sound tags, picture change).
5. Find hook lines in the transcript (strong words, questions, reactions).
6. Take frame strips of each candidate and check what is on screen.
7. Combine transcript + audio + picture into a score sheet.
8. Judge each candidate with Claude (title, hook, score, reasons). Later: Gemini / local model.
9. Find and track the streamer's face (per second, not one box per clip).
10. Render the clips (punch layout, captions, campaign logo).
11. Show the clips for review: approve / reject / edit title and caption / download / delete.

---

## 2. What exists today

| Area | Current state | Where |
|---|---|---|
| Download | yt-dlp download of a Twitch VOD (video + audio), retries | `clipper/sources/vod_source.py`, `audio_detect.py` |
| Moment finding (sound) | chat spikes, or loud-audio spikes when there is no chat | `clipper/detect/detector.py`, `audio_detect.py` |
| Moment finding (picture) | frame scan with CLIP / Claude contact sheets | `clipper/detect/frame_scan.py` |
| Monitor | per-second loudness + picture change, 30 s windows, filters, score sheet | `clipper/detect/energy.py`, `monitor.py` |
| Transcription | Whisper large-v3-turbo on GPU, **per clip window** | `clipper/ai/transcribe.py` |
| Judge | Claude only; heuristic fallback when there is no key | `clipper/ai/judge.py` |
| Face | MediaPipe face finder, **one fixed box per clip** | `clipper/render/face_track.py` |
| Render | 6 layouts incl. punch (title box, webcam, gameplay), captions, campaign logo | `clipper/render/media.py`, `layouts.py` |
| Commands | `vod.py`, `scan.py`, `merge.py`, `monitor.py`, `run_stream.py`, `cut.py` | repo root |
| Review API | stdlib HTTP server: sessions, clips, review, delete (trash), jobs | replaced by `backend/` (Phase 1–2.5) |
| Jobs | one background thread, log file, % parsed from yt-dlp output | replaced by `backend/worker/` |
| Frontend | Next.js 15 + Tailwind: Library page, New stream page, components | `review_ui/frontend` |

---

## 3. What is missing (the gaps)

**Automation and jobs**
- A job is one Python thread inside the API process. Restarting the API loses the job's tracking.
- No queue, no cancel, no retry, no resume from the last finished step.
- Progress is parsed from raw tool output; only the download step has a real %.
- No list of steps per job (what is done, what is running, how long each took).
- Only Twitch links; no local file input.

**Pipeline**
- Whisper runs again for every clip (slow: about 10 min per clip in the last run). The whole stream
  should be transcribed once and reused.
- No transcript-based hook finder (strong words, questions, reactions).
- Picture check measures change, not action (camera pans and club lights score as "action").
- Hook and payoff checks pass almost everything, so they don't rank anything.
- Face position is fixed per clip; a webcam that moves mid-clip is lost.
- The judge only speaks Claude; no Gemini or local model; no cost tracking.
- Steps are not separated into functions with progress callbacks; they are scripts calling scripts.

**Data**
- No database. State is spread over JSON files (`session.json`, `status.json`, `judge.json`,
  `review.json`, `monitor.json`, job files).
- No campaign records (rules, logo, caption, payout, deadline) — the campaign lives in `config.json`.
- No record of what was posted where, or how many views it got.

**Frontend**
- Two pages only. No dashboard, no job detail with step timeline, no settings, no campaigns,
  no live activity panel.
- Polling every few seconds instead of live updates.

**Quality / safety**
- No tests. Errors in long jobs are only visible in log files.
- No disk policy (one stream is 18–38 GB).

---

## 4. Target architecture

```
frontend/  (Next.js, React, Tailwind)  ──HTTP + live events (SSE)──►  backend/  (FastAPI, Python)
                                                                        │
                                                                        ├── SQLite database (jobs, steps, streams, clips, campaigns, settings)
                                                                        ├── job queue (table in SQLite)
                                                                        └── worker process ── runs pipeline steps ── clipper/ (existing pipeline package)
```

**Backend: FastAPI (Python).** The whole pipeline is Python (Whisper, MediaPipe, ffmpeg wrappers), so the
API and the worker stay in Python and import `clipper/` directly. FastAPI gives typed endpoints, file
serving with seeking, and Server-Sent Events for live progress.

**Database: SQLite** (via SQLAlchemy / SQLModel). One file, no server to install, enough for one user.

**Queue and worker: SQLite-backed queue + one worker process.**
- The API only writes a job row; a separate worker process picks up jobs and runs the steps.
- Restarting the API or the frontend does not stop a running job.
- One worker at a time on purpose: the GPU (Whisper, MediaPipe, NVENC) is a single shared resource.
- Why not BullMQ: BullMQ is a Node.js library on Redis. Our steps are Python, so we would need Node
  workers calling Python — an extra layer and an extra service (Redis) for no gain on one PC.
  If more workers are needed later, the same design moves to Redis with `arq` or `RQ` (Python).

**Live progress: Server-Sent Events.** The worker writes step events (started / progress % / message /
done / failed) to the database; the API streams them to the browser.

**Keys and settings: `.env`** (already git-ignored) for API keys; everything else in the settings table,
editable in the UI. Keys never reach the browser.

---

## 5. Pipeline steps (each one a function with a progress callback)

| # | Step | Output | Progress shown |
|---|---|---|---|
| 1 | Ingest — download URL or register local file | `vod.mp4` | %, MB, speed, time left |
| 2 | Extract audio | `audio.wav` / `audio.mp4` | % of duration |
| 3 | Transcribe whole stream (once) | `transcript.json` (words + times) | % of duration |
| 4 | Signals — loudness, sound tags (PANNs), picture change | `signals.npz` | % of duration |
| 5 | Candidates — sliding windows + filters | `candidates.json` | windows scored |
| 6 | Hook finder — transcript lines with strong words, questions, reactions | hook times per candidate | candidates done |
| 7 | Visual check — frame strip per candidate (CLIP local; Claude vision optional) | what is on screen | candidates done |
| 8 | Score sheet — combine 4–7, keep top N | `scores.json` | — |
| 9 | Judge — Claude (later Gemini / local) for title, hook, score, reasons | `judge.json` per clip | clips judged, cost so far |
| 10 | Face track — face position every second, smoothed | `face_track.json` | clips done |
| 11 | Render — punch layout, moving webcam crop, captions, logo | `clip.mp4`, `thumb.jpg` | clips rendered |
| 12 | Ready for review | clips in Library | — |

Every step saves its output, so a job can resume from the last finished step after a crash or a cancel.

---

## 6. Frontend (pages and components)

**Layout**
- Left: sidebar with logo, navigation, collapse.
- Centre: the page.
- Right: activity panel — running job, current step, %, time left, recent events. Visible on every page.

**Pages**
| Page | Contents |
|---|---|
| Dashboard | running job, recent streams, clips waiting for review, disk usage, API credit used |
| New job | URL or local file path, campaign, number of clips, layout; Start |
| Jobs | list with state; filters |
| Job detail | step timeline (12 steps), live %, per-step time, log viewer (clean, collapsible), cancel / retry |
| Streams | each downloaded stream, size, clips made, delete stream data |
| Clip library | grid, filters, sort, approve / reject / delete, bulk actions |
| Clip detail | player, title / caption / tags editor, score sheet, judge notes, transcript, re-render |
| Score sheet | candidate table with sub-scores and charts |
| Campaigns | rules, logo overlay, caption, payout, platforms, active / ended |
| Posted | which clip went where, views entered by hand, payout estimate |
| Trash | deleted clips; restore / delete forever |
| Settings | API keys status (set / missing, never the value), judge provider, Whisper model, layout defaults, disk rules |

**Components:** design-system pieces (Button, Card, Badge, Progress, Tabs, Dialog, Table, Toast), app pieces
(Sidebar, ActivityPanel, StepTimeline, JobCard, ClipCard, VideoPlayer, ScoreBars, LogViewer, EmptyState).
Built ourselves with Tailwind (no code copied from SupoClip — its license limits use for paid work).

---

## 7. Phases

### Status

| Phase | State |
|---|---|
| 0 — Foundation | **Done** (2026-11-26). `backend/` created, frontend moved to `frontend/`, `start_all.bat`. Stray-file cleanup waits for review (list below). |
| 1 — Backend core | **Done** (2026-11-26). SQLite + worker + live events + v1 API + routes for the current frontend. Tested: job survives API restart, cancel, retry, live events, video seeking. |
| 2 — Pipeline as steps | **Built** (2026-11-26). 12 step functions in `backend/pipeline/steps.py`, each run as its own process by the worker, with progress, resume (finished outputs are skipped), URL or local file input, whole-stream transcript reused by every clip, token tracking per job. Tested end to end on a 3-minute local file. Full AsianJeff run: steps 1–8 in progress; steps 9–12 need the Anthropic key in `.env`. |
| 2.5 — Clean architecture | **Done** (2026-11-26). Schemas, services, thin routes, one module per step, prefix-sum scoring, tests. |
| 3 — Frontend v2 | **Done** (2026-11-26). TanStack Query, live events over SSE, 11 pages, design-system components. |
| 4 — Clip quality | **Built** (2026-11-26). Action score, payoff named by the judge, judge sees frames, per-second face crop, provider switch. Waits on your review of the AsianJeff clips. |
| 5 — Campaigns and posting | **Done** (2026-11-26). Campaign on jobs (logo, caption, brief), posting kit, Posted page with payout. |
| 6 — Reliability | **Done** (2026-11-26). Readable step errors with hints, retry from the failed step, disk checks, video delete, DB backup. |

Cleanup (2026-11-26): removed the old copies (`config.backup.json`, `picks.backup.json`, `gta6_knowledge.*.bak.json`, `backups/*.bak.*`), one-time scripts (`finish_restructure.bat`, `setup_git.bat`), test leftovers (`cam_test.jpg`, `update_raw.txt`, test streams and videos) and the old review server. Fixed `.gitignore`: `*.ts` (video) was also hiding the frontend's TypeScript files.

### Phase 0 — Foundation and cleanup
- New layout: `backend/` (FastAPI app), `frontend/` (move `review_ui/frontend`), keep `clipper/` as the pipeline package.
- Keep the existing CLI commands working.
- One settings loader: `.env` for keys, defaults in code, overrides in the database later.
- Remove stray files (`backups/`, `*.bak.json`, `update_raw.txt`, test images) after review.
- **Done when:** backend and frontend start with one command each; old commands still run.

### Phase 1 — Backend core: database, queue, worker, live events
- SQLite models: `stream`, `job`, `job_step`, `clip`, `campaign`, `setting`, `event`.
- Endpoints: jobs (create / list / detail / cancel / retry), streams, clips (list / update / delete / restore),
  media (video with seeking, thumbnails), settings, campaigns, SSE `/events`.
- Worker process: picks queued jobs, runs steps in order, writes step events, handles cancel.
- Import existing JSON data (current AsianJeff stream) into the database.
- **Done when:** a job survives an API restart; the browser receives live step events.

### Phase 2 — Pipeline as steps
- Split the pipeline into the 12 step functions with a shared progress callback.
- Ingest: Twitch URL **and** local file path.
- Transcribe the whole stream once; clips reuse it (big speed-up).
- Resume from the last finished step; skip steps whose output already exists.
- Track Claude tokens and cost per job.
- **Done when:** one Start button takes a URL to rendered clips with no manual step, and the
  AsianJeff stream runs end to end.

### Phase 2.5 — Clean architecture (backend)
- Typed request / response schemas (Pydantic) for every route; no hand-built dicts in routes.
- Service layer: routes only parse input, call a service, return a schema.
- One module per pipeline step under `backend/pipeline/steps/`, plus a step registry.
- Remove dead and duplicate code: `review_ui/server.py`, `review_ui/jobs.py`; retire `api/compat.py` when the frontend moves to `/api/v1` (Phase 3).
- Full type hints; no silent broad `except` blocks (log and re-raise, or handle a named error).
- Window scoring with prefix sums: each 30 s window in O(1), the whole stream in O(n).
- Tests (pytest): services, step skip / resume, window scoring, API routes.
- **Done when:** tests pass, routes contain no business logic, each step is its own module, and a full job still runs.
- **Status (2026-11-26): done.** `backend/schemas/`, `backend/services/` (errors mapped to HTTP in `app.py`),
  `backend/api/routes/` (one thin router per resource), `backend/pipeline/registry.py` + `steps/<name>.py`,
  prefix-sum pre-gate + bisect spacing in `clipper/detect/energy.py` (same results, 4.4× faster on a 5 h stream),
  `review_ui/` removed, 21 pytest tests (`python -m pytest tests`). Job 8 ran all 12 steps on a fresh file.

### Phase 3 — Frontend v2
- App shell: sidebar, activity panel, toasts, dark / light theme.
- Pages from section 6, in this order: New job → Job detail → Clip library → Clip detail → Dashboard →
  Streams → Settings → Campaigns → Trash → Posted.
- Live updates over SSE (no polling).
- **Done when:** every step of a running job is visible live, and a clip can be reviewed, edited and
  downloaded without leaving the app.
- **Status (2026-11-26): built.** TanStack Query + one SSE connection (`lib/useLiveEvents.ts`) that refreshes
  only the affected queries. Pages: Dashboard, New job, Jobs, Job detail (12-step timeline, live %, ETA, log),
  Clips (filters, sort, approve/reject), Clip detail (player, title/caption editor with copy, judge notes,
  clickable transcript, score bars, frame strip, download), Streams, Campaigns (CRUD), Trash (restore),
  Settings (key status only). Light/dark theme, collapsible sidebar, activity panel, toasts.
  New API: `GET /api/v1/clips/{id}/details`; `/media/.../strip.jpg`; `?download=true`.
  Not yet: Posted page (needs Phase 5 data), "delete forever" in Trash, stream data delete, bulk actions.
  Live events connect straight to the API (port 8766): the Next dev proxy buffers streamed responses.

### Phase 4 — Clip quality
- Hook finder from the transcript (strong words, questions, laughter / shouting tags).
- Real action check: sudden picture change, moving objects, not camera pans.
- Payoff check that actually rejects windows without a result at the end.
- Face tracking every second with smoothing; webcam crop that follows a moving cam.
- Judge provider setting: Claude → Gemini → local model (Ollama), same prompt and output format.
- Learn from approve / reject (adjust score weights from your decisions).
- **Done when:** in a test stream, at least half of the top 10 picks are clips you would post.
- **Status (2026-11-26): built; the "done when" needs your review of the 4 ready AsianJeff clips.**
  - Action: CLIP group-softmax saturated (~0.99 for everything). Now the best-action vs best-boring margin plus
    frame-to-frame scene change, ranked within the stream (`clipper/detect/quality.py`): range 0.17-0.90.
  - Payoff: tested a loudness payoff on the last third of the window. On AsianJeff it pointed the wrong way
    (Claude's accepted comedy clips scored lowest) and the judge cuts inside the window anyway. So loudness
    payoff is info only; the judge must name `payoff_text` and is rejected without one.
  - Judge now sees what is on screen (`visual_scan` from the visual step). Re-judge of the top 10:
    3 -> 4 accepted (912 was rejected only for missing picture context). Frame labels are hints, not events.
  - Face: one frame per second, 30 % tiles (BlazeFace misses small faces in bigger tiles), merge duplicates,
    snap the crop to the webcam overlay's border, stream-wide fallback. AsianJeff: 1/3 -> 3/3 clips with the
    face, 100 % of seconds; crop = webcam only (no gameplay, no overlay text).
  - Judge provider switch: `judge_provider` claude | gemini | ollama (`clipper/ai/providers.py`), same prompt.
    Gemini and Ollama are written but not run yet (no key / no local server).
  - Not done: learning weights from approve/reject (needs more decisions first); a crop that follows a webcam
    that moves mid-clip (tracked and flagged as `moving`, not followed).

### Phase 5 — Campaigns and posting
- Campaign records with rules, logo, caption, platforms, payout, end date.
- Per-campaign render settings (logo on / off, caption text).
- Posting kit per clip: title, description, tags per platform, thumbnail, best posting time.
- Posted list with views entered by hand and payout estimate.
- **Done when:** a new campaign is set up in the UI, and its clips come out with the right logo and caption.
- **Status (2026-11-26): done.** Tested in the UI: made a campaign with a TEST logo, started a job with it,
  clip 912 came out with the logo on screen for the whole clip and the campaign caption word for word
  (test campaign, post and render removed afterwards; 912 restored).
  - Campaign settings (logo file / on-off / width / top, caption, hashtags, brief) are copied into the job,
    so editing a campaign never changes a running job. Logo must exist and be PNG / WEBP / JPG.
  - Posting kit per clip (YouTube / TikTok / Instagram): title (never "GTA 5"), caption with the campaign
    text first, tags, character limits, next three peak times for a USA / Canada audience in local time.
    No API call.
  - Posted page: mark a clip as posted (link optional), type in views, payout = views / 1000 x rate,
    totals per campaign. Views are typed by hand (no platform logins).
  - SQLite gets new columns automatically (add-only migration in `backend/db.py`).

### Phase 6 — Reliability and housekeeping
- Tests for step functions and API endpoints.
- Disk rules: delete the source video after rendering (optional), warn when disk is low.
- Clear error messages in the UI, with retry of a single step.
- Backup / export of the database.
- **Done when:** a failed step shows why in the UI and can be retried without restarting the job.
- **Status (2026-11-26): done.** Tested for real: a broken video made "Get the audio" fail; the job page showed
  the reason and "The video file is damaged…", the file was replaced, Retry continued from that step and the
  job finished (step 1 was not run again).
  - `backend/worker/errors.py` turns the step output into one line + a hint (GPU memory, disk full, bad key,
    no credit, rate limit, damaged video, Twitch refused, network, ffmpeg missing, missing file).
  - A step will not start with less than 5 GB free (FERAL_MIN_FREE_GB); a banner shows below 30 GB.
  - Streams page: permanently delete a stream's downloaded video (asks first; clips stay; never a file
    outside the app's folder; refused while a job uses the stream).
  - Settings: one-click database backup into backups/ (SQLite online backup, safe while jobs run).
  - Not done: deleting the source video automatically after render (left as the manual button), and the
    stray-file cleanup (waits for your OK).

---

## 8. Decisions to make

1. Database: SQLite (recommended) or PostgreSQL.
2. Queue: SQLite queue + one worker (recommended) or Redis + `arq`.
3. Judge after the Claude credit runs out: Gemini or a local model.
4. Keep source videos after rendering, or delete them automatically.
5. Frontend location: move `review_ui/frontend` to `frontend/` (recommended) or keep it.

## 9. Risks

- **Disk:** one stream is 18–38 GB. Needs a cleanup rule.
- **GPU contention:** Whisper, MediaPipe and NVENC share one GPU → one worker at a time.
- **Twitch network drops:** downloads already retry; resume must survive API restarts.
- **API cost:** track Claude tokens per job; stop when a budget is hit.
- **Clip quality:** the main open problem. Phase 4 is where it is solved, measured on real streams.
- **Licenses:** do not copy SupoClip code; Feral Streams Clipper code is MIT (keep its notice).
