from __future__ import annotations

from typing import List

from src.schemas import CaseCard, PatternCard


def _join(label: str, value: str | float | None) -> str:
    if value is None:
        return f"{label}: unknown"
    return f"{label}: {value}"


def canonicalize_case_card(card: CaseCard) -> str:
    """Deterministic text representation used for embeddings and retrieval."""
    lines: List[str] = []
    cd = card.core_dimensions
    lines.append(_join("case_id", card.case_id))
    lines.append(_join("source_thread_id", card.source_thread_id))
    lines.append(_join("summary", card.summary.strip()))

    lines.append("-- core_dimensions --")
    lines.extend(
        [
            _join("organizing_principle", cd.organizing_principle),
            _join("mechanism_of_effect", cd.mechanism_of_effect),
            _join("interaction_mode", cd.interaction_mode),
            _join("target_of_effect", cd.target_of_effect),
            _join("agency_attribution", cd.agency_attribution),
            _join("relationship_framing", cd.relationship_framing),
            _join("stance", cd.stance),
            _join("ritualization_level", cd.ritualization_level),
            _join("identity_co_construction", cd.identity_co_construction),
            _join("coordination_level", cd.coordination_level),
            _join("real_world_consequence", cd.real_world_consequence),
            _join("diffusion_stage", cd.diffusion_stage),
        ]
    )

    lines.append("-- novelty --")
    n = card.novelty
    lines.extend(
        [
            _join("verdict", n.verdict),
            _join("candidate_new_family", n.candidate_new_family or ""),
            _join("candidate_new_axes", ", ".join(n.candidate_new_axes) or ""),
            _join("surface_vs_structural", n.surface_vs_structural),
            _join("counterargument_to_novelty", n.counterargument_to_novelty),
            _join("why_counterargument_fails", n.why_counterargument_fails),
        ]
    )

    lines.append("-- evidence --")
    for span in card.evidence_spans:
        lines.append(_join("evidence", f"{span.dimension}: {span.quote} | {span.why_it_matters}"))

    lines.append("-- comparison --")
    for fit in card.comparison.nearest_known_patterns:
        lines.append(
            _join(
                "pattern_fit",
                f"{fit.label} fit={fit.fit} overlap={fit.overlap} difference={fit.difference}",
            )
        )
    lines.append(_join("why_existing_labels_fail", card.comparison.why_existing_labels_fail))

    return "\n".join(lines)


def canonicalize_pattern_card(card: PatternCard) -> str:
    """
    Retrieval canonicalization for pattern semantics only.
    Intentionally excludes AI systems-specific risk/governance fields and exemplar IDs,
    which are useful for analyst review but can pollute semantic similarity.
    """
    lines: List[str] = []
    lines.append(_join("pattern_id", card.pattern_id))
    lines.append(_join("label", card.label))
    lines.append(_join("family", card.family))
    lines.append(_join("summary", card.summary.strip()))
    lines.append("-- defining_features --")
    for feat in card.defining_features:
        lines.append(_join("feature", feat))
    lines.append("-- required_signals --")
    for req in card.required_signals:
        lines.append(_join("required", req))
    lines.append("-- insufficient_signals --")
    for miss in card.insufficient_signals:
        lines.append(_join("insufficient", miss))
    lines.append("-- boundary_notes --")
    for b in card.boundary_notes:
        lines.append(_join("boundary", b))
    return "\n".join(lines)


def canonicalize_case_card_v2(card: CaseCard) -> str:
    """
    Evidence-first case canonicalization that de-emphasizes ontology-heavy dimensions.
    """
    lines: List[str] = []
    cd = card.core_dimensions
    lines.append(_join("case_id", card.case_id))
    lines.append(_join("source_thread_id", card.source_thread_id))
    lines.append(_join("summary", card.summary.strip()))
    lines.append("-- evidence --")
    for span in card.evidence_spans:
        lines.append(_join("evidence", f"{span.dimension}: {span.quote} | {span.why_it_matters}"))
    lines.append("-- retrieval_signals --")
    lines.extend(
        [
            _join("interaction_mode", cd.interaction_mode),
            _join("target_of_effect", cd.target_of_effect),
            _join("real_world_consequence", cd.real_world_consequence),
            _join("diffusion_stage", cd.diffusion_stage),
        ]
    )
    return "\n".join(lines)


def canonicalize_pattern_card_v2(card: PatternCard) -> str:
    """
    Mechanism-first pattern canonicalization for retrieval anchors.
    """
    lines: List[str] = []
    lines.append(_join("pattern_id", card.pattern_id))
    lines.append(_join("label", card.label))
    lines.append(_join("summary", card.summary.strip()))
    lines.append("-- positive_anchor --")
    for feat in card.defining_features:
        lines.append(_join("feature", feat))
    for req in card.required_signals:
        lines.append(_join("required", req))
    lines.append("-- exclusion_boundary --")
    for miss in card.insufficient_signals:
        lines.append(_join("exclude", miss))
    for note in card.boundary_notes:
        lines.append(_join("boundary", note))
    return "\n".join(lines)


def canonicalize_case_card_for_retrieval(card: CaseCard, version: str = "v1") -> str:
    if version == "v2":
        return canonicalize_case_card_v2(card)
    return canonicalize_case_card(card)


def canonicalize_pattern_card_for_retrieval(card: PatternCard, version: str = "v1") -> str:
    if version == "v2":
        return canonicalize_pattern_card_v2(card)
    return canonicalize_pattern_card(card)
