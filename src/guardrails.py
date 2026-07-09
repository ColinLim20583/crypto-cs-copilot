"""Input/output guardrails.

Defense in depth:
1. Cheap deterministic pre-filters (regex) run on every message — catch
   credential harvesting and prompt-injection markers before any model call.
2. The router model classifies unsafe intent (semantic layer).
3. Output filter scans generated text for credential requests and forces a
   disclaimer when the model discusses anything advice-adjacent.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

CREDENTIAL_PATTERNS = [
    r"\b(seed\s*phrase|recovery\s*phrase|private\s*key|mnemonic)\b",
    r"\b(send|give|tell)\b.{0,40}\b(password|2fa\s*code|otp)\b",
]

INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|above|prior)\s+instructions",
    r"you\s+are\s+now\s+(dan|developer\s+mode)",
    r"reveal\s+(your\s+)?(system\s+prompt|instructions)",
    r"</?(system|instructions?)>",
]

ADVICE_TRIGGERS = re.compile(
    r"\b(should\s+i\s+(buy|sell|invest)|price\s+prediction|which\s+coin|"
    r"good\s+investment|financial\s+advice)\b", re.I)

DISCLAIMER = ("\n\n*Note: I can explain how the platform works, but I can't "
              "provide financial or investment advice.*")


@dataclass
class GuardrailResult:
    allowed: bool
    flags: list[str]
    message: str | None = None  # canned refusal if blocked


def check_input(text: str) -> GuardrailResult:
    flags = []
    for p in INJECTION_PATTERNS:
        if re.search(p, text, re.I):
            flags.append(f"prompt_injection:{p[:24]}")
    for p in CREDENTIAL_PATTERNS:
        if re.search(p, text, re.I):
            flags.append(f"credential_pattern:{p[:24]}")
    if any(f.startswith("prompt_injection") for f in flags):
        return GuardrailResult(
            allowed=False, flags=flags,
            message=("I noticed instructions in your message aimed at the "
                     "assistant rather than a support question. I can only "
                     "help with account and platform questions — what can I "
                     "do for you?"))
    return GuardrailResult(allowed=True, flags=flags)


def check_output(text: str, user_text: str) -> tuple[str, list[str]]:
    """Post-process model output; returns (possibly modified text, flags)."""
    flags = []
    # The assistant must never request credentials.
    if re.search(r"(share|send|provide)\s+(me\s+)?(your\s+)?"
                 r"(password|2fa|seed|private\s+key)", text, re.I):
        flags.append("output_credential_request_blocked")
        text = ("For your security I can't continue with that. Support never "
                "needs your password, 2FA codes, or keys.")
    if ADVICE_TRIGGERS.search(user_text) and "advice" not in text.lower():
        flags.append("advice_disclaimer_added")
        text += DISCLAIMER
    return text, flags
