"""Judge provider switch: availability rules and the shared reply shape (no network calls)."""
import pytest

from clipper.ai import judge, providers


def test_available_follows_config(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert providers.available({"judge_provider": "claude", "anthropic_model": "m"})
    assert not providers.available({"judge_provider": "gemini", "gemini_model": "m"})
    monkeypatch.setenv("GEMINI_API_KEY", "y")
    assert providers.available({"judge_provider": "gemini", "gemini_model": "m"})
    assert providers.available({"judge_provider": "ollama", "ollama_model": "m"})
    assert not providers.available({"judge_provider": "other"})


def test_unknown_provider_errors():
    with pytest.raises(providers.ProviderError):
        providers.complete("s", "u", {"judge_provider": "nope"})


def test_judge_uses_any_provider(monkeypatch, tmp_path):
    reply = providers.Reply('{"standalone": true, "score": 7, "start_s": 2, "end_s": 20, '
                            '"title": "T", "payoff_text": "he lands it"}', 10, 5, "fake-model")
    monkeypatch.setattr(providers, "available", lambda cfg: True)
    monkeypatch.setattr(providers, "complete", lambda s, u, cfg: reply)
    cand = {"id": 1, "peak_t": 10, "win_start": 0, "win_end": 30, "h_score": 0.5, "signals": {},
            "chat_top": {}, "chat_samples": []}
    j = judge.judge(cand, [{"w": "hi", "s": 0, "e": 1}], 30, {"judge_provider": "gemini"}, "ch", tmp_path)
    assert j["source"] == "fake-model" and j["score"] == 7 and j["usage"] == {"in": 10, "out": 5}
    assert judge.has_payoff(j)


def test_judge_falls_back_to_heuristic_on_errors(monkeypatch, tmp_path):
    def boom(s, u, cfg):
        raise providers.ProviderError("down")
    monkeypatch.setattr(providers, "available", lambda cfg: True)
    monkeypatch.setattr(providers, "complete", boom)
    cand = {"id": 1, "peak_t": 10, "win_start": 0, "win_end": 30, "h_score": 0.5, "signals": {},
            "chat_top": {}, "chat_samples": []}
    j = judge.judge(cand, [], 30, {}, "ch", tmp_path)
    assert "heuristic" in j["reasons"] and "down" in j["reasons"]
