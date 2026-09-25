"""Sentence embeddings (AI_PIPELINE §1): fastembed multilingual-e5-small (384-d) or a fake for tests.

`EMBEDDING_BACKEND=auto` uses the fake whenever `AI_PROVIDER=mock` (dev/tests stay offline, no 470 MB model),
otherwise fastembed. The 384-dimension `VectorField` is baked into migrations — not swappable by env.
"""

from __future__ import annotations

import hashlib
import math
import re
import threading
from typing import Any, Protocol

import structlog
from django.conf import settings

log = structlog.get_logger(__name__)
DIMENSIONS = 384
E5_MODEL = "intfloat/multilingual-e5-small"
_registered = False
_lock = threading.Lock()


class Embedder(Protocol):
    name: str

    def embed(self, text: str) -> list[float]: ...


def _normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]


class FakeEmbedding:
    """Feature-hashed character trigrams (2^12 buckets folded to 384), L2-normalized.

    Near-identical texts get cosine ≥ 0.9, unrelated texts < 0.5 — the dedupe tests rely on this.
    """

    name = "fake"

    def embed(self, text: str) -> list[float]:
        clean = re.sub(r"\s+", " ", (text or "").lower()).strip()
        buckets = [0.0] * 4096
        padded = f"  {clean}  "
        for i in range(len(padded) - 2):
            gram = padded[i : i + 3]
            digest = hashlib.blake2b(gram.encode("utf-8"), digest_size=4).digest()
            buckets[int.from_bytes(digest, "big") % 4096] += 1.0
        folded = [0.0] * DIMENSIONS
        for i, value in enumerate(buckets):
            folded[i % DIMENSIONS] += value
        return _normalize(folded)


def _register_e5() -> None:
    global _registered
    if _registered:
        return
    from fastembed import TextEmbedding
    from fastembed.common.model_description import ModelSource, PoolingType

    try:
        TextEmbedding.add_custom_model(
            model=E5_MODEL,
            pooling=PoolingType.MEAN,
            normalization=True,
            sources=ModelSource(hf=E5_MODEL),
            dim=DIMENSIONS,
            model_file="onnx/model.onnx",
        )
    except ValueError:  # already registered in this process
        pass
    _registered = True


class FastEmbedEmbedding:
    """Lazy singleton model; e5 convention: input is `"query: " + text`."""

    name = "fastembed"

    def __init__(self) -> None:
        self._model: Any = None

    def _load(self) -> Any:
        with _lock:
            if self._model is None:
                _register_e5()
                from fastembed import TextEmbedding

                self._model = TextEmbedding(
                    model_name=settings.EMBEDDING_MODEL, cache_dir=settings.FASTEMBED_CACHE_DIR
                )
                log.info("embedding_model_loaded", model=settings.EMBEDDING_MODEL)
        return self._model

    def embed(self, text: str) -> list[float]:
        vector = next(iter(self._load().embed([f"query: {text or ''}"])))
        return [float(v) for v in vector]


_backend: Embedder | None = None


def get_embedder() -> Embedder:
    global _backend
    choice = settings.EMBEDDING_BACKEND
    if choice == "auto":
        choice = "fake" if settings.AI_PROVIDER == "mock" else "fastembed"
    if _backend is None or _backend.name != choice:
        _backend = FakeEmbedding() if choice == "fake" else FastEmbedEmbedding()
    return _backend


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))
