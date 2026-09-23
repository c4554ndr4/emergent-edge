from __future__ import annotations

from src.pipeline.llm_origin_gate import decide_llm_origin
from src.pipeline.run_pipeline import _prune_empty_patterns
from src.schemas import (
    NoveltyDecision,
    PatternCard,
    Thread,
)


class _StubLLM:
    def __init__(self, raw: str) -> None:
        self.raw = raw

    def generate(self, prompt: str, system_prompt: str | None = None, max_tokens: int = 800) -> str:
        return self.raw


def _thread(tid: str) -> Thread:
    return Thread(
        thread_id=tid,
        subreddit="testsub",
        title="Test title",
        body="Test body with first-person writing.",
        comments=[],
        created_utc=None,
        url="https://example.com",
        author="user",
        metadata={},
    )


def _pattern(pid: str, family: str, exemplars: list[str]) -> PatternCard:
    return PatternCard(
        pattern_id=pid,
        label=pid,
        family=family,
        summary="s",
        defining_features=[],
        required_signals=[],
        insufficient_signals=[],
        boundary_notes=[],
        impact_pathways=[],
        risk_escalation_triggers=[],
        monitoring_priority="medium",
        why_review_matters="",
        exemplar_case_ids=exemplars,
        confounder_case_ids=[],
        canonical_text="",
    )


def _decision(case_id: str, verdict: str, closest_pattern: str | None) -> NoveltyDecision:
    return NoveltyDecision(
        case_id=case_id,
        verdict=verdict,
        closest_pattern=closest_pattern,
        supporting_pattern_ids=[closest_pattern] if closest_pattern else [],
        supporting_case_ids=[],
        shared_features=[],
        differentiators=[],
        new_axis=None,
        surface_vs_structural="mixed",
        counterargument="",
        why_counterargument_fails="",
        needs_more_context=False,
        requested_context=[],
        confidence=0.6,
    )


def test_origin_gate_drops_non_llm_when_required() -> None:
    thread = _thread("t1")
    llm = _StubLLM(
        '{"verdict":"human_like","llm_written_extent":"none","confidence":0.88,"rationale":"chatty personal style"}'
    )
    decision = decide_llm_origin(thread, llm=llm, keep_only_llm_like=True)
    assert decision.verdict == "human_like"
    assert decision.llm_written_extent == "none"
    assert decision.should_keep is False


def test_origin_gate_keeps_llm_like() -> None:
    thread = _thread("t2")
    llm = _StubLLM(
        '{"verdict":"llm_like","llm_written_extent":"full","confidence":0.81,"rationale":"templated structure"}'
    )
    decision = decide_llm_origin(thread, llm=llm, keep_only_llm_like=True)
    assert decision.verdict == "llm_like"
    assert decision.llm_written_extent == "full"
    assert decision.should_keep is True


def test_prune_removes_empty_non_core_patterns() -> None:
    patterns = [
        _pattern("spiral_core", "structured_interaction", []),
        _pattern("live_keep", "live", ["case-lib-1"]),
        _pattern("live_drop", "live", []),
    ]
    decisions = [_decision("case-new-1", "existing_pattern", "live_keep")]
    kept = _prune_empty_patterns(
        patterns,
        decisions=decisions,
        library_case_ids={"case-lib-1"},
        new_case_ids={"case-new-1"},
        preserve_families={"structured_interaction"},
    )
    kept_ids = {p.pattern_id for p in kept}
    assert "spiral_core" in kept_ids
    assert "live_keep" in kept_ids
    assert "live_drop" not in kept_ids
