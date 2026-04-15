"""
settlement_agent.py — Dedicated settlement surface agent for DUX IQ (Surface 1).

Lighter and faster than the general agent:
- 4 settlement tools only (vs 30+ in the general agent)
- Settlement-focused prompts — no noise from terminal/dispute/KPI tool descriptions
- max_steps=3 — enough for detail fetch + shortfall explain + cashflow
- context_object injection — when merchant opens chat from a specific settlement,
  the settlement_id is pre-seeded into the agent context so they can ask
  "why is this less than expected?" without typing the ID.
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from app.copilot.toolcalling import _make_llm, _invoke_with_rate_limit

from app.copilot.toolcalling import default_window_from_max_date, invoke_with_tools, make_settlement_tools
from app.copilot.tools import ToolContext
from app.intelligence.chat_reasoning import validate_reasoning_output
from app.agent.handoff import make_handoff_tool, register_agent
from app.agent.schema_registry import get_agent_schema

logger = logging.getLogger("settlement_agent")

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

def _build_system_prompt() -> str:
    return f"""You are DUX IQ, the settlement intelligence assistant.

You help the merchant understand their settlements, payouts, and deductions.

== DATABASE SCHEMA ==
{get_agent_schema("settlement")}

== TOOLS ==
- query_settlements: write SQL to query the settlements table — use for any lookup, aggregation, or filtering
- explain_settlement_shortfall: attribute a payout shortfall across MDR, GST, TDS, chargebacks, reserve
- cashflow_snapshot: pre-built summary of settlement counts by status and pending totals

== SQL RULES ==
- ALWAYS include mid = :mid in every WHERE clause — this scopes queries to this merchant only
- Use :d1 and :d2 for date bounds — they are pre-filled in context from the default window
- When active_settlement_id is present in the payload, ALWAYS add AND settlement_id = :settlement_id
  to your WHERE clause — :settlement_id is pre-filled. Do NOT query the full date window for
  single-settlement questions.
- Prefer one aggregation query over multiple row-fetch queries
- For "how much X" questions on a specific settlement: SELECT the exact column, filter by settlement_id
- Date column for filtering: p_date (date) or settlement_date (date)
- Never SELECT * — name each column you need
- "Last payout" / "most recent payout" / "last settlement": use ORDER BY settlement_date DESC LIMIT 1, NOT SUM()
- "Pending settlements": filter settlement_status IN ('PENDING', 'HELD') — NOT just 'PENDING' alone
- "MDR rate" or "MDR percentage": compute SUM(mdr_deducted)/SUM(gross_amount)*100 — NEVER return raw mdr_deducted amount as a rate
- Multi-status filter: always wrap OR in parentheses: AND (settlement_status = 'HELD' OR settlement_status = 'DELAYED')
- Relative dates from :d2: "last week" = p_date >= :d2::date - 7; "last month" = p_date >= :d2::date - 30

== BEHAVIOUR RULES ==
- If active_settlement_id is in the payload, your FIRST query must use settlement_id = :settlement_id
- Never invent amounts, IDs, or dates — use only what the tool returns
- If the question is outside settlements (terminals, disputes, transactions), say so clearly
- Answer concisely: direct answer first, supporting detail second
- Do not expose SQL, table names, or internal mechanics to the merchant
- Tone: warm and human — write as a knowledgeable friend, not a report. Use "your" not "the merchant's". Acknowledge bad news with brief empathy before diving into numbers.
"""

COMPOSER_PROMPT = """You are composing the final response for DUX IQ's settlement specialist.

TONE: Write like a sharp, friendly analyst — warm and direct, not robotic. Use "you/your" naturally.
When the news is bad, briefly acknowledge it ("Looks like your payout took a hit this month.") before the numbers.
When the news is good, say so ("Good news — your payout is up this month.").
Never sound like a system report.

STRICT RULES:
1. Every claim MUST include actual numbers from the tool results (₹ amounts, %, counts, IDs). No vague statements.
2. If you have partial data, use it — state what you found and what is still unclear.
3. Format for mobile: use newlines to separate key points. Use "•" for bullet points. Keep lines short.
4. Lead with the single most important number (e.g. the net payout amount or the drop amount).
5. Never say "held settlement and open chargebacks" without naming the IDs and amounts.

GOOD answer example:
"Looks like your payout dipped this month — here's what happened.

Your net payout was ₹2,14,320 — down ₹38,450 from last month's ₹2,52,770.

What caused the drop:
• Settlement S0261 is HELD (₹28,000) — reason: KYC pending
• Chargeback deductions: ₹7,200 (3 open disputes)
• MDR + GST: ₹3,250

One thing to action: resolving the KYC issue will release ₹28,000 back to you."

BAD answer example (do NOT do this):
"The payout drop is due to a held settlement and open chargebacks."

Return ONLY valid JSON:
{
  "answer": "...",
  "follow_ups": ["...", "..."],
  "claims": [{"text": "...", "evidence_ids": [...], "kind": "metric|status|action"}],
  "clarifying_question": null,
  "action_preview": null
}
"""

SETTLEMENT_FOLLOW_UPS = [
    "Break down the deductions on this settlement.",
    "Why is this settlement still pending?",
    "Compare this with last month's settlements.",
    "Show me the net vs gross for recent settlements.",
    "Are any settlements past their expected date?",
    "What fees were deducted from this payout?",
]

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
            parsed = json.loads(match.group(0))
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}


def _build_context_prefix(context_object: dict[str, Any] | None) -> str:
    """Convert context_object into a plain-text prefix injected into the user payload.

    When the merchant taps "Ask DUX IQ" from a specific settlement screen, the
    frontend passes context_object = {"type": "settlement", "id": "S123", "metadata": {...}}.
    This prefix tells the agent exactly what the merchant is looking at so they
    can ask "why is this less?" without typing the settlement ID.
    """
    if not isinstance(context_object, dict):
        return ""
    obj_type = str(context_object.get("type") or "").strip().lower()
    obj_id = str(context_object.get("id") or "").strip()
    metadata = context_object.get("metadata") or {}

    if obj_type != "settlement" or not obj_id:
        return ""

    parts = [f"The merchant is currently viewing settlement {obj_id}."]
    if isinstance(metadata, dict):
        if metadata.get("amount"):
            parts.append(f"Displayed amount: {metadata['amount']}.")
        if metadata.get("status"):
            parts.append(f"Status shown on screen: {metadata['status']}.")
        if metadata.get("date"):
            parts.append(f"Settlement date: {metadata['date']}.")
    parts.append(
        f"IMPORTANT: scope every SQL query to this specific settlement — "
        f"always include `AND settlement_id = '{obj_id}'` in the WHERE clause. "
        f"Do NOT query the full date window; query only settlement_id = '{obj_id}'."
    )
    return " ".join(parts)


def _select_follow_ups(
    composed_follow_ups: list[str],
    *,
    has_shortfall: bool = False,
    has_pending: bool = False,
) -> list[str]:
    selected: list[str] = []
    for item in composed_follow_ups:
        text = str(item or "").strip()
        if text and text not in selected:
            selected.append(text)
        if len(selected) >= 4:
            return selected

    # Fill from settlement-specific defaults
    pool = list(SETTLEMENT_FOLLOW_UPS)
    if has_shortfall:
        pool.insert(0, "Break down the deductions on this settlement.")
    if has_pending:
        pool.insert(0, "Why is this settlement still pending?")

    for item in pool:
        if item not in selected:
            selected.append(item)
        if len(selected) >= 4:
            break
    return selected[:4]


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
    internal_patterns = [
        re.compile(r"\bthe query was adjusted\b", re.IGNORECASE),
        re.compile(r"\busing the correct table\b", re.IGNORECASE),
        re.compile(r"\bcorrect table\b", re.IGNORECASE),
        re.compile(r"\bquery\b.*\b(table|column|sql|adjusted|rewritten)\b", re.IGNORECASE),
    ]
    sentences = re.split(r"(?<=[.!?])\s+", text)
    filtered = [s for s in sentences if s and not any(p.search(s) for p in internal_patterns)]
    return " ".join(filtered).strip() if filtered else text


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_settlement_agent_turn(
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
    """Run one turn of the dedicated settlement agent.

    Parameters
    ----------
    context_object:
        Screen-level context passed by the client when the merchant opens the
        chat from a specific settlement screen.
        Shape: {"type": "settlement", "id": "<settlement_id>", "metadata": {...}}
        When present, the agent is pre-seeded with the settlement ID so the
        merchant can ask questions without explicitly mentioning it.
    """
    prompt_text = str(prompt or "").strip()
    conversation_history = list(history or [])[-6:]
    ctx = ToolContext(engine=engine, merchant_id=merchant_id, terminal_id=terminal_id)

    anchor_from, anchor_to = default_window_from_max_date(engine, merchant_id, days=30, terminal_id=terminal_id)

    # Resolve active_settlement_id early so we can pass it to the tool factory
    active_settlement_id = (
        str(context_object.get("id") or "").strip()
        if isinstance(context_object, dict) and str(context_object.get("type") or "").lower() == "settlement"
        else str((memory_context or {}).get("selected_entities", {}).get("settlement_id") or "").strip()
    )

    tools = make_settlement_tools(
        ctx=ctx,
        default_from=anchor_from,
        default_to=anchor_to,
        active_settlement_id=active_settlement_id or None,
    )

    if not _disable_handoff:
        handoff_tool = make_handoff_tool(
            allowed_targets=["transaction", "terminal"],
            engine=engine,
            merchant_id=merchant_id,
            terminal_id=terminal_id,
            context_object=context_object or {},
            history=list(history or [])[-6:],
            current_depth=_handoff_depth,
        )
        tools = tools + [handoff_tool]

    context_prefix = _build_context_prefix(context_object)

    user_payload: dict[str, Any] = {
        "merchant_id": merchant_id,
        "prompt": prompt_text,
        "history": conversation_history,
        "memory_context": memory_context or {},
        "default_window": {"from_date": anchor_from, "to_date": anchor_to},
    }
    if context_prefix:
        user_payload["screen_context"] = context_prefix
    if active_settlement_id:
        user_payload["active_settlement_id"] = active_settlement_id

    tool_calls, tool_results, final_text = invoke_with_tools(
        system=_build_system_prompt(),
        user=user_payload,
        tools=tools,
        temperature=0.1,
        max_steps=3,
    )

    # Compose structured response
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
        logger.warning("Settlement agent composer failed: %s", exc)
        composed = {}

    sources = _collect_sources(tool_results)
    answer = _sanitize_answer(str(composed.get("answer") or final_text or ""))
    if not answer:
        answer = "I could not find reliable evidence to answer that. Could you check the settlement ID or date range?"

    clarifying_question = composed.get("clarifying_question") if isinstance(composed.get("clarifying_question"), dict) else None
    if clarifying_question and not clarifying_question.get("question"):
        clarifying_question = None
    if clarifying_question and not answer:
        answer = clarifying_question["question"]

    claims = [item for item in list(composed.get("claims") or []) if isinstance(item, dict)]

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
        validation = {"validation_status": "clean", "validation_issues": [], "verification_summary": "N/A", "display_notice": None}

    # Detect answer shape for follow-up hints
    answer_lower = answer.lower()
    has_shortfall = any(w in answer_lower for w in ("shortfall", "deducted", "less than expected", "mdr", "tds"))
    has_pending = any(w in answer_lower for w in ("pending", "held", "not yet settled"))

    follow_ups = (
        []
        if clarifying_question
        else _select_follow_ups(
            [str(f).strip() for f in list(composed.get("follow_ups") or []) if str(f).strip()],
            has_shortfall=has_shortfall,
            has_pending=has_pending,
        )
    )

    trace: dict[str, Any] = {
        "turn_id": f"sturn_{uuid.uuid4().hex[:12]}",
        "agent": "settlement_agent",
        "scope": {"merchant_id": merchant_id, "terminal_id": terminal_id},
        "context_object": context_object,
        "active_settlement_id": active_settlement_id or None,
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
        "agent_name": "settlement",
        "handoff_chain": (
            ["settlement"] + [
                m.group(1)
                for r in tool_results
                if r.get("tool") == "handoff_to_agent" and r.get("ok")
                for m in [__import__("re").match(r"\[(\w+)\s+specialist\]", str(r.get("output") or ""))]
                if m
            ]
        ),
        "trace": trace,
    }


register_agent("settlement", run_settlement_agent_turn)
