"""Tests for the Tier-1 embedding classifier.

Uses an injected fake embedder so tests run fast with no model download.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import yaml

from src.ai.router.classifier import ClassifierResult, EmbeddingClassifier


class FakeEmbedder:
    """Deterministic text embedder: one-hot per known keyword.

    Each keyword gets its own dimension; cosine similarity is 1.0 for
    texts containing the same keyword, 0 otherwise. Good enough for tests
    that only care about nearest-neighbor behavior.
    """

    KEYWORDS = [
        "spotify", "chrome", "calculator", "notepad", "vscode", "discord",
        "teams", "firefox", "word", "excel",
        "volume", "mute", "louder", "quieter",
        "remind", "reminder", "timer",
        "time", "date", "day",
        "shutdown", "restart", "sleep", "lock", "hibernate", "reboot",
        "system", "cpu", "memory", "disk", "battery",
    ]

    def __init__(self):
        self._dim = len(self.KEYWORDS) + 1  # +1 for "unknown" fallback
        self._lookup = {w: i for i, w in enumerate(self.KEYWORDS)}

    def encode(self, texts, normalize_embeddings=True, show_progress_bar=False, **_):
        out = np.zeros((len(texts), self._dim), dtype=np.float32)
        for i, t in enumerate(texts):
            tokens = t.lower().split()
            hit = False
            for tok in tokens:
                if (idx := self._lookup.get(tok.strip(".,!?"))) is not None:
                    out[i, idx] = 1.0
                    hit = True
            if not hit:
                out[i, -1] = 1.0  # "unknown" dimension
        if normalize_embeddings:
            norms = np.linalg.norm(out, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            out = out / norms
        return out


@pytest.fixture
def intents_file(tmp_path: Path) -> Path:
    data = {
        "intents": {
            "open_app": {
                "examples": ["launch spotify", "open chrome", "start notepad"],
                "params_extractor": "extract_app_name",
            },
            "set_volume": {
                "examples": ["volume up", "make it louder", "mute"],
                "params_extractor": "extract_volume",
            },
            "get_time": {
                "examples": ["what time is it", "time please"],
                "params_extractor": None,
            },
        }
    }
    p = tmp_path / "intents.yaml"
    p.write_text(yaml.safe_dump(data))
    return p


def test_classifier_loads_intents(intents_file):
    clf = EmbeddingClassifier(intents_path=str(intents_file), embedder=FakeEmbedder())
    assert set(clf.intents.keys()) == {"open_app", "set_volume", "get_time"}


def test_classifier_in_distribution_above_threshold(intents_file):
    clf = EmbeddingClassifier(intents_path=str(intents_file), embedder=FakeEmbedder())
    result = clf.classify("launch chrome")
    assert isinstance(result, ClassifierResult)
    assert result.intent == "open_app"
    assert result.confidence >= 0.75


def test_classifier_out_of_distribution_low_confidence(intents_file):
    clf = EmbeddingClassifier(intents_path=str(intents_file), embedder=FakeEmbedder())
    result = clf.classify("summarize my emails")
    assert result.confidence < 0.75


def test_classifier_extracts_params_for_open_app(intents_file):
    clf = EmbeddingClassifier(intents_path=str(intents_file), embedder=FakeEmbedder())
    result = clf.classify("launch chrome")
    assert result.intent == "open_app"
    assert result.params == {"app": "chrome"}


def test_classifier_returns_none_params_when_extraction_fails(intents_file):
    """If the best intent's extractor returns None, params is None (router
    will then downgrade to ReAct)."""
    clf = EmbeddingClassifier(intents_path=str(intents_file), embedder=FakeEmbedder())
    # "spotify" alone matches open_app via the fake embedder, but the
    # extractor requires a launch/close verb in the text and won't find one.
    result = clf.classify("spotify")
    assert result.intent == "open_app"
    assert result.params is None


def test_classifier_no_params_intent(intents_file):
    clf = EmbeddingClassifier(intents_path=str(intents_file), embedder=FakeEmbedder())
    result = clf.classify("what time is it")
    assert result.intent == "get_time"
    assert result.params == {}


def test_classifier_empty_text(intents_file):
    clf = EmbeddingClassifier(intents_path=str(intents_file), embedder=FakeEmbedder())
    result = clf.classify("")
    assert result.intent is None
    assert result.confidence == 0.0
