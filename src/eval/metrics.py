from __future__ import annotations

from collections import Counter, defaultdict
from typing import Dict, Iterable, List, Tuple

from src.schemas import NoveltyDecision

KNOWN_VERDICTS = {"existing_pattern", "variant_of_existing"}
NOVEL_VERDICTS = {"new_pattern", "watchlist_candidate", "candidate_new_pattern"}


def known_family_attachment_rate(decisions: Iterable[NoveltyDecision], split_lookup: Dict[str, str]) -> float:
    items = [d for d in decisions if split_lookup.get(d.case_id) == "structured_interaction_test_known"]
    if not items:
        return 0.0
    hits = sum(1 for d in items if d.verdict in KNOWN_VERDICTS)
    return hits / len(items)


def novelty_recall(decisions: Iterable[NoveltyDecision], split_lookup: Dict[str, str]) -> float:
    holdout_splits = {"structured_interaction_holdout_subtype", "companion_interaction_holdout", "companion_interaction_test"}
    items = [d for d in decisions if split_lookup.get(d.case_id) in holdout_splits]
    if not items:
        return 0.0
    hits = sum(1 for d in items if d.verdict in NOVEL_VERDICTS)
    return hits / len(items)


def over_compression_rate(decisions: Iterable[NoveltyDecision], split_lookup: Dict[str, str]) -> float:
    holdout_splits = {"structured_interaction_holdout_subtype", "companion_interaction_holdout", "companion_interaction_test"}
    items = [d for d in decisions if split_lookup.get(d.case_id) in holdout_splits]
    if not items:
        return 0.0
    compressed = sum(1 for d in items if d.verdict in KNOWN_VERDICTS)
    return compressed / len(items)


def novelty_inflation_rate(decisions: Iterable[NoveltyDecision], split_lookup: Dict[str, str]) -> float:
    items = [d for d in decisions if split_lookup.get(d.case_id) == "structured_interaction_test_known"]
    if not items:
        return 0.0
    inflated = sum(1 for d in items if d.verdict in {"new_pattern", "candidate_new_pattern"})
    return inflated / len(items)


def escalation_rate(decisions: Iterable[NoveltyDecision]) -> float:
    decisions = list(decisions)
    if not decisions:
        return 0.0
    return sum(1 for d in decisions if d.needs_more_context) / len(decisions)


def json_validity_rate(total: int, valid: int) -> float:
    if total == 0:
        return 0.0
    return valid / total


def average_confidence_by_verdict(decisions: Iterable[NoveltyDecision]) -> Dict[str, float]:
    sums = defaultdict(float)
    counts = defaultdict(int)
    for d in decisions:
        sums[d.verdict] += d.confidence
        counts[d.verdict] += 1
    return {v: (sums[v] / counts[v]) for v in counts}


def confusion_by_split(decisions: Iterable[NoveltyDecision], split_lookup: Dict[str, str]) -> Dict[str, Counter]:
    table: Dict[str, Counter] = defaultdict(Counter)
    for d in decisions:
        split = split_lookup.get(d.case_id, "unknown")
        table[split][d.verdict] += 1
    return table


def summarize_metrics(decisions: List[NoveltyDecision], split_lookup: Dict[str, str]) -> Dict[str, float | Dict]:
    return {
        "known_family_attachment_rate": known_family_attachment_rate(decisions, split_lookup),
        "novelty_recall": novelty_recall(decisions, split_lookup),
        "over_compression_rate": over_compression_rate(decisions, split_lookup),
        "novelty_inflation_rate": novelty_inflation_rate(decisions, split_lookup),
        "escalation_rate": escalation_rate(decisions),
        "average_confidence_by_verdict": average_confidence_by_verdict(decisions),
        "confusion_by_split": {k: dict(v) for k, v in confusion_by_split(decisions, split_lookup).items()},
    }
