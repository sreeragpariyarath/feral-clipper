# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

GTA Clipper: turns Twitch/YouTube streams (live or VOD) into 9:16 captioned shorts. Windows-only workflow (PowerShell, NVENC, CUDA). Python 3.11, ffmpeg on PATH. There is no test suite or linter; verify changes by running the commands below (`--dry`, `--list`, `--detect-only` modes spend nothing / render nothing).

## Commands

Run from the repo root with `.venv` active (`.venv\Scripts\activate`). Setup: `pip install -r requirements.txt`, `copy config.example.json config.json`. `ANTHROPIC_API_KEY` is optional; without it clips are cut around the spike and a `prompt.txt` is written per clip for manual judging.

```
python vod.py <vod_url> --top 10            # VOD: chat/audio spikes -> clips (--detect-only lists moments, --download-only just fetches chat+video)
python live.py <channel> --auto             # live Twitch: record, detect, cut, judge, render
python scan.py <session> --dry|--list       # frame scan of a downloaded VOD (picture-based moments); no flag renders top N
python merge.py <session> --list|--top 8    # merge vod.py (chat/audio) + scan.py moments into one ranking, render
python picks.py <vod_url> picks.json        # render exact hand/Claude-chosen start/end times
python cut.py "<session>" --all|--id 7 [--force]   # cut leftovers from a session
python cut.py --rerender data\...\clips\003 # re-render a clip (e.g. after editing judge.json or facecam box)
python tools\setup_models.py                # one-time: download local CLIP + PANNs models into models\
python tools\frame.py <session>             # dump frame.jpg with grid to set facecam box in config.json
```

## App (backend + frontend)

`start_all.bat` opens three windows: `python -m backend.run_api` (FastAPI on 127.0.0.1:8766), `python -m backend.run_worker` (runs queued jobs one at a time), and the Next.js frontend in `frontend/` (`npm run dev`, http://127.0.0.1:3107, proxies `/api/*` and `/media/*` to the API). State lives in SQLite `data/feral.db`; the importer re-reads `data/vod/*` files at API start and after each job step. API keys come from `.env` (git-ignored, never sent to the browser). Routes: `/api/v1/*` (new) and `/api/sessions`, `/api/jobs`, `/media` (kept for the current frontend). See `plan.md` for the phased roadmap.

## Architecture

Top-level scripts (`vod.py scan.py merge.py live.py picks.py cut.py`) only parse options and sequence steps; reusable logic lives in `clipper/`. Imports go strictly downward (`sources/detect/ai/render` -> `common`) to avoid cycles; keep it that way.

Pipeline for one moment (`clipper/pipeline.py`): window cut -> Whisper word timings (`ai/transcribe.py`) -> Claude judge for start/end, hook, title, score (`ai/judge.py`) -> ffmpeg render of facecam-top + gameplay-bottom + word captions (`render/media.py`, `overlay.py`, `facecam_auto.py`) -> `clips/NNN/clip.mp4`.

Two independent moment finders feed that pipeline:
- Chat/audio (`detect/detector.py`, `sources/chat_twitch.py`, `sources/audio_detect.py`) — talk/chat-driven; tuned via `config.json` -> `detect`.
- Frame scan (`detect/frame_scan.py`) — picture-driven. Local mode scores every frame with CLIP + PANNs on GPU, then Claude double-checks the top shortlist; falls back to Claude-only contact sheets without the models. Results cached in `<session>\scan\results.json` so re-runs are safe/cheap. Uses `gta6_knowledge.json` (refreshed by `tools\update_knowledge.py`).
- `merge.py` joins them: a scan frame matches a chat candidate if it falls 45 s before to 10 s after the chat peak (chat reacts late); agreement gives +0.10 score; dedupes by gap; already-rendered moments (peak within 6 s) are skipped.

Clip ID ranges encode origin: chat `001+`, scan `501+`, merged `701+`, manual `801+`.

Session layout: `data/<channel>/<session>/` (live) or `data/vod/<id>/` containing `chat.jsonl`, `candidates.json(l)`, `scan/`, and `clips/NNN/{clip.mp4, judge.json, transcript.json, prompt.txt, status.json}`. Clips with final score < 0.55 or flagged by the judge are marked skipped but kept; `--force` overrides. Finished clips are copied to `READY_TO_POST/` (`tools\rerender_ready.py` re-renders them).

## Config

`config.json` (gitignored-style local settings; template is `config.example.json`) controls facecam/gameplay crop boxes (fractions of frame, `facecam: null` = gameplay-only center crop), Whisper model/device, encoder (`h264_nvenc`), `anthropic_model`, `campaign_brief` (judge checks clips against it), and `detect` thresholds. Per-pick `layout` overrides exist in `picks.json`. Judge rules reject story spoilers, cutscenes, in-game radio/TV, money glitches, music-heavy clips.

Gitignored: `data/`, `models/`, `READY_TO_POST/`, `backups/`, media files, `.env`, `TwitchDownloaderCLI.exe` (needed in repo root for Twitch VOD chat).

## Known limits

Live mode is Twitch only (Kick unsupported, no chat replay). Only post clips from streamers with a paid campaign or permission.
