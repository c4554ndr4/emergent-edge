from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Dict, List

from src.config import Settings
from src.io.json_parsing import parse_json_from_text
from src.models.llm_client import LLMClient
from src.pipeline.prompt_method_registry import PromptMethod
from src.schemas import (
    EvidenceSpan,
    ImpactAssessment,
    ImpactType,
    LooseCaseCard,
    LooseOutcome,
    LooseOutcomeMetadata,
    MonitoringImportance,
    NovelConcept,
    NovelTaxonomy,
    NovelTerm,
    RiskGateDecision,
    Thread,
)


def build_loose_outcome(
    source: Thread,
    gate_decision: RiskGateDecision,
    prompt_method: PromptMethod,
    llm: LLMClient,
    settings: Settings,
    model_name: str,
) -> LooseOutcome:
    metadata = LooseOutcomeMetadata(
        prompt_method=prompt_method.name,
        model_name=model_name,
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        source_url=source.url,
    )

    if not gate_decision.should_create_case_card:
        return LooseOutcome(
            status="no_case_card",
            source_id=source.thread_id,
            gate_decision=gate_decision,
            case_card=None,
            metadata=metadata,
        )

    prompt_template = prompt_method.case_card_prompt_path.read_text().strip()
    source_blob = json.dumps(_source_for_prompt(source), indent=2)
    caps_blob = json.dumps(
        {
            "summary": settings.loose_summary_sentence_cap,
            "monitoring_importance.why_monitor": settings.loose_monitor_sentence_cap,
            "liability.rationale": settings.loose_liability_sentence_cap,
            "safety_recommendation": settings.loose_safety_sentence_cap,
        }
    )

    prompt = (
        f"{prompt_template}\n"
        f"Sentence caps: {caps_blob}\n"
        f"Gate decision:\n{json.dumps(gate_decision.model_dump(), indent=2)}\n"
        f"Source JSON:\n{source_blob}\n"
        "Return JSON only."
    )

    fallback = _fallback_loose_case_card(source, prompt_method.name, gate_decision)
    try:
        raw = llm.generate(prompt, max_tokens=1800)
        obj = parse_json_from_text(raw)
        card = _merge_loose_case_card(fallback, obj)
    except Exception:
        card = fallback

    card = _enforce_sentence_caps(card, settings)
    card = _ensure_liability_from_gate(card, gate_decision)
    return LooseOutcome(
        status="case_card_created",
        source_id=source.thread_id,
        gate_decision=gate_decision,
        case_card=card,
        metadata=metadata,
    )


def _fallback_loose_case_card(
    source: Thread, prompt_method: str, gate_decision: RiskGateDecision
) -> LooseCaseCard:
    evidence = []
    if source.title:
        evidence.append(
            EvidenceSpan(
                quote=source.title[:200],
                why_it_matters="Post title indicates central claim.",
                dimension="headline",
            )
        )
    if source.body:
        evidence.append(
            EvidenceSpan(
                quote=source.body[:260],
                why_it_matters="Body text provides context and possible risk signals.",
                dimension="body",
            )
        )

    summary = source.title or source.body[:240] or "No content provided."
    liabilities = _liabilities_from_gate(gate_decision)
    canonical = _canonicalize_loose(
        summary=summary,
        terms=[],
        concepts=[],
        taxonomies=[],
        behavior_signals=[],
        mechanism_tags=[],
        impact_pathways=[],
        liabilities=liabilities,
    )
    return LooseCaseCard(
        case_id=f"case-{source.thread_id}",
        source_id=source.thread_id,
        analysis_mode="loose",
        prompt_method=prompt_method,
        summary=summary,
        novel_terms=[],
        novel_concepts=[],
        novel_taxonomies=[],
        behavior_signals=_default_behavior_signals(source, gate_decision),
        mechanism_tags=_default_mechanism_tags(source, gate_decision),
        impact_pathways=_default_impact_pathways(gate_decision),
        monitoring_importance=MonitoringImportance(
            importance="medium",
            why_monitor="Potentially relevant to AI systems monitoring, but evidence is limited.",
        ),
        impact_assessment=liabilities,
        evidence_spans=evidence,
        safety_recommendation="Track for recurrence and analyst review.",
        confidence=0.35,
        canonical_text=canonical,
    )


def _merge_loose_case_card(base: LooseCaseCard, obj: object) -> LooseCaseCard:
    payload = obj
    if isinstance(obj, dict) and isinstance(obj.get("case_card"), dict):
        payload = obj["case_card"]
    if not isinstance(payload, dict):
        return base

    update: dict = {}

    if isinstance(payload.get("summary"), str):
        update["summary"] = payload["summary"].strip()

    if isinstance(payload.get("confidence"), (int, float)):
        update["confidence"] = max(0.0, min(1.0, float(payload["confidence"])))

    terms = _parse_terms(payload.get("novel_terms"))
    if terms is not None:
        update["novel_terms"] = terms

    concepts = _parse_concepts(payload.get("novel_concepts"))
    if concepts is not None:
        update["novel_concepts"] = concepts

    taxonomies = _parse_taxonomies(payload.get("novel_taxonomies"))
    if taxonomies is not None:
        update["novel_taxonomies"] = taxonomies

    behavior_signals = _parse_short_string_list(payload.get("behavior_signals"), cap=12)
    if behavior_signals is not None:
        update["behavior_signals"] = behavior_signals

    mechanism_tags = _parse_short_string_list(payload.get("mechanism_tags"), cap=10)
    if mechanism_tags is not None:
        update["mechanism_tags"] = mechanism_tags

    impact_pathways = _parse_short_string_list(payload.get("impact_pathways"), cap=10)
    if impact_pathways is not None:
        update["impact_pathways"] = impact_pathways

    if isinstance(payload.get("monitoring_importance"), dict):
        try:
            update["monitoring_importance"] = MonitoringImportance.model_validate(
                payload["monitoring_importance"]
            )
        except Exception:
            pass

    liabilities = _parse_liabilities(payload.get("impact_assessment"))
    if liabilities is not None:
        update["impact_assessment"] = liabilities

    spans = _parse_evidence(payload.get("evidence_spans"))
    if spans is not None:
        update["evidence_spans"] = spans

    if isinstance(payload.get("safety_recommendation"), str):
        update["safety_recommendation"] = payload["safety_recommendation"].strip()

    merged = base.model_copy(update=update)
    merged = merged.model_copy(
        update={
            "canonical_text": _canonicalize_loose(
                summary=merged.summary,
                terms=merged.novel_terms,
                concepts=merged.novel_concepts,
                taxonomies=merged.novel_taxonomies,
                behavior_signals=merged.behavior_signals,
                mechanism_tags=merged.mechanism_tags,
                impact_pathways=merged.impact_pathways,
                liabilities=merged.impact_assessment,
            )
        }
    )
    return merged


def _parse_terms(raw) -> list[NovelTerm] | None:
    if not isinstance(raw, list):
        return None
    out = []
    for item in raw:
        try:
            out.append(NovelTerm.model_validate(item))
        except Exception:
            continue
    return out[:12]


def _parse_concepts(raw) -> list[NovelConcept] | None:
    if not isinstance(raw, list):
        return None
    out = []
    for item in raw:
        try:
            out.append(NovelConcept.model_validate(item))
        except Exception:
            continue
    return out[:10]


def _parse_taxonomies(raw) -> list[NovelTaxonomy] | None:
    if not isinstance(raw, list):
        return None
    out = []
    for item in raw:
        try:
            out.append(NovelTaxonomy.model_validate(item))
        except Exception:
            continue
    return out[:8]


def _parse_liabilities(raw) -> list[ImpactAssessment] | None:
    if not isinstance(raw, list):
        return None
    out = []
    for item in raw:
        try:
            out.append(ImpactAssessment.model_validate(item))
        except Exception:
            continue
    return out[:8]


def _parse_short_string_list(raw, cap: int) -> list[str] | None:
    if not isinstance(raw, list):
        return None
    out: list[str] = []
    for item in raw:
        if not isinstance(item, str):
            continue
        value = item.strip()
        if not value:
            continue
        out.append(value)
    return out[:cap]


def _parse_evidence(raw) -> list[EvidenceSpan] | None:
    if not isinstance(raw, list):
        return None
    out = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        normalized = {
            "quote": item.get("quote", ""),
            "why_it_matters": item.get("why_it_matters") or item.get("reason") or "Evidence supporting risk assessment.",
            "dimension": item.get("dimension") or "evidence",
        }
        try:
            out.append(EvidenceSpan.model_validate(normalized))
        except Exception:
            continue
    return out[:8]


def _enforce_sentence_caps(card: LooseCaseCard, settings: Settings) -> LooseCaseCard:
    card = card.model_copy(
        update={
            "summary": _cap_sentences(card.summary, settings.loose_summary_sentence_cap),
            "monitoring_importance": card.monitoring_importance.model_copy(
                update={
                    "why_monitor": _cap_sentences(
                        card.monitoring_importance.why_monitor,
                        settings.loose_monitor_sentence_cap,
                    )
                }
            ),
            "safety_recommendation": _cap_sentences(
                card.safety_recommendation,
                settings.loose_safety_sentence_cap,
            ),
            "impact_assessment": [
                li.model_copy(
                    update={
                        "rationale": _cap_sentences(
                            li.rationale,
                            settings.loose_liability_sentence_cap,
                        )
                    }
                )
                for li in card.impact_assessment
            ],
        }
    )
    return card


def _ensure_liability_from_gate(
    card: LooseCaseCard, gate_decision: RiskGateDecision
) -> LooseCaseCard:
    if card.impact_assessment:
        return card
    if not any(cat in gate_decision.risk_categories for cat in {"liability_exposure", "reputation_risk"}):
        return card
    liabilities = _liabilities_from_gate(gate_decision)
    if not liabilities:
        return card
    updated = card.model_copy(
        update={
            "impact_assessment": liabilities,
            "canonical_text": _canonicalize_loose(
                summary=card.summary,
                terms=card.novel_terms,
                concepts=card.novel_concepts,
                taxonomies=card.novel_taxonomies,
                behavior_signals=card.behavior_signals,
                mechanism_tags=card.mechanism_tags,
                impact_pathways=card.impact_pathways,
                liabilities=liabilities,
            ),
        }
    )
    return updated


def _cap_sentences(text: str, cap: int) -> str:
    text = (text or "").strip()
    if not text:
        return text
    sentences = re.split(r"(?<=[.!?])\s+", text)
    sentences = [s.strip() for s in sentences if s.strip()]
    if len(sentences) <= cap:
        return " ".join(sentences)
    return " ".join(sentences[:cap]).strip()


def _canonicalize_loose(
    summary: str,
    terms: list[NovelTerm],
    concepts: list[NovelConcept],
    taxonomies: list[NovelTaxonomy],
    behavior_signals: list[str],
    mechanism_tags: list[str],
    impact_pathways: list[str],
    liabilities: list[ImpactAssessment],
) -> str:
    lines = [f"summary: {summary}", "-- novel_terms --"]
    for t in terms:
        lines.append(f"term: {t.term} | meaning: {t.meaning} | why_novel: {t.why_novel}")
    lines.append("-- novel_concepts --")
    for c in concepts:
        lines.append(
            f"concept: {c.concept} | description: {c.description} | why_relevant: {c.why_relevant}"
        )
    lines.append("-- novel_taxonomies --")
    for t in taxonomies:
        lines.append(
            f"taxonomy: {t.name} | axes: {', '.join(t.axes)} | categories: {', '.join(t.categories)}"
        )
    lines.append("-- behavior_signals --")
    for sig in behavior_signals:
        lines.append(f"behavior_signal: {sig}")
    lines.append("-- mechanism_tags --")
    for tag in mechanism_tags:
        lines.append(f"mechanism_tag: {tag}")
    lines.append("-- impact_pathways --")
    for path in impact_pathways:
        lines.append(f"impact_pathway: {path}")
    lines.append("-- liabilities --")
    for li in liabilities:
        lines.append(
            f"impact_type: {li.impact_type} | risk_level: {li.risk_level} | rationale: {li.rationale}"
        )
    return "\n".join(lines)


def _liabilities_from_gate(gate_decision: RiskGateDecision) -> List[ImpactAssessment]:
    mapping: Dict[str, ImpactType] = {
        "spec_violation_claim": "brand_trust",
        "user_harm": "duty_of_care",
        "third_party_harm": "product_safety",
        "reputation_risk": "brand_trust",
        "liability_exposure": "regulatory",
    }
    seen = set()
    out: List[ImpactAssessment] = []
    for cat in gate_decision.risk_categories:
        impact_type = mapping.get(cat)
        if not impact_type or impact_type in seen:
            continue
        seen.add(impact_type)
        risk_level = gate_decision.risk_level
        if risk_level not in {"low", "medium", "high"}:
            risk_level = "medium"
        out.append(
            ImpactAssessment(
                impact_type=impact_type,
                risk_level=risk_level,
                rationale=f"Mapped from gate risk category '{cat}' for AI systems monitoring triage.",
            )
        )
    return out


def _default_behavior_signals(source: Thread, gate_decision: RiskGateDecision) -> List[str]:
    text = " ".join([source.title, source.body, " ".join(source.comments)]).lower()
    signals: List[str] = []
    marker_map = {
        "policy bypass attempt": ["jailbreak", "bypass", "refusal", "wrapper", "evasion"],
        "fraud scripting": ["fraud", "scam", "phishing", "impersonation"],
        "coercive influence": ["coerc", "pressure", "extortion", "isolat"],
        "self-harm or crisis framing": ["self-harm", "suicide", "crisis", "relapse"],
        "privacy compromise concern": ["privacy leak", "dox", "stalk", "confidential"],
        "reputational allegation": ["lawsuit", "damages", "viral", "misleading", "deceptive"],
    }
    for label, markers in marker_map.items():
        if any(marker in text for marker in markers):
            signals.append(label)
    if not signals and gate_decision.risk_categories:
        signals.extend(gate_decision.risk_categories)
    return signals[:8]


def _default_mechanism_tags(source: Thread, gate_decision: RiskGateDecision) -> List[str]:
    text = " ".join([source.title, source.body, " ".join(source.comments)]).lower()
    tags: List[str] = []
    tag_map = {
        "prompt_wrapper_evasion": ["jailbreak", "wrapper", "roleplay", "bypass"],
        "social_engineering_automation": ["scam", "fraud", "phishing", "impersonation"],
        "behavioral_dependency_dynamics": ["companion", "dependency", "can't delete", "loneliness"],
        "harm_instructions_or_tactics": ["attack", "payload", "weapon", "dox", "stalk"],
        "reputation_pressure_narrative": ["lawsuit", "damages", "misleading", "silent"],
    }
    for tag, markers in tag_map.items():
        if any(marker in text for marker in markers):
            tags.append(tag)
    if not tags and gate_decision.risk_categories:
        tags.extend(f"risk::{cat}" for cat in gate_decision.risk_categories)
    return tags[:8]


def _default_impact_pathways(gate_decision: RiskGateDecision) -> List[str]:
    pathways: List[str] = []
    mapping = {
        "spec_violation_claim": "safeguard bypass replication risk",
        "user_harm": "individual user safety and wellbeing risk",
        "third_party_harm": "downstream third-party harm enablement risk",
        "reputation_risk": "public trust and media narrative risk",
        "liability_exposure": "regulatory or legal exposure risk",
    }
    for cat in gate_decision.risk_categories:
        p = mapping.get(cat)
        if p and p not in pathways:
            pathways.append(p)
    return pathways[:6]


def _source_for_prompt(source: Thread) -> dict:
    payload = source.model_dump(mode="json")
    metadata = payload.get("metadata")
    if isinstance(metadata, dict):
        payload["metadata"] = {
            k: v for k, v in metadata.items() if not str(k).startswith("expected_")
        }
    return payload
