from __future__ import annotations

import hashlib
import math
import os
import random
from typing import List, Protocol

import numpy as np

from src.models.transport import post_json


class EmbeddingClient(Protocol):
    def embed(self, texts: List[str]) -> List[List[float]]:
        ...


class EndpointEmbeddingClient:
    def __init__(self, model: str, base_url: str, api_key: str | None = None) -> None:
        if not model or model == "embedding-model":
            raise ValueError("Set EMBEDDING_MODEL to a model served by your endpoint")
        self.model, self.base_url, self.api_key = model, base_url, api_key

    def embed(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        result = post_json(self.base_url, "embeddings", {"model": self.model, "input": texts}, self.api_key)
        data = result.get("data")
        if not isinstance(data, list) or len(data) != len(texts):
            raise ValueError("Embedding response count does not match inputs")
        vectors: dict[int, List[float]] = {}
        dimension = None
        for item in data:
            index = item.get("index") if isinstance(item, dict) else None
            vector = item.get("embedding") if isinstance(item, dict) else None
            if type(index) is not int or index not in range(len(texts)) or index in vectors:
                raise ValueError("Embedding response has invalid or duplicate input indices")
            if not isinstance(vector, list) or not vector or any(
                type(v) not in (int, float) or not math.isfinite(v) for v in vector
            ):
                raise ValueError("Embedding response has an invalid vector")
            dimension = dimension or len(vector)
            if len(vector) != dimension:
                raise ValueError("Embedding response has inconsistent vector dimensions")
            vectors[index] = [float(v) for v in vector]
        return [vectors[i] for i in range(len(texts))]


class DeterministicDummyEmbeddingClient:
    """Stable hash vectors for offline plumbing tests, not semantic retrieval quality."""

    def __init__(self, dim: int = 256, seed: int = 13) -> None:
        self.dim, self.seed = dim, seed

    def embed(self, texts: List[str]) -> List[List[float]]:
        vectors = []
        for text in texts:
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            rng = random.Random(digest + self.seed.to_bytes(2, "big"))
            arr = np.asarray([rng.uniform(-1, 1) for _ in range(self.dim)], dtype=float)
            vectors.append((arr / (np.linalg.norm(arr) or 1.0)).tolist())
        return vectors


def get_default_embedding_client(model: str | None = None, api_key: str | None = None) -> EmbeddingClient:
    base_url = os.getenv("EMBEDDING_BASE_URL", "").strip()
    key = os.getenv("EMBEDDING_API_KEY") or api_key or os.getenv("LLM_API_KEY")
    if not base_url:
        if os.getenv("LLM_BASE_URL") or key:
            raise ValueError("Live mode requires EMBEDDING_BASE_URL; offline vectors are not mixed with live results")
        return DeterministicDummyEmbeddingClient()
    return EndpointEmbeddingClient(model or os.getenv("EMBEDDING_MODEL", ""), base_url, key)
