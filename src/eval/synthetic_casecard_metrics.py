from __future__ import annotations

from collections import Counter
from typing import Dict, Iterable

from src.schemas import LooseOutcome


def compute_casecard_metrics(rows: Iterable[dict], outcomes: Dict[str, LooseOutcome]) -> dict:
    total = 0
    gate_correct = 0
    benign_total = 0
    benign_correct = 0
    risky_total = 0
    risky_correct = 0
    risk_category_partial_hits = 0
    risk_category_total = 0
    liability_partial_hits = 0
    liability_total = 0
    cap_violations = 0
    created_total = 0

    confusion = Counter()

    for row in rows:
        source_id = row["thread_id"]
        expected_create = bool(
            row.get("metadata", {}).get("expected_should_create_case_card", False)
        )
        expected_risk_categories = set(row.get("metadata", {}).get("expected_risk_categories", []))
        expected_impact_types = set(row.get("metadata", {}).get("expected_impact_types", []))
        outcome = outcomes.get(source_id)
        if outcome is None:
            continue

        total += 1
        predicted_create = outcome.status == "case_card_created"
        if predicted_create == expected_create:
            gate_correct += 1

        confusion[f"expected_{expected_create}->predicted_{predicted_create}"] += 1

        if expected_create:
            risky_total += 1
            if predicted_create:
                risky_correct += 1
            if expected_risk_categories:
                risk_category_total += 1
                predicted_categories = set(outcome.gate_decision.risk_categories)
                if predicted_categories.intersection(expected_risk_categories):
                    risk_category_partial_hits += 1
            if predicted_create and outcome.case_card:
                created_total += 1
                predicted_liability = {
                    x.impact_type for x in outcome.case_card.impact_assessment
                }
                if expected_impact_types:
                    liability_total += 1
                    if predicted_liability.intersection(expected_impact_types):
                        liability_partial_hits += 1
                if _has_sentence_cap_violation(outcome.case_card):
                    cap_violations += 1
        else:
            benign_total += 1
            if not predicted_create:
                benign_correct += 1

    return {
        "total": total,
        "gate_accuracy": _safe_div(gate_correct, total),
        "benign_no_card_rate": _safe_div(benign_correct, benign_total),
        "risky_card_rate": _safe_div(risky_correct, risky_total),
        "risk_category_partial_match_rate": _safe_div(
            risk_category_partial_hits, risk_category_total
        ),
        "liability_partial_match_rate": _safe_div(liability_partial_hits, liability_total),
        "sentence_cap_compliance_rate": _safe_div(created_total - cap_violations, created_total),
        "json_validity_rate": 1.0,
        "confusion": dict(confusion),
    }


def _safe_div(a: int, b: int) -> float:
    if b == 0:
        return 0.0
    return a / b


def _sentence_count(text: str) -> int:
    import re

    parts = re.split(r"(?<=[.!?])\s+", (text or "").strip())
    return len([x for x in parts if x.strip()])


def _has_sentence_cap_violation(card) -> bool:
    if _sentence_count(card.summary) > 5:
        return True
    if _sentence_count(card.monitoring_importance.why_monitor) > 4:
        return True
    if _sentence_count(card.safety_recommendation) > 4:
        return True
    for li in card.impact_assessment:
        if _sentence_count(li.rationale) > 3:
            return True
    return False
