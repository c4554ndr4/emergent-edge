from src.eval.metrics import known_family_attachment_rate, novelty_recall, over_compression_rate, novelty_inflation_rate
from src.schemas import NoveltyDecision


def make_decision(case_id: str, verdict: str) -> NoveltyDecision:
    return NoveltyDecision(
        case_id=case_id,
        verdict=verdict,
        closest_pattern=None,
        supporting_pattern_ids=[],
        supporting_case_ids=[],
        shared_features=[],
        differentiators=[],
        new_axis=None,
        surface_vs_structural="mixed",
        counterargument="",
        why_counterargument_fails="",
        needs_more_context=False,
        requested_context=[],
        confidence=0.5,
    )


def test_metric_computations():
    decs = [
        make_decision("a", "existing_pattern"),
        make_decision("b", "new_pattern"),
        make_decision("c", "variant_of_existing"),
    ]
    split = {
        "a": "structured_interaction_test_known",
        "b": "companion_interaction_holdout",
        "c": "structured_interaction_holdout_subtype",
    }
    assert known_family_attachment_rate(decs, split) == 1.0
    assert novelty_recall(decs, split) == 0.5
    assert over_compression_rate(decs, split) == 0.5
    assert novelty_inflation_rate(decs, split) == 0.0
