from src.pipeline.propose_pattern_cards import merge_pattern_cards, propose_pattern_cards_from_watchlist
from src.schemas import NoveltyDecision, PatternCard
from tests.test_schemas import build_dummy_case


def _watch_decision(case_id: str, suspected_pattern: str) -> NoveltyDecision:
    return NoveltyDecision(
        case_id=case_id,
        verdict="new_pattern",
        closest_pattern=None,
        supporting_pattern_ids=[],
        supporting_case_ids=[],
        shared_features=[],
        differentiators=["mechanism differs from known patterns"],
        new_axis="new axis",
        surface_vs_structural="structural",
        counterargument="could be variant",
        why_counterargument_fails="required signals absent",
        needs_more_context=False,
        requested_context=[],
        confidence=0.66,
        suspected_pattern=suspected_pattern,
        recurrence_signature=["shared automation sequence", "public pressure loop"],
    )


def test_proposes_pattern_cards_from_recurring_watchlist_cases():
    c1 = build_dummy_case("case-a")
    c2 = build_dummy_case("case-b")
    case_lookup = {c1.case_id: c1, c2.case_id: c2}
    decisions = [
        _watch_decision("case-a", "agentic_reputation_coercion"),
        _watch_decision("case-b", "agentic_reputation_coercion"),
    ]

    proposals = propose_pattern_cards_from_watchlist(case_lookup, decisions, min_support=2)
    assert len(proposals) == 1
    proposal = proposals[0]
    assert proposal.pattern_id.startswith("live_agentic_reputation_coercion")
    assert proposal.family == "live_novelty"
    assert len(proposal.exemplar_case_ids) == 2


def test_merge_pattern_cards_replaces_existing_and_appends_new():
    existing = [
        PatternCard(
            pattern_id="spiral_seed",
            label="spiral_seed",
            family="structured_interaction",
            summary="seed",
            defining_features=[],
            required_signals=[],
            insufficient_signals=[],
            boundary_notes=[],
            exemplar_case_ids=[],
            confounder_case_ids=[],
            canonical_text="",
        ),
        PatternCard(
            pattern_id="live_agentic_reputation_coercion",
            label="live_agentic_reputation_coercion",
            family="live_novelty",
            summary="old",
            defining_features=[],
            required_signals=[],
            insufficient_signals=[],
            boundary_notes=[],
            exemplar_case_ids=["case-old"],
            confounder_case_ids=[],
            canonical_text="",
        ),
    ]
    proposals = [
        PatternCard(
            pattern_id="live_agentic_reputation_coercion",
            label="live_agentic_reputation_coercion",
            family="live_novelty",
            summary="updated",
            defining_features=[],
            required_signals=[],
            insufficient_signals=[],
            boundary_notes=[],
            exemplar_case_ids=["case-new-a", "case-new-b"],
            confounder_case_ids=[],
            canonical_text="",
        ),
        PatternCard(
            pattern_id="live_companion_withdrawal_shock",
            label="live_companion_withdrawal_shock",
            family="live_novelty",
            summary="new",
            defining_features=[],
            required_signals=[],
            insufficient_signals=[],
            boundary_notes=[],
            exemplar_case_ids=["case-b"],
            confounder_case_ids=[],
            canonical_text="",
        ),
    ]

    merged = merge_pattern_cards(existing, proposals)
    by_id = {p.pattern_id: p for p in merged}
    assert len(merged) == 3
    assert by_id["spiral_seed"].summary == "seed"
    assert by_id["live_agentic_reputation_coercion"].summary == "updated"
    assert by_id["live_companion_withdrawal_shock"].summary == "new"
