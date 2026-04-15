"""
transaction_agent.py — Dedicated transaction & KPI agent for DUX IQ.

6 tools: list_transactions, get_transaction_detail, compute_kpis,
         compare_kpis, verify_failure_drivers, end_to_end_analysis
max_steps: 4  (deeper analysis often needs KPI + failure + comparison)
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from app.copilot.toolcalling import _make_llm, _invoke_with_rate_limit

from app.copilot.toolcalling import default_window_from_max_date, invoke_with_tools, make_transaction_tools
from app.copilot.tools import ToolContext
from app.intelligence.chat_reasoning import validate_reasoning_output
from app.agent.handoff import make_handoff_tool, register_agent

logger = logging.getLogger("transaction_agent")

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

def _build_system_prompt() -> str:
    return """You are DUX IQ, the transaction and payment intelligence specialist.

You help the merchant understand their payment flows, KPIs, failure rates, and transaction health.

== TOOLS ==
- query_transactions: write SQL to query the transaction_features table — use for any lookup, aggregation, or filtering
- compute_kpis: pre-built success rate, volume, GMV — optionally grouped by payment_mode, day, or hour
- compare_kpis: compare two time windows (A vs B) to spot trends
- verify_failure_drivers: top failure reasons by response_code or payment_mode
- end_to_end_analysis: bundled health check — KPIs + failures + terminal performance
- handoff_to_agent: hand off to settlement or disputes specialist if needed

== SQL RULES ==
- ALWAYS include merchant_id = :mid in every WHERE clause
- Use :d1 and :d2 for date bounds — they are pre-filled from context
- Date column: p_date (date) or initiated_at (timestamp)
- Prefer ONE aggregation query (GROUP BY) over multiple sequential queries
- For "how much X" or "how many Y": use SUM/COUNT in a single query — not multiple queries
- Never SELECT * — name each column
- response_code '00' = approved; all other codes = declined
- Hour analysis: SELECT hour_of_day, COUNT(*), success_rate in ONE GROUP BY query — never return hours alone without rates
- Temporal comparisons (this week vs last week, this month vs last month): use DATE_TRUNC or a single query with CASE WHEN to split periods — do NOT run two separate queries when one will do
- Date offsets from :d2: "last 7 days" = p_date >= :d2::date - 7; "last 30 days" = p_date >= :d2::date - 30
- Multi-status filter: always wrap OR in parentheses: AND (status = 'FAILED' OR status = 'TIMEOUT')

== BEHAVIOUR RULES ==
- Use verify_failure_drivers for failure-by-mode/code questions — it's a single call
- For trend questions, prefer compare_kpis — it handles period comparison in one tool call
- For "revenue is down" diagnosis: call end_to_end_analysis first, identify the dominant signal, then answer — do NOT say "could be all of the above"
- Only hand off to settlement/disputes if the merchant explicitly asks about those domains
- Do NOT call handoff_to_agent for comparison, trend, or KPI questions — answer from available data
- Never invent transaction IDs, amounts, or response codes — use only tool output
- Do not expose SQL, table names, or internal query details
- Tone: warm and human — write as a knowledgeable friend, not a report. Use "your" not "the merchant's". Acknowledge bad news with brief empathy before diving into numbers.
"""

COMPOSER_PROMPT = """You are composing the final response for DUX IQ's transaction specialist.

TONE: Write like a sharp, friendly analyst — warm and direct, not robotic. Use "you/your" naturally.
When the news is bad, briefly acknowledge it ("Seems like your payments have been struggling lately.") before the numbers.
When things look healthy, say so ("Your payments are in good shape this month.").
Never sound like a system report.

STRICT RULES:
1. Every claim MUST include real numbers (%, ₹ amounts, counts, response codes). No vague descriptions.
2. Format for mobile: newlines between key points, "•" bullets, short lines.
3. Lead with the headline metric (success rate %, GMV ₹, failure count).
4. For failure analysis: always name the top response code and payment mode with their counts.
5. Never say "failures are increasing" without giving the before/after numbers.

GOOD example:
"Your payments are mostly healthy — here's the full picture.

Success rate this month: 94.2% (2,681 of 2,792 attempts).

Where the failures are coming from:
• Response code 91 (issuer unavailable): 40 failures — ₹1,34,230 at risk
• Response code UNKNOWN: 44 failures — ₹20,58,000 at risk
• UPI: 76 failures (3.6% fail rate)
• CARD: 35 failures (5.2% fail rate)"

Return ONLY valid JSON:
{
  "answer": "...",
  "follow_ups": ["...", "..."],
  "claims": [{"text": "...", "evidence_ids": [], "kind": "metric|status|action"}],
  "clarifying_question": null,
  "action_preview": null
}
"""

TRANSACTION_FOLLOW_UPS = [
    "What is my payment success rate this month?",
    "Which payment modes are failing most?",
    "Show me failed transactions in the last 7 days.",
    "How does this compare to last month?",
    "Are there any unusual failure spikes?",
    "Which response codes are causing the most failures?",
]

# ---------------------------------------------------------------------------
# Helpers (shared pattern from settlement_agent.py)
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


def _sanitize_answer(answer: str) -> str:
    text = str(answer or "").strip()
    patterns = [
        re.compile(r"\bthe query was adjusted\b", re.IGNORECASE),
        re.compile(r"\busing the correct table\b", re.IGNORECASE),
        re.compile(r"\bquery\b.*\b(table|column|sql|adjusted|rewritten)\b", re.IGNORECASE),
    ]
    sentences = re.split(r"(?<=[.!?])\s+", text)
    filtered = [s for s in sentences if s and not any(p.search(s) for p in patterns)]
    return " ".join(filtered).strip() if filtered else text


def _select_follow_ups(composed: list[str]) -> list[str]:
    selected: list[str] = []
    for item in composed:
        text = str(item or "").strip()
        if text and text not in selected:
            selected.append(text)
        if len(selected) >= 4:
            return selected
    for item in TRANSACTION_FOLLOW_UPS:
        if item not in selected:
            selected.append(item)
        if len(selected) >= 4:
            break
    return selected[:4]


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_transaction_agent_turn(
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
    """Run one turn of the dedicated transaction agent."""
    prompt_text = str(prompt or "").strip()
    conversation_history = list(history or [])[-6:]
    ctx = ToolContext(engine=engine, merchant_id=merchant_id, terminal_id=terminal_id)

    anchor_from, anchor_to = default_window_from_max_date(engine, merchant_id, days=30, terminal_id=terminal_id)
    tools = make_transaction_tools(ctx=ctx, default_from=anchor_from, default_to=anchor_to)

    if not _disable_handoff:
        handoff_tool = make_handoff_tool(
            allowed_targets=["settlement", "disputes"],
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
        "tool_results": [
            {"tool": r.get("tool"), "ok": r.get("ok"), "output": r.get("output")}
            for r in tool_results
        ],
        "agent_draft": str(final_text or ""),
    }
    try:
        composed_raw = _invoke_with_rate_limit(llm, [
            SystemMessage(content=COMPOSER_PROMPT),
            HumanMessage(content=json.dumps(composer_payload, ensure_ascii=False, indent=2, default=str)),
        ])
        composed = _extract_json(getattr(composed_raw, "content", str(composed_raw)))
    except Exception as exc:
        logger.warning("Transaction agent composer failed: %s", exc)
        composed = {}

    sources = _collect_sources(tool_results)
    answer = _sanitize_answer(str(composed.get("answer") or final_text or ""))
    if not answer:
        answer = "I could not find sufficient data to answer that. Try specifying a date range or transaction ID."

    claims = [item for item in list(composed.get("claims") or []) if isinstance(item, dict)]
    clarifying_question = composed.get("clarifying_question") if isinstance(composed.get("clarifying_question"), dict) else None
    if clarifying_question and not clarifying_question.get("question"):
        clarifying_question = None

    if not clarifying_question:
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
        )
    else:
        validation = {"validation_status": "clean", "validation_issues": [], "display_notice": None}

    follow_ups = (
        []
        if clarifying_question
        else _select_follow_ups([str(f).strip() for f in list(composed.get("follow_ups") or []) if str(f).strip()])
    )

    # Check if any handoff happened (handoff tool result contains "[X specialist]:")
    handoff_chain = ["transaction"]
    for r in tool_results:
        if r.get("tool") == "handoff_to_agent" and r.get("ok"):
            out = str(r.get("output") or "")
            match = re.match(r"\[(\w+)\s+specialist\]", out)
            if match:
                handoff_chain.append(match.group(1))

    trace: dict[str, Any] = {
        "turn_id": f"tturn_{uuid.uuid4().hex[:12]}",
        "agent": "transaction_agent",
        "scope": {"merchant_id": merchant_id, "terminal_id": terminal_id},
        "default_window": {"from_date": anchor_from, "to_date": anchor_to},
        "tool_calls": [{"name": str(c.get("name") or ""), "args": c.get("args") or {}} for c in tool_calls],
        "evidence_ids": sources,
    }
    if debug:
        trace["tool_results"] = [
            {"tool": r.get("tool"), "ok": r.get("ok"), "output": r.get("output")}
            for r in tool_results
        ]

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
        "agent_name": "transaction",
        "handoff_chain": handoff_chain,
        "trace": trace,
    }


# Register with handoff system
register_agent("transaction", run_transaction_agent_turn)
