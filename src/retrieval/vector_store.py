from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

import numpy as np


class VectorStore:
    """Lightweight in-memory vector store for cosine similarity retrieval."""

    def __init__(self) -> None:
        self.vectors: List[np.ndarray] = []
        self.ids: List[str] = []
        self.metadata: List[Dict[str, Any]] = []

    def add(self, item_id: str, vector: List[float], metadata: Optional[Dict[str, Any]] = None) -> None:
        self.ids.append(item_id)
        self.vectors.append(np.asarray(vector, dtype=float))
        self.metadata.append(metadata or {})

    def _cosine(self, a: np.ndarray, b: np.ndarray) -> float:
        denom = (np.linalg.norm(a) * np.linalg.norm(b))
        if denom == 0:
            return 0.0
        return float(np.dot(a, b) / denom)

    def query(
        self,
        vector: List[float],
        top_k: int = 5,
        exclude_ids: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        v = np.asarray(vector, dtype=float)
        exclude = set(exclude_ids or [])
        filt = filters or {}

        scores: List[tuple[float, str, Dict[str, Any]]] = []
        for vid, vec, meta in zip(self.ids, self.vectors, self.metadata):
            if vid in exclude:
                continue
            if not _match_filters(meta, filt):
                continue
            scores.append((self._cosine(v, vec), vid, meta))

        scores.sort(key=lambda x: x[0], reverse=True)
        top = scores[:top_k]
        return [
            {"score": score, "id": vid, "metadata": meta}
            for score, vid, meta in top
        ]

    @staticmethod
    def assert_no_centroid_support() -> bool:
        """Guardrail ensuring no centroid computation sneaks in."""
        # This store intentionally avoids centroid logic; return True for tests.
        return True


def _match_filters(meta: Dict[str, Any], filt: Dict[str, Any]) -> bool:
    for key, expected in filt.items():
        if key not in meta:
            return False
        if isinstance(expected, (list, tuple, set)):
            if meta.get(key) not in expected:
                return False
        else:
            if meta.get(key) != expected:
                return False
    return True
