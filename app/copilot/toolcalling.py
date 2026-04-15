from __future__ import annotations

import datetime as dt
import json
import logging
import threading
import time
from collections import deque
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool, tool
from langchain_core.callbacks import StreamingStdOutCallbackHandler
from langchain_ollama import ChatOllama
from langchain_groq import ChatGroq

from config import Config
from .kb import reindex_kb, search_kb
from .tools import (
    ToolContext,
    assess_credit_fit,
    cashflow_snapshot,
    compute_kpis,
    compare_kpis,
    end_to_end_analysis,
    explain_settlement_shortfall,
    geo_drift_check,
    get_chargeback_detail,
    get_merchant_context,
    get_merchant_lending_offers,
    get_settlement_detail,
    get_transaction_detail,
    intelligence_probe,
    list_chargebacks,
    list_refunds,
    list_settlements,
    list_transactions,
    propose_and_create_merchant_action,
    sql_database,
    terminal_health_summary,
    terminal_issue_correlator,
    terminal_performance,
    verify_failure_drivers,
)

logger = logging.getLogger("copilot_toolcalling")


# ---------------------------------------------------------------------------
# Groq rate limiter — prevents intra-loop 429s without full agent restart
# ---------------------------------------------------------------------------

class _GroqRateLimiter:
    """Rate limiter for Groq free tier: 30 RPM / 6000 TPM.

    Enforces two guards:
    1. Max 28 calls per 60s window (RPM headroom)
    2. Min 2s gap between consecutive calls (spreads TPM usage across the window
       so a burst of large requests does not exhaust the rolling TPM budget)
    """

    _MAX_CALLS = 28
    _WINDOW_S = 60.0
    _MIN_CALL_GAP_S = 4.0   # minimum seconds between consecutive LLM calls (Groq free tier: 6000 TPM)
    _lock = threading.Lock()
    _timestamps: deque = deque()
    _last_call_ts: float = 0.0

    @classmethod
    def wait_if_needed(cls) -> None:
        if not Config.GROQ_API_KEY:
            return
        with cls._lock:
            now = time.monotonic()

            # Enforce minimum gap between consecutive calls
            gap_needed = cls._MIN_CALL_GAP_S - (now - cls._last_call_ts)
            if gap_needed > 0:
                time.sleep(gap_needed)
                now = time.monotonic()

            cutoff = now - cls._WINDOW_S
            while cls._timestamps and cls._timestamps[0] < cutoff:
                cls._timestamps.popleft()
            if len(cls._timestamps) >= cls._MAX_CALLS:
                oldest = cls._timestamps[0]
                sleep_for = (oldest + cls._WINDOW_S) - now + 0.1
                if sleep_for > 0:
                    logger.info("Groq rate limit: sleeping %.1fs before next LLM call", sleep_for)
                    time.sleep(sleep_for)
                cutoff = time.monotonic() - cls._WINDOW_S
                while cls._timestamps and cls._timestamps[0] < cutoff:
                    cls._timestamps.popleft()
            cls._last_call_ts = time.monotonic()
            cls._timestamps.append(cls._last_call_ts)

    @classmethod
    def on_429(cls, retry_after_s: float = 10.0) -> None:
        """Call when a 429 is caught — back off and clear the window tracking."""
        logger.warning("Groq 429 caught inside loop — sleeping %.1fs", retry_after_s)
        time.sleep(retry_after_s)
        with cls._lock:
            cls._timestamps.clear()


def _strip_think_blocks(msg: Any) -> Any:
    """Remove <think>...</think> blocks emitted by Qwen3 and similar reasoning models.

    Handles both closed blocks (<think>...</think>) and unclosed ones (model cut off
    mid-think). Always returns a new AIMessage so Pydantic immutability is not an issue.
    """
    if msg is None:
        return msg
    content = getattr(msg, "content", None)
    if not isinstance(content, str) or "<think>" not in content.lower():
        return msg
    import re as _re
    from langchain_core.messages import AIMessage
    # Remove closed blocks
    cleaned = _re.sub(r"<think>[\s\S]*?</think>", "", content, flags=_re.IGNORECASE)
    # Remove unclosed block (model cut off mid-think — everything from <think> to end)
    cleaned = _re.sub(r"<think>[\s\S]*$", "", cleaned, flags=_re.IGNORECASE)
    cleaned = cleaned.strip()
    return AIMessage(content=cleaned)


def _invoke_with_rate_limit(llm_bound, messages: list, max_retries: int = 3):
    """Wrap a single llm.invoke() call with rate-limit handling.

    413 (payload too large) is NOT retried — the same payload will always fail.
    429 (rate limit) is retried with exponential backoff.
    Think blocks (<think>...</think>) from reasoning models are stripped before returning.
    """
    for attempt in range(max_retries):
        _GroqRateLimiter.wait_if_needed()
        try:
            return _strip_think_blocks(llm_bound.invoke(messages))
        except Exception as exc:
            err = str(exc).lower()
            is_413 = "413" in err or "payload too large" in err or "request too large" in err
            is_429 = "429" in err or "rate limit" in err or "rate_limit" in err
            if is_413:
                # Never retry — reduce context and fail fast
                logger.warning("Groq 413 payload too large — not retrying (context too long)")
                raise
            elif is_429:
                wait = min(15 * (2 ** attempt), 60)
                _GroqRateLimiter.on_429(wait)
                if attempt == max_retries - 1:
                    raise
            else:
                raise
    raise RuntimeError("unreachable")


def _iso(d: dt.date) -> str:
    return d.isoformat()


def default_window_from_max_date(engine: Any, merchant_id: str, days: int = 30, terminal_id: str | None = None) -> tuple[str, str]:
    """Default window anchored to latest available p_date for this merchant.

    Mirrors runtime._default_window but kept here to avoid import cycles.
    """
    try:
        from sqlalchemy import text

        max_date = None
        with engine.connect() as conn:
            if terminal_id:
                try:
                    max_date = conn.execute(
                        text(
                            f"""
                            SELECT MAX(p_date)
                            FROM {Config.QUERY_SOURCE_TABLE}
                            WHERE merchant_id = :mid
                              AND terminal_id = :tid
                            """
                        ),
                        {"mid": merchant_id, "tid": str(terminal_id)},
                    ).scalar()
                except Exception:
                    max_date = None
            if max_date is None:
                max_date = conn.execute(
                    text(f"SELECT MAX(p_date) FROM {Config.QUERY_SOURCE_TABLE} WHERE merchant_id = :mid"),
                    {"mid": merchant_id},
                ).scalar()

        if max_date:
            end = max_date + dt.timedelta(days=1)
            start = end - dt.timedelta(days=days)
            return _iso(start), _iso(end)
    except Exception:
        pass

    today = dt.date.today()
    return _iso(today - dt.timedelta(days=days)), _iso(today + dt.timedelta(days=1))


def make_tools(*, ctx: ToolContext, default_from: str, default_to: str) -> list[BaseTool]:
    """Create LangChain tool wrappers.

    Note: We keep args optional where reasonable and fill from default window,
    so the model can call tools without always supplying dates.
    """

    @tool("get_merchant_context")
    def get_merchant_context_tool() -> dict:
        """Fetch merchant profile + risk + KYC snapshot (merchant-scoped)."""
        return get_merchant_context(ctx)

    @tool("get_merchant_lending_offers")
    def get_merchant_lending_offers_tool() -> dict:
        """Call this tool EXCLUSIVELY if the user asks ANY question about:
        - funding options
        - loans or lending
        - borrowing money
        - overdraft or cash advances
        - eligibility for credit

        DO NOT call merchant_profile instead. ALWAYS use this tool for anything related to funding/loans.
        """
        return get_merchant_lending_offers(ctx)

    @tool("merchant_profile")
    def merchant_profile_tool() -> dict:
        """Alias: merchant profile snapshot (same output as get_merchant_context)."""
        return get_merchant_context(ctx)

    @tool("compute_kpis")
    def compute_kpis_tool(
        from_date: str | None = None,
        to_date: str | None = None,
        group_by: str = "payment_mode",
    ) -> dict:
        """Compute KPI aggregates over a date range (merchant-scoped)."""
        return compute_kpis(
            ctx,
            from_date=from_date or default_from,
            to_date=to_date or default_to,
            group_by=group_by,
        )

    @tool("list_transactions")
    def list_transactions_tool(
        from_date: str | None = None,
        to_date: str | None = None,
        limit: int = 50,
    ) -> dict:
        """List transactions in a date range (merchant-scoped, paginated by limit)."""
        return list_transactions(
            ctx,
            from_date=from_date or default_from,
            to_date=to_date or default_to,
            limit=limit,
        )

    @tool("get_transaction_detail")
    def get_transaction_detail_tool(tx_id: str | int) -> dict:
        """Fetch a single transaction record by tx_id (merchant-scoped)."""
        return get_transaction_detail(ctx, tx_id=str(tx_id))

    @tool("list_settlements")
    def list_settlements_tool(
        from_date: str | None = None,
        to_date: str | None = None,
        limit: int = 50,
    ) -> dict:
        """List settlements for the merchant in a date range."""
        return list_settlements(
            ctx,
            from_date=from_date or default_from,
            to_date=to_date or default_to,
            limit=limit,
        )

    @tool("get_settlement_detail")
    def get_settlement_detail_tool(settlement_id: str | int) -> dict:
        """Fetch one settlement and (if available) reconciliation breakdown."""
        return get_settlement_detail(ctx, settlement_id=str(settlement_id))

    @tool("explain_settlement_shortfall")
    def explain_settlement_shortfall_tool(
        from_date: str | None = None,
        to_date: str | None = None,
        expected_amount: str | None = None,
        received_amount: str | None = None,
        limit: int = 20,
    ) -> dict:
        """Explain a payout shortfall using settlement deduction fields when available."""
        return explain_settlement_shortfall(
            ctx,
            from_date=from_date or default_from,
            to_date=to_date or default_to,
            expected_amount=float(expected_amount) if expected_amount is not None else None,
            received_amount=float(received_amount) if received_amount is not None else None,
            limit=limit,
        )

    @tool("list_chargebacks")
    def list_chargebacks_tool(
        from_date: str | None = None,
        to_date: str | None = None,
        status: str = "open",
        limit: int = 50,
    ) -> dict:
        """List chargebacks (optionally date-filtered) for the merchant."""
        return list_chargebacks(
            ctx,
            status=status,
            from_date=from_date or default_from,
            to_date=to_date or default_to,
            limit=limit,
        )

    @tool("get_chargeback_detail")
    def get_chargeback_detail_tool(chargeback_id: str | int) -> dict:
        """Fetch a single chargeback record by chargeback_id (merchant-scoped)."""
        return get_chargeback_detail(ctx, chargeback_id=str(chargeback_id))

    @tool("list_refunds")
    def list_refunds_tool(
        from_date: str | None = None,
        to_date: str | None = None,
        limit: int = 50,
    ) -> dict:
        """List refunds in a date range (merchant-scoped)."""
        return list_refunds(
            ctx,
            from_date=from_date or default_from,
            to_date=to_date or default_to,
            limit=limit,
        )

    @tool("compare_kpis")
    def compare_kpis_tool(
        from_date_a: str | None = None,
        to_date_a: str | None = None,
        from_date_b: str | None = None,
        to_date_b: str | None = None,
        window_a: dict | None = None,
        window_b: dict | None = None,
        group_by: str = "payment_mode",
    ) -> dict:
        """Compare KPI windows A vs B for the merchant.

        Accepts either explicit dates (from_date_*/to_date_*) or window dicts
        ({from_date,to_date} or {from,to}).
        """

        def _from_window(win: dict[str, Any] | None, key_a: str, key_b: str) -> str | None:
            if not isinstance(win, dict):
                return None
            return str(win.get(key_a) or win.get(key_b) or "").strip() or None

        a_from = from_date_a or _from_window(window_a, "from_date", "from") or default_from
        a_to = to_date_a or _from_window(window_a, "to_date", "to") or default_to
        b_from = from_date_b or _from_window(window_b, "from_date", "from")
        b_to = to_date_b or _from_window(window_b, "to_date", "to")

        # If B window is omitted, auto-use previous period matching A's span.
        if not b_from or not b_to:
            try:
                a1 = dt.date.fromisoformat(a_from)
                a2 = dt.date.fromisoformat(a_to)
                span = max(1, (a2 - a1).days)
                b_to_date = a1
                b_from_date = a1 - dt.timedelta(days=span)
                b_from = b_from or b_from_date.isoformat()
                b_to = b_to or b_to_date.isoformat()
            except Exception:
                b_from = b_from or default_from
                b_to = b_to or default_to

        return compare_kpis(
            ctx,
            from_date_a=a_from,
            to_date_a=a_to,
            from_date_b=b_from,
            to_date_b=b_to,
            group_by=group_by,
        )

    @tool("terminal_performance")
    def terminal_performance_tool(
        from_date: str | None = None,
        to_date: str | None = None,
        limit: int = 20,
    ) -> dict:
        """Rank terminals/devices by attempts and success rate (merchant-scoped)."""
        return terminal_performance(
            ctx,
            from_date=from_date or default_from,
            to_date=to_date or default_to,
            limit=limit,
        )

    @tool("assess_credit_fit")
    def assess_credit_fit_tool(from_date: str | None = None, to_date: str | None = None) -> dict:
        """Compute an indicative fit assessment for volume-based working-capital credit."""
        return assess_credit_fit(
            ctx,
            from_date=from_date or default_from,
            to_date=to_date or default_to,
        )

    @tool("cashflow_snapshot")
    def cashflow_snapshot_tool(from_date: str | None = None, to_date: str | None = None) -> dict:
        """Summarize settlement timing and cashflow signals (counts/amounts/past-expected)."""
        return cashflow_snapshot(
            ctx,
            from_date=from_date or default_from,
            to_date=to_date or default_to,
        )

    @tool("terminal_health_summary")
    def terminal_health_summary_tool(
        from_date: str | None = None,
        to_date: str | None = None,
        group_by: str = "tid_hour",
        limit: int = 50,
    ) -> dict:
        """Summarize terminal health snapshots (network/battery/printer) for RCA."""
        return terminal_health_summary(
            ctx,
            from_date=from_date or default_from,
            to_date=to_date or default_to,
            group_by=group_by,
            limit=limit,
        )

    @tool("geo_drift_check")
    def geo_drift_check_tool(from_date: str | None = None, to_date: str | None = None, tid: str | None = None) -> dict:
        """Check whether terminals show location drift/deviation (geo factor evidence)."""
        return geo_drift_check(
            ctx,
            from_date=from_date or default_from,
            to_date=to_date or default_to,
            tid=tid,
        )

    @tool("terminal_issue_correlator")
    def terminal_issue_correlator_tool(
        from_date: str | None = None,
        to_date: str | None = None,
        flag: str = "low_network_strength",
        limit: int = 20,
    ) -> dict:
        """Correlate terminal health flags with elevated payment failure rates."""
        return terminal_issue_correlator(
            ctx,
            from_date=from_date or default_from,
            to_date=to_date or default_to,
            flag=flag,
            limit=limit,
        )

    @tool("end_to_end_analysis")
    def end_to_end_analysis_tool(from_date: str | None = None, to_date: str | None = None) -> dict:
        """Run a bundled merchant health check (KPIs, failures, terminal health, etc.)."""
        return end_to_end_analysis(
            ctx,
            from_date=from_date or default_from,
            to_date=to_date or default_to,
        )

    @tool("intelligence_probe")
    def intelligence_probe_tool(window_days: int = 30, enable_reasoning: bool = False) -> dict:
        """Run the intelligence runner (signals + recommendations) for the merchant."""
        return intelligence_probe(ctx, window_days=window_days, enable_reasoning=enable_reasoning)

    @tool("propose_and_create_merchant_action")
    def propose_and_create_merchant_action_tool(**kwargs) -> dict:
        """Propose (and optionally create) a merchant action; supports confirmation token."""
        # Two-step write confirmation is handled inside the underlying function.
        return propose_and_create_merchant_action(ctx, **kwargs)

    @tool("kb_search")
    def kb_search_tool(query: str, top_k: int = 5) -> dict:
        """Search the bank knowledge base (bank_kb/*.md) for relevant snippets."""
        return search_kb(query=query, top_k=top_k)

    @tool("knowledge_base")
    def knowledge_base_tool(query: str, top_k: int = 5) -> dict:
        """Alias: search bank knowledge base snippets and citations."""
        return search_kb(query=query, top_k=top_k)

    @tool("kb_reindex")
    def kb_reindex_tool() -> dict:
        """Rebuild the bank knowledge base index from bank_kb/*.md."""
        return reindex_kb()

    @tool("sql_database")
    def sql_database_tool(query: str, parameters: dict | None = None, limit: int = 100) -> dict:
        """Run a read-only SQL query scoped to active merchant via :mid placeholder."""
        return sql_database(ctx, query=query, parameters=parameters, limit=limit)

    @tool("verify_failure_drivers")
    def verify_failure_drivers_tool(
        from_date: str | None = None,
        to_date: str | None = None,
        by: str = "response_code",
        limit: int = 5,
    ) -> dict:
        """Deterministically rank failure drivers by response_code or payment_mode."""
        return verify_failure_drivers(
            ctx,
            from_date=from_date or default_from,
            to_date=to_date or default_to,
            by="payment_mode" if str(by).strip().lower() == "payment_mode" else "response_code",
            limit=limit,
        )

    @tool("startup_kpis")
    def startup_kpis_tool(from_date: str | None = None, to_date: str | None = None) -> dict:
        """Return one-shot merchant profile + KPI snapshot for operating brief generation."""
        d1 = from_date or default_from
        d2 = to_date or default_to

        profile = get_merchant_context(ctx)
        kpis_overall = compute_kpis(
            ctx,
            from_date=d1,
            to_date=d2,
            group_by="none",
        )
        kpis_mode = compute_kpis(
            ctx,
            from_date=d1,
            to_date=d2,
            group_by="payment_mode",
        )

        summary_row = {}
        if isinstance(kpis_overall, dict):
            rows = kpis_overall.get("rows")
            if isinstance(rows, list) and rows:
                summary_row = rows[0] if isinstance(rows[0], dict) else {}

        evidence: list[str] = [f"startup_kpis:{ctx.merchant_id}:{d1}:{d2}"]
        if getattr(ctx, "terminal_id", None):
            evidence.append(f"terminal:{ctx.terminal_id}")
        for payload in (kpis_overall, kpis_mode):
            if isinstance(payload, dict):
                for ev in payload.get("evidence") or []:
                    sev = str(ev)
                    if sev and sev not in evidence:
                        evidence.append(sev)

        return {
            "merchant_profile": profile,
            "window": {"from": d1, "to": d2},
            "kpi_snapshot": summary_row,
            "kpi_by_mode": (kpis_mode.get("rows") if isinstance(kpis_mode, dict) else []) or [],
            "evidence": evidence[:80],
        }

    return [
        merchant_profile_tool,
        get_merchant_context_tool,
        get_merchant_lending_offers_tool,
        compute_kpis_tool,
        list_transactions_tool,
        get_transaction_detail_tool,
        list_settlements_tool,
        get_settlement_detail_tool,
        explain_settlement_shortfall_tool,
        list_chargebacks_tool,
        get_chargeback_detail_tool,
        list_refunds_tool,
        compare_kpis_tool,
        terminal_performance_tool,
        terminal_health_summary_tool,
        geo_drift_check_tool,
        terminal_issue_correlator_tool,
        end_to_end_analysis_tool,
        intelligence_probe_tool,
        propose_and_create_merchant_action_tool,
        startup_kpis_tool,
        sql_database_tool,
        verify_failure_drivers_tool,
        knowledge_base_tool,
        kb_search_tool,
        kb_reindex_tool,
        assess_credit_fit_tool,
        cashflow_snapshot_tool,
    ]


def make_settlement_tools(
    *, ctx: ToolContext, default_from: str, default_to: str,
    active_settlement_id: str | None = None,
) -> list[BaseTool]:
    """Settlement agent tool set: sql_database + two computation tools."""

    _sid = str(active_settlement_id).strip() if active_settlement_id else None

    @tool("query_settlements")
    def query_settlements_tool(query: str, parameters: dict | None = None) -> dict:
        """Execute a read-only SQL query against the settlements table.

        Always include mid = :mid in the WHERE clause to scope to this merchant.
        Use :d1 and :d2 for date bounds — they are pre-filled from context.
        When a specific settlement is in context, use :settlement_id in the WHERE clause
        — it is pre-filled and scopes the query to that single settlement.
        Prefer aggregation queries (SUM, AVG, COUNT) over fetching many rows.

        Examples:
          -- Single settlement lookup (when settlement_id is in context):
          SELECT settlement_id, gross_amount, mdr_deducted, gst_on_mdr, tds_deducted,
                 chargeback_deductions, reserve_held, net_settlement_amount,
                 settlement_status, hold_reason
          FROM settlements WHERE mid = :mid AND settlement_id = :settlement_id

          -- Aggregate over a date window:
          SELECT SUM(gst_on_mdr) FROM settlements WHERE mid = :mid AND p_date >= :d1 AND p_date < :d2

          -- List recent settlements:
          SELECT settlement_id, net_settlement_amount, settlement_status
          FROM settlements WHERE mid = :mid ORDER BY p_date DESC LIMIT 20
        """
        params = {"mid": ctx.merchant_id, "d1": default_from, "d2": default_to}
        if _sid:
            params["settlement_id"] = _sid
        if isinstance(parameters, dict):
            params.update(parameters)
        return sql_database(ctx, query=query, parameters=params)

    @tool("explain_settlement_shortfall")
    def explain_settlement_shortfall_tool(
        from_date: str | None = None,
        to_date: str | None = None,
        expected_amount: str | None = None,
        received_amount: str | None = None,
        limit: int = 20,
    ) -> dict:
        """Attribute a payout shortfall across deduction categories: MDR, GST, TDS, chargebacks, reserve."""
        return explain_settlement_shortfall(
            ctx,
            from_date=from_date or default_from,
            to_date=to_date or default_to,
            expected_amount=float(expected_amount) if expected_amount is not None else None,
            received_amount=float(received_amount) if received_amount is not None else None,
            limit=limit,
        )

    @tool("cashflow_snapshot")
    def cashflow_snapshot_tool(from_date: str | None = None, to_date: str | None = None) -> dict:
        """Settlement cashflow summary: counts by status, pending vs settled totals, overdue count."""
        return cashflow_snapshot(
            ctx,
            from_date=from_date or default_from,
            to_date=to_date or default_to,
        )

    return [
        query_settlements_tool,
        explain_settlement_shortfall_tool,
        cashflow_snapshot_tool,
    ]


def _make_llm(temperature: float, streaming: bool = False):
    """Return a ChatGroq or ChatOllama instance based on config."""
    callbacks = [StreamingStdOutCallbackHandler()] if streaming else []
    if Config.GROQ_API_KEY:
        return ChatGroq(
            model=Config.GROQ_MODEL,
            api_key=Config.GROQ_API_KEY,
            temperature=temperature,
            streaming=streaming,
            callbacks=callbacks,
        )
    return ChatOllama(
        model=Config.OLLAMA_MODEL,
        base_url=Config.OLLAMA_BASE_URL,
        temperature=temperature,
        callbacks=callbacks,
    )


def invoke_with_tools(
    *,
    system: str,
    user: dict[str, Any],
    tools: list[BaseTool],
    temperature: float = 0.1,
    max_steps: int = 1,
    streaming: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
    """Invoke the model with tools bound, optionally allowing multi-step tool loops.

    Returns:
    - tool_calls: flat list of tool call dicts across all steps
    - tool_results: tool execution results across all steps
    - final_text: last assistant text content from the loop (may be empty)
    """
    max_steps = max(1, min(int(max_steps or 1), 12))

    llm = _make_llm(temperature, streaming=streaming).bind_tools(tools)

    messages = [
        SystemMessage(content=system),
        HumanMessage(content=json.dumps(user, ensure_ascii=False, indent=2, default=str)),
    ]

    all_tool_calls: list[dict[str, Any]] = []
    all_results: list[dict[str, Any]] = []
    final_text = ""

    for _ in range(max_steps):
        try:
            ai = _invoke_with_rate_limit(llm, messages)
        except Exception as exc:
            err_lower = str(exc).lower()
            if "413" in err_lower or "payload too large" in err_lower or "request too large" in err_lower:
                # Context window exceeded — stop the loop and return whatever we have
                logger.warning("Groq 413 mid-loop — returning partial results (%d tool calls so far)", len(all_tool_calls))
                break
            raise
        messages.append(ai)

        ai_text = getattr(ai, "content", "")
        if isinstance(ai_text, str):
            final_text = ai_text.strip() or final_text
        elif ai_text is not None:
            text_fallback = str(ai_text).strip()
            if text_fallback:
                final_text = text_fallback

        tool_calls = getattr(ai, "tool_calls", None) or []
        if not tool_calls:
            break

        for tc in tool_calls:
            name = str(tc.get("name") or "")
            args = tc.get("args") or {}
            call_id = str(tc.get("id") or f"call_{len(all_tool_calls) + 1}")
            tool_fn: BaseTool | None = next((t for t in tools if t.name == name), None)
            if not tool_fn:
                result = {"tool": name, "ok": False, "output": None, "error": f"Unknown tool: {name}"}
                all_results.append(result)
                logger.info(
                    "\n┌─ TOOL CALL ─────────────────────────────\n"
                    "│  name : %s\n│  args : %s\n"
                    "└─ RESULT ────────────────────────────────\n"
                    "│  ok   : False\n│  error: Unknown tool\n"
                    "└─────────────────────────────────────────",
                    name, json.dumps(args, default=str)
                )
                messages.append(
                    ToolMessage(
                        tool_call_id=call_id,
                        name=name,
                        content=json.dumps({"error": result["error"]}, ensure_ascii=False),
                    )
                )
                continue

            logger.info(
                "\n┌─ TOOL CALL ─────────────────────────────\n"
                "│  name : %s\n│  args : %s\n"
                "└─────────────────────────────────────────",
                name, json.dumps(args, ensure_ascii=False, default=str)
            )

            try:
                out = tool_fn.invoke(args)
                result = {"tool": name, "ok": True, "output": out, "error": None}
                tool_content = json.dumps(out, ensure_ascii=False, default=str)
                logger.info(
                    "\n┌─ TOOL RESULT ───────────────────────────\n"
                    "│  tool : %s  ok=True\n│  output (truncated):\n%s\n"
                    "└─────────────────────────────────────────",
                    name, tool_content[:800]
                )
            except Exception as exc:
                result = {"tool": name, "ok": False, "output": None, "error": str(exc)}
                tool_content = json.dumps({"error": str(exc)}, ensure_ascii=False, default=str)
                logger.info(
                    "\n┌─ TOOL RESULT ───────────────────────────\n"
                    "│  tool : %s  ok=False\n│  error: %s\n"
                    "└─────────────────────────────────────────",
                    name, exc
                )

            all_results.append(result)
            messages.append(
                ToolMessage(
                    tool_call_id=call_id,
                    name=name,
                    content=tool_content[:800],
                )
            )

        all_tool_calls.extend(tool_calls)

    return all_tool_calls, all_results, final_text


# ---------------------------------------------------------------------------
# Specialised tool sets — one per agent domain
# ---------------------------------------------------------------------------

def make_transaction_tools(*, ctx: ToolContext, default_from: str, default_to: str) -> list[BaseTool]:
    """Transaction agent tool set: sql_database + KPI computation tools."""

    @tool("query_transactions")
    def query_transactions_tool(query: str, parameters: dict | None = None) -> dict:
        """Execute a read-only SQL query against the transaction_features table.

        Always include merchant_id = :mid in the WHERE clause.
        Use :d1 and :d2 for date bounds.
        Prefer aggregation over fetching individual rows unless a specific transaction is requested.

        Examples:
          SELECT transaction_fact_id, amount_rupees, status, payment_mode, response_code, initiated_at
          FROM transaction_features WHERE merchant_id = :mid AND p_date >= :d1 AND p_date < :d2 AND status = 'FAILED' LIMIT 50

          SELECT response_code, COUNT(*) AS failures, SUM(amount_rupees) AS failed_gmv
          FROM transaction_features WHERE merchant_id = :mid AND p_date >= :d1 AND p_date < :d2 AND status = 'FAILED'
          GROUP BY response_code ORDER BY failures DESC

          SELECT DATE(p_date) AS day, COUNT(*) AS attempts,
                 SUM(CASE WHEN status='SUCCESS' THEN 1 ELSE 0 END) AS successes
          FROM transaction_features WHERE merchant_id = :mid AND p_date >= :d1 AND p_date < :d2
          GROUP BY day ORDER BY day
        """
        params = {"mid": ctx.merchant_id, "d1": default_from, "d2": default_to}
        if isinstance(parameters, dict):
            params.update(parameters)
        return sql_database(ctx, query=query, parameters=params)

    @tool("compute_kpis")
    def compute_kpis_tool(
        from_date: str | None = None,
        to_date: str | None = None,
        group_by: str | None = None,
    ) -> dict:
        """Compute payment KPIs (success rate, GMV, volume) grouped by payment_mode, day, hour, or response_code."""
        return compute_kpis(
            ctx,
            from_date=from_date or default_from,
            to_date=to_date or default_to,
            group_by=group_by,
        )

    @tool("compare_kpis")
    def compare_kpis_tool(
        from_date_a: str | None = None,
        to_date_a: str | None = None,
        from_date_b: str | None = None,
        to_date_b: str | None = None,
    ) -> dict:
        """Compare KPIs between two time windows (A vs B) — use for trend and regression questions."""
        return compare_kpis(
            ctx,
            from_date_a=from_date_a or default_from,
            to_date_a=to_date_a or default_to,
            from_date_b=from_date_b or default_from,
            to_date_b=to_date_b or default_to,
        )

    @tool("verify_failure_drivers")
    def verify_failure_drivers_tool(
        from_date: str | None = None,
        to_date: str | None = None,
        by: str = "response_code",
    ) -> dict:
        """Rank top failure drivers by response_code or payment_mode with failure rate and GMV impact."""
        return verify_failure_drivers(
            ctx,
            from_date=from_date or default_from,
            to_date=to_date or default_to,
            by=by,
        )

    @tool("end_to_end_analysis")
    def end_to_end_analysis_tool(
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> dict:
        """Bundled health check: KPIs + failure drivers + terminal performance in one call."""
        return end_to_end_analysis(
            ctx,
            from_date=from_date or default_from,
            to_date=to_date or default_to,
        )

    return [
        query_transactions_tool,
        compute_kpis_tool,
        compare_kpis_tool,
        verify_failure_drivers_tool,
        end_to_end_analysis_tool,
    ]


def make_dispute_tools(*, ctx: ToolContext, default_from: str, default_to: str) -> list[BaseTool]:
    """Disputes agent tool set: single sql_database tool covering chargebacks and refunds."""

    @tool("query_disputes")
    def query_disputes_tool(query: str, parameters: dict | None = None) -> dict:
        """Execute a read-only SQL query against the chargebacks or refunds tables.

        Always include mid = :mid in the WHERE clause.
        Use :d1 and :d2 for date bounds.

        Key columns:
          chargebacks: chargeback_id, chargeback_amount, chargeback_stage, chargeback_reason_code,
                       filed_date, response_due_date, resolution_outcome, card_network, settlement_id
          refunds:     refund_id, refund_amount, refund_status, refund_type, refund_date, settlement_id

        chargeback_stage values: OPEN, CHARGEBACK
        resolution_outcome values: WON, LOST (only set after resolution)
        Open disputes: WHERE chargeback_stage NOT IN ('CLOSED', 'RESOLVED')
        Overdue:       WHERE response_due_date < CURRENT_DATE AND chargeback_stage NOT IN ('CLOSED','RESOLVED')

        Examples:
          SELECT chargeback_id, chargeback_amount, chargeback_reason_code, response_due_date
          FROM chargebacks WHERE mid = :mid AND chargeback_stage NOT IN ('CLOSED','RESOLVED')
          ORDER BY response_due_date ASC

          SELECT chargeback_reason_code, COUNT(*) AS count, SUM(chargeback_amount) AS total_exposure
          FROM chargebacks WHERE mid = :mid AND filed_date >= :d1 AND filed_date < :d2
          GROUP BY chargeback_reason_code ORDER BY count DESC

          SELECT refund_id, refund_amount, refund_status, refund_date
          FROM refunds WHERE mid = :mid AND p_date >= :d1 AND p_date < :d2 LIMIT 50
        """
        params = {"mid": ctx.merchant_id, "d1": default_from, "d2": default_to}
        if isinstance(parameters, dict):
            params.update(parameters)
        return sql_database(ctx, query=query, parameters=params)

    return [query_disputes_tool]


def make_terminal_tools(*, ctx: ToolContext, default_from: str, default_to: str) -> list[BaseTool]:
    """Terminal agent tool set: sql_database + two Python-computation tools."""

    @tool("query_terminals")
    def query_terminals_tool(query: str, parameters: dict | None = None) -> dict:
        """Execute a read-only SQL query against terminal_health_snapshots or transaction_features.

        Pass your SQL as the "query" string argument. Always include mid = :mid in WHERE clause.
        Use :d1 and :d2 for date bounds (pre-filled automatically).

        terminal_health_snapshots columns:
          tid, mid, captured_at, battery_status (0-100), ram_rom_utilization (0-100),
          low_network_strength (bool), quick_battery_drainage (bool),
          latitude_longitude_deviation (bool), printer_status, latitude, longitude

        transaction_features columns (for terminal performance):
          terminal_id, merchant_id, p_date, status, amount_rupees, payment_mode
        """
        params = {"mid": ctx.merchant_id, "d1": default_from, "d2": default_to}
        if isinstance(parameters, dict):
            params.update(parameters)
        return sql_database(ctx, query=query, parameters=params)

    @tool("geo_drift_check")
    def geo_drift_check_tool(
        from_date: str | None = None,
        to_date: str | None = None,
        tid: str | None = None,
    ) -> dict:
        """Detect geographic location deviations using haversine distance — flags terminals that moved."""
        return geo_drift_check(
            ctx,
            from_date=from_date or default_from,
            to_date=to_date or default_to,
            tid=tid,
        )

    @tool("terminal_issue_correlator")
    def terminal_issue_correlator_tool(
        from_date: str | None = None,
        to_date: str | None = None,
        flag: str = "low_network_strength",
    ) -> dict:
        """Correlate health flags (low_network_strength / quick_battery_drainage / geo_deviation) with failure rates."""
        return terminal_issue_correlator(
            ctx,
            from_date=from_date or default_from,
            to_date=to_date or default_to,
            flag=flag,
        )

    return [
        query_terminals_tool,
        geo_drift_check_tool,
        terminal_issue_correlator_tool,
    ]


def make_growth_tools(*, ctx: ToolContext, default_from: str, default_to: str) -> list[BaseTool]:
    """Growth agent tool set: sql_database for ad-hoc revenue queries + three computation tools."""

    @tool("query_growth_data")
    def query_growth_data_tool(query: str, parameters: dict | None = None) -> dict:
        """Execute a read-only SQL query for revenue trends, GMV analysis, or settlement history.

        Always include merchant_id = :mid (transaction_features) or mid = :mid (settlements).
        Use :d1 and :d2 for date bounds.

        Examples:
          SELECT DATE_TRUNC('month', p_date) AS month, SUM(amount_rupees) AS gmv
          FROM transaction_features WHERE merchant_id = :mid AND status = 'SUCCESS'
          AND p_date >= :d1 AND p_date < :d2 GROUP BY month ORDER BY month

          SELECT SUM(net_settlement_amount) AS total_settled, COUNT(*) AS settlements
          FROM settlements WHERE mid = :mid AND p_date >= :d1 AND p_date < :d2
        """
        params = {"mid": ctx.merchant_id, "d1": default_from, "d2": default_to}
        if isinstance(parameters, dict):
            params.update(parameters)
        return sql_database(ctx, query=query, parameters=params)

    @tool("get_merchant_lending_offers")
    def get_merchant_lending_offers_tool() -> dict:
        """Fetch available working capital and lending offers with eligibility limits."""
        return get_merchant_lending_offers(ctx)

    @tool("assess_credit_fit")
    def assess_credit_fit_tool(
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> dict:
        """Evaluate credit eligibility: fit band (likely/possible/unlikely), policy checks, stability score."""
        return assess_credit_fit(
            ctx,
            from_date=from_date or default_from,
            to_date=to_date or default_to,
        )

    @tool("intelligence_probe")
    def intelligence_probe_tool(window_days: int = 30) -> dict:
        """Surface proactive growth signals and ranked recommendations with estimated impact."""
        return intelligence_probe(ctx, window_days=window_days)

    return [
        query_growth_data_tool,
        get_merchant_lending_offers_tool,
        assess_credit_fit_tool,
        intelligence_probe_tool,
    ]
