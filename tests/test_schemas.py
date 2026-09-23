from src.schemas import (
    CaseCard,
    ComparisonBlock,
    CoreDimensions,
    EvidenceSpan,
    NoveltyBlock,
    PatternFit,
    SchemaVersion,
)


def build_dummy_case(case_id: str = "case-1") -> CaseCard:
    core = CoreDimensions(
        interaction_mode="discussion",
        organizing_principle="structured_interaction",
        mechanism_of_effect="iterative prompts",
        target_of_effect="community",
        agency_attribution="users",
        relationship_framing="mixed",
        ritualization_level="low",
        identity_co_construction="low",
        coordination_level="low",
        real_world_consequence="unknown",
        stance="curious",
        diffusion_stage="isolated",
    )
    comparison = ComparisonBlock(
        nearest_known_patterns=[
            PatternFit(label="ritual_induction", fit="moderate", overlap="loops", difference="less ritual"),
        ],
        why_existing_labels_fail="limited evidence",
    )
    novelty = NoveltyBlock(
        verdict="variant_of_existing",
        candidate_new_family=None,
        candidate_new_axes=["ritual_intensity"],
        surface_vs_structural="mixed",
        counterargument_to_novelty="may just be style",
        why_counterargument_fails="mechanism differs",
        needs_more_context=False,
        requested_context=[],
    )
    card = CaseCard(
        case_id=case_id,
        source_thread_id="t1",
        summary="test summary",
        evidence_spans=[EvidenceSpan(quote="q", why_it_matters="w", dimension="d")],
        core_dimensions=core,
        comparison=comparison,
        novelty=novelty,
        confidence=0.5,
        canonical_text="",
        schema_version=SchemaVersion,
    )
    return card


def test_case_card_roundtrip():
    card = build_dummy_case()
    dumped = card.model_dump()
    parsed = CaseCard.model_validate(dumped)
    assert parsed.case_id == "case-1"
    assert parsed.core_dimensions.organizing_principle == "structured_interaction"
