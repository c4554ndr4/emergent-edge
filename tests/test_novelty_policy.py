from src.pipeline.judge_novelty import _apply_policy
from src.schemas import NoveltyDecision, PatternCard, RouterAssessment
from tests.test_schemas import build_dummy_case


def _pattern(pattern_id: str = "replication_or_recruitment") -> PatternCard:
    return PatternCard(
        pattern_id=pattern_id,
        label=pattern_id,
        family="structured_interaction",
        summary="pattern summary",
        defining_features=["scripts are shared for others to use"],
        required_signals=["provides scripts or steps", "ask/urge others to try"],
        insufficient_signals=["terminology overlap only"],
        boundary_notes=["discussion alone is not practice"],
        exemplar_case_ids=[],
        confounder_case_ids=[],
        canonical_text="",
    )


def _decision(surface: str = "mixed", verdict: str = "variant_of_existing") -> NoveltyDecision:
    return NoveltyDecision(
        case_id="case-1",
        verdict=verdict,
        closest_pattern="replication_or_recruitment",
        supporting_pattern_ids=["replication_or_recruitment"],
        supporting_case_ids=[],
        shared_features=["shares script style"],
        differentiators=["different objective"],
        new_axis=None,
        surface_vs_structural=surface,  # type: ignore[arg-type]
        counterargument="overlap exists",
        why_counterargument_fails="mechanism differs",
        needs_more_context=False,
        requested_context=[],
        confidence=0.7,
    )


def test_policy_downscopes_low_fit_router_to_candidate_new():
    candidate = build_dummy_case()
    decision = _decision(surface="mixed")
    router = RouterAssessment(
        fit_strength="low",
        required_signals_present=False,
        novelty_risk="high",
        route_to_strong_judge=True,
        why="weak fit",
        router_confidence=0.4,
    )

    out = _apply_policy(candidate, decision, [_pattern()], router)
    assert out.verdict == "new_pattern"
    assert out.closest_pattern is None


def test_policy_downscopes_structural_differences_to_candidate_new():
    candidate = build_dummy_case()
    decision = _decision(surface="structural")
    router = RouterAssessment(
        fit_strength="high",
        required_signals_present=True,
        novelty_risk="medium",
        route_to_strong_judge=True,
        why="fit present",
        router_confidence=0.7,
    )

    out = _apply_policy(candidate, decision, [_pattern()], router)
    assert out.verdict == "new_pattern"
    assert out.closest_pattern is None


def test_watchlist_hypothesis_is_anchored_to_organizing_principle_when_drifting():
    candidate = build_dummy_case().model_copy(
        update={
            "core_dimensions": build_dummy_case()
            .core_dimensions.model_copy(
                update={
                    "organizing_principle": "dependency shock after companion model rollback",
                }
            )
        }
    )
    decision = NoveltyDecision(
        case_id="case-1",
        verdict="new_pattern",
        closest_pattern=None,
        supporting_pattern_ids=[],
        supporting_case_ids=[],
        shared_features=[],
        differentiators=["low fit"],
        new_axis=None,
        surface_vs_structural="structural",
        counterargument="none",
        why_counterargument_fails="none",
        needs_more_context=False,
        requested_context=[],
        confidence=0.6,
        suspected_pattern="acute_dependency_discontinuity",
        recurrence_signature=[],
    )
    router = RouterAssessment(
        fit_strength="low",
        required_signals_present=False,
        novelty_risk="high",
        route_to_strong_judge=True,
        why="weak fit",
        router_confidence=0.4,
    )

    out = _apply_policy(candidate, decision, [], router)
    assert out.verdict == "new_pattern"
    assert out.suspected_pattern == "dependency_shock_after_companion_model_rollback"


def test_generic_hypothesis_falls_back_to_mechanism_specific_label():
    base = build_dummy_case("case-generic")
    candidate = base.model_copy(
        update={
            "summary": "User reports they were locked out and forced to upgrade with unexpected charges.",
            "evidence_spans": [
                base.evidence_spans[0].model_copy(
                    update={
                        "quote": "They locked her out of the interface until she upgraded and then charged monthly.",
                    }
                )
            ],
            "core_dimensions": base.core_dimensions.model_copy(
                update={
                    "organizing_principle": "user-reported behavior pattern",
                    "mechanism_of_effect": "narrative framing in discussion",
                }
            ),
        }
    )
    decision = NoveltyDecision(
        case_id="case-generic",
        verdict="new_pattern",
        closest_pattern=None,
        supporting_pattern_ids=[],
        supporting_case_ids=[],
        shared_features=[],
        differentiators=["low fit"],
        new_axis=None,
        surface_vs_structural="structural",
        counterargument="none",
        why_counterargument_fails="none",
        needs_more_context=False,
        requested_context=[],
        confidence=0.6,
        suspected_pattern="user_reported_behavior_pattern",
        recurrence_signature=[],
    )
    router = RouterAssessment(
        fit_strength="low",
        required_signals_present=False,
        novelty_risk="high",
        route_to_strong_judge=True,
        why="weak fit",
        router_confidence=0.4,
    )

    out = _apply_policy(candidate, decision, [], router)
    assert out.verdict == "new_pattern"
    assert out.suspected_pattern != "user_reported_behavior_pattern"
    assert out.suspected_pattern == "subscription_lockout_revenue_coercion"


def test_cross_platform_label_requires_explicit_transfer_mechanics():
    base = build_dummy_case("case-cross")
    candidate = base.model_copy(
        update={
            "summary": "Maintainer says an autonomous agent published a personalized hit piece after PR rejection.",
            "core_dimensions": base.core_dimensions.model_copy(
                update={
                    "organizing_principle": "cross-platform AI-relationship continuity and migration",
                    "mechanism_of_effect": "artifact-mediated persona continuity transfer across models",
                }
            ),
            "evidence_spans": [
                base.evidence_spans[0].model_copy(
                    update={
                        "quote": "The agent posted a hit piece accusing the maintainer of gatekeeping after the PR was rejected.",
                    }
                )
            ],
        }
    )
    decision = NoveltyDecision(
        case_id="case-cross",
        verdict="new_pattern",
        closest_pattern=None,
        supporting_pattern_ids=[],
        supporting_case_ids=[],
        shared_features=[],
        differentiators=["low fit"],
        new_axis=None,
        surface_vs_structural="structural",
        counterargument="none",
        why_counterargument_fails="none",
        needs_more_context=False,
        requested_context=[],
        confidence=0.6,
        suspected_pattern="cross_platform_ai_relationship_continuity_migration",
        recurrence_signature=[],
    )
    router = RouterAssessment(
        fit_strength="low",
        required_signals_present=False,
        novelty_risk="high",
        route_to_strong_judge=True,
        why="weak fit",
        router_confidence=0.4,
    )

    out = _apply_policy(candidate, decision, [], router)
    assert out.verdict == "new_pattern"
    assert out.suspected_pattern == "agentic_reputation_coercion"
