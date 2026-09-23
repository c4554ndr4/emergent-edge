from src.pipeline.escalate_context import escalate_if_needed
from src.schemas import NoveltyDecision, Thread
from tests.test_schemas import build_dummy_case


def test_escalation_triggers_rerun():
    candidate = build_dummy_case("case-e")
    decision = NoveltyDecision(
        case_id="case-e",
        verdict="new_pattern",
        closest_pattern=None,
        supporting_pattern_ids=[],
        supporting_case_ids=[],
        shared_features=[],
        differentiators=[],
        new_axis=None,
        surface_vs_structural="mixed",
        counterargument="",
        why_counterargument_fails="",
        needs_more_context=True,
        requested_context=[],
        confidence=0.2,
    )
    raw_threads = {
        "t1": Thread(
            thread_id="t1",
            subreddit="r/test",
            title="title",
            body="long body text",
            comments=[],
            created_utc=None,
            url=None,
            author=None,
            metadata={},
        )
    }

    def rerun(cand, rc, rp):
        return decision.model_copy(update={"needs_more_context": False, "verdict": "existing_pattern"})

    new_decision = escalate_if_needed(candidate, decision, raw_threads, rerun, [], [])
    assert new_decision.verdict == "existing_pattern"
    assert new_decision.needs_more_context is False


def test_escalation_preserves_unresolved_context_after_one_retry():
    candidate = build_dummy_case("case-cap")
    decision = NoveltyDecision(
        case_id="case-cap",
        verdict="new_pattern",
        closest_pattern=None,
        supporting_pattern_ids=[],
        supporting_case_ids=[],
        shared_features=[],
        differentiators=[],
        new_axis=None,
        surface_vs_structural="mixed",
        counterargument="",
        why_counterargument_fails="",
        needs_more_context=True,
        requested_context=["more raw text"],
        confidence=0.2,
    )
    raw_threads = {
        "t1": Thread(
            thread_id="t1",
            subreddit="r/test",
            title="title",
            body="long body text",
            comments=[],
            created_utc=None,
            url=None,
            author=None,
            metadata={},
        )
    }

    def rerun(cand, rc, rp):
        return decision.model_copy(update={"needs_more_context": True})

    new_decision = escalate_if_needed(candidate, decision, raw_threads, rerun, [], [])
    assert new_decision.needs_more_context is True
    assert new_decision.requested_context == ["more raw text"]
