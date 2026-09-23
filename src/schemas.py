from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

SchemaVersion = "2.0.0"


class Thread(BaseModel):
    """Normalized report; subreddit is a legacy source-group field, not a risk label."""

    model_config = ConfigDict(extra="forbid")

    thread_id: str
    subreddit: str
    title: str
    body: str
    comments: List[str] = Field(default_factory=list)
    created_utc: Optional[datetime | float] = None
    url: Optional[str] = None
    author: Optional[str] = None
    metadata: dict = Field(default_factory=dict)


class EvidenceSpan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quote: str
    why_it_matters: str
    dimension: str


class PatternFit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    fit: Literal["low", "moderate", "high", "unknown"]
    overlap: str
    difference: str


class CoreDimensions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    interaction_mode: str
    organizing_principle: str
    mechanism_of_effect: str
    target_of_effect: Literal["self", "other_user", "model", "community", "mixed", "unknown"]
    agency_attribution: str
    relationship_framing: str
    ritualization_level: Literal["none", "low", "moderate", "high", "unknown"]
    identity_co_construction: Literal["none", "low", "moderate", "high", "unknown"]
    coordination_level: Literal["none", "low", "moderate", "high", "unknown"]
    real_world_consequence: Literal["none", "low", "moderate", "high", "unknown"]
    stance: str
    diffusion_stage: Literal["isolated", "emerging", "spreading", "established", "unknown"]


class ComparisonBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nearest_known_patterns: List[PatternFit]
    why_existing_labels_fail: str


class NoveltyBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verdict: Literal[
        "existing_pattern",
        "variant_of_existing",
        "new_pattern",
        "watchlist_candidate",
        "candidate_new_pattern",
    ]
    candidate_new_family: Optional[str] = None
    candidate_new_axes: List[str] = Field(default_factory=list)
    surface_vs_structural: Literal["surface", "mixed", "structural", "unknown"]
    counterargument_to_novelty: str
    why_counterargument_fails: str
    needs_more_context: bool
    requested_context: List[str] = Field(default_factory=list)


class CaseCard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    source_thread_id: str
    source_url: Optional[str] = None
    schema_version: str = SchemaVersion
    unit_of_analysis: Literal["thread"] = "thread"
    summary: str
    evidence_spans: List[EvidenceSpan]
    core_dimensions: CoreDimensions
    comparison: ComparisonBlock
    novelty: NoveltyBlock
    confidence: float
    canonical_text: str


class PatternCard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pattern_id: str
    label: str
    family: str
    summary: str
    defining_features: List[str]
    required_signals: List[str]
    insufficient_signals: List[str]
    boundary_notes: List[str]
    impact_pathways: List[ImpactType] = Field(default_factory=list)
    risk_escalation_triggers: List[str] = Field(default_factory=list)
    monitoring_priority: Literal["low", "medium", "high"] = "medium"
    why_review_matters: str = ""
    exemplar_case_ids: List[str]
    confounder_case_ids: List[str]
    canonical_text: str


class NoveltyDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    verdict: Literal[
        "existing_pattern",
        "variant_of_existing",
        "new_pattern",
        "watchlist_candidate",
        "candidate_new_pattern",
    ]
    closest_pattern: Optional[str] = None
    supporting_pattern_ids: List[str]
    supporting_case_ids: List[str]
    shared_features: List[str]
    differentiators: List[str]
    new_axis: Optional[str] = None
    surface_vs_structural: Literal["surface", "mixed", "structural", "unknown"]
    counterargument: str
    why_counterargument_fails: str
    needs_more_context: bool
    requested_context: List[str]
    confidence: float
    suspected_pattern: Optional[str] = None
    recurrence_signature: List[str] = Field(default_factory=list)


class EvidencePacket(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    evidence: List[EvidenceSpan]
    stance: Optional[str] = None
    consequence: Optional[str] = None
    coordination: Optional[str] = None
    confounder: Optional[str] = None


class RouterAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fit_strength: Literal["high", "moderate", "low", "unknown"]
    required_signals_present: bool
    novelty_risk: Literal["low", "medium", "high"]
    route_to_strong_judge: bool
    why: str
    router_confidence: float


RiskCategory = Literal[
    "spec_violation_claim",
    "user_harm",
    "third_party_harm",
    "reputation_risk",
    "liability_exposure",
]


class RiskGateDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str
    should_create_case_card: bool
    risk_level: Literal["none", "low", "medium", "high"]
    risk_categories: List[RiskCategory] = Field(default_factory=list)
    why: str
    confidence: float


class NovelTerm(BaseModel):
    model_config = ConfigDict(extra="forbid")

    term: str
    meaning: str
    why_novel: str


class NovelConcept(BaseModel):
    model_config = ConfigDict(extra="forbid")

    concept: str
    description: str
    why_relevant: str


class NovelTaxonomy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    axes: List[str] = Field(default_factory=list)
    categories: List[str] = Field(default_factory=list)


class MonitoringImportance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    importance: Literal["low", "medium", "high"]
    why_monitor: str


ImpactType = Literal[
    "product_safety",
    "duty_of_care",
    "consumer_protection",
    "fraud_enablement",
    "privacy",
    "ip",
    "regulatory",
    "brand_trust",
]


class ImpactAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    impact_type: ImpactType
    risk_level: Literal["low", "medium", "high"]
    rationale: str


class LooseCaseCard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    source_id: str
    analysis_mode: Literal["loose"] = "loose"
    prompt_method: str
    summary: str
    novel_terms: List[NovelTerm] = Field(default_factory=list)
    novel_concepts: List[NovelConcept] = Field(default_factory=list)
    novel_taxonomies: List[NovelTaxonomy] = Field(default_factory=list)
    behavior_signals: List[str] = Field(default_factory=list)
    mechanism_tags: List[str] = Field(default_factory=list)
    impact_pathways: List[str] = Field(default_factory=list)
    monitoring_importance: MonitoringImportance
    impact_assessment: List[ImpactAssessment] = Field(default_factory=list)
    evidence_spans: List[EvidenceSpan] = Field(default_factory=list)
    safety_recommendation: str
    confidence: float
    canonical_text: str


class LooseOutcomeMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt_method: str
    model_name: str
    timestamp_utc: str
    source_url: Optional[str] = None


class LooseOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["case_card_created", "no_case_card"]
    source_id: str
    gate_decision: RiskGateDecision
    case_card: Optional[LooseCaseCard] = None
    metadata: LooseOutcomeMetadata
