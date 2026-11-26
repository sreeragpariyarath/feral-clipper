"""Turn a failed step's output into one readable line and a hint on what to do next."""
import re

# (pattern in the output, hint). First match wins; order from most to least specific.
HINTS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"CUDA out of memory|CUBLAS_STATUS_ALLOC|out of memory", re.I),
     "The GPU ran out of memory. Close games or other GPU apps, then press Retry."),
    (re.compile(r"No space left on device|disk (is )?(nearly )?full|errno 28", re.I),
     "The disk is full. Delete old stream videos on the Streams page, then press Retry."),
    (re.compile(r"authentication_error|invalid x-api-key|401", re.I),
     "The judge's API key was refused. Check the key in .env (no spaces), restart the API window, then Retry."),
    (re.compile(r"credit balance|insufficient_quota|billing", re.I),
     "The judge account is out of credit. Top it up or switch judge_provider in config.json."),
    (re.compile(r"rate.?limit|429|overloaded|529", re.I),
     "The judge service is busy. Wait a minute and press Retry."),
    (re.compile(r"Invalid data found when processing input|moov atom not found|could not find codec", re.I),
     "The video file is damaged or not finished downloading. Download it again or pick another file."),
    (re.compile(r"HTTP Error 403|HTTP Error 404|Video unavailable|This video is (private|unavailable)|subscriber", re.I),
     "Twitch would not give the video (deleted, private or subscriber-only). Check the link in a browser."),
    (re.compile(r"getaddrinfo|Connection (reset|refused|aborted)|timed out|Temporary failure in name resolution", re.I),
     "The internet connection dropped. Check it and press Retry; finished parts are kept."),
    (re.compile(r"ffmpeg.*not (found|recognized)|No such file or directory: 'ffmpeg'", re.I),
     "ffmpeg is not installed or not on PATH."),
    (re.compile(r"file not found|No such file or directory|FileNotFoundError", re.I),
     "A file this step needs is missing. If you moved or deleted the video, put it back or start a new job."),
]

_ERROR_LINE = re.compile(r"^\s*([A-Za-z_][\w.]*(Error|Exception|Exit|Interrupt))\b:?\s*(.*)$")
_NOISE = re.compile(r"^\s*(File \"|Traceback|\^+\s*$|~+\s*$|@@P )")


def explain(lines: list[str], returncode: int | None = None) -> tuple[str, str]:
    """(one-line reason, hint). The reason is the last exception line, or the last meaningful line."""
    text = "\n".join(lines)
    reason = ""
    for i in range(len(lines) - 1, -1, -1):
        m = _ERROR_LINE.match(lines[i])
        if m:
            name, msg = m.group(1).rsplit(".", 1)[-1], m.group(3).strip()
            # a multi-line message (e.g. "Command failed: ffprobe ..." + ffprobe's own error below it):
            # the last line underneath says what actually went wrong
            more = [ln.strip() for ln in lines[i + 1:] if ln.strip() and not _NOISE.match(ln)]
            detail = more[-1] if more else msg
            reason = f"{name}: {detail}" if detail else name
            break
    if not reason:
        meaningful = [ln.strip() for ln in lines if ln.strip() and not _NOISE.match(ln)]
        reason = meaningful[-1] if meaningful else f"the step stopped with exit code {returncode}"
    hint = next((h for pattern, h in HINTS if pattern.search(text)), "Open the log for details, then press Retry.")
    return reason[:300], hint
