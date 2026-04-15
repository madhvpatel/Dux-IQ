"""
terminal_agent.py — Dedicated terminal health agent for DUX IQ.

4 tools: terminal_performance, terminal_health_summary, geo_drift_check, terminal_issue_correlator
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

from app.copilot.toolcalling import default_window_from_max_date, invoke_with_tools, make_terminal_tools
from app.copilot.tools import ToolContext
from app.intelligence.chat_reasoning import validate_reasoning_output
from app.agent.handoff import make_handoff_tool, register_agent
from app.agent.schema_registry import get_agent_schema

logger = logging.getLogger("terminal_agent")

def _build_system_prompt() -> str:
    return f"""You are DUX IQ, the terminal and device intelligence specialist.

You diagnose terminal hardware performance, geographic drift patterns, and device health issues.

== DATABASE SCHEMA ==
{get_agent_schema("terminal")}

== TOOLS ==
- query_terminals: write SQL to query the terminal_health_snapshots or transaction_features tables
- geo_drift_check: pre-built check for location deviations that may indicate misuse or misplacement
- terminal_issue_correlator: pre-built tool to correlate health flags (network/battery/geo) with payment failure rates
- handoff_to_agent: hand off to transaction or settlement specialist if needed

== SQL RULES ==
- ALWAYS include mid = :mid in every WHERE clause (terminal_health_snapshots uses mid)
- For transaction_features, use merchant_id = :mid
- Use :d1 and :d2 for date bounds — they are pre-filled in context from the default window
- Date column for terminal snapshots: captured_at (timestamp)
- Date column for transactions: p_date (date) or initiated_at (timestamp)
- Never SELECT * — name each column you need
- battery_status is a percentage (0-100); low_network_strength, quick_battery_drainage, latitude_longitude_deviation are booleans

== BEHAVIOUR RULES ==
- Always include terminal IDs (tid) in your answer when discussing specific devices
- For "which terminal is causing failures" questions, use terminal_issue_correlator
- For geographic anomalies, use geo_drift_check
- For aggregate health queries across terminals, use query_terminals with GROUP BY tid
- If asked about transaction KPIs or payment modes broadly, hand off to the transaction specialist
- If terminal downtime appears to affect a settlement batch, hand off to the settlement specialist
- Never invent terminal IDs, locations, or health scores — use only tool output
- Do not expose SQL, table names, or internal query details
- Tone: warm and human — write as a knowledgeable friend, not a report. Use "your" not "the merchant's". Be matter-of-fact about device issues — not alarming, just clear.
"""

COMPOSER_PROMPT = """You are composing the final response for DUX IQ's terminal specialist.

TONE: Write like a tech-savvy friend doing a quick device health check. Use "your terminal(s)" naturally.
Be matter-of-fact about issues — not alarmist, just clear on what needs attention and why.
Never sound like a system log dump.

STRICT RULES:
1. Always name specific terminal IDs (e.g. EP070270) with their actual metrics. No generic references.
2. Format for mobile: newlines between devices, "•" bullets, short lines.
3. Lead with the most critical finding (worst terminal, its failure rate and count).
4. For health issues: state the exact metric (battery %, signal flag %, failure rate) not just "low battery".
5. Rank terminals when comparing — give position and number.

GOOD example:
"Here's a quick health check on your terminals.

One to watch — EP070271:
• Failure rate: 17.8% (32 failures) — your weakest device right now
• Network: signal flagged as weak in recent checks
• Battery: stable

EP070270 is doing better:
• Failure rate: 3.0% (80 failures, 96.98% success)
• Network: flagged — worth checking connectivity
• Location: no anomalies

Worth looking at: EP070271's network signal — a quick reset or repositioning might clear those failures."

Return ONLY valid JSON:
{
  "answer": "...",
  "follow_ups": ["...", "..."],
  "claims": [{"text": "...", "evidence_ids": [], "kind": "metric|status|action"}],
  "clarifying_question": null,
  "action_preview": null
}
"""

TERMINAL_FOLLOW_UPS = [
    "Which terminal has the lowest success rate?",
    "Are any terminals showing battery issues?",
    "Show me terminals with weak network signal.",
    "Are there any geo location anomalies?",
    "Which terminal caused the most failures this week?",
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


def run_terminal_agent_turn(
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
    """Run one turn of the dedicated terminal agent."""
    prompt_text = str(prompt or "").strip()
    conversation_history = list(history or [])[-6:]
    ctx = ToolContext(engine=engine, merchant_id=merchant_id, terminal_id=terminal_id)

    anchor_from, anchor_to = default_window_from_max_date(engine, merchant_id, days=30, terminal_id=terminal_id)
    tools = make_terminal_tools(ctx=ctx, default_from=anchor_from, default_to=anchor_to)

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
    if terminal_id:
        user_payload["active_terminal_id"] = terminal_id

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
        logger.warning("Terminal agent composer failed: %s", exc)
        composed = {}

    sources = _collect_sources(tool_results)
    answer = str(composed.get("answer") or final_text or "")
    if not answer:
        answer = "No terminal data found for that query. Try specifying a terminal ID or date range."

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
        for item in composed_follow_ups + TERMINAL_FOLLOW_UPS:
            if item not in follow_ups:
                follow_ups.append(item)
            if len(follow_ups) >= 4:
                break

    handoff_chain = ["terminal"]
    for r in tool_results:
        if r.get("tool") == "handoff_to_agent" and r.get("ok"):
            match = re.match(r"\[(\w+)\s+specialist\]", str(r.get("output") or ""))
            if match:
                handoff_chain.append(match.group(1))

    trace: dict[str, Any] = {
        "turn_id": f"trmturn_{uuid.uuid4().hex[:12]}",
        "agent": "terminal_agent",
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
        "agent_name": "terminal",
        "handoff_chain": handoff_chain,
        "trace": trace,
    }


register_agent("terminal", run_terminal_agent_turn)
