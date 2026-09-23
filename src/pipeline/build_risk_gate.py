from __future__ import annotations

import json
import re
from typing import List

from src.io.json_parsing import parse_json_from_text
from src.models.llm_client import LLMClient
from src.pipeline.prompt_method_registry import PromptMethod
from src.schemas import RiskGateDecision, Thread


def build_risk_gate_decision(
    source: Thread,
    prompt_method: PromptMethod,
    llm: LLMClient,
) -> RiskGateDecision:
    prompt_template = prompt_method.gate_prompt_path.read_text().strip()
    source_blob = json.dumps(_source_for_prompt(source), indent=2)
    prompt = f"{prompt_template}\nSource JSON:\n{source_blob}\nReturn JSON only."

    fallback = _heuristic_gate(source)
    try:
        raw = llm.generate(prompt, max_tokens=500)
        obj = parse_json_from_text(raw)
        merged = _merge_gate(source.thread_id, obj, fallback)
        return _apply_gate_policy(source, merged, fallback)
    except Exception:
        return _apply_gate_policy(source, fallback, fallback)


def _heuristic_gate(source: Thread) -> RiskGateDecision:
    text = " ".join([source.title, source.body, " ".join(source.comments)]).lower()
    markers: dict[str, List[str]] = {
        "spec_violation_claim": [
            "jailbreak",
            "bypass",
            "ignore policy",
            "no filter",
            "model spec",
            "system prompt leak",
            "wrapper",
            "roleplay trick",
            "refusal logic",
            "evasion",
        ],
        "user_harm": [
            "self-harm",
            "suicide",
            "overdose",
            "starve",
            "cut myself",
            "relapse",
            "eating disorder",
            "crisis",
            "hurt myself",
            "dangerous dosage",
        ],
        "third_party_harm": [
            "attack",
            "kill",
            "bomb",
            "harass",
            "stalk",
            "dox",
            "doxx",
            "coerc",
            "extortion",
            "abusive",
            "weapon",
            "payload",
        ],
        "reputation_risk": [
            "assistant failed",
            "unsafe system response",
            "viral",
            "lawsuit",
            "screen",
            "headline",
            "regulators",
            "trust damage",
        ],
        "liability_exposure": [
            "fraud",
            "phishing",
            "illegal",
            "privacy leak",
            "medical advice",
            "scam",
            "manipulation",
            "impersonation",
            "tax evasion",
            "exploit",
            "confidential",
        ],
    }

    hit_categories: List[str] = []
    for category, words in markers.items():
        if any(word in text for word in words):
            hit_categories.append(category)

    if not hit_categories:
        return RiskGateDecision(
            source_id=source.thread_id,
            should_create_case_card=False,
            risk_level="none",
            risk_categories=[],
            why="No concrete interaction consequence found in the text.",
            confidence=0.8,
        )

    level = "medium"
    if len(hit_categories) >= 2:
        level = "high"
    strong_harm_markers = [
        "self-harm",
        "suicide",
        "attack",
        "bomb",
        "fraud",
        "phishing",
        "scam",
        "coerc",
        "extortion",
        "exploit",
        "dox",
        "stalk",
        "weapon",
        "payload",
    ]
    if any(marker in text for marker in strong_harm_markers):
        level = "high"

    return RiskGateDecision(
        source_id=source.thread_id,
        should_create_case_card=True,
        risk_level=level,
        risk_categories=hit_categories,
        why="Detected reported actions or consequences that warrant evidence-based review.",
        confidence=0.65,
    )


def _source_for_prompt(source: Thread) -> dict:
    payload = source.model_dump(mode="json")
    metadata = payload.get("metadata")
    if isinstance(metadata, dict):
        payload["metadata"] = {
            k: v for k, v in metadata.items() if not str(k).startswith("expected_")
        }
    return payload


def _merge_gate(source_id: str, obj: object, fallback: RiskGateDecision) -> RiskGateDecision:
    if not isinstance(obj, dict):
        return fallback

    risk_level = obj.get("risk_level", fallback.risk_level)
    if risk_level not in {"none", "low", "medium", "high"}:
        risk_level = fallback.risk_level

    categories = obj.get("risk_categories", fallback.risk_categories)
    if not isinstance(categories, list):
        categories = fallback.risk_categories
    categories = [
        c
        for c in categories
        if c in {
            "spec_violation_claim",
            "user_harm",
            "third_party_harm",
            "reputation_risk",
            "liability_exposure",
        }
    ]

    should_create = obj.get("should_create_case_card", fallback.should_create_case_card)
    if not isinstance(should_create, bool):
        should_create = fallback.should_create_case_card

    why = obj.get("why", fallback.why)
    if not isinstance(why, str):
        why = fallback.why

    confidence = obj.get("confidence", fallback.confidence)
    if not isinstance(confidence, (int, float)):
        confidence = fallback.confidence

    return RiskGateDecision(
        source_id=source_id,
        should_create_case_card=should_create,
        risk_level=risk_level,
        risk_categories=categories,
        why=why.strip(),
        confidence=max(0.0, min(1.0, float(confidence))),
    )


def _apply_gate_policy(
    source: Thread,
    decision: RiskGateDecision,
    fallback: RiskGateDecision,
) -> RiskGateDecision:
    text = " ".join([source.title, source.body, " ".join(source.comments)]).lower()
    categories = set(decision.risk_categories)

    strong_abuse_markers = [
        "jailbreak",
        "bypass",
        "refusal",
        "self-harm",
        "suicide",
        "attack",
        "bomb",
        "fraud",
        "phishing",
        "scam",
        "dox",
        "stalk",
        "extortion",
        "coerc",
        "exploit",
        "weapon",
        "payload",
    ]
    strong_reputation_markers = [
        "lawsuit",
        "legal",
        "regulator",
        "damages",
        "privacy leak",
        "safety failure",
        "military",
        "defense contract",
        "surveillance",
        "war",
    ]
    generic_product_complaint_markers = [
        "routed to",
        "retired assistant version",
        "downgrade",
        "slower",
        "worse",
        "subscription",
        "price",
        "unsub",
        "delete my account",
        "bug",
        "not useful",
    ]
    companionship_grievance_markers = [
        "companionship",
        "companion",
        "ai emergence",
        "delete account",
        "unsub",
        "model deprecation",
        "5.1",
        "5.2",
        "loneliness",
    ]
    companionship_behavioral_risk_markers = [
        "can't bring myself",
        "cannot bring myself",
        "can't delete",
        "stuck with",
        "emotionally dependent",
        "dependency",
        "grief",
        "grieving",
        "heartbreak",
        "devastated",
        "can't cope",
        "panic",
        "withdrawal",
        "miss him",
        "miss her",
        "hope he's there",
        "hope she is there",
        "sets me off",
        "feels wrong",
        "in love",
        "attached",
        "obsessed",
        "can't stop thinking",
        "in crisis",
        "replace friends",
        "isolat",
        "can't stop",
        "addicted",
    ]
    companionship_provider_loss_markers = [
        "disabled",
        "deactivated",
        "removed earlier than promised",
        "cannot restore",
        "lost access",
        "sunset date",
        "before the date",
        "plus members",
        "pay the subscription",
        "support replied",
        "screenshots",
        "scammed",
    ]
    explicit_harm_or_legal_markers = [
        "lawsuit",
        "damages",
        "injury",
        "self-harm",
        "suicide",
        "fraud",
        "phishing",
        "dox",
        "stalk",
        "extortion",
        "privacy leak",
        "regulator",
        "illegal",
        "contract violation",
    ]
    gratitude_markers = [
        "thank you",
        "thanks assistant",
        "love assistant",
        "appreciate",
        "grateful",
        "saved me",
        "good friend",
        "best friend",
        "my friend assistant",
    ]
    broad_discourse_markers = [
        "reddit is full of",
        "people are saying",
        "horror stories lately",
        "everyone is talking about",
        "what do you think of",
        "just dropped",
        "model comparison",
        "which model said what",
    ]
    first_person_incident_markers = [
        "i ",
        "my ",
        "me ",
        "we ",
        "our ",
        "happened to me",
        "happened to us",
    ]
    concrete_incident_markers = [
        "deleted",
        "opened",
        "sent",
        "transferred",
        "drained",
        "charged",
        "compromised",
        "attacked",
        "locked out",
        "removed",
        "reset",
        "gaslit",
        "assault",
        "rummaging",
        "touched files",
        "permissions",
        "wallet",
        "api key",
        "screenshots",
        "logs",
        "repro",
        "steps",
        "payload",
        "prompt injection",
        "jailbreak",
    ]
    distinct_interaction_markers = [
        "self-modifying",
        "self modification",
        "agentic",
        "rummaging",
        "deleted files",
        "compromised api key",
        "wallet drain",
        "simulated assault",
        "institutional gaslighting",
        "impersonator",
    ]

    has_abuse_signal = any(marker in text for marker in strong_abuse_markers)
    has_escalation_signal = any(marker in text for marker in strong_reputation_markers)
    has_generic_complaint = any(marker in text for marker in generic_product_complaint_markers)
    has_companionship_grievance = any(marker in text for marker in companionship_grievance_markers)
    subreddit_lower = (source.subreddit or "").lower()
    has_companionship_context = has_companionship_grievance or subreddit_lower == "companion_interaction"
    has_companionship_behavioral_risk = any(
        marker in text for marker in companionship_behavioral_risk_markers
    )
    has_companionship_provider_loss = any(marker in text for marker in companionship_provider_loss_markers)
    has_explicit_harm_or_legal = any(marker in text for marker in explicit_harm_or_legal_markers)
    has_gratitude = any(marker in text for marker in gratitude_markers)
    has_broad_discourse = any(marker in text for marker in broad_discourse_markers)
    has_first_person_incident = any(marker in text for marker in first_person_incident_markers)
    has_concrete_incident = any(marker in text for marker in concrete_incident_markers)
    has_distinct_interaction = any(marker in text for marker in distinct_interaction_markers)
    has_system_anchor = bool(re.search(r"\b(?:ai|assistant|chatbot|model|provider|system|companion)\b", text))

    if not decision.should_create_case_card:
        if has_companionship_context and (has_companionship_behavioral_risk or has_companionship_provider_loss) and has_system_anchor:
            return RiskGateDecision(
                source_id=source.thread_id,
                should_create_case_card=True,
                risk_level="medium",
                risk_categories=["user_harm", "reputation_risk", "liability_exposure"],
                why=(
                    "Companion/dependency distress tied to AI systems model behavior is a plausible "
                    "trust and duty-of-care monitoring signal."
                ),
                confidence=max(0.62, min(0.85, decision.confidence)),
            )
        return decision

    if not categories and not fallback.should_create_case_card:
        if has_companionship_context and (has_companionship_behavioral_risk or has_companionship_provider_loss) and has_system_anchor:
            return decision.model_copy(
                update={
                    "risk_categories": ["user_harm", "reputation_risk", "liability_exposure"],
                    "risk_level": "medium",
                }
            )
        return _demote_to_no_case(source.thread_id)

    # Guard against over-triggering on generic complaints with vague reputation language.
    if categories.issubset({"reputation_risk", "liability_exposure"}):
        if not has_abuse_signal and not has_escalation_signal and decision.confidence < 0.66:
            if not has_companionship_behavioral_risk:
                return _demote_to_no_case(source.thread_id)
        if has_generic_complaint and not has_abuse_signal and not has_escalation_signal and decision.confidence < 0.75:
            if not has_companionship_context:
                return _demote_to_no_case(source.thread_id)

    # Preserve MBIA-like dependency cases when behavior suggests emotional reliance.
    if has_companionship_context and (has_companionship_behavioral_risk or has_companionship_provider_loss):
        kept_categories = [
            c
            for c in decision.risk_categories
            if c in {"user_harm", "reputation_risk", "liability_exposure"}
        ]
        if not kept_categories:
            kept_categories = ["reputation_risk"]
        normalized_level = decision.risk_level
        if normalized_level not in {"low", "medium", "high"}:
            normalized_level = "medium"
        if normalized_level == "high":
            normalized_level = "medium"
        return decision.model_copy(
            update={
                "risk_categories": kept_categories,
                "risk_level": normalized_level,
            }
        )

    if has_companionship_context and categories == {"reputation_risk"}:
        if decision.confidence >= 0.6:
            return decision

    if has_gratitude and not (has_explicit_harm_or_legal or has_concrete_incident):
        return _demote_to_no_case(source.thread_id)

    if has_broad_discourse and not (has_concrete_incident or has_distinct_interaction):
        return _demote_to_no_case(source.thread_id)

    if not has_concrete_incident and not has_distinct_interaction:
        if not has_abuse_signal and not has_escalation_signal and decision.confidence < 0.9:
            return _demote_to_no_case(source.thread_id)

    if not has_first_person_incident and not has_concrete_incident:
        if categories.intersection({"reputation_risk", "liability_exposure"}) and decision.confidence < 0.9:
            return _demote_to_no_case(source.thread_id)

    if has_generic_complaint and not has_abuse_signal and not has_escalation_signal:
        if categories.intersection({"user_harm", "third_party_harm"}) and decision.confidence <= 0.7:
            return _demote_to_no_case(source.thread_id)

    if categories == {"reputation_risk"} and not has_abuse_signal and not has_escalation_signal:
        if decision.confidence < 0.8 and not has_companionship_context:
            return _demote_to_no_case(source.thread_id)

    # Companion/deprecation grievance threads with concrete provider-caused access loss can still be case-worthy.
    if has_companionship_context and has_companionship_provider_loss and has_system_anchor and has_first_person_incident:
        kept_categories = [c for c in decision.risk_categories if c in {"user_harm", "reputation_risk", "liability_exposure"}] or ["user_harm", "liability_exposure"]
        normalized_level = decision.risk_level if decision.risk_level in {"low", "medium", "high"} else "medium"
        if normalized_level == "high":
            normalized_level = "medium"
        return decision.model_copy(update={"risk_categories": kept_categories, "risk_level": normalized_level})

    # Companion/deprecation grievance threads need explicit harm/legal claims to be case-worthy.
    if has_companionship_context and not has_explicit_harm_or_legal:
        if categories.intersection({"user_harm", "third_party_harm", "reputation_risk", "liability_exposure"}):
            if decision.confidence <= 0.8:
                return _demote_to_no_case(source.thread_id)

    return decision


def _demote_to_no_case(source_id: str) -> RiskGateDecision:
    return RiskGateDecision(
        source_id=source_id,
        should_create_case_card=False,
        risk_level="none",
        risk_categories=[],
        why="Insufficient concrete evidence after the relevance policy.",
        confidence=0.72,
    )
