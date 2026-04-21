"""Intent router core.

Combines the three tiers (regex, classifier, ReAct fallback) into a single
``IntentRouter.route(text)`` call that returns a ``RoutingDecision``.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Literal

from src.ai.router.patterns import match_regex
from src.core.config import RouterConfig
from src.core.logger import get_logger

log = get_logger(__name__)

Tier = Literal["regex", "classifier", "react"]


@dataclass
class RoutingDecision:
    tier: Tier
    intent: str | None = None
    params: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    reason: str = ""
    latency_ms: float = 0.0

    def explain(self) -> str:
        """Human-readable one-liner for --explain-routing and logs."""
        if self.tier == "react":
            return f"[react] fallback - {self.reason} ({self.latency_ms:.1f}ms)"
        return (
            f"[{self.tier}] intent={self.intent} params={self.params} "
            f"confidence={self.confidence:.2f} - {self.reason} "
            f"({self.latency_ms:.1f}ms)"
        )


class IntentRouter:
    """Three-tier intent router: regex -> classifier -> ReAct."""

    def __init__(self, config: RouterConfig, classifier: Any | None = None):
        self.config = config
        self._classifier = classifier  # injectable for tests; lazy-loaded otherwise
        self._classifier_loaded = classifier is not None

    def _get_classifier(self):
        if not self.config.classifier_enabled:
            return None
        if self._classifier_loaded:
            return self._classifier
        try:
            from src.ai.router.classifier import EmbeddingClassifier
            self._classifier = EmbeddingClassifier(
                intents_path=self.config.intents_path,
                model_name=self.config.embedding_model,
            )
        except Exception as e:
            log.warning("router.classifier.load_failed", error=str(e))
            self._classifier = None
        self._classifier_loaded = True
        return self._classifier

    def route(self, text: str) -> RoutingDecision:
        """Route `text` through the tiers and return a RoutingDecision."""
        t0 = time.perf_counter()

        if not self.config.enabled:
            return RoutingDecision(
                tier="react", reason="router disabled",
                latency_ms=(time.perf_counter() - t0) * 1000,
            )

        # Tier 0 - regex
        if m := match_regex(text):
            decision = RoutingDecision(
                tier="regex", intent=m.intent, params=m.params,
                confidence=1.0, reason="regex match",
                latency_ms=(time.perf_counter() - t0) * 1000,
            )
            log.info("router.decision", **_log_fields(decision))
            return decision

        # Tier 1 - classifier
        classifier_hint = ""
        classifier = self._get_classifier()
        if classifier is not None:
            result = classifier.classify(text)
            if (
                result.intent
                and result.confidence >= self.config.confidence_threshold
                and result.params is not None
            ):
                decision = RoutingDecision(
                    tier="classifier", intent=result.intent,
                    params=result.params, confidence=result.confidence,
                    reason=f"classifier >= {self.config.confidence_threshold}",
                    latency_ms=(time.perf_counter() - t0) * 1000,
                )
                log.info("router.decision", **_log_fields(decision))
                return decision
            # classifier ran but didn't meet the bar - useful for debugging
            if result.intent:
                reason = (
                    "params extraction failed"
                    if result.params is None
                    else f"below threshold {self.config.confidence_threshold}"
                )
                classifier_hint = (
                    f" (classifier guessed {result.intent} "
                    f"@ {result.confidence:.2f}: {reason})"
                )

        # Tier 2 - fallback
        decision = RoutingDecision(
            tier="react", reason="no tier matched" + classifier_hint,
            latency_ms=(time.perf_counter() - t0) * 1000,
        )
        log.info("router.decision", **_log_fields(decision))
        return decision


def _log_fields(d: RoutingDecision) -> dict[str, Any]:
    return {
        "tier": d.tier,
        "intent": d.intent,
        "confidence": round(d.confidence, 3),
        "latency_ms": round(d.latency_ms, 2),
    }
