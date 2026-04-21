"""Tier-1 classifier - embedding similarity over example utterances.

At startup the classifier loads `config/intents.yaml`, embeds every example
once, and caches the matrix. At query time it embeds the user's text, does
a single batched cosine similarity against all cached embeddings, and picks
the nearest intent.

For testability, the `embedder` is injectable. In production the default is
`sentence-transformers` with `all-MiniLM-L6-v2` (~22MB, CPU-friendly).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from src.ai.router.patterns import EXTRACTORS
from src.core.logger import get_logger

log = get_logger(__name__)


@dataclass
class ClassifierResult:
    intent: str | None = None
    # None => "this intent matched but params extraction failed"; callers
    # should treat None the same as an unconfident classification.
    params: dict[str, Any] | None = field(default_factory=dict)
    confidence: float = 0.0


@dataclass
class _Intent:
    name: str
    examples: list[str]
    extractor_name: str | None
    embeddings: np.ndarray | None = None  # shape (N_examples, dim)


class EmbeddingClassifier:
    """Nearest-neighbor intent classifier over embedded example utterances."""

    def __init__(
        self,
        intents_path: str,
        model_name: str = "all-MiniLM-L6-v2",
        embedder: Any | None = None,
    ):
        self.intents_path = Path(intents_path)
        self.model_name = model_name
        self._embedder = embedder
        self._embedded = False
        self.intents: dict[str, _Intent] = self._load_intents()

    def _load_intents(self) -> dict[str, _Intent]:
        if not self.intents_path.exists():
            log.warning("classifier.intents.missing", path=str(self.intents_path))
            return {}

        data = yaml.safe_load(self.intents_path.read_text(encoding="utf-8")) or {}
        raw = data.get("intents", {})
        result = {}
        for name, spec in raw.items():
            result[name] = _Intent(
                name=name,
                examples=list(spec.get("examples", [])),
                extractor_name=spec.get("params_extractor"),
            )
        return result

    def _get_embedder(self):
        if self._embedder is not None:
            return self._embedder
        # Lazy-load sentence-transformers only when actually needed
        from sentence_transformers import SentenceTransformer
        log.info("classifier.model.loading", model=self.model_name)
        self._embedder = SentenceTransformer(self.model_name)
        return self._embedder

    def _ensure_embedded(self) -> None:
        if self._embedded:
            return
        embedder = self._get_embedder()
        for intent in self.intents.values():
            if not intent.examples:
                continue
            intent.embeddings = embedder.encode(
                intent.examples,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
        self._embedded = True

    def classify(self, text: str) -> ClassifierResult:
        if not text or not text.strip():
            return ClassifierResult()
        if not self.intents:
            return ClassifierResult()

        self._ensure_embedded()
        embedder = self._get_embedder()
        q = embedder.encode(
            [text], normalize_embeddings=True, show_progress_bar=False,
        )[0]

        best_name: str | None = None
        best_score = -1.0
        for intent in self.intents.values():
            if intent.embeddings is None:
                continue
            scores = intent.embeddings @ q  # cosine since both normalized
            top = float(np.max(scores))
            if top > best_score:
                best_score = top
                best_name = intent.name

        if best_name is None:
            return ClassifierResult()

        intent = self.intents[best_name]
        extractor = (
            EXTRACTORS.get(intent.extractor_name) if intent.extractor_name else None
        )
        if extractor is None:
            params: dict[str, Any] | None = {}
        else:
            params = extractor(text)  # may be None on failure

        return ClassifierResult(
            intent=best_name,
            params=params,
            confidence=max(0.0, best_score),
        )
