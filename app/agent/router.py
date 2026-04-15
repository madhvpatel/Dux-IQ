"""
router.py — Two-tier intent router for DUX IQ.

Tier 1 (fast, no LLM): intent_scoring.py — lexical, entity, session, semantic axes.
  High-confidence single-domain result → dispatch directly to specialist. No LLM call.

Tier 2 (strong model): orchestrator.py — invoked when intent_scoring needs_llm=True
  or when the query is detected as genuinely cross-domain.
  The orchestrator plans, dispatches, and synthesizes using llama-3.3-70b-versatile.

The old 8B LLM router and run_agent_turn fallback are retained for emergencies
but are no longer on the primary path.
"""
from __future__ import annotations

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage

from app.agent.handoff import AGENT_REGISTRY
from app.agent.domain_graph import INTENT_TO_AGENT, SOCIAL_INTENTS
from app.copilot.toolcalling import _make_llm, _invoke_with_rate_limit
from config import Config

logger = logging.getLogger("agent.router")

# ---------------------------------------------------------------------------
# Router LLM — small, fast, cheap
# ---------------------------------------------------------------------------

def _make_router_llm() -> ChatGroq:
    return ChatGroq(
        api_key=Config.GROQ_API_KEY,
        model=Config.GROQ_ROUTER_MODEL,
        temperature=0.0,
        max_tokens=64,
    )


# ---------------------------------------------------------------------------
# Router classification prompt
# ---------------------------------------------------------------------------

ROUTER_SYSTEM_PROMPT = """You are a routing classifier for DUX IQ, a friendly merchant intelligence assistant.

Classify the user's message into ONE of these agents:
- settlement   : payouts, settlement amounts, shortfalls, disbursements, deductions, MDR
- transaction  : payment success rate, GMV, failed payments, KPIs, business overview, what changed
- disputes     : chargebacks, refunds, dispute resolution
- terminal     : POS device health, battery, network signal, geo drift, device failures
- growth       : loans, working capital, credit eligibility, growth opportunities
- general      : greetings, thanks, identity questions, casual chat, out-of-scope, unclear intent

If the message clearly spans TWO domains (e.g. payout drop + chargebacks), return both.

Respond ONLY with valid JSON — no explanation, no markdown:
{"agent": "<primary>", "also": "<secondary or null>"}

Examples:
User: show my recent settlements
{"agent": "settlement", "also": null}

User: why did my payout drop and chargebacks go up?
{"agent": "settlement", "also": "disputes"}

User: which terminal has the worst failure rate?
{"agent": "terminal", "also": null}

User: am I eligible for a loan?
{"agent": "growth", "also": null}

User: hi there
{"agent": "general", "also": null}

User: thanks, that helps!
{"agent": "general", "also": null}

User: why are payments failing?
{"agent": "transaction", "also": null}
"""

# ---------------------------------------------------------------------------
# Fan-out merger prompt
# ---------------------------------------------------------------------------

MERGER_PROMPT = """You are a senior merchant intelligence analyst at DUX IQ.
You have received analysis from multiple specialists. Synthesise their findings into ONE coherent answer.

Rules:
- Answer the merchant's question directly and concisely.
- Credit each specialist's findings naturally (e.g. "Your settlement data shows X, while transaction records indicate Y").
- Do not repeat the same information twice.
- Highlight any contradictions or connections between specialist findings.
- Use plain merchant-friendly language.

Return ONLY valid JSON matching this schema:
{
  "answer": "...",
  "follow_ups": ["...", "..."],
  "claims": [],
  "clarifying_question": null,
  "action_preview": null
}
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_json(raw: str) -> dict[str, Any]:
    text = str(raw or "").strip()
    text = re.sub(r"```(?:json)?", "", text, flags=re.IGNORECASE).replace("```", "").strip()
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            return {}
        try:
            return json.loads(match.group(0)) or {}
        except Exception:
            return {}


VALID_AGENTS = {"settlement", "transaction", "disputes", "terminal", "growth", "general"}


def _classify_intent(prompt: str) -> tuple[str, str | None]:
    """
    Call the 3B router LLM and return (primary_agent, secondary_agent_or_None).
    Falls back to ("general", None) on any error.
    """
    try:
        llm = _make_router_llm()
        raw = _invoke_with_rate_limit(llm, [
            SystemMessage(content=ROUTER_SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ])
        result = _extract_json(getattr(raw, "content", str(raw)))
        primary = str(result.get("agent") or "").strip().lower()
        also = result.get("also")
        secondary = str(also).strip().lower() if also and str(also).strip().lower() != "null" else None

        if primary not in VALID_AGENTS:
            primary = "general"
        if secondary and secondary not in VALID_AGENTS:
            secondary = None
        if secondary == primary:
            secondary = None

        return primary, secondary
    except Exception as exc:
        logger.warning("Router LLM classification failed: %s — falling back to general", exc)
        return "general", None


def _run_agent(
    agent_name: str,
    engine: Any,
    merchant_id: str,
    prompt: str,
    terminal_id: str | None,
    history: list[dict] | None,
    memory_context: dict | None,
    context_object: dict | None,
    debug: bool,
) -> dict[str, Any]:
    """Invoke a named agent synchronously. Used in fan-out threads."""
    fn = AGENT_REGISTRY.get(agent_name)
    if not fn:
        return {
            "answer": f"Agent '{agent_name}' is not available.",
            "agent_name": agent_name,
            "sources": [],
            "follow_ups": [],
        }
    return fn(
        engine,
        merchant_id=merchant_id,
        prompt=prompt,
        terminal_id=terminal_id,
        history=history,
        memory_context=memory_context,
        context_object=context_object,
        debug=debug,
        _handoff_depth=0,
        _disable_handoff=True,
    )


def _merge_responses(
    responses: list[dict[str, Any]],
    prompt: str,
    merchant_id: str,
) -> dict[str, Any]:
    """Merge multiple agent responses into one using an LLM composer call."""
    agent_summaries = []
    all_sources: list[str] = []
    all_follow_ups: list[str] = []
    handoff_chain: list[str] = []

    for resp in responses:
        name = resp.get("agent_name", "unknown")
        handoff_chain.extend(resp.get("handoff_chain") or [name])
        agent_summaries.append({
            "agent": name,
            "answer": resp.get("answer", ""),
            "key_findings": (resp.get("answer_sections") or {}).get("key_findings") or [],
        })
        for s in resp.get("sources") or []:
            if s not in all_sources:
                all_sources.append(s)
        for f in resp.get("follow_ups") or []:
            if f not in all_follow_ups:
                all_follow_ups.append(f)

    llm = _make_llm(0.1)
    payload = {
        "merchant_question": prompt,
        "specialist_reports": agent_summaries,
    }
    try:
        raw = _invoke_with_rate_limit(llm, [
            SystemMessage(content=MERGER_PROMPT),
            HumanMessage(content=json.dumps(payload, ensure_ascii=False, indent=2, default=str)),
        ])
        merged = _extract_json(getattr(raw, "content", str(raw)))
    except Exception as exc:
        logger.warning("Router merger LLM failed: %s", exc)
        merged = {
            "answer": " | ".join(r.get("answer", "") for r in responses if r.get("answer")),
            "follow_ups": all_follow_ups[:4],
        }

    answer = str(merged.get("answer") or "")
    follow_ups = [str(f) for f in list(merged.get("follow_ups") or []) if str(f).strip()]
    if not follow_ups:
        follow_ups = all_follow_ups[:4]

    return {
        "answer": answer,
        "sources": all_sources,
        "follow_ups": follow_ups[:4],
        "clarifying_question": None,
        "validation_status": "clean",
        "display_notice": None,
        "action_preview": None,
        "structured_result": None,
        "answer_sections": {
            "executive_summary": answer,
            "key_findings": [],
            "next_best_action": None,
            "caveats": [],
        },
        "scope": {"merchant_id": merchant_id},
        "agent_name": "router",
        "handoff_chain": list(dict.fromkeys(handoff_chain)),
        "trace": {
            "agent": "router",
            "fan_out_agents": [r.get("agent_name") for r in responses],
            "tool_calls": [],
        },
    }


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def route_and_execute(
    engine: Any,
    *,
    merchant_id: str,
    prompt: str,
    terminal_id: str | None = None,
    history: list[dict[str, Any]] | None = None,
    memory_context: dict[str, Any] | None = None,
    context_object: dict[str, Any] | None = None,
    debug: bool = False,
) -> dict[str, Any]:
    """Two-tier routing:

    Tier 1 — intent_scoring (no LLM, <1ms):
      High-confidence single-domain → dispatch directly to specialist.

    Tier 2 — orchestrator (llama-3.3-70b):
      Ambiguous, multi-domain, or social queries → orchestrator plans and executes.
    """
    from app.intelligence.intent_scoring import (
        score_intent, ROUTE_GREETING, ROUTE_SOCIAL_ACK, ROUTE_OUT_OF_SCOPE, ROUTE_RISKY,
    )
    from app.agent.orchestrator import orchestrate

    _SOCIAL_ROUTES = {ROUTE_GREETING, ROUTE_SOCIAL_ACK, ROUTE_OUT_OF_SCOPE, ROUTE_RISKY}

    # ── Tier 1: fast pre-filter ─────────────────────────────────────────────
    score = score_intent(question=prompt, memory_context=memory_context)

    logger.info(
        "\n┌─ ROUTER (intent_scoring) ───────────────\n"
        "│  intent     : %s\n"
        "│  route      : %s\n"
        "│  confidence : %.2f  source: %s\n"
        "│  needs_llm  : %s\n"
        "└─────────────────────────────────────────",
        score.intent, score.route, score.confidence, score.source, score.needs_llm,
    )

    if not score.needs_llm:
        # Social / out-of-scope from fast path → orchestrator handles gracefully
        if score.route in _SOCIAL_ROUTES:
            logger.info("Fast path: social/out-of-scope → orchestrator")
            return orchestrate(
                engine, merchant_id=merchant_id, prompt=prompt,
                terminal_id=terminal_id, history=history,
                memory_context=memory_context, context_object=context_object, debug=debug,
            )

        # Map intent → agent name
        agent_name = INTENT_TO_AGENT.get(score.intent)
        if agent_name:
            agent_fn = AGENT_REGISTRY.get(agent_name)
            if agent_fn:
                logger.info("Fast path: intent=%s → agent=%s (confidence=%.2f)", score.intent, agent_name, score.confidence)
                return agent_fn(
                    engine,
                    merchant_id=merchant_id,
                    prompt=prompt,
                    terminal_id=terminal_id,
                    history=history,
                    memory_context=memory_context,
                    context_object=context_object,
                    debug=debug,
                    _handoff_depth=0,
                )

    # ── Tier 2: orchestrator ────────────────────────────────────────────────
    logger.info("Escalating to orchestrator (needs_llm=%s, intent=%s)", score.needs_llm, score.intent)
    return orchestrate(
        engine, merchant_id=merchant_id, prompt=prompt,
        terminal_id=terminal_id, history=history,
        memory_context=memory_context, context_object=context_object, debug=debug,
    )
