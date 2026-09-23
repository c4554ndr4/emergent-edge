from src.pipeline.judge_novelty import _merge_partial_decision, judge_novelty
from tests.test_schemas import build_dummy_case


def test_judge_returns_valid_decision():
    candidate = build_dummy_case("case-x")
    decision = judge_novelty(candidate, retrieved_cases=[], retrieved_patterns=[])
    assert decision.case_id == "case-x"
    assert decision.verdict in {
        "existing_pattern",
        "variant_of_existing",
        "new_pattern",
    }


def test_merge_partial_decision_parses_watchlist_hypothesis_fields():
    obj = {
        "verdict": "candidate_new_pattern",
        "closest_pattern": None,
        "supporting_pattern_ids": [],
        "supporting_case_ids": [],
        "shared_features": [],
        "differentiators": ["mechanism differs"],
        "new_axis": "new mechanism",
        "surface_vs_structural": "structural",
        "counterargument": "maybe variant",
        "why_counterargument_fails": "required signals missing",
        "needs_more_context": False,
        "requested_context": [],
        "confidence": 0.62,
        "suspected_pattern": "agentic_reputation_coercion",
        "recurrence_signature": ["public smear pressure", "autonomous posting loop"],
    }
    decision = _merge_partial_decision("case-x", obj, valid_pattern_ids=[], valid_case_ids=[])
    assert decision.verdict == "new_pattern"
    assert decision.suspected_pattern == "agentic_reputation_coercion"
    assert decision.recurrence_signature == ["public smear pressure", "autonomous posting loop"]
