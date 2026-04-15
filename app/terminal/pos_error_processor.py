"""
pos_error_processor.py — Gemini vision-based POS terminal error analysis.

Accepts an image of a PAX POS terminal screen showing an error, extracts the
error message via Gemini Flash vision, then matches it against the PAX error
knowledge base to provide an explanation and troubleshooting steps.
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import re
from typing import Any

from app.terminal.pax_errors import lookup_pax_error, search_pax_errors, PaxError

logger = logging.getLogger("terminal.pos_error_processor")

_VISION_PROMPT = """You are a POS terminal support specialist for an Indian acquiring bank.

Carefully examine this image of a PAX POS terminal screen.

Extract the following fields and return ONLY a JSON object — no prose, no markdown:

{
  "error_message": "<the exact error text shown on the terminal screen, or null>",
  "error_code": "<any numeric/alphanumeric error code visible, or null>",
  "terminal_id": "<terminal ID if visible on screen, or null>",
  "merchant_id": "<merchant ID if visible on screen, or null>",
  "transaction_type": "<Sale/Void/Refund/UPI/EMI/Settlement/Pre-Auth if identifiable, or null>",
  "screen_context": "<brief description of what screen/stage is shown, e.g. 'PIN entry screen', 'amount entry', 'network error dialog'>",
  "additional_text": "<any other relevant text visible on screen, or null>",
  "raw_ocr": "<full verbatim text read from the terminal screen>"
}

Rules:
- Use null for any field not visible.
- Focus on the ERROR MESSAGE — that is the most important field.
- If multiple lines of text are shown, capture the primary error in error_message and other text in additional_text.
- Return ONLY the JSON object. No explanation.
"""


def _gemini_vision_extract(image_bytes: bytes, mime_type: str) -> dict[str, Any]:
    """Call Gemini Flash with vision to extract POS error screen content."""
    from config import Config

    if not Config.GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not set — returning demo POS error extraction.")
        return {
            "error_message": "No Internet Connection",
            "error_code": None,
            "terminal_id": None,
            "merchant_id": None,
            "transaction_type": "Sale",
            "screen_context": "Network error dialog before transaction",
            "additional_text": None,
            "raw_ocr": "No Internet Connection\nPlease check your network and try again",
        }

    try:
        from google import genai

        client = genai.Client(api_key=Config.GEMINI_API_KEY)

        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=[
                _VISION_PROMPT,
                {
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": base64.b64encode(image_bytes).decode("utf-8"),
                    }
                },
            ],
        )
        raw_text = (response.text or "").strip()

        raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text, flags=re.MULTILINE)
        raw_text = re.sub(r"\s*```$", "", raw_text, flags=re.MULTILINE)

        return json.loads(raw_text)

    except Exception as exc:
        logger.warning("Gemini vision POS error extraction failed: %s", exc)
        return {}


def _format_match(err: PaxError) -> dict[str, str]:
    return {
        "category": err.category,
        "known_message": err.message,
        "trigger": err.trigger,
        "transaction_flow": err.flow,
        "recommended_action": err.action,
    }


def analyze_pos_error_image(
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
    merchant_id: str | None = None,
) -> dict[str, Any]:
    """Analyze a POS terminal error image end-to-end.

    1. Extract error text from image via Gemini vision
    2. Match against PAX error knowledge base
    3. Return structured diagnosis with troubleshooting steps

    Returns dict with: ok, extracted, matches, diagnosis, evidence_id
    """
    image_hash = hashlib.sha256(image_bytes).hexdigest()[:16]
    evidence_id = f"pos_error:{merchant_id or 'unknown'}:{image_hash}"

    extracted = _gemini_vision_extract(image_bytes, mime_type)

    if not extracted:
        return {
            "ok": False,
            "error": "Could not read the terminal screen. Please take a clearer photo.",
            "evidence_id": evidence_id,
            "merchant_id": merchant_id,
            "extracted": {},
            "matches": [],
            "diagnosis": None,
        }

    error_msg = extracted.get("error_message") or ""
    error_code = extracted.get("error_code") or ""

    # Try exact match first, then keyword search
    matches = lookup_pax_error(error_msg) if error_msg else []
    if not matches and error_code:
        matches = lookup_pax_error(error_code)
    if not matches:
        search_query = f"{error_msg} {error_code}".strip()
        if search_query:
            matches = search_pax_errors(search_query, top_k=3)

    formatted_matches = [_format_match(m) for m in matches]

    # Build diagnosis
    if matches:
        primary = matches[0]
        diagnosis = {
            "error_identified": True,
            "error_category": primary.category,
            "what_happened": primary.trigger,
            "affected_flow": primary.flow,
            "how_to_fix": primary.action,
            "severity": _assess_severity(primary),
        }
    elif error_msg:
        diagnosis = {
            "error_identified": False,
            "error_category": "Unknown",
            "what_happened": f"The terminal is displaying: \"{error_msg}\"",
            "affected_flow": extracted.get("transaction_type") or "Unknown",
            "how_to_fix": "Try restarting the terminal. If the error persists, contact ICICI support with the error message shown.",
            "severity": "medium",
        }
    else:
        diagnosis = {
            "error_identified": False,
            "error_category": "Unknown",
            "what_happened": "Could not identify a specific error message on screen.",
            "affected_flow": "Unknown",
            "how_to_fix": "Please take a clearer photo showing the error message on the terminal screen.",
            "severity": "low",
        }

    return {
        "ok": True,
        "error": None,
        "evidence_id": evidence_id,
        "merchant_id": merchant_id,
        "extracted": {
            "error_message": error_msg or None,
            "error_code": error_code or None,
            "terminal_id": extracted.get("terminal_id"),
            "merchant_id": extracted.get("merchant_id"),
            "transaction_type": extracted.get("transaction_type"),
            "screen_context": extracted.get("screen_context"),
            "raw_ocr": (extracted.get("raw_ocr") or "")[:800],
        },
        "matches": formatted_matches,
        "diagnosis": diagnosis,
    }


def _assess_severity(err: PaxError) -> str:
    """Rough severity based on error category."""
    high = {"Network & Host Communication", "Data Protocol", "Transaction State", "Reversal"}
    medium = {"Card Reading", "PIN & Password", "Card Validation", "Void Transaction"}
    if err.category in high:
        return "high"
    if err.category in medium:
        return "medium"
    return "low"
