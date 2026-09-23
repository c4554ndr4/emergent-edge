from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Dict, Iterable, List, Tuple

from src.config import get_settings
from src.retrieval.canonicalize import canonicalize_pattern_card_for_retrieval
from src.schemas import CaseCard, NoveltyDecision, PatternCard


def _slugify(text: str) -> str:
    t = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    t = re.sub(r"_+", "_", t)
    return t[:64] or "novel_hypothesis"


def _group_key(decision: NoveltyDecision) -> str | None:
    if decision.suspected_pattern:
        return _slugify(decision.suspected_pattern)
    if decision.new_axis:
        return _slugify(decision.new_axis)
    return None


def _top_terms(values: Iterable[str], limit: int = 5) -> List[str]:
    counter: Counter[str] = Counter()
    for v in values:
        cleaned = v.strip()
        if cleaned:
            counter[cleaned] += 1
    return [k for k, _ in counter.most_common(limit)]


def propose_pattern_cards_from_watchlist(
    case_cards: Dict[str, CaseCard],
    decisions: Iterable[NoveltyDecision],
    min_support: int = 2,
) -> List[PatternCard]:
    settings = get_settings()
    grouped: Dict[str, List[Tuple[NoveltyDecision, CaseCard]]] = defaultdict(list)
    for d in decisions:
        if d.verdict not in {"new_pattern", "watchlist_candidate", "candidate_new_pattern"}:
            continue
        key = _group_key(d)
        if not key:
            continue
        c = case_cards.get(d.case_id)
        if c is None:
            continue
        grouped[key].append((d, c))

    proposals: List[PatternCard] = []
    for key, rows in sorted(grouped.items()):
        if len(rows) < min_support:
            continue

        exemplars = [c.case_id for _, c in rows][:8]
        organizing = _top_terms((c.core_dimensions.organizing_principle for _, c in rows), limit=3)
        mechanisms = _top_terms((c.core_dimensions.mechanism_of_effect for _, c in rows), limit=3)
        signatures = _top_terms(
            (s for d, _ in rows for s in d.recurrence_signature),
            limit=6,
        )
        differentiators = _top_terms(
            (x for d, _ in rows for x in d.differentiators),
            limit=4,
        )

        summary_bits = []
        if organizing:
            summary_bits.append(f"Organizing principle: {organizing[0]}")
        if mechanisms:
            summary_bits.append(f"Mechanism: {mechanisms[0]}")
        summary = " | ".join(summary_bits) or "Watchlist-derived emerging pattern proposal."

        required = signatures[:3] if signatures else mechanisms[:2]
        defining = signatures[:5] if signatures else mechanisms[:3]
        insufficient = [
            "keyword overlap without behavior-level evidence",
            "discussion or critique without practice/incident mechanism",
        ]
        boundary = [
            "Promote only after recurrence across independent cases.",
            "Do not treat vocabulary novelty alone as structural novelty.",
        ]
        if differentiators:
            boundary.append(f"Current differentiator trend: {differentiators[0]}")

        card = PatternCard(
            pattern_id=f"live_{key}",
            label=key,
            family="live_novelty",
            summary=summary,
            defining_features=defining,
            required_signals=required,
            insufficient_signals=insufficient,
            boundary_notes=boundary,
            exemplar_case_ids=exemplars,
            confounder_case_ids=[],
            canonical_text="",
        )
        card.canonical_text = canonicalize_pattern_card_for_retrieval(
            card, settings.pattern_card_canonicalization_version
        )
        proposals.append(card)

    return proposals


def merge_pattern_cards(
    existing: Iterable[PatternCard], proposals: Iterable[PatternCard]
) -> List[PatternCard]:
    """Merge proposals into active library by pattern_id (replace on collision)."""
    merged: List[PatternCard] = []
    index: Dict[str, int] = {}

    for card in existing:
        index[card.pattern_id] = len(merged)
        merged.append(card)

    for proposal in proposals:
        pos = index.get(proposal.pattern_id)
        if pos is None:
            index[proposal.pattern_id] = len(merged)
            merged.append(proposal)
        else:
            merged[pos] = proposal

    return merged
