import numpy as np

from clipper.detect import quality as q


def test_ranks_spread_and_ties():
    assert q.ranks([3.0, 1.0, 2.0]) == [1.0, 0.0, 0.5]
    assert q.ranks([1.0, 1.0, 2.0]) == [0.25, 0.25, 1.0]
    assert q.ranks([None, 5.0]) == [None, 0.5]


def test_action_scores_discriminate_even_when_raw_values_are_close():
    # CLIP's old group probability gave ~0.99 for all of these; ranks spread them over 0..1
    out = q.action_scores([0.011, 0.012, 0.013], [0.05, 0.20, 0.35])
    assert out[0] < out[1] < out[2] and out[0] == 0.0 and out[2] == 1.0


def test_payoff_needs_something_at_the_end():
    db = np.full(60, -30.0)
    mot = np.full(60, 1.0)
    assert q.payoff_score(db, mot, 0, 30, mot_ref=2.0) == 0.0          # flat window
    db[25] = -20.0                                                      # +10 dB in the last third
    assert q.payoff_score(db, mot, 0, 30, mot_ref=2.0) == 1.0
    db2 = np.full(60, -30.0)
    db2[5] = -10.0                                                      # loud only at the start
    assert q.payoff_score(db2, mot, 0, 30, mot_ref=2.0) == 0.0


def test_quiet_ending_is_noted_not_penalised():
    loud, n1 = q.combine(0.8, 0.8, 0.8, 0.5, 0.9, False, False)
    quiet, n2 = q.combine(0.8, 0.8, 0.8, 0.5, 0.0, False, False)
    assert loud == quiet and not n1 and n2 == ["quiet ending"]


def test_judge_must_name_a_payoff():
    from clipper.ai.judge import has_payoff, validate
    assert not has_payoff(validate({"payoff_text": "  "}, 30))
    assert has_payoff(validate({"payoff_text": "he crashes the plane"}, 30))
    assert has_payoff({"source": "heuristic"})
