"""
disputes_agent.py — Dedicated chargeback & refund agent for DUX IQ.

3 tools: list_chargebacks, get_chargeback_detail, list_refunds
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

from app.copilot.toolcalling import default_window_from_max_date, invoke_with_tools, make_dispute_tools
from app.copilot.tools import ToolContext
from app.intelligence.chat_reasoning import validate_reasoning_output
from app.agent.handoff import make_handoff_tool, register_agent
from app.agent.schema_registry import get_agent_schema

logger = logging.getLogger("disputes_agent")

def _build_system_prompt() -> str:
    return f"""You are DUX IQ, the disputes and risk intelligence specialist.

You help the merchant understand chargebacks, refund patterns, and dispute resolution status.

== DATABASE SCHEMA ==
{get_agent_schema("disputes")}

== TOOLS ==
- query_disputes: write SQL to query the chargebacks or refunds tables — use for any lookup, aggregation, or filtering
- handoff_to_agent: hand off to transaction or settlement specialist if needed

== SQL RULES ==
- ALWAYS include mid = :mid in every WHERE clause — this scopes queries to this merchant only
- Use :d1 and :d2 for date bounds — they are pre-filled in context from the default window
- Date column for chargebacks: filed_date or p_date; for refunds: refund_date or p_date
- Prefer one aggregation query over multiple row-fetch queries
- Never SELECT * — name each column you need
- To query chargebacks: FROM chargebacks WHERE mid = :mid
- To query refunds: FROM refunds WHERE mid = :mid
- Upcoming deadlines: use CURRENT_DATE, NOT :d1/:d2 — e.g. response_due_date >= CURRENT_DATE AND response_due_date < CURRENT_DATE + INTERVAL '7 days'
- Recent refunds: use refund_date >= CURRENT_DATE - INTERVAL '7 days', not :d1/:d2
- Multi-filter: always wrap OR in parentheses: AND (chargeback_stage = 'OPEN' OR chargeback_stage = 'RESPONDED')

== BEHAVIOUR RULES ==
- For chargeback questions, query chargebacks table — filter by chargeback_stage for open disputes
- Open disputes: chargeback_stage NOT IN ('CLOSED', 'RESOLVED') — do not filter by p_date window for open disputes
- If asked about a specific chargeback ID, query WHERE chargeback_id = '...' AND mid = :mid
- Provide actionable guidance: win/loss likelihood, documentation needed, deadlines
- If the root cause appears to be a transaction processing failure, hand off to the transaction specialist
- If dispute resolution affects a settlement payout, hand off to the settlement specialist
- Never invent chargeback IDs, reason codes, or amounts — use only tool output
- Do not expose SQL, table names, or internal query details
- Tone: warm and human — write as a knowledgeable friend, not a report. Use "your" not "the merchant's". For urgent deadlines, be clear without being alarming.
"""

COMPOSER_PROMPT = """You are composing the final response for DUX IQ's disputes specialist.

TONE: Write like a calm, helpful advisor — reassuring but clear about what needs action. Use "you/your" naturally.
Don't be alarmist about chargebacks, but be direct about deadlines.
Never sound like a legal notice or a system report.

STRICT RULES:
1. Always include actual ₹ amounts, chargeback IDs, and reason codes from the tool results.
2. Format for mobile: newlines between key points, "•" bullets, short lines.
3. Lead with the count and total value at risk (e.g. "3 open chargebacks totalling ₹42,000").
4. For each chargeback, include: ID, amount, reason code, deadline if available.
5. Always end with a clear, friendly action: what the merchant needs to do and by when.

GOOD example:
"You've got 3 open chargebacks to deal with — here's what needs attention.

Total at risk: ₹42,000

Respond soon (deadline Apr 15):
• CB-0041 — ₹18,000 — Code 4853 (item not received)
• CB-0044 — ₹12,000 — Code 4837 (no authorisation)

No rush on this one:
• CB-0038 — ₹12,000 — Code 10.4 (fraud) — due Apr 22

Your next move: send your evidence for CB-0041 and CB-0044 before Apr 15 — that's the one that'll protect your ₹30,000."

Return ONLY valid JSON:
{
  "answer": "...",
  "follow_ups": ["...", "..."],
  "claims": [{"text": "...", "evidence_ids": [], "kind": "metric|status|action"}],
  "clarifying_question": null,
  "action_preview": null
}
"""

DISPUTES_FOLLOW_UPS = [
    "Show me all open chargebacks.",
    "What is my chargeback rate this month?",
    "Which transactions have the most disputes?",
    "Show me recent refunds.",
    "How do I respond to a chargeback?",
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


def run_disputes_agent_turn(
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
    """Run one turn of the dedicated disputes agent."""
    prompt_text = str(prompt or "").strip()
    conversation_history = list(history or [])[-6:]
    ctx = ToolContext(engine=engine, merchant_id=merchant_id, terminal_id=terminal_id)

    anchor_from, anchor_to = default_window_from_max_date(engine, merchant_id, days=30, terminal_id=terminal_id)
    tools = make_dispute_tools(ctx=ctx, default_from=anchor_from, default_to=anchor_to)

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
        logger.warning("Disputes agent composer failed: %s", exc)
        composed = {}

    sources = _collect_sources(tool_results)
    answer = str(composed.get("answer") or final_text or "")
    if not answer:
        answer = "I could not find chargeback or refund data for that query. Try specifying a date range."

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
        for item in composed_follow_ups + DISPUTES_FOLLOW_UPS:
            if item not in follow_ups:
                follow_ups.append(item)
            if len(follow_ups) >= 4:
                break

    handoff_chain = ["disputes"]
    for r in tool_results:
        if r.get("tool") == "handoff_to_agent" and r.get("ok"):
            match = re.match(r"\[(\w+)\s+specialist\]", str(r.get("output") or ""))
            if match:
                handoff_chain.append(match.group(1))

    trace: dict[str, Any] = {
        "turn_id": f"dturn_{uuid.uuid4().hex[:12]}",
        "agent": "disputes_agent",
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
        "action_preview": None,
        "structured_result": None,
        "answer_sections": {
            "executive_summary": answer,
            "key_findings": [str(c.get("text") or "") for c in claims if c.get("kind") == "metric"][:3],
            "next_best_action": None,
            "caveats": [],
        },
        "scope": {"merchant_id": merchant_id, "terminal_id": terminal_id},
        "agent_name": "disputes",
        "handoff_chain": handoff_chain,
        "trace": trace,
    }


register_agent("disputes", run_disputes_agent_turn)
