"""Claude judge: decides if a window works as a standalone short.

With ANTHROPIC_API_KEY set -> calls the API.
Without it -> heuristic cut + saves prompt.txt so you can paste it into claude.ai,
then re-render with:  python cut.py --rerender <clip_dir> --judge judge.json
"""
import json
import os
import re

SYSTEM_PROMPT = """You are a short-form video editor for gaming livestream clips (TikTok, Reels, YouTube Shorts).
Judge whether a window from a live stream works as a STANDALONE vertical short.

The game is GTA 6 (Grand Theft Auto VI, released 19 Nov 2026). Never write 'GTA 5', 'GTA V' or any other game/version name in
hook_text or title; say 'GTA 6' or just 'GTA'. If the footage is clearly a different game, set standalone=false.
Only describe events you can support from the transcript/chat/discovery; do not invent a crash, kill or reveal.
Rules:
- A good short has a hook in the first 2-3 seconds (action, a shocking line, a question, a fail mid-moment),
  a clear payoff, and needs no prior context.
- Prefer 15-45 s; never longer than 60 s; never shorter than 8 s.
- Start as late as possible while keeping the setup; end right after the payoff/reaction.
- Reject: story cutscenes, ending/plot spoilers, in-game TV/radio played on its own, money glitches/exploits,
  clips where copyrighted music is the main audio, dead air, anything against the campaign brief.
- If 'discovery' is present, it lists what the streamer found (creature/place/secret). Prefer windows where the
  discovery is on screen AND reacted to; start just before it appears. If discovery.blocked is non-empty, add it to violations.
- 'visual_scan', if present, is what a frame scan saw ON SCREEN (kind, what, at_s seconds into the window). It can
  confirm a silent action moment; treat it as a hint, never describe more than it and the transcript support.
- Chat/audio signals are hints only; chat reacts 5-20 s AFTER the moment, loud audio is AT the moment.
- Timestamps are seconds relative to the window start (0 = window start).
- Output ONLY one JSON object, no markdown, with exactly these keys:
{"standalone": bool, "score": 0-10 integer, "category": "funny|hype|fail|clutch|wholesome|rage|other",
 "start_s": number, "end_s": number, "hook_text": "max 8 words, on-screen banner",
 "title": "post title, max 70 chars", "emphasize": ["WORD", ...],
 "reasons": "one sentence", "violations": [], "needs_context": bool}"""


def build_user_message(cand, words, window_len, channel, brief=None):
    spike_rel = cand["peak_t"] - cand["win_start"]
    payload = {
        "channel": channel,
        "campaign_brief": brief or "none provided",
        "window": {"duration_s": round(window_len, 1), "signal_peak_at_s": round(spike_rel, 1)},
        "transcript_words": [[w["w"], w["s"], w["e"]] for w in words],
        "chat": {"top_tokens": cand.get("chat_top", {}), "sample_msgs": cand.get("chat_samples", [])},
        "detector_score_0_1": cand.get("h_score"),
        "signals": cand.get("signals", {}),
        "discovery": cand.get("discovery"),
        "visual_scan": cand.get("scan"),
    }
    return json.dumps(payload, ensure_ascii=False)


def parse_json(text):
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("No JSON object in response")
    return json.loads(m.group(0))


def validate(j, window_len):
    j = dict(j)
    start = float(j.get("start_s", 0))
    end = float(j.get("end_s", window_len))
    start = max(0.0, min(start, window_len - 8))
    end = max(start + 8, min(end, window_len, start + 60))
    j["start_s"], j["end_s"] = round(start, 2), round(end, 2)
    j["score"] = int(max(0, min(10, int(j.get("score", 0)))))
    j.setdefault("standalone", True)
    j.setdefault("violations", [])
    j.setdefault("hook_text", "")
    j.setdefault("title", "")
    j.setdefault("emphasize", [])
    return j


def heuristic(cand, window_len):
    spike = cand["peak_t"] - cand["win_start"]
    return {
        "standalone": True, "score": round(cand["h_score"] * 10), "category": "other",
        "start_s": max(0, spike - 25), "end_s": min(window_len, spike + 12),
        "hook_text": "", "title": "", "emphasize": [], "reasons": "heuristic (no API key)",
        "violations": [], "needs_context": False, "source": "heuristic",
    }


def judge(cand, words, window_len, cfg, channel, clip_dir, brief=None):
    user_msg = build_user_message(cand, words, window_len, channel, brief)
    (clip_dir / "prompt.txt").write_text(SYSTEM_PROMPT + "\n\nINPUT:\n" + user_msg, encoding="utf-8")

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return validate(heuristic(cand, window_len), window_len)

    import anthropic
    client = anthropic.Anthropic()
    last_err = None
    for attempt in range(2):
        try:
            resp = client.messages.create(
                model=cfg["anthropic_model"],
                max_tokens=2000,
                system=[{"type": "text", "text": SYSTEM_PROMPT,
                         "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": user_msg if attempt == 0 else
                           user_msg + "\n\nReturn valid JSON only."}],
            )
            text = "".join(b.text for b in resp.content if b.type == "text")
            if not text.strip() or "{" not in text:
                kinds = [b.type for b in resp.content]
                (clip_dir / "judge_raw.txt").write_text(
                    f"stop_reason={resp.stop_reason} blocks={kinds}\n---\n{text}", encoding="utf-8")
                raise ValueError(f"no JSON (stop_reason={resp.stop_reason}, blocks={kinds}, "
                                 f"text={text[:120]!r})")
            j = validate(parse_json(text), window_len)
            j["source"] = cfg["anthropic_model"]
            j["usage"] = {"in": resp.usage.input_tokens, "out": resp.usage.output_tokens}
            return j
        except Exception as e:  # network, parse, overload
            last_err = e
    j = validate(heuristic(cand, window_len), window_len)
    j["reasons"] = f"Claude failed ({last_err}); heuristic used"
    return j
