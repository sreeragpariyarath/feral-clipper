# GTA Clipper (Phase 0)

Turns Twitch / YouTube streams into 9:16 captioned clips.

```
stream ─► record (10 s pieces) ─► chat spike detector ─► cut ~65 s window
       ─► Whisper (word timings) ─► Claude judge (start/end, hook, title, score)
       ─► ffmpeg: facecam top + gameplay bottom + word captions ─► clips/NNN/clip.mp4
```

Two modes, same pipeline:

| Mode | Command | Use when |
|---|---|---|
| Live (Twitch) | `python live.py <channel> --auto` | You're home while they stream |
| VOD (Twitch or YouTube) | `python vod.py <vod_url> --top 10` | Stream already ended |

---

## 1. One-time setup (Windows)

1. **Python 3.11** from python.org (tick "Add to PATH").
2. **ffmpeg**: download the "full" build from gyan.dev, unzip, add its `bin` folder to PATH.
   Check NVENC: `ffmpeg -hide_banner -encoders | findstr nvenc`
3. In this folder:
   ```
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   copy config.example.json config.json
   ```
4. **Check Whisper on the GPU** (first run downloads the model, about 1.6 GB):
   ```
   python -c "from transcribe import get_model; from common import load_config; get_model(load_config())"
   ```
   It should print `Whisper loaded: large-v3-turbo on cuda`. If it says it fell back to CPU,
   update your NVIDIA driver and run the command again.
5. **Twitch VOD chat only**: download `TwitchDownloaderCLI` (Windows CLI zip) from
   github.com/lay295/TwitchDownloader/releases and put the `.exe` in this folder.
6. **Claude (optional)**: set your API key for this terminal:
   ```
   set ANTHROPIC_API_KEY=sk-ant-...            (Command Prompt)
   $env:ANTHROPIC_API_KEY="sk-ant-..."         (PowerShell)
   ```
   Without a key, everything still works. Clips are cut around the spike, and each clip folder
   gets a `prompt.txt`. Paste it into claude.ai, save the JSON reply over `judge.json`, then run:
   `python cut.py --rerender data\...\clips\003`

## 2. Tonight's test

**A. VOD test (works any time):**
```
python vod.py https://www.twitch.tv/videos/XXXXXXXXX --top 5
python vod.py https://www.youtube.com/watch?v=XXXXXXXXX --top 5
```
Pick a GTA stream with active chat. Add `--detect-only` to just list moments without downloading the video.

**B. Live test (Twitch):**
```
python live.py somechannel --auto
```
- Detection starts after a 3-minute warm-up. Moments print as `MOMENT #001 ...`.
- With `--auto`, each moment is transcribed, judged and rendered about 1–3 minutes later.
- Stop with **Ctrl+C**. Leftover moments can be cut later with `python cut.py "<session>" --all`.
- For small channels (< ~1,000 viewers), lower the chat floor: `--min-m30 6`.

**C. Set the facecam box once per streamer:**
```
python frame.py "data\somechannel\20261117-210512"
```
Open `frame.jpg`. The yellow grid splits the frame into tenths. Read the facecam box and put it in `config.json`:
```json
"facecam": {"x": 0.74, "y": 0.02, "w": 0.24, "h": 0.27},
"gameplay": {"x": 0.12, "y": 0.0, "w": 0.76, "h": 1.0}
```
`null` facecam means a gameplay-only center crop. Re-render to check:
`python cut.py --rerender "data\...\clips\001"`

## 3. Output

```
data/<channel>/<session>/
  segments/*.ts         rolling recording (older than 6 h deleted)
  chat.jsonl            every chat message
  candidates.jsonl      detected moments
  clips/001/
    clip.mp4            the 1080x1920 short
    thumb.jpg
    judge.json          Claude's decision: start/end, hook, title, score, reasons
    transcript.json     words with timings
    prompt.txt          what was sent to Claude (paste into claude.ai if no API key)
    status.json         ready / skipped, final score
```
Clips with a final score under 0.55, or that Claude marks as needing context or breaking rules,
are **skipped** (kept on disk). Force one: `python cut.py "<session>" --id 7 --force`.

## 4. Tuning (config.json → "detect")

| Setting | Default | Raise it if... | Lower it if... |
|---|---|---|---|
| `threshold` | 0.45 | too many weak moments | missing obvious moments |
| `min_m30` | 15 | big channel, too noisy | small channel, nothing detected |
| `min_ratio` | 1.6 | normal chat triggers moments | only huge spikes trigger |

## 5. Rules built in

- The Claude judge rejects story spoilers, cutscenes, in-game radio/TV, money glitches and music-heavy clips.
- Put the campaign brief text in `config.json` → `"campaign_brief"` so Claude checks clips against it.
- **Only post clips of streamers from a paid campaign or who gave you permission.** Testing locally is fine.

## Known limits (Phase 0)

- Live mode is Twitch only. Use VOD mode for YouTube streams. Kick isn't supported yet (no chat replay).
- No audio-spike or viewer-clip signals yet (Phase 1). Detection uses chat only.
- No dashboard yet. Review clips in File Explorer.
