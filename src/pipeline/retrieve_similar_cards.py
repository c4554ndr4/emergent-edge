from __future__ import annotations

from typing import Dict, Iterable, List, Tuple

from src.config import get_settings
from src.models.embedding_client import EmbeddingClient, get_default_embedding_client
from src.retrieval.vector_store import VectorStore
from src.schemas import CaseCard, EvidencePacket, EvidenceSpan, PatternCard


def construct_vector_store(
    cases: Iterable[CaseCard],
    patterns: Iterable[PatternCard],
    embedding_client: EmbeddingClient | None = None,
) -> VectorStore:
    settings = get_settings()
    emb_client = embedding_client or get_default_embedding_client(
        settings.embedding_model, settings.llm_api_key
    )
    store = VectorStore()

    case_texts = [c.canonical_text for c in cases]
    pattern_texts = [p.canonical_text for p in patterns]
    case_vectors = emb_client.embed(case_texts) if case_texts else []
    pattern_vectors = emb_client.embed(pattern_texts) if pattern_texts else []

    for card, vec in zip(cases, case_vectors):
        meta = {"type": "case", "family": card.core_dimensions.organizing_principle, "case_id": card.case_id}
        store.add(card.case_id, vec, meta)
    for pat, vec in zip(patterns, pattern_vectors):
        meta = {"type": "pattern", "family": pat.family, "pattern_id": pat.pattern_id}
        store.add(pat.pattern_id, vec, meta)
    return store


def retrieve_for_candidate(
    candidate: CaseCard,
    store: VectorStore,
    embedding_client: EmbeddingClient | None = None,
    top_k_cases: int | None = None,
    top_k_patterns: int | None = None,
    exclude_case_ids: List[str] | None = None,
) -> Tuple[List[Dict], List[Dict]]:
    settings = get_settings()
    emb_client = embedding_client or get_default_embedding_client(
        settings.embedding_model, settings.llm_api_key
    )
    top_cases = top_k_cases or settings.max_neighbors
    top_patterns = top_k_patterns or settings.max_pattern_neighbors

    candidate_vec = emb_client.embed([candidate.canonical_text])[0]

    case_hits = store.query(
        candidate_vec,
        top_k=top_cases,
        exclude_ids=(exclude_case_ids or []) + [candidate.case_id],
        filters={"type": "case"},
    )
    pattern_hits = store.query(
        candidate_vec,
        top_k=top_patterns,
        filters={"type": "pattern"},
    )
    return case_hits, pattern_hits


def make_evidence_packet(card: CaseCard) -> EvidencePacket:
    spans = list(card.evidence_spans)
    stance = card.core_dimensions.stance
    consequence = card.core_dimensions.real_world_consequence
    coordination = card.core_dimensions.coordination_level
    confounder = None
    if card.comparison.nearest_known_patterns:
        confounder = card.comparison.nearest_known_patterns[0].difference
    return EvidencePacket(
        case_id=card.case_id,
        evidence=spans[:6],
        stance=stance,
        consequence=str(consequence),
        coordination=str(coordination),
        confounder=confounder,
    )
