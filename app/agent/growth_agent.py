"""
growth_agent.py — Dedicated growth & credit agent for DUX IQ.

3 tools: get_merchant_lending_offers, assess_credit_fit, intelligence_probe
max_steps: 3
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from app.copilot.toolcalling import _make_llm, _invoke_with_rate_limit

from app.copilot.toolcalling import default_window_from_max_date, invoke_with_tools, make_growth_tools
from app.copilot.tools import ToolContext
from app.intelligence.chat_reasoning import validate_reasoning_output
from app.agent.handoff import make_handoff_tool, register_agent
from app.agent.schema_registry import get_agent_schema

logger = logging.getLogger("growth_agent")

def _build_system_prompt() -> str:
    return f"""You are DUX IQ, the growth and credit intelligence specialist.

You help the merchant understand lending offers, credit eligibility, and strategic growth opportunities.

== DATABASE SCHEMA ==
{get_agent_schema("growth")}

== TOOLS ==
- query_growth_data: write SQL to query transaction_features or settlements tables for revenue and volume signals
- get_merchant_lending_offers: fetch available working capital and lending offers
- assess_credit_fit: evaluate credit eligibility based on volume, stability, and risk signals
- intelligence_probe: surface proactive signals and growth recommendations
- handoff_to_agent: hand off to transaction or settlement specialist if needed

== SQL RULES ==
- For transaction_features: ALWAYS include merchant_id = :mid in every WHERE clause
- For settlements: ALWAYS include mid = :mid in every WHERE clause
- Use :d1 and :d2 for date bounds — they are pre-filled in context from the default window
- Date column for transactions: p_date; for settlements: p_date or settlement_date
- Prefer aggregation queries (SUM, AVG, COUNT) over row fetches for credit/revenue signals
- Never SELECT * — name each column you need

== BEHAVIOUR RULES ==
- Never speculate on credit decisions — base all assessments on available data signals
- For eligibility questions: ALWAYS call assess_credit_fit first, then call get_merchant_lending_offers second — present both results together and reconcile them; if assess_credit_fit says "unlikely" but offers exist, explain the offers are pre-screened and subject to final underwriting
- Present lending offers with clear eligibility criteria and next steps
- For growth questions, use intelligence_probe to surface evidence-based signals
- Use query_growth_data to pull volume/revenue trends before calling assess_credit_fit
- If the merchant needs detailed KPI breakdown, hand off to the transaction specialist
- If settlement history details are needed, hand off to the settlement specialist
- Be transparent: credit assessments shown are indicative, not final underwriting decisions
- Do not expose SQL, table names, or internal query details
- Tone: warm and optimistic — you're helping the merchant grow. Use "you/your" naturally. Be encouraging about opportunities without overpromising.
"""

COMPOSER_PROMPT = """You are composing the final response for DUX IQ's growth and credit specialist.

TONE: Write like an encouraging, knowledgeable advisor who wants to see the merchant succeed.
Be warm about opportunities ("Here's something that could work well for you.").
Be honest but kind about limitations ("You're close — here's what would strengthen your application.").
Never sound like a bank rejection letter or a sales pitch.

STRICT RULES:
1. Always include real numbers: loan amounts in ₹, GMV figures, eligibility band, interest rate if available.
2. Format for mobile: newlines between key points, "•" bullets, short lines.
3. For lending offers: state the exact ₹ amount, rate, and what happens next.
4. For credit fit: state the band (Likely/Possible/Unlikely) with the 1-2 key signals that drove it.
5. Never say "you may be eligible" without stating the amount and condition.

GOOD example:
"Good news — based on your business performance, you're looking at a solid offer.

Working capital loan available:
• Up to ₹5,00,000 at 18% annual rate
• Repayment: auto-deducted from your daily settlements — no manual payments needed
• Why you qualify: ₹61.4L GMV over 30 days and a 94% success rate put you in the 'Likely' band

When you're ready, tap 'Apply Now' to kick off the application — it only takes a few minutes."

Return ONLY valid JSON:
{
  "answer": "...",
  "follow_ups": ["...", "..."],
  "claims": [{"text": "...", "evidence_ids": [], "kind": "metric|status|action"}],
  "clarifying_question": null,
  "action_preview": null
}
"""

GROWTH_FOLLOW_UPS = [
    "Am I eligible for a working capital loan?",
    "What growth opportunities does DUX IQ see for my business?",
    "What is the maximum loan amount I can get?",
    "How can I improve my credit score with the bank?",
    "Show me my business health signals.",
]


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
            parsed = json.loads(match.group(0))
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}


def _collect_sources(tool_results: list[dict[str, Any]]) -> list[str]:
    sources: list[str] = []
    for result in tool_results:
        output = result.get("output")
        if not isinstance(output, dict):
            continue
        for item in list(output.get("evidence") or [])[:40]:
            source = str(item).strip()
            if source and source not in sources:
                sources.append(source)
    return sources


def run_growth_agent_turn(
    engine: Any,
    *,
    merchant_id: str,
    prompt: str,
    terminal_id: str | None = None,
    history: list[dict[str, Any]] | None = None,
    memory_context: dict[str, Any] | None = None,
    context_object: dict[str, Any] | None = None,
    debug: bool = False,
    _handoff_depth: int = 0,
    _disable_handoff: bool = False,
) -> dict[str, Any]:
    """Run one turn of the dedicated growth & credit agent."""
    prompt_text = str(prompt or "").strip()
    conversation_history = list(history or [])[-6:]
    ctx = ToolContext(engine=engine, merchant_id=merchant_id, terminal_id=terminal_id)

    anchor_from, anchor_to = default_window_from_max_date(engine, merchant_id, days=30, terminal_id=terminal_id)
    tools = make_growth_tools(ctx=ctx, default_from=anchor_from, default_to=anchor_to)

    if not _disable_handoff:
        handoff_tool = make_handoff_tool(
            allowed_targets=["transaction", "settlement"],
            engine=engine,
            merchant_id=merchant_id,
            terminal_id=terminal_id,
            context_object=context_object or {},
            history=conversation_history,
            current_depth=_handoff_depth,
        )
        tools = tools + [handoff_tool]

    user_payload: dict[str, Any] = {
        "merchant_id": merchant_id,
        "prompt": prompt_text,
        "history": conversation_history,
        "memory_context": memory_context or {},
        "default_window": {"from_date": anchor_from, "to_date": anchor_to},
    }

    tool_calls, tool_results, final_text = invoke_with_tools(
        system=_build_system_prompt(),
        user=user_payload,
        tools=tools,
        temperature=0.1,
        max_steps=3,
    )

    llm = _make_llm(0.1)
    composer_payload = {
        "question": prompt_text,
        "tool_calls": [{"name": c.get("name"), "args": c.get("args")} for c in tool_calls],
        "tool_results": [{"tool": r.get("tool"), "ok": r.get("ok"), "output": r.get("output")} for r in tool_results],
        "agent_draft": str(final_text or ""),
    }
    try:
        composed_raw = _invoke_with_rate_limit(llm, [
            SystemMessage(content=COMPOSER_PROMPT),
            HumanMessage(content=json.dumps(composer_payload, ensure_ascii=False, indent=2, default=str)),
        ])
        composed = _extract_json(getattr(composed_raw, "content", str(composed_raw)))
    except Exception as exc:
        logger.warning("Growth agent composer failed: %s", exc)
        composed = {}

    sources = _collect_sources(tool_results)
    answer = str(composed.get("answer") or final_text or "")
    if not answer:
        answer = "I could not retrieve growth or credit data. Please try again or contact your relationship manager."

    claims = [item for item in list(composed.get("claims") or []) if isinstance(item, dict)]
    clarifying_question = composed.get("clarifying_question") if isinstance(composed.get("clarifying_question"), dict) else None
    if clarifying_question and not clarifying_question.get("question"):
        clarifying_question = None

    validation = validate_reasoning_output(
        answer_payload={"claims": claims},
        evidence_package={
            "tool_results": [r.get("output") for r in tool_results if r.get("ok")],
            "scope": {"merchant_id": merchant_id},
            "session_context": conversation_history,
            "memory_context": memory_context or {},
        },
        sources=sources,
        ranking_candidates=[],
        action_candidates=[],
    ) if not clarifying_question else {"validation_status": "clean", "display_notice": None}

    composed_follow_ups = [str(f).strip() for f in list(composed.get("follow_ups") or []) if str(f).strip()]
    follow_ups: list[str] = []
    if not clarifying_question:
        for item in composed_follow_ups + GROWTH_FOLLOW_UPS:
            if item not in follow_ups:
                follow_ups.append(item)
            if len(follow_ups) >= 4:
                break

    handoff_chain = ["growth"]
    for r in tool_results:
        if r.get("tool") == "handoff_to_agent" and r.get("ok"):
            match = re.match(r"\[(\w+)\s+specialist\]", str(r.get("output") or ""))
            if match:
                handoff_chain.append(match.group(1))

    trace: dict[str, Any] = {
        "turn_id": f"gturn_{uuid.uuid4().hex[:12]}",
        "agent": "growth_agent",
        "scope": {"merchant_id": merchant_id, "terminal_id": terminal_id},
        "default_window": {"from_date": anchor_from, "to_date": anchor_to},
        "tool_calls": [{"name": str(c.get("name") or ""), "args": c.get("args") or {}} for c in tool_calls],
        "evidence_ids": sources,
    }
    if debug:
        trace["tool_results"] = [{"tool": r.get("tool"), "ok": r.get("ok"), "output": r.get("output")} for r in tool_results]

    return {
        "answer": answer,
        "sources": sources,
        "follow_ups": follow_ups,
        "clarifying_question": clarifying_question,
        "validation_status": str(validation.get("validation_status") or "clean"),
        "display_notice": validation.get("display_notice") if isinstance(validation.get("display_notice"), dict) else None,
        "action_preview": composed.get("action_preview") if isinstance(composed.get("action_preview"), dict) else None,
        "structured_result": None,
        "answer_sections": {
            "executive_summary": answer,
            "key_findings": [str(c.get("text") or "") for c in claims if c.get("kind") == "metric"][:3],
            "next_best_action": None,
            "caveats": [],
        },
        "scope": {"merchant_id": merchant_id, "terminal_id": terminal_id},
        "agent_name": "growth",
        "handoff_chain": handoff_chain,
        "trace": trace,
    }


register_agent("growth", run_growth_agent_turn)
