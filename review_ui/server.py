"""Review API for the clipper: lists stream sessions and clips, serves the clip videos, and saves
approve/reject decisions next to each clip (review.json). Standard library only.

    python review_ui\\server.py            # http://127.0.0.1:8765

Nothing here posts anything anywhere. Decisions are written only into data\\vod\\<session>\\clips\\<id>\\review.json.
"""
import json
import mimetypes
import os
import re
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, unquote

ROOT = Path(__file__).resolve().parents[1]
VOD_DIR = ROOT / "data" / "vod"
PORT = int(os.environ.get("GTA_REVIEW_PORT", "8765"))
SAFE_ID = re.compile(r"^[A-Za-z0-9_\-]{1,80}$")
ALLOWED_DECISIONS = {"approved", "rejected", "pending"}


def _read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _safe(name):
    return bool(SAFE_ID.match(name or ""))


def _title_from_post(clip_dir):
    """Title from post.txt (written by the pipeline when a campaign needs it)."""
    p = clip_dir / "post.txt"
    if not p.exists():
        return ""
    lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    for i, line in enumerate(lines):
        if line.startswith("TITLE"):
            for nxt in lines[i + 1:]:
                text = nxt.strip()
                if not text:
                    continue
                # the next heading (CAPTION ...) means the title line was empty
                if text.upper().startswith("CAPTION") or text.endswith(":"):
                    return ""
                return text
    return ""


def list_sessions():
    out = []
    if not VOD_DIR.exists():
        return out
    for d in sorted(VOD_DIR.iterdir()):
        if not d.is_dir() or not (d / "clips").exists():
            continue
        session = _read_json(d / "session.json", {}) or {}
        clips = [c for c in (d / "clips").iterdir() if c.is_dir() and (c / "status.json").exists()]
        out.append({
            "id": d.name,
            "title": session.get("title") or d.name,
            "channel": session.get("channel") or "",
            "clips": len(clips),
            "ready": sum(1 for c in clips if (_read_json(c / "status.json", {}) or {}).get("status") == "ready"),
        })
    return out


def list_clips(session_id):
    base = VOD_DIR / session_id / "clips"
    out = []
    if not base.exists():
        return out
    for c in sorted(base.iterdir()):
        status = _read_json(c / "status.json")
        if not c.is_dir() or status is None:
            continue
        judge = _read_json(c / "judge.json", {}) or {}
        review = _read_json(c / "review.json", {}) or {}
        out.append({
            "id": c.name,
            "status": status.get("status", "?"),
            "final": status.get("final") or judge.get("final_score") or 0,
            "strong": bool(status.get("strong")),
            "has_video": (c / "clip.mp4").exists(),
            "title": review.get("title") or judge.get("title") or _title_from_post(c) or "",
            "caption": review.get("caption") or "",
            "hook": judge.get("hook_text") or "",
            "reasons": judge.get("reasons") or "",
            "judge_source": judge.get("source") or "",
            "decision": review.get("decision") or "pending",
        })
    out.sort(key=lambda r: (r["status"] != "ready", -float(r["final"] or 0)))
    return out


def read_monitor(session_id):
    """The monitor's picks for a stream (monitor.json), with the rendered clip id if one exists."""
    data = _read_json(VOD_DIR / session_id / "monitor.json")
    if not data:
        return {"exists": False, "picks": []}
    clips_dir = VOD_DIR / session_id / "clips"
    picks = []
    for p in data.get("picks", []):
        cid = str(p.get("id"))
        rendered = (clips_dir / cid / "status.json").exists()
        status = (_read_json(clips_dir / cid / "status.json", {}) or {}).get("status") if rendered else None
        picks.append({**p, "clip_id": cid if rendered else None, "clip_status": status})
    return {"exists": True, "from": data.get("from"), "to": data.get("to"),
            "window": data.get("window"), "step": data.get("step"), "picks": picks}


def save_review(session_id, clip_id, body):
    decision = body.get("decision", "pending")
    if decision not in ALLOWED_DECISIONS:
        return 400, {"error": "decision must be approved, rejected or pending"}
    clip_dir = VOD_DIR / session_id / "clips" / clip_id
    if not clip_dir.is_dir():
        return 404, {"error": "clip not found"}
    data = {
        "decision": decision,
        "title": str(body.get("title", ""))[:200],
        "caption": str(body.get("caption", ""))[:2200],
    }
    (clip_dir / "review.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return 200, data


class Handler(BaseHTTPRequestHandler):
    server_version = "ClipReview/1.0"

    def log_message(self, fmt, *args):
        pass  # keep the terminal quiet

    def _json(self, status, payload):
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _file(self, path):
        if not path.is_file():
            self.send_error(404)
            return
        size = path.stat().st_size
        ctype = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        start, end = 0, size - 1
        rng = self.headers.get("Range")
        status = 200
        if rng and rng.startswith("bytes="):
            a, _, b = rng[6:].partition("-")
            start = int(a) if a else max(0, size - int(b))
            end = int(b) if (a and b) else size - 1
            end = min(end, size - 1)
            status = 206
        length = end - start + 1
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(length))
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        with open(path, "rb") as f:
            f.seek(start)
            remaining = length
            while remaining > 0:
                chunk = f.read(min(1 << 20, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    def do_GET(self):
        frontend = Path(__file__).resolve().parent / "frontend"
        path = urlparse(self.path).path
        assets = {"/": "index.html", "/logo.png": "logo.png", "/style.css": "style.css", "/app.js": "app.js"}
        if path in assets:
            return self._file(frontend / assets[path])
        parts = [unquote(p) for p in urlparse(self.path).path.split("/") if p]
        if parts == ["api", "sessions"]:
            return self._json(200, list_sessions())
        if len(parts) == 4 and parts[0] == "api" and parts[1] == "sessions" and parts[3] == "clips":
            if not _safe(parts[2]):
                return self._json(400, {"error": "bad session id"})
            return self._json(200, list_clips(parts[2]))
        if len(parts) == 4 and parts[0] == "api" and parts[1] == "sessions" and parts[3] == "monitor":
            if not _safe(parts[2]):
                return self._json(400, {"error": "bad session id"})
            return self._json(200, read_monitor(parts[2]))
        if len(parts) == 4 and parts[0] == "media" and _safe(parts[1]) and _safe(parts[2]):
            if parts[3] not in ("clip.mp4", "thumb.jpg"):
                return self._json(404, {"error": "not found"})
            return self._file(VOD_DIR / parts[1] / "clips" / parts[2] / parts[3])
        return self._json(404, {"error": "not found"})

    def do_POST(self):
        parts = [unquote(p) for p in urlparse(self.path).path.split("/") if p]
        if len(parts) == 6 and parts[0] == "api" and parts[1] == "sessions" and parts[3] == "clips" \
                and parts[5] == "review" and _safe(parts[2]) and _safe(parts[4]):
            length = int(self.headers.get("Content-Length") or 0)
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
            except ValueError:
                return self._json(400, {"error": "bad json"})
            status, payload = save_review(parts[2], parts[4], body)
            return self._json(status, payload)
        return self._json(404, {"error": "not found"})


def main():
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Review API on http://127.0.0.1:{PORT}  (sessions in {VOD_DIR})", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
