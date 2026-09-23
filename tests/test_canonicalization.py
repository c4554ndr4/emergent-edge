from src.retrieval.canonicalize import canonicalize_case_card, canonicalize_pattern_card
from tests.test_schemas import build_dummy_case
from src.schemas import PatternCard


def test_canonicalize_case_orders_dimensions():
    card = build_dummy_case()
    text = canonicalize_case_card(card)
    assert "organizing_principle" in text
    assert text.index("organizing_principle") < text.index("novelty") if "novelty" in text else True


def test_canonicalize_pattern_card_includes_features():
    pat = PatternCard(
        pattern_id="p1",
        label="ritual_induction",
        family="structured_interaction",
        summary="summary",
        defining_features=["f1"],
        required_signals=["r1"],
        insufficient_signals=["i1"],
        boundary_notes=["b1"],
        exemplar_case_ids=["c1"],
        confounder_case_ids=[],
        canonical_text="",
    )
    text = canonicalize_pattern_card(pat)
    assert "defining_features" in text
    assert "required_signals" in text
    assert "boundary_notes" in text
    # Retrieval canonicalization intentionally excludes governance/analyst fields.
    assert "exemplar_case_ids" not in text
    assert "monitoring_priority" not in text
