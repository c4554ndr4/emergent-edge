from src.models.embedding_client import DeterministicDummyEmbeddingClient
from src.pipeline.retrieve_similar_cards import construct_vector_store, retrieve_for_candidate
from src.retrieval.vector_store import VectorStore
from tests.test_schemas import build_dummy_case
from src.schemas import PatternCard


def test_vector_store_excludes_candidate():
    cases = [build_dummy_case("case-a"), build_dummy_case("case-b")]
    patterns = [
        PatternCard(
            pattern_id="p1",
            label="ritual",
            family="structured_interaction",
            summary="",
            defining_features=[],
            required_signals=[],
            insufficient_signals=[],
            boundary_notes=[],
            exemplar_case_ids=[],
            confounder_case_ids=[],
            canonical_text="p1",
        )
    ]
    emb = DeterministicDummyEmbeddingClient(dim=8)
    store = construct_vector_store(cases, patterns, emb)
    candidate = cases[0]
    case_hits, pattern_hits = retrieve_for_candidate(candidate, store, emb, top_k_cases=5)
    ids = [h["id"] for h in case_hits]
    assert candidate.case_id not in ids
    assert pattern_hits  # should retrieve pattern


def test_vector_store_has_no_centroid_support():
    assert VectorStore.assert_no_centroid_support() is True
