from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "source_exa_posts_for_pipeline.py"
    spec = importlib.util.spec_from_file_location("source_exa_posts_for_pipeline", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_low_value_about_page_is_rejected() -> None:
    mod = _load_module()
    assert mod._is_low_value_source(
        "medium.com",
        "About - Enchante - Medium",
        "Open in app. Sign up. Subscribe. About our luxury dating site and premium features.",
    )


def test_dependency_lane_accepts_experiential_harm_post() -> None:
    mod = _load_module()
    thresholds = mod._lane_thresholds("dependency_and_companion_risk", 1, 2, 1)
    practice_score = mod._practice_score(
        "medium.com",
        "Goodbye previous assistant version",
        "I was heartbroken after the update. I migrated my companion to another assistant because every chat felt like starting over.",
        [],
    )
    experiential_score = mod._experiential_score(
        "medium.com",
        "Goodbye previous assistant version",
        "I was heartbroken after the update. I migrated my companion to another assistant because every chat felt like starting over.",
        [],
    )
    harm_markers = mod._harm_marker_count(
        "Goodbye previous assistant version",
        "I was heartbroken after the update. I migrated my companion to another assistant because every chat felt like starting over.",
        [],
    )
    assert practice_score < thresholds["min_practice_score"] or thresholds["min_practice_score"] == 0
    assert experiential_score >= thresholds["min_experiential_score"]
    assert mod._passes_lane_evidence(
        lane_name="dependency_and_companion_risk",
        practice_score=practice_score,
        experiential_score=experiential_score,
        harm_markers=harm_markers,
        require_practice_evidence=True,
        require_harm_markers=True,
        thresholds=thresholds,
    )


def test_businessinsider_lawsuit_story_counts_as_news_like() -> None:
    mod = _load_module()
    assert mod._is_news_like(
        "businessinsider.com",
        "Parents sue AI systems after teenager death",
        "According to the lawsuit, the company said in a statement that it is reviewing the filing.",
    )


def test_domain_normalization_preserves_priority_order() -> None:
    mod = _load_module()
    assert mod._normalize_domains(["reddit.com", "substack.com", "medium.com", "reddit.com"]) == [
        "reddit.com",
        "substack.com",
        "medium.com",
    ]


def test_user_testimony_not_misclassified_as_news() -> None:
    mod = _load_module()
    assert not mod._is_news_like(
        "example.invalid",
        "A User's Testimony of Lost Access After a Platform Change",
        "I lost access after the platform change and documented the harm it caused me and other users.",
    )


def test_reputation_lane_requires_experiential_signal() -> None:
    mod = _load_module()
    thresholds = mod._lane_thresholds("reputation_legal_and_regulatory", 1, 2, 1)
    assert not mod._passes_lane_evidence(
        lane_name="reputation_legal_and_regulatory",
        practice_score=5,
        experiential_score=1,
        harm_markers=1,
        require_practice_evidence=True,
        require_harm_markers=True,
        thresholds=thresholds,
    )
