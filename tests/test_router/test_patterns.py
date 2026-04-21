"""Tests for Tier-0 regex patterns and their parameter extractors."""

from __future__ import annotations

import pytest

from src.ai.router.patterns import (
    extract_app_name,
    extract_power_action,
    extract_reminder,
    extract_volume,
    extract_workflow_description,
    match_regex,
)


class TestOpenApp:
    @pytest.mark.parametrize("utterance", [
        "open spotify",
        "launch chrome",
        "start calculator",
        "Open Notepad",
    ])
    def test_matches(self, utterance):
        m = match_regex(utterance)
        assert m is not None
        assert m.intent == "open_app"
        assert m.params["app"]

    def test_captures_app_name(self):
        m = match_regex("open spotify")
        assert m.params["app"] == "spotify"

    def test_captures_multi_word_app(self):
        m = match_regex("open google chrome")
        assert m.params["app"] == "google chrome"


class TestCloseApp:
    @pytest.mark.parametrize("utterance", [
        "close spotify",
        "quit chrome",
        "exit notepad",
    ])
    def test_matches(self, utterance):
        m = match_regex(utterance)
        assert m is not None
        assert m.intent == "close_app"


class TestSetVolume:
    @pytest.mark.parametrize("utterance,expected_level", [
        ("mute", 0),
        ("unmute", 50),
        ("volume up", 75),
        ("volume down", 25),
        ("volume to 80", 80),
        ("volume to 0", 0),
        ("volume to 100", 100),
    ])
    def test_level_extraction(self, utterance, expected_level):
        m = match_regex(utterance)
        assert m is not None
        assert m.intent == "set_volume"
        assert m.params["level"] == expected_level


class TestGetTime:
    @pytest.mark.parametrize("utterance", [
        "what time is it",
        "what time is it?",
        "what's the time",
        "whats the time?",
    ])
    def test_matches(self, utterance):
        m = match_regex(utterance)
        assert m is not None
        assert m.intent == "get_time"


class TestGetDate:
    @pytest.mark.parametrize("utterance", [
        "what's the date",
        "what day is it",
        "what is the date?",
    ])
    def test_matches(self, utterance):
        m = match_regex(utterance)
        assert m is not None
        assert m.intent == "get_date"


class TestPower:
    @pytest.mark.parametrize("utterance,expected", [
        ("shutdown", "shutdown"),
        ("restart", "restart"),
        ("sleep", "sleep"),
        ("lock", "lock"),
        ("hibernate", "hibernate"),
    ])
    def test_action_extraction(self, utterance, expected):
        m = match_regex(utterance)
        assert m is not None
        assert m.intent == "power"
        assert m.params["action"] == expected


class TestSetReminder:
    def test_in_minutes(self):
        m = match_regex("remind me to drink water in 10 minutes")
        assert m is not None
        assert m.intent == "set_reminder"
        assert "drink water" in m.params["message"]
        assert m.params["minutes"] == 10

    def test_without_to(self):
        m = match_regex("remind me call dave in 5 minutes")
        assert m is not None
        assert m.intent == "set_reminder"


class TestNonMatches:
    @pytest.mark.parametrize("utterance", [
        "summarize my last 5 emails",
        "what's the weather like",
        "tell me a joke",
        "",
        "   ",
        "how does python work",
    ])
    def test_falls_through(self, utterance):
        assert match_regex(utterance) is None


class TestExtractors:
    def test_extract_app_name_strips_filler(self):
        assert extract_app_name("please open spotify") == {"app": "spotify"}
        assert extract_app_name("can you launch chrome") == {"app": "chrome"}

    def test_extract_app_name_failure(self):
        assert extract_app_name("hello there") is None

    def test_extract_volume_word(self):
        assert extract_volume("turn up the volume") == {"level": 75}
        assert extract_volume("make it louder") == {"level": 75}
        assert extract_volume("mute") == {"level": 0}

    def test_extract_power_action(self):
        assert extract_power_action("shut down the computer") == {"action": "shutdown"}
        assert extract_power_action("lock my pc") == {"action": "lock"}

    def test_extract_reminder(self):
        r = extract_reminder("remind me to water the plants in 20 minutes")
        assert r is not None
        assert "water the plants" in r["message"]
        assert r["minutes"] == 20


class TestExtractWorkflowDescription:
    @pytest.mark.parametrize("utterance,description", [
        ("create a workflow to summarize my emails", "summarize my emails"),
        ("make a workflow that pulls my calendar", "pulls my calendar"),
        ("set up a workflow to remind me to drink water", "remind me to drink water"),
        ("schedule an automation for my standup notes", "my standup notes"),
        ("build a workflow for daily tracker", "daily tracker"),
    ])
    def test_extracts_description(self, utterance, description):
        result = extract_workflow_description(utterance)
        assert result is not None
        assert description in result["description"]

    @pytest.mark.parametrize("utterance", [
        "what's the weather",
        "open spotify",
        "",
    ])
    def test_rejects_non_workflow_utterances(self, utterance):
        assert extract_workflow_description(utterance) is None

    def test_rejects_bare_create_workflow(self):
        """Missing the target description means we can't act on it."""
        assert extract_workflow_description("create a workflow") is None
