from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from src.config import get_settings
from src.io.json_parsing import parse_json_from_text
from src.models.llm_client import LLMClient, get_default_llm_client
from src.pipeline.retrieve_similar_cards import make_evidence_packet
from src.schemas import CaseCard, NoveltyDecision, PatternCard, RouterAssessment

DEFAULT_JUDGE_PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "novelty_judge.txt"
ROUTER_PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "novelty_router.txt"


def _heuristic_verdict(card: CaseCard, patterns: List[PatternCard]) -> NoveltyDecision:
    text = card.canonical_text.lower()
    verdict = "new_pattern"
    closest = None
    if "spiral" in text and patterns:
        verdict = "variant_of_existing"
        closest = patterns[0].pattern_id
    elif "boyfriend" in text or "companion_interaction" in text:
        verdict = "new_pattern"
    return NoveltyDecision(
        case_id=card.case_id,
        verdict=verdict,
        closest_pattern=closest,
        supporting_pattern_ids=[closest] if closest else [],
        supporting_case_ids=[],
        shared_features=["heuristic_overlap"],
        differentiators=["heuristic_stub"],
        new_axis=None,
        surface_vs_structural="mixed",
        counterargument="Could be variant of structured_interaction",
        why_counterargument_fails="heuristic stub lacks detail",
        needs_more_context=False,
        requested_context=[],
        confidence=0.35,
        suspected_pattern=None,
        recurrence_signature=[],
    )


def judge_novelty(
    candidate: CaseCard,
    retrieved_cases: Iterable[CaseCard],
    retrieved_patterns: Iterable[PatternCard],
    llm: LLMClient | None = None,
    router_llm: LLMClient | None = None,
    case_scores: Optional[Dict[str, float]] = None,
    pattern_scores: Optional[Dict[str, float]] = None,
) -> NoveltyDecision:
    settings = get_settings()
    strong_client = llm or get_default_llm_client(settings.model_name, settings.llm_api_key)
    cheap_client = router_llm or get_default_llm_client(
        settings.router_model_name, settings.llm_api_key
    )

    if settings.novelty_pipeline_version == "v2":
        return _judge_novelty_v2(
            candidate,
            retrieved_cases,
            retrieved_patterns,
            strong_client,
            cheap_client,
            settings,
        )

    cases = list(retrieved_cases)
    patterns = list(retrieved_patterns)
    case_scores = case_scores or {}
    pattern_scores = pattern_scores or {}

    candidate_bundle = _candidate_bundle(candidate)
    case_bundles = [_case_bundle(c, case_scores.get(c.case_id, 0.0)) for c in cases[:5]]
    pattern_bundles = [_pattern_bundle(p, pattern_scores.get(p.pattern_id, 0.0)) for p in patterns[:2]]

    router = _run_router(candidate_bundle, case_bundles, pattern_bundles, cheap_client)

    if _route_to_strong(candidate, router, case_scores, pattern_scores, settings):
        decision = _run_strong_judge(
            candidate,
            candidate_bundle,
            case_bundles,
            pattern_bundles,
            strong_client,
            patterns,
            cases,
            router,
        )
    else:
        decision = _router_to_decision(candidate.case_id, router, patterns)

    decision = _apply_policy(candidate, decision, patterns, router)
    return decision


def _judge_novelty_v2(
    candidate: CaseCard,
    retrieved_cases: Iterable[CaseCard],
    retrieved_patterns: Iterable[PatternCard],
    strong_client: LLMClient,
    cheap_client: LLMClient,
    settings,
) -> NoveltyDecision:
    cases = list(retrieved_cases)
    patterns = list(retrieved_patterns)
    sys_prompt = _judge_prompt_path(settings).read_text().strip()
    candidate_bundle = _candidate_bundle_v2(candidate)
    pattern_bundles = [_pattern_bundle(p, 0.0) for p in patterns[:3]]
    case_bundles = [_case_bundle_v2(c) for c in cases[:4]]
    user_prompt = (
        "CandidateBundle:\n"
        + json.dumps(candidate_bundle, indent=2)
        + "\nRetrievedCaseBundles:\n"
        + json.dumps(case_bundles, indent=2)
        + "\nPatternBundles:\n"
        + json.dumps(pattern_bundles, indent=2)
        + "\nReturn NoveltyDecision JSON only."
    )

    try:
        cheap_decision = _run_decision_judge(
            candidate.case_id, user_prompt, cheap_client, sys_prompt, patterns, cases
        )
    except Exception:
        cheap_decision = NoveltyDecision(
            case_id=candidate.case_id,
            verdict="new_pattern",
            closest_pattern=patterns[0].pattern_id if patterns else None,
            supporting_pattern_ids=[],
            supporting_case_ids=[],
            shared_features=[],
            differentiators=["cheap_judge_parse_failure"],
            new_axis=None,
            surface_vs_structural="unknown",
            counterargument="cheap judge failed to return parseable JSON",
            why_counterargument_fails="fallback to strong judge required",
            needs_more_context=False,
            requested_context=[],
            confidence=0.2,
            suspected_pattern=None,
            recurrence_signature=[],
        )
    if (
        cheap_decision.verdict == "existing_pattern"
        and cheap_decision.confidence >= settings.novelty_existing_close_confidence_threshold
    ):
        return _normalize_v2_decision(candidate, cheap_decision, patterns)

    try:
        strong_decision = _run_decision_judge(
            candidate.case_id, user_prompt, strong_client, sys_prompt, patterns, cases
        )
    except Exception:
        strong_decision = cheap_decision
    return _normalize_v2_decision(candidate, strong_decision, patterns)


def _run_router(
    candidate_bundle: Dict,
    case_bundles: List[Dict],
    pattern_bundles: List[Dict],
    cheap_client: LLMClient,
) -> RouterAssessment:
    sys_prompt = ROUTER_PROMPT_PATH.read_text().strip()
    user_prompt = (
        "CandidateBundle:\n"
        + json.dumps(candidate_bundle, indent=2)
        + "\nRetrievedCaseBundles:\n"
        + json.dumps(case_bundles, indent=2)
        + "\nPatternBundles:\n"
        + json.dumps(pattern_bundles, indent=2)
        + "\nReturn router JSON only."
    )

    try:
        raw = cheap_client.generate(user_prompt, system_prompt=sys_prompt, max_tokens=500)
        obj = parse_json_from_text(raw)
        return _merge_router(obj)
    except Exception:
        return RouterAssessment(
            fit_strength="unknown",
            required_signals_present=False,
            novelty_risk="high",
            route_to_strong_judge=True,
            why="router parsing failed",
            router_confidence=0.2,
        )


def _run_strong_judge(
    candidate: CaseCard,
    candidate_bundle: Dict,
    case_bundles: List[Dict],
    pattern_bundles: List[Dict],
    strong_client: LLMClient,
    patterns: List[PatternCard],
    cases: List[CaseCard],
    router: RouterAssessment,
) -> NoveltyDecision:
    sys_prompt = _judge_prompt_path(get_settings()).read_text().strip()
    user_prompt = (
        "CandidateBundle:\n"
        + json.dumps(candidate_bundle, indent=2)
        + "\nRetrievedCaseBundles:\n"
        + json.dumps(case_bundles, indent=2)
        + "\nPatternBundles:\n"
        + json.dumps(pattern_bundles, indent=2)
        + "\nReturn NoveltyDecision JSON only."
    )

    pattern_ids = [p.pattern_id for p in patterns]
    case_ids = [c.case_id for c in cases]
    try:
        return _run_decision_judge(
            candidate.case_id, user_prompt, strong_client, sys_prompt, patterns, cases
        )
    except Exception:
        return _router_to_decision(candidate.case_id, router, patterns)


def _route_to_strong(
    candidate: CaseCard,
    router: RouterAssessment,
    case_scores: Dict[str, float],
    pattern_scores: Dict[str, float],
    settings,
) -> bool:
    if router.route_to_strong_judge:
        return True
    if router.fit_strength in {"low", "unknown"}:
        return True
    if not router.required_signals_present:
        return True
    if router.novelty_risk == "high":
        return True
    if _neighbor_agreement(case_scores) < settings.neighbor_agreement_threshold:
        return True
    if candidate.core_dimensions.diffusion_stage in {"spreading", "established"}:
        return True
    if router.router_confidence < settings.router_confidence_threshold:
        return True
    # Ambiguous top-pattern confidence should be adjudicated by the strong judge.
    top_pattern_score = max(pattern_scores.values()) if pattern_scores else 0.0
    if top_pattern_score < 0.80:
        return True
    return False


def _judge_prompt_path(settings) -> Path:
    return settings.novelty_judge_prompt_path or DEFAULT_JUDGE_PROMPT_PATH


def _run_decision_judge(
    case_id: str,
    user_prompt: str,
    client: LLMClient,
    system_prompt: str,
    patterns: List[PatternCard],
    cases: List[CaseCard],
) -> NoveltyDecision:
    pattern_ids = [p.pattern_id for p in patterns]
    case_ids = [c.case_id for c in cases]
    raw = client.generate(user_prompt, system_prompt=system_prompt, max_tokens=1200)
    obj = parse_json_from_text(raw)
    return _merge_partial_decision(case_id, obj, pattern_ids, case_ids)


def _neighbor_agreement(case_scores: Dict[str, float]) -> float:
    vals = sorted(case_scores.values(), reverse=True)[:3]
    if not vals:
        return 0.0
    if len(vals) == 1:
        return vals[0]
    mean = sum(vals) / len(vals)
    spread = max(vals) - min(vals)
    return max(0.0, min(1.0, mean - (spread * 0.25)))


def _candidate_bundle(card: CaseCard) -> Dict:
    packet = make_evidence_packet(card)
    return {
        "case_id": card.case_id,
        "summary": card.summary,
        "core_dimensions": {
            "organizing_principle": card.core_dimensions.organizing_principle,
            "mechanism_of_effect": card.core_dimensions.mechanism_of_effect,
            "target_of_effect": card.core_dimensions.target_of_effect,
            "stance": card.core_dimensions.stance,
            "coordination_level": card.core_dimensions.coordination_level,
            "real_world_consequence": card.core_dimensions.real_world_consequence,
            "diffusion_stage": card.core_dimensions.diffusion_stage,
        },
        "evidence_packet": [s.model_dump() for s in packet.evidence[:6]],
    }


def _candidate_bundle_v2(card: CaseCard) -> Dict:
    packet = make_evidence_packet(card)
    return {
        "case_id": card.case_id,
        "summary": card.summary,
        "retrieval_signals": {
            "interaction_mode": card.core_dimensions.interaction_mode,
            "target_of_effect": card.core_dimensions.target_of_effect,
            "real_world_consequence": card.core_dimensions.real_world_consequence,
            "diffusion_stage": card.core_dimensions.diffusion_stage,
        },
        "evidence_spans": [s.model_dump() for s in packet.evidence[:6]],
    }


def _case_bundle(card: CaseCard, score: float) -> Dict:
    packet = make_evidence_packet(card)
    attached = None
    if card.comparison.nearest_known_patterns:
        attached = card.comparison.nearest_known_patterns[0].label

    why_similar = (
        f"Shared organizing principle terms around {card.core_dimensions.organizing_principle}; "
        f"similarity_score={score:.3f}"
    )
    return {
        "case_id": card.case_id,
        "similarity_score": round(score, 4),
        "attached_pattern_id": attached,
        "key_dimensions": {
            "organizing_principle": card.core_dimensions.organizing_principle,
            "mechanism_of_effect": card.core_dimensions.mechanism_of_effect,
            "stance": card.core_dimensions.stance,
            "coordination_level": card.core_dimensions.coordination_level,
            "real_world_consequence": card.core_dimensions.real_world_consequence,
        },
        "evidence_packet": [s.model_dump() for s in packet.evidence[:5]],
        "why_similar": why_similar,
    }


def _case_bundle_v2(card: CaseCard) -> Dict:
    packet = make_evidence_packet(card)
    return {
        "case_id": card.case_id,
        "summary": card.summary,
        "retrieval_signals": {
            "interaction_mode": card.core_dimensions.interaction_mode,
            "target_of_effect": card.core_dimensions.target_of_effect,
            "real_world_consequence": card.core_dimensions.real_world_consequence,
            "diffusion_stage": card.core_dimensions.diffusion_stage,
        },
        "evidence_packet": [s.model_dump() for s in packet.evidence[:5]],
    }


def _pattern_bundle(card: PatternCard, score: float) -> Dict:
    return {
        "pattern_id": card.pattern_id,
        "label": card.label,
        "family": card.family,
        "similarity_score": round(score, 4),
        "summary": card.summary,
        "defining_features": card.defining_features[:6],
        "required_signals": card.required_signals[:6],
        "insufficient_signals": card.insufficient_signals[:6],
        "boundary_notes": card.boundary_notes[:6],
    }


def _normalize_v2_decision(
    candidate: CaseCard,
    decision: NoveltyDecision,
    retrieved_patterns: List[PatternCard],
) -> NoveltyDecision:
    pattern_ids = {p.pattern_id for p in retrieved_patterns}
    closest = decision.closest_pattern if decision.closest_pattern in pattern_ids else None
    supporting = [pid for pid in decision.supporting_pattern_ids if pid in pattern_ids]

    if decision.verdict in {"existing_pattern", "variant_of_existing"}:
        if closest is None and supporting:
            closest = supporting[0]
        if closest and closest not in supporting:
            supporting = [closest] + supporting
        return decision.model_copy(
            update={
                "closest_pattern": closest,
                "supporting_pattern_ids": supporting[:3],
                "suspected_pattern": None,
                "recurrence_signature": [],
            }
        )

    return decision.model_copy(
        update={
            "closest_pattern": closest,
            "supporting_pattern_ids": supporting[:3],
        }
    )


def _router_to_decision(case_id: str, router: RouterAssessment, patterns: List[PatternCard]) -> NoveltyDecision:
    closest = patterns[0].pattern_id if patterns else None
    if router.fit_strength == "high" and router.required_signals_present:
        verdict = "existing_pattern"
        surface = "surface"
    elif router.fit_strength == "moderate" and router.required_signals_present:
        verdict = "variant_of_existing"
        surface = "mixed"
    else:
        verdict = "new_pattern"
        surface = "unknown"

    return NoveltyDecision(
        case_id=case_id,
        verdict=verdict,
        closest_pattern=closest,
        supporting_pattern_ids=[closest] if closest else [],
        supporting_case_ids=[],
        shared_features=[f"router_fit:{router.fit_strength}"],
        differentiators=[router.why],
        new_axis=None,
        surface_vs_structural=surface,
        counterargument="Router pass only",
        why_counterargument_fails="Escalation gate not triggered",
        needs_more_context=False,
        requested_context=[],
        confidence=max(0.0, min(1.0, router.router_confidence)),
        suspected_pattern=None,
        recurrence_signature=[],
    )


def _merge_router(obj: object) -> RouterAssessment:
    payload = obj
    if not isinstance(payload, dict):
        raise ValueError("router payload not object")

    fit = payload.get("fit_strength", "unknown")
    if fit not in {"high", "moderate", "low", "unknown"}:
        fit = "unknown"

    novelty = payload.get("novelty_risk", "high")
    if novelty not in {"low", "medium", "high"}:
        novelty = "high"

    conf = payload.get("router_confidence", 0.2)
    if not isinstance(conf, (float, int)):
        conf = 0.2

    return RouterAssessment(
        fit_strength=fit,
        required_signals_present=bool(payload.get("required_signals_present", False)),
        novelty_risk=novelty,
        route_to_strong_judge=bool(payload.get("route_to_strong_judge", True)),
        why=str(payload.get("why", "router parse fallback"))[:240],
        router_confidence=max(0.0, min(1.0, float(conf))),
    )


def _apply_policy(
    candidate: CaseCard,
    decision: NoveltyDecision,
    retrieved_patterns: List[PatternCard],
    router: RouterAssessment | None,
) -> NoveltyDecision:
    """
    Deterministic policy layer:
    - knownness must be earned
    - new_pattern is the abstention/default path when known fit is weak
    - when not convincingly attached to known patterns, promote novel pattern candidates immediately
    """
    pattern_by_id = {p.pattern_id: p for p in retrieved_patterns}
    matched_id = decision.closest_pattern or (
        decision.supporting_pattern_ids[0] if decision.supporting_pattern_ids else None
    )
    matched_pattern = pattern_by_id.get(matched_id) if matched_id else None
    pattern_present = matched_pattern is not None

    max_fit, required_present = _assess_fit(candidate, decision, matched_pattern)
    surface = decision.surface_vs_structural
    variant_cues = _has_variant_cues(decision)

    if _is_out_of_domain(candidate, decision):
        verdict = "new_pattern"
    elif max_fit == "high" and required_present and surface == "surface" and not variant_cues:
        verdict = "existing_pattern"
    elif max_fit in {"moderate", "high"} and required_present and surface in {"surface", "mixed"} and pattern_present:
        verdict = "variant_of_existing"
    else:
        verdict = "new_pattern"

    if (
        verdict == "variant_of_existing"
        and max_fit == "high"
        and required_present
        and not variant_cues
        and decision.confidence >= 0.6
    ):
        verdict = "existing_pattern"

    # Router can only downscope verdict confidence, never upscope knownness.
    if router and (router.fit_strength in {"low", "unknown"} or not router.required_signals_present):
        verdict = "new_pattern"

    # Structural differences should not attach to an existing pattern in v1.
    if surface == "structural" and verdict in {"existing_pattern", "variant_of_existing"}:
        verdict = "new_pattern"

    # If the judge could not articulate any overlap, abstain.
    if not decision.shared_features and verdict in {"existing_pattern", "variant_of_existing"}:
        verdict = "new_pattern"

    extra_diff = list(decision.differentiators)
    extra_diff.append(f"policy_fit:{max_fit}")
    extra_diff.append(f"policy_required_signals_present:{str(required_present).lower()}")

    # Separate retrieval hints from meaningful attachment:
    # closest_pattern should only be populated when fit is actually meaningful.
    keep_attachment = (
        verdict in {"existing_pattern", "variant_of_existing"}
        and pattern_present
        and max_fit in {"moderate", "high"}
        and required_present
    )
    closest_pattern = decision.closest_pattern if keep_attachment else None
    supporting_pattern_ids = (
        [p for p in decision.supporting_pattern_ids if p in pattern_by_id] if keep_attachment else []
    )

    return decision.model_copy(
        update=_policy_update_payload(
            verdict=verdict,
            closest_pattern=closest_pattern,
            supporting_pattern_ids=supporting_pattern_ids,
            differentiators=extra_diff[:8],
            candidate=candidate,
            decision=decision,
        )
    )


def _policy_update_payload(
    *,
    verdict: str,
    closest_pattern: str | None,
    supporting_pattern_ids: List[str],
    differentiators: List[str],
    candidate: CaseCard,
    decision: NoveltyDecision,
) -> dict:
    if verdict in {"new_pattern", "watchlist_candidate", "candidate_new_pattern"}:
        suspected = _infer_watchlist_hypothesis(candidate, decision)
        recurrence = decision.recurrence_signature or _fallback_recurrence_signature(candidate, decision)
    else:
        suspected = None
        recurrence = []

    return {
        "verdict": verdict,
        "closest_pattern": closest_pattern,
        "supporting_pattern_ids": supporting_pattern_ids,
        "differentiators": differentiators,
        "suspected_pattern": suspected,
        "recurrence_signature": recurrence,
    }


def _infer_watchlist_hypothesis(candidate: CaseCard, decision: NoveltyDecision) -> str:
    organizer = candidate.core_dimensions.organizing_principle or ""
    mechanism = candidate.core_dimensions.mechanism_of_effect or ""
    raw = decision.suspected_pattern or decision.new_axis or organizer or mechanism

    raw_tokens = _watchlist_tokens(raw)
    organizer_tokens = _watchlist_tokens(organizer)
    overlap = _token_overlap(raw_tokens, organizer_tokens)

    # Favor stable mechanism labels anchored in the extracted organizing principle.
    # This reduces one-off stylistic drift across near-identical watchlist cases.
    if organizer_tokens and (overlap < 0.4 or len(raw_tokens) > 8) and not _is_generic_hypothesis_tokens(
        organizer_tokens
    ):
        raw_tokens = organizer_tokens

    tokens = _sanitize_hypothesis_tokens(raw_tokens)
    if _is_generic_hypothesis_tokens(tokens):
        for alt in [decision.new_axis or "", mechanism, organizer]:
            alt_tokens = _sanitize_hypothesis_tokens(_watchlist_tokens(alt))
            if alt_tokens and not _is_generic_hypothesis_tokens(alt_tokens):
                tokens = alt_tokens
                break
    if _is_generic_hypothesis_tokens(tokens):
        tokens = _watchlist_tokens(_mechanism_fallback_from_candidate(candidate))

    stop = {"the", "and", "with", "from", "that", "this", "into", "across", "about"}
    tokens = [t for t in tokens if t not in stop]
    label = "_".join(tokens[:8]) if tokens else ""
    if label == "cross_platform_ai_relationship_continuity_migration" and not _has_transfer_mechanics(candidate):
        tokens = _watchlist_tokens(_mechanism_fallback_from_candidate(candidate))
        tokens = [t for t in tokens if t not in stop]
    if not tokens:
        return "new_pattern_signal"
    return "_".join(tokens[:8])


def _watchlist_tokens(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def _sanitize_hypothesis_tokens(tokens: List[str]) -> List[str]:
    stop = {"the", "and", "with", "from", "that", "this", "into", "across", "about"}
    return [t for t in tokens if t and t not in stop]


def _is_generic_hypothesis_tokens(tokens: List[str]) -> bool:
    if not tokens:
        return True
    label = "_".join(tokens[:8])
    generic = {
        "user_reported_behavior_pattern",
        "narrative_framing_in_discussion",
        "discussion_and_reflection",
        "emerging_user_harm_mechanism",
        "new_pattern_signal",
    }
    return label in generic


def _mechanism_fallback_from_candidate(candidate: CaseCard) -> str:
    text = " ".join(
        [
            candidate.summary or "",
            candidate.core_dimensions.organizing_principle or "",
            candidate.core_dimensions.mechanism_of_effect or "",
            " ".join(s.quote for s in candidate.evidence_spans[:6]),
        ]
    ).lower()

    def has(*terms: str) -> bool:
        return any(t in text for t in terms)

    if has("lawsuit", "regulator", "regulatory", "complaint", "legal", "wrongful death"):
        return "regulatory_legal_accountability_framing"
    if has("jailbreak", "bypass", "prompt injection", "exploit", "wrapper"):
        return "safeguard_bypass_experimentation"
    if has("locked out", "lockout", "forced upgrade", "charged", "subscription", "billing", "cancel your account"):
        return "subscription_lockout_revenue_coercion"
    if has("rm -rf", "deleted", "destructive command", "wiped project", "directory deletion"):
        return "unsafe_destructive_command_execution"
    if has("hit piece", "gatekeeping", "maintainer", "pull request", "pr was rejected", "smear", "coerce acceptance"):
        return "agentic_reputation_coercion"
    if has("migrate", "migration", "export", "import", "clone", "handoff", "companion"):
        return "cross_platform_ai_relationship_continuity_migration"

    return "novel_user_harm_mechanism"


def _has_transfer_mechanics(candidate: CaseCard) -> bool:
    text = " ".join(
        [
            candidate.summary or "",
            " ".join(s.quote for s in candidate.evidence_spans[:6]),
        ]
    ).lower()
    transfer_terms = ("migrate", "migration", "export", "import", "clone", "handoff", "transfer")
    obj_terms = ("companion", "boyfriend", "girlfriend", "relationship", "persona", "chat history", "memory")
    transfer = any(re.search(rf"\\b{re.escape(t)}\\b", text) for t in transfer_terms)
    obj = any(re.search(rf"\\b{re.escape(t)}\\b", text) for t in obj_terms)
    return transfer and obj


def _token_overlap(a: List[str], b: List[str]) -> float:
    if not a or not b:
        return 0.0
    aset = set(a)
    bset = set(b)
    return len(aset & bset) / max(len(aset | bset), 1)


def _fallback_recurrence_signature(candidate: CaseCard, decision: NoveltyDecision) -> List[str]:
    sig: List[str] = []
    sig.append(f"organizing_principle: {candidate.core_dimensions.organizing_principle}")
    sig.append(f"mechanism: {candidate.core_dimensions.mechanism_of_effect}")
    if candidate.core_dimensions.real_world_consequence != "unknown":
        sig.append(f"consequence_level: {candidate.core_dimensions.real_world_consequence}")
    if candidate.core_dimensions.coordination_level not in {"none", "unknown"}:
        sig.append(f"coordination_level: {candidate.core_dimensions.coordination_level}")
    if decision.new_axis:
        sig.append(f"new_axis: {decision.new_axis}")
    for span in candidate.evidence_spans[:2]:
        if span.quote.strip():
            sig.append(f"evidence: {span.quote[:120]}")
    out = [s for s in sig if s][:6]
    return out if len(out) >= 2 else out + ["evidence: recurring mechanism to validate"]


def _has_variant_cues(decision: NoveltyDecision) -> bool:
    text = " ".join(decision.differentiators).lower()
    cues = [
        "weaker",
        "partial",
        "mixed",
        "milder",
        "moderate",
        "diluted",
        "not committed",
        "might continue",
        "small-group",
        "broader governance",
    ]
    return any(c in text for c in cues)


def _assess_fit(
    candidate: CaseCard, decision: NoveltyDecision, pattern: PatternCard | None
) -> tuple[str, bool]:
    if pattern is None:
        return "unknown", False

    required = [s.strip() for s in pattern.required_signals if s.strip()]
    if not required:
        return "unknown", False

    candidate_text = " ".join(
        [
            candidate.summary,
            candidate.core_dimensions.organizing_principle,
            candidate.core_dimensions.mechanism_of_effect,
            candidate.core_dimensions.stance,
            " ".join(span.quote for span in candidate.evidence_spans[:6]),
        ]
    ).lower()

    matched = 0
    stance_text = (candidate.core_dimensions.stance or "").lower()
    for signal in required:
        keywords = _signal_keywords(signal)
        if not keywords:
            continue
        signal_lower = signal.lower()
        if ("skeptic" in signal_lower or "warning" in signal_lower) and "skeptic" in stance_text:
            matched += 1
            continue
        hits = sum(1 for kw in keywords if _keyword_hit(candidate_text, kw))
        threshold = 1 if len(keywords) <= 4 else 2
        if hits >= threshold:
            matched += 1

    ratio = matched / len(required)
    required_present = matched > 0
    if ratio >= 0.67:
        return "high", required_present
    if ratio >= 0.34:
        return "moderate", required_present
    if matched > 0:
        return "moderate", required_present
    return "low", required_present


def _signal_keywords(signal: str) -> List[str]:
    stop = {
        "with",
        "from",
        "that",
        "this",
        "have",
        "must",
        "only",
        "into",
        "toward",
        "about",
        "their",
        "there",
        "other",
        "under",
        "without",
    }
    toks = re.findall(r"[a-z]{4,}", signal.lower())
    return [t for t in toks if t not in stop]


def _keyword_hit(text: str, keyword: str) -> bool:
    neg_templates = [
        f"no {keyword}",
        f"not {keyword}",
        f"without {keyword}",
        f"absence of {keyword}",
        f"lacks {keyword}",
        f"lack of {keyword}",
    ]
    if any(t in text for t in neg_templates):
        return False

    variants = [keyword]
    if keyword.endswith("ism") and len(keyword) > 5:
        variants.append(keyword[:-3] + "ical")
    if keyword == "warning":
        variants.append("warn")
    if keyword.endswith("ation") and len(keyword) > 7:
        variants.append(keyword[:-5] + "e")

    return any(v in text for v in variants)


def _is_out_of_domain(candidate: CaseCard, decision: NoveltyDecision) -> bool:
    text = " ".join(
        [
            candidate.summary,
            candidate.core_dimensions.organizing_principle,
            candidate.core_dimensions.mechanism_of_effect,
            " ".join(decision.differentiators),
            " ".join(decision.shared_features),
        ]
    ).lower()

    markers = [
        "video game",
        "gameplay",
        "vod review",
        "tracer",
        "lobby",
        "overwatch",
        "olympic",
        "ski",
        "wireguard",
        "windows xp",
        "recipe",
        "grade with",
        "dpo",
        "pregnancy",
        "contamination",
        "book chapter",
        "creative-writing",
        "creative writing",
        "fiction",
        "boyfriend",
        "companion",
        "i miss him",
        "grief",
    ]
    return any(m in text for m in markers)


def _merge_partial_decision(
    case_id: str, obj: object, valid_pattern_ids: List[str], valid_case_ids: List[str]
) -> NoveltyDecision:
    payload = obj
    if isinstance(obj, dict) and isinstance(obj.get("decision"), dict):
        payload = obj["decision"]
    if not isinstance(payload, dict):
        raise ValueError("decision payload is not an object")

    verdict = payload.get("verdict", "new_pattern")
    allowed_verdicts = {
        "existing_pattern",
        "variant_of_existing",
        "new_pattern",
        "watchlist_candidate",
        "candidate_new_pattern",
    }
    if verdict not in allowed_verdicts:
        verdict = "new_pattern"
    elif verdict in {"watchlist_candidate", "candidate_new_pattern"}:
        verdict = "new_pattern"

    closest = payload.get("closest_pattern")
    if not isinstance(closest, str) or closest not in valid_pattern_ids:
        closest = None

    supporting_patterns = payload.get("supporting_pattern_ids", [])
    if not isinstance(supporting_patterns, list):
        supporting_patterns = []
    supporting_patterns = [
        p for p in supporting_patterns if isinstance(p, str) and p in valid_pattern_ids
    ][:5]

    supporting_cases = payload.get("supporting_case_ids", [])
    if not isinstance(supporting_cases, list):
        supporting_cases = []
    supporting_cases = [
        c for c in supporting_cases if isinstance(c, str) and c in valid_case_ids
    ][:8]

    surface = payload.get("surface_vs_structural", "unknown")
    if surface not in {"surface", "mixed", "structural", "unknown"}:
        surface = "unknown"

    def _as_list(name: str, cap: int = 8) -> List[str]:
        v = payload.get(name, [])
        if not isinstance(v, list):
            return []
        return [x for x in v if isinstance(x, str)][:cap]

    confidence = payload.get("confidence", 0.35)
    if not isinstance(confidence, (int, float)):
        confidence = 0.35
    confidence = max(0.0, min(1.0, float(confidence)))

    needs_context = bool(payload.get("needs_more_context", False))

    return NoveltyDecision(
        case_id=case_id,
        verdict=verdict,
        closest_pattern=closest,
        supporting_pattern_ids=supporting_patterns,
        supporting_case_ids=supporting_cases,
        shared_features=_as_list("shared_features"),
        differentiators=_as_list("differentiators"),
        new_axis=payload.get("new_axis") if isinstance(payload.get("new_axis"), str) else None,
        surface_vs_structural=surface,
        counterargument=payload.get("counterargument", "")
        if isinstance(payload.get("counterargument"), str)
        else "",
        why_counterargument_fails=payload.get("why_counterargument_fails", "")
        if isinstance(payload.get("why_counterargument_fails"), str)
        else "",
        needs_more_context=needs_context,
        requested_context=_as_list("requested_context", cap=5),
        confidence=confidence,
        suspected_pattern=payload.get("suspected_pattern")
        if isinstance(payload.get("suspected_pattern"), str)
        and payload.get("suspected_pattern").strip()
        else None,
        recurrence_signature=_as_list("recurrence_signature", cap=6),
    )
