"""Keep gta6_knowledge.json current: what is in GTA 6 and what players are sharing right now.

Claude searches the web (news, Reddit, YouTube Shorts titles) for new GTA 6 discoveries, then this
script MERGES them into the list (it never deletes):
  - new finds are added (tier 'rare' if few people have clips yet, 'hot' if going viral)
  - existing items can move hot -> common as they get posted everywhere
  - a backup of the old file is kept as gta6_knowledge.<date>.bak.json

  python tools/update_knowledge.py            # update now (~1-3 cents)
  python tools/update_knowledge.py --show     # just print the current list

Run it once a day (or let live.py / a Windows scheduled task run it).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # so `clipper` is found when run from tools\

import argparse
import datetime as dt
import json
import os
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KFILE = ROOT / "gta6_knowledge.json"

PROMPT = """You maintain a list of things inside Grand Theft Auto VI (released 19 Nov 2026) that make good \
viral short clips: creatures, animals, secrets, easter eggs, funny physics, new vehicles, locations, \
random events, mechanics people are surprised by.

Today is {today}. Search the web for what GTA 6 players found and shared in the last few days \
(news sites, Reddit r/GTA6, YouTube Shorts / TikTok titles, X posts). Do several searches with different \
angles (e.g. "GTA 6 easter egg", "GTA 6 secret found", "GTA 6 rare animal", "GTA 6 random event", \
"GTA 6 viral clip", "GTA 6 hidden").

The current list (name: tier) is:
{current}

Return ONLY JSON, no prose:
{{"new": [{{"name": "...", "where": "map area or how it triggers", "tier": "hot|rare|common",
           "words": ["3-6 lowercase words/phrases a streamer or chat would type, e.g. 'ufo', 'alien'"],
           "look": "what it looks like on screen, max 15 words, for an image model",
           "source": "site name"}}],
 "tier_changes": [{{"name": "exact name from current list", "tier": "hot|rare|common", "why": "..."}}]}}

Rules: only things that are really in the game (reported by at least one real source); no story spoilers, \
no cutscene-only moments, nothing sexual, no cheats/glitch money exploits. tier: hot = many people posting \
it right now; rare = confirmed but few clips exist; common = everyone has posted it. Max 15 new items. \
Skip anything already on the current list."""


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--model", default=None)
    args = ap.parse_args()
    k = json.loads(KFILE.read_text(encoding="utf-8"))
    if args.show:
        for x in k["discoveries"]:
            print(f"  [{x['tier']:<6}] {x['name']}  ({x['where']})")
        print(f"{len(k['discoveries'])} items, updated {k.get('updated')}")
        return
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("Set ANTHROPIC_API_KEY first.")
    sys.path.insert(0, str(ROOT))
    from clipper.common import load_config
    cfg = load_config()
    model = args.model or cfg["anthropic_model"]
    import anthropic
    client = anthropic.Anthropic()
    today = dt.date.today().isoformat()
    current = "\n".join(f"- {x['name']}: {x['tier']}" for x in k["discoveries"])
    print(f"Searching the web for new GTA 6 finds with {model}... (30-90 s)")
    msgs = [{"role": "user", "content": PROMPT.format(today=today, current=current)}]
    tools = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 8}]
    log_lines, text = [], ""
    for turn in range(6):
        resp = client.messages.create(model=model, max_tokens=8000, tools=tools, messages=msgs)
        kinds = [b.type for b in resp.content]
        log_lines.append(f"turn {turn + 1}: stop_reason={resp.stop_reason} blocks={kinds}")
        print(f"  turn {turn + 1}: {resp.stop_reason}, {kinds.count('server_tool_use')} searches")
        text += "".join(getattr(b, "text", "") for b in resp.content if b.type == "text")
        if resp.stop_reason == "pause_turn":          # long search: hand the turn back so it continues
            msgs = msgs + [{"role": "assistant", "content": resp.content}]
            continue
        if resp.stop_reason == "end_turn" and "{" not in text:
            msgs = msgs + [{"role": "assistant", "content": resp.content},
                           {"role": "user", "content": "Now output ONLY the JSON object described above."}]
            continue
        break
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        (ROOT / "update_raw.txt").write_text("\n".join(log_lines) + "\n---\n" + text, encoding="utf-8")
        raise SystemExit("No JSON in the reply (saved to update_raw.txt). Try again, or use --model with a bigger model.")
    data = json.loads(m.group(0))

    names = {norm(x["name"]): x for x in k["discoveries"]}
    added, changed = [], []
    for it in data.get("new", []):
        if not it.get("name") or not it.get("words") or norm(it["name"]) in names:
            continue
        if any(norm(it["name"]) in n or n in norm(it["name"]) for n in names):
            continue
        item = {"name": it["name"], "where": it.get("where", ""), "tier": it.get("tier", "rare")
                if it.get("tier") in ("hot", "rare", "common") else "rare",
                "words": [w.lower() for w in it["words"] if isinstance(w, str) and len(w) > 2][:6],
                "look": it.get("look", ""), "source": it.get("source", ""), "added": today}
        if item["words"]:
            k["discoveries"].append(item)
            names[norm(item["name"])] = item
            added.append(item)
    for ch in data.get("tier_changes", []):
        x = names.get(norm(ch.get("name", "")))
        if x and ch.get("tier") in ("hot", "rare", "common") and ch["tier"] != x["tier"]:
            changed.append((x["name"], x["tier"], ch["tier"], ch.get("why", "")))
            x["tier"] = ch["tier"]

    if not added and not changed:
        print("Nothing new found today. List unchanged.")
        return
    shutil.copy(KFILE, ROOT / f"gta6_knowledge.{today}.bak.json")
    k["updated"] = today
    KFILE.write_text(json.dumps(k, indent=2, ensure_ascii=False), encoding="utf-8")
    for x in added:
        print(f"  + [{x['tier']}] {x['name']}  ({x['where']})  words: {', '.join(x['words'])}")
    for n, a, b, why in changed:
        print(f"  ~ {n}: {a} -> {b}  ({why})")
    print(f"Saved. {len(k['discoveries'])} items now. Restart live.py / scan.py to use the new list.")


if __name__ == "__main__":
    main()
