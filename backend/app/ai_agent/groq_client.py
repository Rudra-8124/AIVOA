# ─────────────────────────────────────────────────────────────────
# ai_agent/groq_client.py – Typed Groq API integration layer
#
# Provides two public callables used throughout the agent:
#
#   extract_interaction_fields(text)
#       → Calls Groq with a prompt-engineered extraction prompt.
#       → Returns ExtractedFields (typed dict) with 8 guaranteed keys.
#
#   chat_completion(messages, system, temperature, max_tokens)
#       → Thin async wrapper around groq.chat.completions.create.
#       → Returns the raw reply string — no JSON parsing.
#
# The AsyncGroq client is a module-level lazy singleton so the
# connection is reused across requests without being re-created on
# every graph invocation.
# ─────────────────────────────────────────────────────────────────

from __future__ import annotations

import json
import logging
from typing import Any, TypedDict

from groq import AsyncGroq

from app.config import settings

logger = logging.getLogger(__name__)

# ── Lazy singleton ────────────────────────────────────────────────
_client: AsyncGroq | None = None


def get_client() -> AsyncGroq:
    """Return (and lazily create) the shared AsyncGroq client."""
    global _client
    if _client is None:
        _client = AsyncGroq(api_key=settings.GROQ_API_KEY)
        logger.info("[groq_client] AsyncGroq client initialised (model=%s)", settings.LLM_MODEL)
    return _client


# ─────────────────────────────────────────────────────────────────
# Typed output for extract_interaction_fields()
# ─────────────────────────────────────────────────────────────────

class ExtractedFields(TypedDict, total=False):
    """
    Structured output of the interaction field extraction call.

    All keys are always present in the returned dict (total=False means
    individual keys are optional in type-checking; at runtime we
    guarantee them via the fallback merge).
    """
    hcp_name:             str | None          # Full name of the HCP
    interaction_type:     str | None          # in_person | phone | email | virtual
    interaction_date:     str | None          # YYYY-MM-DD
    interaction_time:     str | None          # HH:MM (24-h) or None
    topics_discussed:     list[str]           # Products, indications, clinical topics
    materials_shared:     list[str]           # Brochures, reprints, PDFs
    sentiment:            str | None          # positive | neutral | negative
    followup_actions:     list[str]           # Verbatim follow-up action strings
    outcomes:             str | None          # Brief summary of what was agreed
    samples_distributed:  list[dict[str, Any]]# [{product_name, quantity}]


# ─────────────────────────────────────────────────────────────────
# Prompt engineering for reliable field extraction
# ─────────────────────────────────────────────────────────────────

_EXTRACTION_SYSTEM_PROMPT = """\
You are a pharmaceutical CRM data-extraction assistant.
A sales representative has described an interaction with a healthcare professional (HCP).
Your task: extract ALL structured fields from the description — no guessing, no hallucination.

────────────────────────────────────────────────
FIELD RULES
────────────────────────────────────────────────
hcp_name (string | null)
  • Full name of the doctor / pharmacist / nurse.
  • Include title if given (e.g. "Dr. Smith", "Prof. Li").
  • null if not mentioned.

interaction_type (string | null)
  • Map to EXACTLY one of: in_person | phone | email | virtual
  • "met", "visited", "saw", "called in", "dropped by"  → in_person
  • "called", "rang", "spoke over the phone"             → phone
  • "emailed", "sent an email", "messaged"               → email
  • "zoom", "teams", "webex", "video call", "online"     → virtual
  • null if unclear.

interaction_date (string | null)
  • ISO-8601 date: YYYY-MM-DD.
  • Resolve relative expressions using today's date provided below.
  • "today" → today | "yesterday" → yesterday | "last Monday" → compute.
  • null if not mentioned.

interaction_time (string | null)
  • 24-hour HH:MM if a time is given, else null.

topics_discussed (array of strings)
  • Every product name, indication, clinical topic, study, or guideline mentioned.
  • Empty array [] if none.

materials_shared (array of strings)
  • Brochures, detail aids, reprints, PDFs, slide decks, patient leaflets.
  • Empty array [] if none.

sentiment (string | null)
  • Infer overall HCP receptiveness:
      positive  – enthusiastic, interested, keen, welcoming, agreed
      neutral   – neither positive nor negative, routine, polite
      negative  – skeptical, dismissed, concerned, refused, annoyed
  • null if truly impossible to infer.

followup_actions (array of strings)
  • Verbatim or paraphrased actions the rep committed to or noted.
  • E.g. "Send clinical data on Cardivex by Friday".
  • Empty array [] if none.

outcomes (string | null)
  • 1-2 sentence summary of what was agreed or accomplished.
  • null if nothing specific.

samples_distributed (array of objects)
  • Each object: {"product_name": "<string>", "quantity": <integer>}
  • Empty array [] if no samples were given.

────────────────────────────────────────────────
OUTPUT FORMAT — respond with ONLY valid JSON, no prose, no markdown fences:
{
  "hcp_name": null,
  "interaction_type": null,
  "interaction_date": null,
  "interaction_time": null,
  "topics_discussed": [],
  "materials_shared": [],
  "sentiment": null,
  "followup_actions": [],
  "outcomes": null,
  "samples_distributed": []
}
────────────────────────────────────────────────"""


# ─────────────────────────────────────────────────────────────────
# Primary public function: extract_interaction_fields
# ─────────────────────────────────────────────────────────────────

async def extract_interaction_fields(
    text: str,
    today: str | None = None,
) -> ExtractedFields:
    """
    Send *text* (a rep's natural-language description) to Groq and
    extract structured interaction fields.

    Parameters
    ----------
    text:
        Raw user input describing an HCP interaction.
    today:
        Today's date as YYYY-MM-DD string (injected so the LLM can
        resolve relative dates). Defaults to ``date.today().isoformat()``.

    Returns
    -------
    ExtractedFields
        Typed dict with guaranteed keys — missing LLM fields are filled
        with safe defaults (None or []).
    """
    from datetime import date as _date
    today_str = today or _date.today().isoformat()

    # Prepend today's date to the user message for relative-date resolution
    user_message = f"[Today's date: {today_str}]\n\n{text}"

    # Safe defaults — merged over LLM output to guarantee all keys exist
    _defaults: ExtractedFields = {
        "hcp_name":            None,
        "interaction_type":    None,
        "interaction_date":    None,
        "interaction_time":    None,
        "topics_discussed":    [],
        "materials_shared":    [],
        "sentiment":           None,
        "followup_actions":    [],
        "outcomes":            None,
        "samples_distributed": [],
    }

    try:
        client = get_client()
        response = await client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[
                {"role": "system", "content": _EXTRACTION_SYSTEM_PROMPT},
                {"role": "user",   "content": user_message},
            ],
            temperature=0.05,           # near-deterministic for extraction
            max_tokens=512,
            response_format={"type": "json_object"},
        )

        raw = response.choices[0].message.content.strip()
        parsed: dict = json.loads(raw)

        # Merge: LLM output overrides defaults (None values from LLM are kept)
        result: ExtractedFields = {**_defaults, **parsed}  # type: ignore[misc]

        logger.info(
            "[groq_client] extraction ok | hcp=%s type=%s date=%s sentiment=%s topics=%s",
            result.get("hcp_name"),
            result.get("interaction_type"),
            result.get("interaction_date"),
            result.get("sentiment"),
            result.get("topics_discussed"),
        )
        return result

    except json.JSONDecodeError as exc:
        logger.error("[groq_client] JSON parse error: %s | raw=%r", exc, raw[:200])
        return _defaults

    except Exception as exc:
        logger.exception("[groq_client] extraction failed: %s", exc)
        return _defaults


# ─────────────────────────────────────────────────────────────────
# Generic wrapper: chat_completion
# ─────────────────────────────────────────────────────────────────

async def chat_completion(
    messages: list[dict[str, str]],
    system: str | None = None,
    temperature: float = 0.5,
    max_tokens: int = 512,
    json_mode: bool = False,
) -> str:
    """
    Generic async wrapper around Groq chat completions.

    Parameters
    ----------
    messages:
        List of ``{"role": ..., "content": ...}`` dicts.
        Do NOT include the system message here — pass it via *system*.
    system:
        Optional system prompt prepended to *messages*.
    temperature:
        Sampling temperature (0.0 = deterministic, 1.0 = creative).
    max_tokens:
        Maximum tokens in the reply.
    json_mode:
        If True, sets ``response_format={"type": "json_object"}``.
        The system prompt MUST instruct the model to return JSON.

    Returns
    -------
    str
        The raw reply string (stripped). Caller is responsible for
        JSON parsing if json_mode=True.
    """
    full_messages: list[dict[str, str]] = []
    if system:
        full_messages.append({"role": "system", "content": system})
    full_messages.extend(messages)

    kwargs: dict[str, Any] = {
        "model":       settings.LLM_MODEL,
        "messages":    full_messages,
        "temperature": temperature,
        "max_tokens":  max_tokens,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    client = get_client()
    response = await client.chat.completions.create(**kwargs)
    return response.choices[0].message.content.strip()
