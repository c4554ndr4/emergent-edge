from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import yaml

from src.schemas import CaseCard


SPLIT_NAMES = {
    "structured_interaction_train",
    "structured_interaction_dev",
    "structured_interaction_test_known",
    "structured_interaction_holdout_subtype",
    "companion_interaction_dev",
    "companion_interaction_test",
    "companion_interaction_holdout",
}


def load_split_lookup(path: Path) -> Dict[str, str]:
    if not path.exists():
        raise FileNotFoundError(path)
    text = path.read_text()
    if path.suffix.lower() in {".yaml", ".yml"}:
        data = yaml.safe_load(text)
    else:
        data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("split file must be a mapping of case_id to split name")
    return {str(k): str(v) for k, v in data.items()}


def ensure_holdout_exclusion(cases: Iterable[CaseCard], split_lookup: Dict[str, str]) -> List[CaseCard]:
    # Known library should be built from train only.
    allowed = {"structured_interaction_train"}
    filtered: List[CaseCard] = []
    for c in cases:
        split = split_lookup.get(c.case_id)
        if split in allowed or split is None:
            filtered.append(c)
    return filtered


def split_cases(cases: Iterable[CaseCard], split_lookup: Dict[str, str]) -> Dict[str, List[CaseCard]]:
    buckets: Dict[str, List[CaseCard]] = {name: [] for name in SPLIT_NAMES}
    for c in cases:
        split = split_lookup.get(c.case_id, "unknown")
        if split not in buckets:
            buckets[split] = []
        buckets[split].append(c)
    return buckets
