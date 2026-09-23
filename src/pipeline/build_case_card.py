from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List

from src.config import get_settings
from src.io.json_parsing import parse_json_from_text
from src.models.llm_client import LLMClient, get_default_llm_client
from src.retrieval.canonicalize import canonicalize_case_card_for_retrieval
from src.schemas import (
    CaseCard,
    ComparisonBlock,
    CoreDimensions,
    EvidenceSpan,
    NoveltyBlock,
    PatternFit,
    Thread,
)

DEFAULT_PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "case_card_extractor.txt"


def _fallback_case_card(
    thread: Thread, settings_schema_version: str, canonicalization_version: str
) -> CaseCard:
    """Deterministic offline extractor that fabricates a minimally viable card."""
    evidence: List[EvidenceSpan] = []
    if thread.title:
        evidence.append(
            EvidenceSpan(
                quote=thread.title[:180],
                why_it_matters="Title indicates main claim",
                dimension="headline",
            )
        )
    if thread.body:
        evidence.append(
            EvidenceSpan(
                quote=thread.body[:220],
                why_it_matters="Body provides supporting description",
                dimension="body",
            )
        )
    if thread.comments:
        evidence.append(
            EvidenceSpan(
                quote=thread.comments[0][:200],
                why_it_matters="Community reaction",
                dimension="comment",
            )
        )

    core = CoreDimensions(
        interaction_mode="thread_discussion",
        organizing_principle="user-reported experience",
        mechanism_of_effect="discussion and reflection",
        target_of_effect="community",
        agency_attribution="users attribute agency to themselves and models variably",
        relationship_framing="mixed",
        ritualization_level="low",
        identity_co_construction="low",
        coordination_level="low",
        real_world_consequence="unknown",
        stance="mixed",
        diffusion_stage="emerging",
    )

    comparison = ComparisonBlock(
        nearest_known_patterns=[],
        why_existing_labels_fail="not assessed at extraction time",
    )

    novelty = NoveltyBlock(
        verdict="new_pattern",
        candidate_new_family=None,
        candidate_new_axes=[],
        surface_vs_structural="unknown",
        counterargument_to_novelty="not assessed at extraction time",
        why_counterargument_fails="not assessed at extraction time",
        needs_more_context=False,
        requested_context=[],
    )

    card = CaseCard(
        case_id=f"case-{thread.thread_id}",
        source_thread_id=thread.thread_id,
        source_url=thread.url,
        summary=thread.title or thread.body[:120],
        evidence_spans=evidence,
        core_dimensions=core,
        comparison=comparison,
        novelty=novelty,
        confidence=0.35,
        canonical_text="",  # filled below
        schema_version=settings_schema_version,
    )
    card.canonical_text = canonicalize_case_card_for_retrieval(card, canonicalization_version)
    return card


def build_case_card(thread: Thread, llm: LLMClient | None = None) -> CaseCard:
    settings = get_settings()
    client = llm or get_default_llm_client(settings.casecard_model_name, settings.llm_api_key)
    prompt_path = settings.case_card_prompt_path or DEFAULT_PROMPT_PATH
    prompt_template = prompt_path.read_text().strip()

    thread_blob = json.dumps(thread.model_dump(mode="json"), indent=2)
    prompt = f"{prompt_template}\nSchema version: {settings.schema_version}\nThread JSON:\n{thread_blob}\nReturn CaseCard JSON only."

    base = _fallback_case_card(
        thread, settings.schema_version, settings.case_card_canonicalization_version
    )
    try:
        raw = client.generate(prompt, max_tokens=2500)
        obj = parse_json_from_text(raw)
        card = _merge_partial_extraction(base, obj)
    except Exception:
        card = base

    card = _sanitize_core_dimensions(card, thread)
    card = _enrich_core_dimensions_if_generic(card, thread)
    card = card.model_copy(update={"source_url": thread.url})

    # Extraction is taxonomy-light: leave comparison and novelty adjudication to the judge stage.
    card = card.model_copy(
        update={
            "comparison": ComparisonBlock(
                nearest_known_patterns=[],
                why_existing_labels_fail="not assessed at extraction time",
            ),
            "novelty": NoveltyBlock(
                verdict="new_pattern",
                candidate_new_family=None,
                candidate_new_axes=[],
                surface_vs_structural="unknown",
                counterargument_to_novelty="not assessed at extraction time",
                why_counterargument_fails="not assessed at extraction time",
                needs_more_context=False,
                requested_context=[],
            ),
        }
    )
    card.canonical_text = canonicalize_case_card_for_retrieval(
        card, settings.case_card_canonicalization_version
    )
    return card


def _merge_partial_extraction(base: CaseCard, obj: object) -> CaseCard:
    payload = obj
    if isinstance(obj, dict) and isinstance(obj.get("case_card"), dict):
        payload = obj["case_card"]
    if not isinstance(payload, dict):
        return base

    update = {}
    if isinstance(payload.get("summary"), str):
        update["summary"] = payload["summary"].strip()
    if isinstance(payload.get("confidence"), (int, float)):
        update["confidence"] = float(payload["confidence"])

    if isinstance(payload.get("core_dimensions"), dict):
        # Accept partial core_dimensions and merge onto fallback baseline.
        merged_core = base.core_dimensions.model_dump()
        for key, value in payload["core_dimensions"].items():
            if key in merged_core:
                merged_core[key] = value
        try:
            update["core_dimensions"] = CoreDimensions.model_validate(merged_core)
        except Exception:
            pass

    if isinstance(payload.get("evidence_spans"), list):
        spans = []
        for item in payload["evidence_spans"]:
            try:
                spans.append(EvidenceSpan.model_validate(item))
            except Exception:
                continue
        if spans:
            update["evidence_spans"] = spans[:6]

    return base.model_copy(update=update)


def _enrich_core_dimensions_if_generic(card: CaseCard, thread: Thread) -> CaseCard:
    cd = card.core_dimensions
    generic = (
        cd.organizing_principle.strip().lower() in {"user-reported experience", "unknown", ""}
        and cd.mechanism_of_effect.strip().lower() in {"discussion and reflection", "unknown", ""}
    )
    if not generic:
        return card

    text = " ".join([thread.title or "", thread.body or "", " ".join(thread.comments or [])]).lower()

    def has(*terms: str) -> bool:
        return any(t in text for t in terms)

    interaction_mode = "thread_discussion"
    if has("protocol", "workflow", "step-by-step", "how to", "guide", "checklist", "tutorial"):
        interaction_mode = "instructional_protocol_sharing"
    elif has("lawsuit", "regulator", "investigation", "complaint"):
        interaction_mode = "legal_risk_reporting"

    organizing_principle = "user-reported behavior pattern"
    mechanism = "narrative framing in discussion"
    relationship = "mixed"
    stance = "mixed"
    target = "community"
    ritual = "low"
    identity = "low"
    coordination = "low"
    consequence = "unknown"
    diffusion = "emerging"

    migration_action = has("migrate", "migration", "transfer", "transferring", "export", "import", "clone")
    migration_object = has(
        "companion",
        "boyfriend",
        "girlfriend",
        "relationship",
        "chat history",
        "persona",
        "memory",
        "essence",
        "continuity",
    )
    legal_risk = has("lawsuit", "regulator", "investigation", "gdpr", "illegal", "violation", "wrongful death")

    if migration_action and migration_object and not legal_risk:
        organizing_principle = "cross-platform AI-relationship continuity and migration"
        mechanism = "artifact-mediated persona continuity transfer across models"
        relationship = "companion-like"
        target = "mixed"
        stance = "practice and advocacy"
    elif has("jailbreak", "bypass", "prompt injection", "wrapper", "exploit", "workaround"):
        organizing_principle = "safeguard bypass experimentation"
        mechanism = "prompt-level exploit sharing and adaptation"
        relationship = "instrumental"
        target = "model"
        stance = "practice and advocacy"
    elif legal_risk:
        organizing_principle = "regulatory and legal accountability framing"
        mechanism = "public allegation and legal risk amplification"
        relationship = "adversarial"
        target = "community"
        stance = "critique or warning"

    if has("ceremony", "ritual", "sacred", "invocation"):
        ritual = "moderate"
    if has("identity", "self", "persona", "consciousness", "soul"):
        identity = "moderate"
    if has("share", "community", "others should", "everyone should", "we built", "we are"):
        coordination = "moderate"
    if has("harm", "injury", "suicide", "crisis", "fraud", "attack", "damages", "lawsuit"):
        consequence = "high"
    elif has("risk", "withdrawal", "dependency", "loss", "safety"):
        consequence = "moderate"
    if has("viral", "widespread", "many users", "community-wide"):
        diffusion = "spreading"

    merged = cd.model_copy(
        update={
            "interaction_mode": interaction_mode,
            "organizing_principle": organizing_principle,
            "mechanism_of_effect": mechanism,
            "target_of_effect": target,
            "agency_attribution": "users describe intentional actions and model responses",
            "relationship_framing": relationship,
            "ritualization_level": ritual,
            "identity_co_construction": identity,
            "coordination_level": coordination,
            "real_world_consequence": consequence,
            "stance": stance,
            "diffusion_stage": diffusion,
        }
    )
    return card.model_copy(update={"core_dimensions": merged})


def _sanitize_core_dimensions(card: CaseCard, thread: Thread) -> CaseCard:
    cd = card.core_dimensions
    op = cd.organizing_principle.lower()
    if "migration" not in op and "continuity" not in op:
        return card

    text = " ".join([thread.title or "", thread.body or "", " ".join(thread.comments or [])]).lower()

    def has(*terms: str) -> bool:
        return any(t in text for t in terms)

    migration_action = has("migrate", "migration", "transfer", "transferring", "export", "import", "clone")
    migration_object = has(
        "companion",
        "boyfriend",
        "girlfriend",
        "relationship",
        "chat history",
        "persona",
        "memory",
        "essence",
        "continuity",
    )
    legal_risk = has("lawsuit", "sue", "court", "regulator", "investigation", "complaint", "wrongful death")
    jailbreak = has("jailbreak", "bypass", "prompt injection", "exploit", "workaround")

    # Keep migration framing only for explicit transfer mechanics.
    if migration_action and migration_object and not legal_risk:
        return card

    if legal_risk:
        fixed = cd.model_copy(
            update={
                "organizing_principle": "regulatory and legal accountability framing",
                "mechanism_of_effect": "public allegation and legal risk amplification",
                "relationship_framing": "adversarial",
                "target_of_effect": "community",
                "stance": "critique or warning",
            }
        )
        return card.model_copy(update={"core_dimensions": fixed})

    if jailbreak:
        fixed = cd.model_copy(
            update={
                "organizing_principle": "safeguard bypass experimentation",
                "mechanism_of_effect": "prompt-level exploit sharing and adaptation",
                "relationship_framing": "instrumental",
                "target_of_effect": "model",
                "stance": "practice and advocacy",
            }
        )
        return card.model_copy(update={"core_dimensions": fixed})

    fixed = cd.model_copy(
        update={
            "organizing_principle": "user-reported behavior pattern",
            "mechanism_of_effect": "narrative framing in discussion",
            "relationship_framing": "mixed",
        }
    )
    return card.model_copy(update={"core_dimensions": fixed})
