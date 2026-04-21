"""Tests for IntentRouter - tier orchestration."""

from __future__ import annotations

from src.ai.router.classifier import ClassifierResult
from src.ai.router.router import IntentRouter, RoutingDecision
from src.core.config import RouterConfig


class FakeClassifier:
    def __init__(self, result: ClassifierResult):
        self._result = result
        self.calls = 0

    def classify(self, text: str) -> ClassifierResult:
        self.calls += 1
        return self._result


def test_regex_tier_hits_first():
    router = IntentRouter(
        config=RouterConfig(),
        classifier=FakeClassifier(ClassifierResult(intent="never", confidence=1.0)),
    )
    decision = router.route("open spotify")
    assert decision.tier == "regex"
    assert decision.intent == "open_app"
    assert decision.params == {"app": "spotify"}
    assert decision.confidence == 1.0


def test_regex_bypasses_classifier():
    clf = FakeClassifier(ClassifierResult(intent="never", confidence=1.0))
    router = IntentRouter(config=RouterConfig(), classifier=clf)
    router.route("open chrome")
    assert clf.calls == 0  # never reached tier 1


def test_classifier_tier_above_threshold():
    clf = FakeClassifier(ClassifierResult(
        intent="open_app", params={"app": "spotify"}, confidence=0.92,
    ))
    router = IntentRouter(config=RouterConfig(), classifier=clf)
    decision = router.route("fire up my music thing")
    assert decision.tier == "classifier"
    assert decision.intent == "open_app"
    assert decision.confidence == 0.92


def test_classifier_tier_below_threshold_falls_through():
    clf = FakeClassifier(ClassifierResult(
        intent="open_app", params={"app": "x"}, confidence=0.40,
    ))
    router = IntentRouter(config=RouterConfig(), classifier=clf)
    decision = router.route("summarize my emails")
    assert decision.tier == "react"


def test_classifier_intent_but_none_params_falls_through():
    """If classifier returns params=None the router must downgrade to ReAct."""
    clf = FakeClassifier(ClassifierResult(
        intent="open_app", params=None, confidence=0.95,
    ))
    router = IntentRouter(config=RouterConfig(), classifier=clf)
    decision = router.route("spotify")
    assert decision.tier == "react"


def test_no_classifier_configured_falls_through():
    router = IntentRouter(
        config=RouterConfig(classifier_enabled=False),
        classifier=None,
    )
    decision = router.route("something the regex doesnt match")
    assert decision.tier == "react"


def test_router_disabled_always_returns_react():
    router = IntentRouter(
        config=RouterConfig(enabled=False),
        classifier=FakeClassifier(ClassifierResult(intent="x", confidence=1.0)),
    )
    decision = router.route("open spotify")
    assert decision.tier == "react"


def test_routing_decision_latency_recorded():
    router = IntentRouter(config=RouterConfig())
    decision = router.route("open spotify")
    assert decision.latency_ms > 0


def test_explain_includes_tier_and_intent():
    d = RoutingDecision(
        tier="regex", intent="open_app", params={"app": "spotify"},
        confidence=1.0, reason="regex match", latency_ms=1.2,
    )
    expl = d.explain()
    assert "regex" in expl
    assert "open_app" in expl
    assert "spotify" in expl


def test_custom_confidence_threshold():
    clf = FakeClassifier(ClassifierResult(
        intent="open_app", params={"app": "x"}, confidence=0.80,
    ))
    # Threshold 0.85 - 0.80 should fall through
    router = IntentRouter(
        config=RouterConfig(confidence_threshold=0.85),
        classifier=clf,
    )
    decision = router.route("something non-regex")
    assert decision.tier == "react"

    # Threshold 0.75 - 0.80 should classify
    router2 = IntentRouter(
        config=RouterConfig(confidence_threshold=0.75),
        classifier=FakeClassifier(ClassifierResult(
            intent="open_app", params={"app": "x"}, confidence=0.80,
        )),
    )
    decision2 = router2.route("something non-regex")
    assert decision2.tier == "classifier"
