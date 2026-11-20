"""Video helpers: segment index, window extraction, captions (ASS), 9:16 render."""
import shutil
import time
import json
from pathlib import Path

from common import log, read_json, run

SEG_FMT = "%Y%m%d-%H%M%S"


# ---------------------------------------------------------------- segments
def seg_start(path):
    return time.mktime(time.strptime(Path(path).stem, SEG_FMT))


def list_segments(seg_dir):
    files = sorted(Path(seg_dir).glob("*.ts"))
    return [(seg_start(f), f) for f in files]


def segments_ready(session_dir, end_t, segment_seconds=10):
    """True when a finished segment exists past end_t (live mode)."""
    segs = list_segments(Path(session_dir) / "segments")
    return bool(segs) and segs[-1][0] >= end_t + 1


def extract_window(session_dir, start_t, end_t, out_dir):
    """Return (media_path, offset_seconds) covering [start_t, end_t].

    live: concatenates the 10 s .ts segments (byte concat is valid for MPEG-TS).
    vod:  points straight at the downloaded file.
    """
    session_dir = Path(session_dir)
    meta = read_json(session_dir / "session.json")
    if meta["type"] == "vod":
        sj = Path(out_dir) / "source.json"            # fast mode: this clip has its own small download
        if sj.exists():
            return Path(out_dir) / "source.mp4", max(0.0, start_t - read_json(sj)["start"])
        return session_dir / meta["file"], max(0.0, start_t)

    segs = list_segments(session_dir / "segments")
    chosen = []
    for i, (st, f) in enumerate(segs):
        nxt = segs[i + 1][0] if i + 1 < len(segs) else None
        if nxt is None:
            continue  # still being written
        if nxt > start_t and st < end_t:
            chosen.append((st, f))
    if not chosen:
        raise RuntimeError("No recorded segments cover this moment (recorder gap?)")
    for (a, _), (b, _) in zip(chosen, chosen[1:]):
        if b - a > 45:
            raise RuntimeError("Recording gap inside this window; skipping")
    out = Path(out_dir) / "window.ts"
    with open(out, "wb") as w:
        for _, f in chosen:
            with open(f, "rb") as r:
                shutil.copyfileobj(r, w)
    return out, max(0.0, start_t - chosen[0][0])


def extract_audio(media, offset, duration, out_wav):
    run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", f"{offset:.2f}",
         "-i", str(media), "-t", f"{duration:.2f}", "-vn", "-ac", "1", "-ar", "16000",
         str(out_wav)])


def grab_frame(media, offset, out_jpg, grid=True):
    vf = "drawgrid=w=iw/10:h=ih/10:t=2:c=yellow@0.8" if grid else "null"
    run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", f"{offset:.2f}",
         "-i", str(media), "-frames:v", "1", "-vf", vf, str(out_jpg)])


def detect_black(media, offset, duration):
    """Return [(start, end)] black stretches (seconds relative to offset)."""
    import re
    import subprocess
    res = subprocess.run(
        ["ffmpeg", "-hide_banner", "-ss", f"{offset:.2f}", "-i", str(media), "-t", f"{duration:.2f}",
         "-vf", "scale=320:-2,blackdetect=d=0.5:pix_th=0.10", "-an", "-f", "null", "-"],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = []
    for m in re.finditer(r"black_start:([\d.]+) black_end:([\d.]+)", res.stderr):
        out.append((float(m.group(1)), float(m.group(2))))
    return out


# ---------------------------------------------------------------- captions
def _ass_time(t):
    t = max(0.0, t)
    h = int(t // 3600)
    m = int(t % 3600 // 60)
    s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _clean(text):
    return text.replace("{", "(").replace("}", ")").replace("\\", "/").replace("\n", " ").strip()


def chunk_words(words, max_chars=14, max_words=3, gap=0.6):
    chunks, cur = [], []
    for w in words:
        text = _clean(w["w"]).upper()
        if not text:
            continue
        item = {"w": text, "s": w["s"], "e": w["e"]}
        if cur:
            joined = " ".join(x["w"] for x in cur + [item])
            if (len(cur) >= max_words or len(joined) > max_chars
                    or item["s"] - cur[-1]["e"] > gap):
                chunks.append(cur)
                cur = []
        cur.append(item)
    if cur:
        chunks.append(cur)
    return chunks


def build_ass(words, clip_len, caption_y, hook=None, emphasize=()):
    """words: [{w,s,e}] with times relative to clip start."""
    emph = {e.upper() for e in emphasize}
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Arial Black,84,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,7,2,5,40,40,0,1
Style: Hook,Arial Black,58,&H00000000,&H00000000,&H00FFFFFF,&H00FFFFFF,-1,0,0,0,100,100,0,0,3,14,0,8,60,60,90,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    if hook:
        lines.append(f"Dialogue: 1,{_ass_time(0)},{_ass_time(min(2.8, clip_len))},Hook,,0,0,0,,"
                     f"{_clean(hook)}")
    chunks = chunk_words([w for w in words if w["e"] > 0 and w["s"] < clip_len])
    for ci, chunk in enumerate(chunks):
        chunk_end = chunk[-1]["e"]
        if ci + 1 < len(chunks) and chunks[ci + 1][0]["s"] - chunk_end < 0.3:
            chunk_end = chunks[ci + 1][0]["s"]
        for wi, word in enumerate(chunk):
            start = word["s"]
            end = chunk[wi + 1]["s"] if wi + 1 < len(chunk) else chunk_end
            if end <= start:
                end = start + 0.08
            parts = []
            for wj, other in enumerate(chunk):
                color = "&H0000FFFF&" if wj == wi else "&H00FFFFFF&"
                if other["w"].strip("!?.,") in emph:
                    color = "&H004DD0FF&" if wj != wi else "&H0000FFFF&"
                parts.append(f"{{\\c{color}}}{other['w']}")
            text = " ".join(parts)
            lines.append(f"Dialogue: 0,{_ass_time(start)},{_ass_time(min(end, clip_len))},Cap,,0,0,0,,"
                         f"{{\\pos(540,{caption_y})}}{text}")
    return header + "\n".join(lines) + "\n"


# ---------------------------------------------------------------- render
def _crop(box):
    return f"crop=iw*{box['w']}:ih*{box['h']}:iw*{box['x']}:ih*{box['y']}"


def _auto_cam(media, offset, duration, out_dir):
    """Find the webcam box for this clip ("facecam": "auto"). Returns a box dict or None (-> fit layout)."""
    try:
        from facecam_auto import draw_debug, find_cam, to_box
        res = find_cam(str(Path(media).resolve()), offset, offset + duration)
        (Path(out_dir) / "auto_cam.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
        box = to_box(res)
        if box and res.get("mode") == "cam" and box["h"] > box["w"] * 1.12:
            # most webcams are 16:9; a taller box has chat/alerts stacked under the cam.
            # On a 16:9 frame a 16:9 box has h_frac == w_frac. Keep the top part if the face is inside.
            fy = res.get("face")
            if not fy or box["y"] <= fy[1] + fy[3] / 2 <= box["y"] + box["w"]:
                log(f"auto facecam: box taller than 16:9 ({box['h']:.2f} vs {box['w']:.2f}), trimming chat below the cam")
                box["h"] = round(box["w"], 4)
                res["trimmed_to_16x9"] = True
                (Path(out_dir) / "auto_cam.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
        if box:
            draw_debug(str(Path(media).resolve()), res, Path(out_dir) / "auto_cam.jpg", offset, offset + duration)
            log(f"auto facecam: {res.get('summary')} (confidence {res.get('confidence')})")
        else:
            log(f"auto facecam: none found ({res.get('reason')}) -> fit layout")
        return box
    except Exception as ex:
        log(f"auto facecam failed ({ex}) -> fit layout. Is opencv-python-headless installed?")
        return None


def campaign_overlay(cfg):
    """Config "campaign_overlay": {"file": "assets/x.png", "w": 520, "y": 28, "x": "center"}.
    Returns (path, width, height, y, x) or None. Raises if the PNG is missing."""
    ov = cfg.get("campaign_overlay")
    if not ov:
        return None
    p = Path(ov["file"])
    if not p.is_absolute():
        p = Path(__file__).resolve().parent / p
    if not p.exists():
        raise RuntimeError(f"campaign_overlay file not found: {p} (download it from the campaign page)")
    from PIL import Image
    with Image.open(p) as im:
        iw, ih = im.size
    w = int(ov.get("w", 520))
    return p, w, round(w * ih / iw), int(ov.get("y", 28)), ov.get("x", "center")


def render_clip(media, offset, duration, out_dir, cfg, words, hook=None, emphasize=()):
    """Render a 1080x1920 clip. words are relative to clip start."""
    out_dir = Path(out_dir)
    ovr = campaign_overlay(cfg)
    if ovr:                              # push the facecam/title down so nothing sits under the logo
        cfg = dict(cfg, cam_top=max(cfg.get("cam_top", 60), ovr[3] + ovr[2] + 12))
    cam = cfg.get("facecam")
    layout = cfg.get("layout")
    if cam == "auto":
        cam = _auto_cam(media, offset, duration, out_dir)
        if cam is None and layout == "overlay":
            layout = "fit"
    game = cfg.get("gameplay") or {"x": 0, "y": 0, "w": 1, "h": 1}
    extra = []          # extra image inputs (overlay layout)
    ass_hook = hook
    if layout == "overlay":
        # blurred backdrop, rounded facecam card on top, compact title card, and a SHARP game panel
        # that shows most of the frame (less zoom than a full-bleed 9:16 crop)
        from overlay import cam_assets, round_mask, title_card
        fx = cfg.get("focus_x", 0.5)
        cw, ch = cfg.get("cam_size", [560, 315])
        cx, cy = (1080 - cw) // 2, cfg.get("cam_top", 60)
        title_w = cfg.get("title_width", 860)
        top = (cy + ch + 20) if cam else cy             # where the title starts
        th = 0
        if hook:                                        # render the title first so the game sits right under it
            tw, th = title_card(hook, out_dir / "title.png", width=title_w,
                                font_path=cfg.get("title_font"), size=cfg.get("title_size", 52))
        game_y = top + (th + 20 if hook else (6 if cam else 0))
        gh = 1800 - game_y                              # game panel height
        caption_y = game_y + gh - 130
        extra, idx = [], 1
        chain = ""
        bg = ("[b]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
              "boxblur=24:3,eq=brightness=-0.12[bg];")
        round_mask(1080, gh, out_dir / "game_mask.png", 30)
        extra.append("game_mask.png")
        gm = (f"[g]{_crop(game)},crop=w='min(iw,ih*1080/{gh})':h=ih:x='(iw-ow)*{fx}':y=0,"
              f"scale=1080:{gh}:flags=lanczos,unsharp=5:5:0.6:5:5:0.0,setsar=1,format=rgba[gm0];"
              f"[{idx}:v]format=gray[gmk];[gm0][gmk]alphamerge[gm];"
              f"[bg][gm]overlay=0:{game_y}:format=auto[t0];")
        last, idx = "[t0]", idx + 1
        if cam:
            pad = cam_assets(cw, ch, out_dir)
            extra += ["cam_mask.png", "shadow.png"]
            chain += (f"[a]{_crop(cam)},scale={cw}:{ch}:force_original_aspect_ratio=increase,"
                      f"crop={cw}:{ch},format=rgba[c0];[{idx}:v]format=gray[m];[c0][m]alphamerge[cam];"
                      f"{last}[{idx + 1}:v]overlay={cx - pad}:{cy - pad}:format=auto[t1];"
                      f"[t1][cam]overlay={cx}:{cy}:format=auto[t2];")
            last, idx = "[t2]", idx + 2
        if hook:
            extra.append("title.png")
            ty = top
            chain += f"{last}[{idx}:v]overlay={(1080 - tw) // 2}:{ty}:format=auto[t3];"
            last = "[t3]"
            ass_hook = None     # title card replaces the ASS hook banner
        split = "[0:v]split=3[a][b][g];" if cam else "[0:v]split=2[b][g];"
        vf = split + bg + gm + chain + f"{last}ass=captions.ass[v]"
    elif layout == "fit":
        # whole 16:9 frame in the middle, blurred copy as background (shows everything)
        caption_y = 1420
        vf = ("[0:v]split=2[bg][fg];"
              "[bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:2[bgb];"
              "[fg]scale=1080:-2:flags=lanczos,unsharp=5:5:0.5:5:5:0.0,setsar=1[f];"
              "[bgb][f]overlay=(W-w)/2:(H-h)/2-80,setsar=1,ass=captions.ass[v]")
    elif cam:
        caption_y = 672
        vf = (f"[0:v]split=2[a][b];"
              f"[a]{_crop(cam)},scale=1080:672:force_original_aspect_ratio=increase,crop=1080:672,setsar=1[cam];"
              f"[b]{_crop(game)},scale=1080:1248:force_original_aspect_ratio=increase,crop=1080:1248,setsar=1[game];"
              f"[cam][game]vstack=inputs=2,ass=captions.ass[v]")
    else:
        caption_y = 1380
        vf = (f"[0:v]{_crop(game)},scale=-2:1920,crop=1080:1920,setsar=1,ass=captions.ass[v]")
    (out_dir / "captions.ass").write_text(
        build_ass(words, duration, caption_y, ass_hook, emphasize), encoding="utf-8")

    if ovr:
        # a logo some campaigns require on screen for the WHOLE clip; drawn on top of everything, incl. captions
        ovf, ow, oh, oy, ox = ovr
        extra.append(str(ovf))
        n = len(extra)                   # input index: 0 is the video, 1..n are the extra images in order
        ox_expr = "(W-w)/2" if ox == "center" else str(int(ox))
        vf = vf.replace("ass=captions.ass[v]",
                        f"ass=captions.ass[vc];[{n}:v]scale={ow}:-1,format=rgba[ovl];"
                        f"[vc][ovl]overlay={ox_expr}:{oy}:format=auto[v]")

    nvenc = ["-c:v", "h264_nvenc", "-preset", "p6", "-cq", "18", "-b:v", "0"]
    x264 = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18"]

    def cmd(vcodec):
        return ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-ss", f"{offset:.2f}", "-i", str(Path(media).resolve()),
                *[a for img in extra for a in ("-loop", "1", "-framerate", "30", "-i", img)],
                "-t", f"{duration:.2f}",
                "-filter_complex", vf, "-map", "[v]", "-map", "0:a?",
                "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-r", "30",
                *vcodec, "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
                "-movflags", "+faststart", "clip.mp4"]

    if cfg.get("encoder", "h264_nvenc") == "h264_nvenc":
        try:
            run(cmd(nvenc), cwd=out_dir)
        except RuntimeError:
            run(cmd(x264), cwd=out_dir)  # NVENC unavailable -> CPU fallback
    else:
        run(cmd(x264), cwd=out_dir)
    run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", "1", "-i", "clip.mp4",
         "-frames:v", "1", "-vf", "scale=360:-2", "thumb.jpg"], cwd=out_dir)
    return out_dir / "clip.mp4"
