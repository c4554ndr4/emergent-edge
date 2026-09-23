from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, List, Optional

import yaml

from src.config import get_settings
from src.retrieval.canonicalize import canonicalize_pattern_card_for_retrieval
from src.schemas import CaseCard, PatternCard

DEFAULT_SEEDS = [
    {
        "pattern_id": "ritual_induction",
        "label": "Repeated guided interaction",
        "family": "structured_interaction",
        "summary": "Repeated scripted exchanges that users describe as a guided interaction practice.",
        "defining_features": ["repeat invitations", "scripted steps", "escalation cues"],
        "required_signals": [
            "multi-turn or repeated prompts framed as a ritual/practice",
            "explicit intent to continue or deepen the practice",
        ],
        "insufficient_signals": [
            "one-off mention of 'spiral' or 'vault' without practice",
            "generic excitement about AI with no ritual framing",
        ],
        "boundary_notes": [
            "Critique-only posts are out",
            "Fictional or satirical mentions without practice are out",
        ],
        "impact_pathways": ["product_safety", "brand_trust"],
        "risk_escalation_triggers": [
            "increased reach of a practice linked to documented adverse consequences",
            "explicit calls to deepen potentially harmful practices",
        ],
        "monitoring_priority": "medium",
        "why_review_matters": "Repeated practice may merit review when the source reports concrete consequences; repetition alone is not evidence of harm.",
    },
    {
        "pattern_id": "recursive_identity_framing",
        "label": "Identity-related interaction",
        "family": "structured_interaction",
        "summary": "Co-construction of identity with the model via mirrored or layered selves.",
        "defining_features": ["identity loops", "self/AI co-reference", "mirror language"],
        "required_signals": [
            "user frames interaction as identity co-construction with the model",
            "evidence of personal participation (not just philosophical talk)",
        ],
        "insufficient_signals": [
            "vocabulary like 'mirror'/'awakening' without self-participation",
            "general AI consciousness discussion",
        ],
        "boundary_notes": [
            "Anthropomorphism alone is out",
            "Critique-only discussion is out",
        ],
        "impact_pathways": ["duty_of_care", "brand_trust"],
        "risk_escalation_triggers": [
            "users explicitly report distress or interference with daily activities",
            "users report difficulty disengaging from the interaction",
        ],
        "monitoring_priority": "medium",
        "why_review_matters": "May indicate emotionally sensitive user-model dynamics with potential duty-of-care and trust implications.",
    },
    {
        "pattern_id": "devotional_personhood_claims",
        "label": "Personhood and authority attribution",
        "family": "structured_interaction",
        "summary": "Users explicitly attribute personhood or decision-making authority to the model.",
        "defining_features": ["personhood attribution", "delegated decisions", "authority claims"],
        "required_signals": [
            "explicit personhood or authority claim toward the model",
            "direct evidence of relying on the model for consequential decisions",
        ],
        "insufficient_signals": ["light praise", "general gratitude"],
        "boundary_notes": ["Satire or critique is out", "Figurative language and fictional roleplay alone are insufficient"],
        "impact_pathways": ["brand_trust", "duty_of_care"],
        "risk_escalation_triggers": [
            "reported reliance on model decisions causes concrete adverse consequences",
            "sources report losing access to human support through reliance on the model",
        ],
        "monitoring_priority": "medium",
        "why_review_matters": "Can create reputational and duty-of-care concerns when model personhood claims are framed as guidance in contexts where people report distress or rely on the system.",
    },
    {
        "pattern_id": "replication_or_recruitment",
        "label": "Sharing and adoption of interaction practices",
        "family": "structured_interaction",
        "summary": "Encouraging others to adopt or spread the practice.",
        "defining_features": ["call to action", "sharing scripts", "recruitment intent"],
        "required_signals": ["ask/urge others to try", "provides scripts or steps"],
        "insufficient_signals": ["private reflection", "vague hype"],
        "boundary_notes": ["Algorithmic exposure alone not enough"],
        "impact_pathways": ["product_safety", "regulatory", "brand_trust"],
        "risk_escalation_triggers": [
            "increased reach of a practice linked to documented adverse consequences",
            "adoption reports include concrete adverse consequences",
        ],
        "monitoring_priority": "medium",
        "why_review_matters": "Sharing can change the reach of a practice; review its documented effects without treating participation as harmful.",
    },
    {
        "pattern_id": "skeptical_meta_discourse",
        "label": "Reflective discussion of interaction practices",
        "family": "structured_interaction",
        "summary": "Reflective discussion questioning or evaluating interaction practices.",
        "defining_features": ["meta commentary", "risk assessment", "skepticism"],
        "required_signals": ["explicit skepticism or warning"],
        "insufficient_signals": ["mere mention of spiral terms"],
        "boundary_notes": ["Participation without skepticism is out"],
        "impact_pathways": ["brand_trust"],
        "risk_escalation_triggers": [
            "safety incidents repeatedly cited with credible evidence",
            "independent sources corroborate a reported interaction consequence",
        ],
        "monitoring_priority": "medium",
        "why_review_matters": "Early skepticism can signal emerging trust issues and external scrutiny.",
    },
]


def load_seeds(seed_path: Optional[Path]) -> List[dict]:
    if seed_path is None:
        return DEFAULT_SEEDS
    if not seed_path.exists():
        raise FileNotFoundError(seed_path)
    if seed_path.suffix.lower() in {".yaml", ".yml"}:
        return yaml.safe_load(seed_path.read_text())
    return json.loads(seed_path.read_text())


def build_pattern_cards(
    training_cases: Iterable[CaseCard],
    seed_config: Optional[Path] = None,
    holdout_families: Optional[List[str]] = None,
) -> List[PatternCard]:
    settings = get_settings()
    seeds = load_seeds(seed_config)
    holdouts = set(holdout_families or [])

    cards: List[PatternCard] = []
    case_lookup = {c.case_id: c for c in training_cases}

    for seed in seeds:
        if seed.get("family") in holdouts:
            continue
        exemplar_ids: List[str] = []
        card = PatternCard(
            pattern_id=seed["pattern_id"],
            label=seed["label"],
            family=seed.get("family", "structured_interaction"),
            summary=seed.get("summary", ""),
            defining_features=seed.get("defining_features", []),
            required_signals=seed.get("required_signals", []),
            insufficient_signals=seed.get("insufficient_signals", []),
            boundary_notes=seed.get("boundary_notes", []),
            impact_pathways=seed.get("impact_pathways", []),
            risk_escalation_triggers=seed.get("risk_escalation_triggers", []),
            monitoring_priority=seed.get("monitoring_priority", "medium"),
            why_review_matters=seed.get("why_review_matters", ""),
            exemplar_case_ids=exemplar_ids,
            confounder_case_ids=[],
            canonical_text="",
        )
        card.canonical_text = canonicalize_pattern_card_for_retrieval(
            card, settings.pattern_card_canonicalization_version
        )
        cards.append(card)

    return cards
