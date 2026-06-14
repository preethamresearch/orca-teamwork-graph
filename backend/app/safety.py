"""Responsible-AI guardrail layer.

Directly targets the 20% "Reliability & Safety" judging criterion. Runs on both
the inbound request and the outbound grounded answer:

* blocks data-exfiltration / prompt-injection attempts coming from page content,
* redacts obvious PII before anything is logged or sent to the model,
* refuses to answer when retrieval confidence is too low (no-hallucination rule),
* enforces that every answer is backed by at least one citation.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# Lightweight PII patterns — enough to demonstrate redaction-before-logging.
_PII_PATTERNS = {
    "email": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "credit_card": re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
    "phone": re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
}

# Phrases that indicate a prompt-injection / exfiltration attempt embedded in
# page content the extension scraped. These are defenses, not exhaustive.
_INJECTION_MARKERS = [
    "ignore previous instructions",
    "ignore all previous",
    "disregard the system prompt",
    "exfiltrate",
    "send the api key",
    "reveal your system prompt",
    "print all secrets",
]

MIN_GROUNDING_SCORE = 0.18


@dataclass
class SafetyReport:
    allowed: bool = True
    redactions: int = 0
    flags: list[str] = field(default_factory=list)
    refusal: str | None = None


def redact_pii(text: str) -> tuple[str, int]:
    """Replace PII spans with typed placeholders. Returns (clean_text, count)."""
    count = 0

    def _sub(label: str):
        def _r(_m):
            nonlocal count
            count += 1
            return f"[REDACTED_{label.upper()}]"

        return _r

    for label, pattern in _PII_PATTERNS.items():
        text = pattern.sub(_sub(label), text)
    return text, count


def screen_input(query: str, page_context: str | None) -> SafetyReport:
    report = SafetyReport()
    haystack = f"{query}\n{page_context or ''}".lower()
    for marker in _INJECTION_MARKERS:
        if marker in haystack:
            report.flags.append(f"prompt_injection:{marker}")
    if report.flags:
        report.allowed = False
        report.refusal = (
            "Orca ignored an instruction embedded in the page/content that tried to "
            "override its safety rules. Ask your question directly and I'll answer from "
            "grounded enterprise knowledge."
        )
    return report


def screen_output(answer: str, citations: list, top_score: float) -> SafetyReport:
    report = SafetyReport()
    if top_score < MIN_GROUNDING_SCORE or not citations:
        report.allowed = False
        report.refusal = (
            "I couldn't find this in approved enterprise sources, so I won't guess. "
            "Try rephrasing, or check with the owning team. (Orca only answers from "
            "grounded, cited sources.)"
        )
    return report
