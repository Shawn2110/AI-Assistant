"""Tier-0 regex patterns for the intent router.

Each pattern returns a ``PatternMatch`` with the intent name and a params
dict extracted from capture groups. Patterns are tried in the order listed;
the first match wins.

The extractor functions (``extract_app_name`` etc.) are also used by the
Tier-1 classifier to pull structured arguments out of fuzzy utterances that
the classifier recognizes by meaning but not by exact phrasing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable


# ─── Result type ───────────────────────────────────────────────────

@dataclass
class PatternMatch:
    intent: str
    params: dict[str, Any] = field(default_factory=dict)


# ─── Helpers ───────────────────────────────────────────────────────

_FILLER = {
    "please", "can", "could", "would", "you", "for", "me", "the", "my",
    "a", "an", "some", "pls", "kindly",
}

_APP_VERBS = {"open", "launch", "start", "fire", "up", "bring", "run", "get", "give"}
_CLOSE_VERBS = {"close", "quit", "exit", "stop", "kill", "shut", "down", "terminate"}


def _strip_words(text: str, words: set[str]) -> str:
    """Remove tokens in `words` (case-insensitive) and return the rest."""
    toks = [t for t in re.split(r"\s+", text.strip()) if t and t.lower() not in words]
    return " ".join(toks).strip()


_WORD_NUMBERS = {
    "zero": 0, "ten": 10, "fifteen": 15, "twenty": 20, "twenty-five": 25,
    "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
    "eighty": 80, "ninety": 90, "hundred": 100,
}


def _parse_int(token: str) -> int | None:
    """Parse '50', 'fifty', or 'twenty-five' to an int."""
    token = token.strip().lower()
    if token.isdigit():
        return int(token)
    return _WORD_NUMBERS.get(token)


# ─── Parameter extractors ──────────────────────────────────────────

def extract_app_name(text: str) -> dict[str, Any] | None:
    """Pull an application name out of a free-form "open X" utterance.

    Requires a launch/close verb to appear in the text - otherwise we have
    no evidence the user is even asking to open an app and return None.
    """
    text = (text or "").strip().lower().rstrip("?.!")
    if not text:
        return None

    tokens = {t for t in re.split(r"\s+", text) if t}
    if not (tokens & _APP_VERBS or tokens & _CLOSE_VERBS):
        return None

    remainder = _strip_words(text, _FILLER | _APP_VERBS | _CLOSE_VERBS)
    if remainder:
        return {"app": remainder}
    return None


def extract_volume(text: str) -> dict[str, Any] | None:
    """Map volume phrasing to a level 0-100."""
    t = (text or "").strip().lower().rstrip("?.!")
    if not t:
        return None

    if re.fullmatch(r"\s*mute\s*", t):
        return {"level": 0}
    if re.fullmatch(r"\s*unmute\s*", t):
        return {"level": 50}
    if "max" in t and "volume" in t:
        return {"level": 100}

    # Explicit number
    m = re.search(r"(?:volume|to)\s+(\d{1,3})", t)
    if m:
        lvl = int(m.group(1))
        return {"level": max(0, min(100, lvl))}

    # Word number
    m = re.search(r"(?:volume|to)\s+([a-z\-]+)", t)
    if m and (n := _parse_int(m.group(1))) is not None:
        return {"level": max(0, min(100, n))}

    if any(w in t for w in ("up", "louder", "increase", "higher")):
        return {"level": 75}
    if any(w in t for w in ("down", "quieter", "decrease", "lower", "softer")):
        return {"level": 25}

    return None


_POWER_ACTIONS = {
    "shutdown": "shutdown", "shut": "shutdown", "shut down": "shutdown",
    "power off": "shutdown", "turn off": "shutdown",
    "restart": "restart", "reboot": "restart",
    "sleep": "sleep", "hibernate": "hibernate",
    "lock": "lock",
}


def extract_power_action(text: str) -> dict[str, Any] | None:
    t = (text or "").strip().lower()
    for phrase, action in _POWER_ACTIONS.items():
        if re.search(rf"\b{re.escape(phrase)}\b", t):
            return {"action": action}
    return None


_TIME_MULTIPLIERS = {
    "minute": 1, "minutes": 1, "min": 1, "mins": 1,
    "hour": 60, "hours": 60, "hr": 60, "hrs": 60,
    "second": 0, "seconds": 0, "sec": 0, "secs": 0,  # round to 0 min
}


_WORKFLOW_LEAD_RE = re.compile(
    r"^\s*(?:please\s+)?"
    r"(?:create|make|set\s*up|schedule|build|automate)"
    r"\s+(?:an?\s+|my\s+)?"
    r"(?:new\s+)?"
    r"(?:recurring\s+)?"
    r"(?:workflow|automation|job|task|recurring\s+task)"
    r"\s*(?:to|for|that)?\s*",
    re.I,
)


def extract_workflow_description(text: str) -> dict[str, Any] | None:
    """Pull the free-form description out of 'create a workflow to X' style text.

    If the leading 'create workflow' phrase is missing we return None so the
    router downgrades to ReAct — the LLM is better at one-shot requests that
    don't match the template.
    """
    t = (text or "").strip()
    if not t:
        return None
    m = _WORKFLOW_LEAD_RE.match(t)
    if not m:
        return None
    rest = t[m.end():].strip(" .!?")
    if not rest:
        return None
    return {"description": rest}


def extract_reminder(text: str) -> dict[str, Any] | None:
    """Parse 'remind me [to] <message> in <N> <unit>'."""
    t = (text or "").strip().lower()
    if not t.startswith("remind"):
        return None

    m = re.search(
        r"remind(?:\s+me)?\s+(?:to\s+)?(.+?)\s+in\s+(\d+|\w+)\s+([a-z]+)",
        t,
    )
    if not m:
        return None
    message = m.group(1).strip()
    qty_raw = m.group(2)
    unit = m.group(3)

    qty = _parse_int(qty_raw)
    if qty is None:
        return None
    mult = _TIME_MULTIPLIERS.get(unit)
    if mult is None:
        return None
    return {"message": message, "minutes": qty * mult if mult else 0}


# ─── Regex patterns (Tier 0) ───────────────────────────────────────

_PATTERNS: list[tuple[re.Pattern[str], str, Callable[[re.Match[str]], dict[str, Any] | None] | None]] = [
    # power first (specific single words before generic open/close)
    (re.compile(r"^\s*(shutdown|restart|sleep|hibernate|lock)\s*$", re.I),
     "power", lambda m: {"action": m.group(1).lower()}),
    (re.compile(r"^\s*(shut\s+down|power\s+off|turn\s+off)\s*(?:the\s+)?(?:computer|pc|system)?\s*$", re.I),
     "power", lambda m: {"action": "shutdown"}),
    (re.compile(r"^\s*(reboot)\s*(?:the\s+)?(?:computer|pc)?\s*$", re.I),
     "power", lambda m: {"action": "restart"}),

    # volume
    (re.compile(r"^\s*mute\s*$", re.I), "set_volume", lambda m: {"level": 0}),
    (re.compile(r"^\s*unmute\s*$", re.I), "set_volume", lambda m: {"level": 50}),
    (re.compile(r"^\s*volume\s+up\s*$", re.I), "set_volume", lambda m: {"level": 75}),
    (re.compile(r"^\s*volume\s+down\s*$", re.I), "set_volume", lambda m: {"level": 25}),
    (re.compile(r"^\s*volume\s+to\s+(\d{1,3})\s*$", re.I),
     "set_volume", lambda m: {"level": max(0, min(100, int(m.group(1))))}),

    # time & date
    (re.compile(r"^\s*what(?:'?s|\s+is)?\s+(?:the\s+)?time\??\s*$", re.I),
     "get_time", lambda m: {}),
    (re.compile(r"^\s*what\s+time\s+is\s+it\??\s*$", re.I),
     "get_time", lambda m: {}),
    (re.compile(r"^\s*what(?:'?s|\s+is)?\s+(?:the\s+)?date\??\s*$", re.I),
     "get_date", lambda m: {}),
    (re.compile(r"^\s*what\s+day\s+is\s+it\??\s*$", re.I),
     "get_date", lambda m: {}),

    # reminder
    (re.compile(r"^\s*remind.+\bin\s+\d+\s+\w+", re.I),
     "set_reminder", lambda m: extract_reminder(m.string)),

    # open / close (run last - most permissive)
    (re.compile(r"^\s*(?:open|launch|start)\s+(.+?)\s*$", re.I),
     "open_app", lambda m: {"app": m.group(1).strip().lower()}),
    (re.compile(r"^\s*(?:close|quit|exit)\s+(.+?)\s*$", re.I),
     "close_app", lambda m: {"app": m.group(1).strip().lower()}),
]


def match_regex(text: str) -> PatternMatch | None:
    """Match `text` against all regex patterns; return the first hit or None."""
    if not text or not text.strip():
        return None
    t = text.strip()
    for pat, intent, extractor in _PATTERNS:
        m = pat.match(t)
        if m:
            params = extractor(m) if extractor else {}
            if params is None:
                continue
            return PatternMatch(intent=intent, params=params)
    return None


# Registry used by the Tier-1 classifier to look up an intent's extractor by
# the `params_extractor` name in config/intents.yaml.
EXTRACTORS: dict[str, Callable[[str], dict[str, Any] | None]] = {
    "extract_app_name": extract_app_name,
    "extract_volume": extract_volume,
    "extract_power_action": extract_power_action,
    "extract_reminder": extract_reminder,
    "extract_workflow_description": extract_workflow_description,
}
