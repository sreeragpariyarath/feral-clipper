"""Quick check that the API key + model work:  python apitest.py"""
import os, sys
from common import load_config
import anthropic
cfg = load_config()
if not os.environ.get("ANTHROPIC_API_KEY"):
    sys.exit("ANTHROPIC_API_KEY is not set in this terminal")
c = anthropic.Anthropic()
r = c.messages.create(model=cfg["anthropic_model"], max_tokens=300,
                      messages=[{"role": "user", "content": 'Reply with only this JSON: {"ok": true}'}])
print("model       :", cfg["anthropic_model"])
print("stop_reason :", r.stop_reason)
print("block types :", [b.type for b in r.content])
print("text        :", "".join(getattr(b, "text", "") for b in r.content))
print("usage       :", r.usage.input_tokens, "in /", r.usage.output_tokens, "out")
