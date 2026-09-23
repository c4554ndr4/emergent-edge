from src.eval.benchmarks import ensure_holdout_exclusion
from tests.test_schemas import build_dummy_case


def test_holdout_exclusion_filters():
    cases = [build_dummy_case("a"), build_dummy_case("b")]
    split = {"a": "structured_interaction_train", "b": "companion_interaction_holdout"}
    filtered = ensure_holdout_exclusion(cases, split)
    ids = {c.case_id for c in filtered}
    assert "a" in ids and "b" not in ids
