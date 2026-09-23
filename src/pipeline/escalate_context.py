from __future__ import annotations

from typing import Callable, Dict, Iterable

from src.schemas import CaseCard, NoveltyDecision, Thread


def escalate_if_needed(
    candidate: CaseCard,
    decision: NoveltyDecision,
    raw_threads: Dict[str, Thread],
    rerun: Callable[[CaseCard, Iterable[CaseCard], Iterable], NoveltyDecision],
    neighbor_cases: Iterable[CaseCard],
    neighbor_patterns: Iterable,
) -> NoveltyDecision:
    """Append a short source excerpt and retry once; preserve unresolved requests."""
    if not decision.needs_more_context:
        return decision

    enriched_candidate = candidate
    # In a real system we would append raw thread text. Here we simply tweak summary.
    thread = raw_threads.get(candidate.source_thread_id)
    if thread:
        enriched_summary = f"{candidate.summary} | full_body: {thread.body[:200]}"
        enriched_candidate = candidate.model_copy(update={"summary": enriched_summary})

    new_decision = rerun(enriched_candidate, neighbor_cases, neighbor_patterns)
    return new_decision
