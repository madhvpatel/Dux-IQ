import logging
import uuid
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import create_engine

from app.application.control_plane import ControlPlaneRouter, build_session_key
from app.application.control_plane.chat_memory import ChatMemoryService
from app.application.kernel.request_models import (
    ActorContext,
    CanonicalRequest,
    DeliveryContext,
    Lane,
    PolicyContext,
    RequestType,
    RequestSource,
    SessionContext,
    Surface,
    TenantContext,
    WorkspaceContext,
)
from app.application.workflows.live_context import LiveContextDeps
from app.application.workflows.merchant_surface import LiveSurfaceDeps
from app.application.workflows import live_context, merchant_surface
from app.data.actions import get_existing_action
from app.data.merchants import load_merchant_options
from app.data.proactive import get_background_proactive_card
from app.data.transactions import fetch_dashboard_metrics, list_transactions, terminal_performance
from app.data.disputes import list_chargebacks, chargeback_summary, list_refunds
from config import Config
from app.agent import schema_registry
from app.agent import (
    run_agent_turn,
    run_settlement_agent_turn,
    run_transaction_agent_turn,
    run_disputes_agent_turn,
    run_terminal_agent_turn,
    run_growth_agent_turn,
    route_and_execute,
)
from app.copilot.validation_server import _json_safe, pick_default_merchant_id
from app.dispute import extract_receipt_fields
from app.terminal import analyze_pos_error_image
from app.terminal.pax_errors import get_all_categories, get_errors_by_category, search_pax_errors
from app.merchant_os import (
    build_report_briefs,
    build_report_packs,
    cleanup_legacy_actions,
    confirm_background_proactive_card_action,
    confirm_merchant_action,
    ensure_background_proactive_refresh,
    get_background_refresh_status,
    get_merchant_os_snapshot,
    list_background_proactive_cards,
    preview_background_proactive_card_action,
    preview_merchant_action,
    scope_snapshot_to_terminal,
    terminal_scope_options,
    update_background_proactive_card_state,
    update_existing_action_details,
    update_existing_action_status,
)

logger = logging.getLogger("copilot_api")
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Bank Foundry API",
    description="Bank Foundry backend for separate merchant and bank-facing surfaces.",
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=Config.CORS_ALLOW_ORIGINS.split(",") if Config.CORS_ALLOW_ORIGINS != "*" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = create_engine(Config.DATABASE_URL)
schema_registry.build(engine)


class ContextObject(BaseModel):
    """Screen-level context passed by the client when the merchant opens the
    DUX IQ chat from a specific object (e.g. a settlement detail screen).

    Fields
    ------
    type     : the object type the merchant is viewing — "settlement", "transaction", "terminal", "payout"
    id       : the object's primary identifier (settlement_id, tx_id, etc.)
    metadata : optional lightweight snapshot of what's visible on screen,
               e.g. {"amount": 42000, "status": "PENDING", "date": "2025-03-15"}.
               The agent uses this to answer questions without an extra DB round-trip.
    """
    type: str
    id: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class AskRequest(BaseModel):
    merchant_id: Optional[str] = None
    prompt: str
    terminal_id: Optional[str] = None
    thread_scope: Optional[str] = None
    history: list[dict[str, str]] = Field(default_factory=list)
    debug: bool = False
    context_object: Optional[ContextObject] = None


class ProactiveRefreshRequest(BaseModel):
    merchant_id: Optional[str] = None
    days: int = 30
    force: bool = True


class ProactiveCardStateRequest(BaseModel):
    merchant_id: Optional[str] = None
    dedupe_key: str
    state: str = Field(..., pattern="^(NEW|ACKNOWLEDGED|DISMISSED|CONVERTED)$")
    card_notes: Optional[str] = None


class ProactiveCardPreviewRequest(BaseModel):
    merchant_id: Optional[str] = None
    dedupe_key: str


class ProactiveCardConfirmRequest(BaseModel):
    merchant_id: Optional[str] = None
    dedupe_key: str
    confirmation_token: str


class ActionPreviewRequest(BaseModel):
    merchant_id: Optional[str] = None
    action_type: str
    payload: dict[str, Any] = Field(default_factory=dict)


class ActionConfirmRequest(BaseModel):
    merchant_id: Optional[str] = None
    confirmation_token: str


class ActionStatusRequest(BaseModel):
    merchant_id: Optional[str] = None
    action_id: Any
    status: str


class ActionDetailsRequest(BaseModel):
    merchant_id: Optional[str] = None
    action_id: Any
    owner: Optional[str] = None
    notes: Optional[str] = None
    blocked_reason: Optional[str] = None
    follow_up_date: Optional[str] = None


class CleanupActionsRequest(BaseModel):
    merchant_id: Optional[str] = None




@app.get("/health")
async def health():
    return {"status": "ok"}


def _resolved_merchant_id(merchant_id: Optional[str]) -> str:
    resolved = str(merchant_id or "").strip() or pick_default_merchant_id(engine)
    if not resolved:
        raise HTTPException(status_code=400, detail="Merchant ID required")
    return resolved


def _live_context_deps() -> LiveContextDeps:
    return LiveContextDeps(
        engine=engine,
        json_safe=_json_safe,
        ensure_background_proactive_refresh=ensure_background_proactive_refresh,
        get_merchant_os_snapshot=get_merchant_os_snapshot,
        terminal_scope_options=terminal_scope_options,
        scope_snapshot_to_terminal=scope_snapshot_to_terminal,
        get_background_refresh_status=get_background_refresh_status,
        build_report_briefs=build_report_briefs,
        build_report_packs=build_report_packs,
    )


def _coerce_int_param(value: Any, default: int) -> int:
    raw = getattr(value, "default", value)
    try:
        return int(raw)
    except Exception:
        return int(default)


def _canonical_request(
    *,
    request_type: RequestType,
    surface: Surface,
    merchant_id: str | None = None,
    terminal_id: str | None = None,
    payload: dict[str, Any] | None = None,
    allow_write: bool = False,
    debug: bool = False,
    thread_scope: str | None = None,
    window_label: str | None = None,
    report_kind: str | None = None,
    job_name: str | None = None,
    actor_id: str = "api_caller",
    actor_role: str = "operator",
    lane: Lane | None = None,
    case_id: str | None = None,
    work_item_id: str | None = None,
    source: RequestSource | None = None,
) -> CanonicalRequest:
    resolved_mid = str(merchant_id or "").strip() or None
    session_key = build_session_key(
        request_type=request_type,
        surface=surface,
        merchant_id=resolved_mid,
        terminal_id=terminal_id,
        thread_scope=thread_scope,
        window_label=window_label,
        report_kind=report_kind,
        job_name=job_name,
        lane=lane.value if lane else None,
        case_id=case_id,
        work_item_id=work_item_id,
        source=source.value if source else None,
    )
    tenant_id = resolved_mid or "platform"
    tenant_type = "merchant" if resolved_mid else "platform"
    return CanonicalRequest(
        request_id=f"req_{uuid.uuid4().hex[:12]}",
        request_type=request_type,
        surface=surface,
        actor=ActorContext(actor_id=actor_id, actor_type="user", role=actor_role),
        tenant=TenantContext(tenant_id=tenant_id, tenant_type=tenant_type),
        workspace=WorkspaceContext(merchant_id=resolved_mid, terminal_id=terminal_id),
        session=SessionContext(session_key=session_key, thread_scope=thread_scope),
        lane=lane,
        case_id=case_id,
        work_item_id=work_item_id,
        source=source,
        payload=payload or {},
        policy_context=PolicyContext(allow_write=allow_write, debug=debug),
        delivery=DeliveryContext(mode="sync_response", target="http_response"),
        debug=debug,
    )


def _live_surface_deps() -> LiveSurfaceDeps:
    context_deps = _live_context_deps()
    return LiveSurfaceDeps(
        engine=engine,
        json_safe=_json_safe,
        pick_default_merchant_id=pick_default_merchant_id,
        merchant_options=lambda limit: load_merchant_options(
            engine,
            limit=limit,
            query_source_table=Config.QUERY_SOURCE_TABLE,
            default_merchant_id_loader=pick_default_merchant_id,
        ),
        merchant_snapshot=lambda merchant_id, terminal_id, *, days=30, refresh=True: live_context.build_merchant_snapshot(
            merchant_id,
            terminal_id,
            days=days,
            refresh=refresh,
            deps=context_deps,
        ),
        merchant_label=live_context.merchant_label,
        report_payload=lambda snapshot: live_context.build_report_payload(snapshot, deps=context_deps),
        run_agent_turn=run_agent_turn,
        ensure_background_proactive_refresh=ensure_background_proactive_refresh,
        list_background_proactive_cards=list_background_proactive_cards,
        update_background_proactive_card_state=update_background_proactive_card_state,
        preview_background_proactive_card_action=preview_background_proactive_card_action,
        confirm_background_proactive_card_action=confirm_background_proactive_card_action,
        preview_merchant_action=preview_merchant_action,
        confirm_merchant_action=confirm_merchant_action,
        update_existing_action_status=update_existing_action_status,
        update_existing_action_details=update_existing_action_details,
        cleanup_legacy_actions=cleanup_legacy_actions,
        dashboard_metrics=lambda **kwargs: fetch_dashboard_metrics(engine, **kwargs),
        chat_memory_service=ChatMemoryService(engine),
    )


def _handle_merchant_options(request: CanonicalRequest) -> dict[str, Any]:
    return merchant_surface.handle_merchant_options(request, deps=_live_surface_deps())


def _handle_workspace_refresh(request: CanonicalRequest) -> dict[str, Any]:
    return merchant_surface.handle_workspace_refresh(request, deps=_live_surface_deps())


def _handle_report_build(request: CanonicalRequest) -> dict[str, Any]:
    return merchant_surface.handle_report_build(request, deps=_live_surface_deps())


def _handle_terminal_options(request: CanonicalRequest) -> dict[str, Any]:
    return merchant_surface.handle_terminal_options(request, deps=_live_surface_deps())


def _handle_chat_turn(request: CanonicalRequest) -> dict[str, Any]:
    return merchant_surface.handle_chat_turn(request, deps=_live_surface_deps())


def _handle_proactive_list(request: CanonicalRequest) -> dict[str, Any]:
    return merchant_surface.handle_proactive_list(request, deps=_live_surface_deps())


def _handle_proactive_refresh(request: CanonicalRequest) -> dict[str, Any]:
    return merchant_surface.handle_proactive_refresh(request, deps=_live_surface_deps())


def _handle_proactive_card_state(request: CanonicalRequest) -> dict[str, Any]:
    return merchant_surface.handle_proactive_card_state(request, deps=_live_surface_deps())


def _handle_proactive_action_preview(request: CanonicalRequest) -> dict[str, Any]:
    return merchant_surface.handle_proactive_action_preview(request, deps=_live_surface_deps())


def _handle_proactive_action_confirm(request: CanonicalRequest) -> dict[str, Any]:
    return merchant_surface.handle_proactive_action_confirm(request, deps=_live_surface_deps())


def _handle_action_preview(request: CanonicalRequest) -> dict[str, Any]:
    return merchant_surface.handle_action_preview(request, deps=_live_surface_deps())


def _handle_action_confirm(request: CanonicalRequest) -> dict[str, Any]:
    return merchant_surface.handle_action_confirm(request, deps=_live_surface_deps())


def _handle_action_status(request: CanonicalRequest) -> dict[str, Any]:
    return merchant_surface.handle_action_status(request, deps=_live_surface_deps())


def _handle_action_details(request: CanonicalRequest) -> dict[str, Any]:
    return merchant_surface.handle_action_details(request, deps=_live_surface_deps())


def _handle_action_cleanup(request: CanonicalRequest) -> dict[str, Any]:
    return merchant_surface.handle_action_cleanup(request, deps=_live_surface_deps())


def _handle_dashboard_query(request: CanonicalRequest) -> dict[str, Any]:
    return merchant_surface.handle_dashboard_query(request, deps=_live_surface_deps())


_CONTROL_PLANE_ROUTER = ControlPlaneRouter(
    handlers={
        RequestType.merchant_options.value: _handle_merchant_options,
        RequestType.workspace_refresh.value: _handle_workspace_refresh,
        RequestType.report_build.value: _handle_report_build,
        RequestType.terminal_options.value: _handle_terminal_options,
        RequestType.chat_turn.value: _handle_chat_turn,
        RequestType.proactive_list.value: _handle_proactive_list,
        RequestType.proactive_refresh.value: _handle_proactive_refresh,
        RequestType.proactive_card_state.value: _handle_proactive_card_state,
        RequestType.proactive_action_preview.value: _handle_proactive_action_preview,
        RequestType.proactive_action_confirm.value: _handle_proactive_action_confirm,
        RequestType.action_preview.value: _handle_action_preview,
        RequestType.action_confirm.value: _handle_action_confirm,
        RequestType.action_status.value: _handle_action_status,
        RequestType.action_details.value: _handle_action_details,
        RequestType.action_cleanup.value: _handle_action_cleanup,
        RequestType.dashboard_query.value: _handle_dashboard_query,
    }
)


@app.get("/api/v1/merchants/options")
async def get_merchant_options(limit: int = Query(25, ge=1, le=100)):
    limit_value = _coerce_int_param(limit, 25)
    request = _canonical_request(
        request_type=RequestType.merchant_options,
        surface=Surface.api,
        payload={"limit": limit_value},
    )
    return _CONTROL_PLANE_ROUTER.handle(request).payload


@app.get("/api/v1/merchant/snapshot")
async def get_merchant_snapshot(
    merchant_id: Optional[str] = None,
    terminal_id: Optional[str] = None,
    days: int = Query(30, ge=7, le=90),
):
    resolved_mid = _resolved_merchant_id(merchant_id)
    days_value = _coerce_int_param(days, 30)
    request = _canonical_request(
        request_type=RequestType.workspace_refresh,
        surface=Surface.workspace,
        merchant_id=resolved_mid,
        terminal_id=terminal_id,
        payload={"days": days_value},
        window_label=f"{days_value}d",
    )
    return _CONTROL_PLANE_ROUTER.handle(request).payload


@app.get("/api/v1/merchant/reports")
async def get_merchant_reports(
    merchant_id: Optional[str] = None,
    terminal_id: Optional[str] = None,
    days: int = Query(30, ge=7, le=90),
):
    resolved_mid = _resolved_merchant_id(merchant_id)
    days_value = _coerce_int_param(days, 30)
    request = _canonical_request(
        request_type=RequestType.report_build,
        surface=Surface.reports,
        merchant_id=resolved_mid,
        terminal_id=terminal_id,
        payload={"days": days_value},
        report_kind="merchant_reports",
        window_label=f"{days_value}d",
    )
    return _CONTROL_PLANE_ROUTER.handle(request).payload


@app.get("/api/v1/merchant/terminals")
async def get_terminal_options(
    merchant_id: Optional[str] = None,
    days: int = Query(30, ge=7, le=90),
):
    resolved_mid = _resolved_merchant_id(merchant_id)
    days_value = _coerce_int_param(days, 30)
    request = _canonical_request(
        request_type=RequestType.terminal_options,
        surface=Surface.workspace,
        merchant_id=resolved_mid,
        payload={"days": days_value},
        window_label=f"{days_value}d",
    )
    return _CONTROL_PLANE_ROUTER.handle(request).payload


@app.get("/api/v1/merchant/transactions")
async def get_merchant_transactions(
    merchant_id: Optional[str] = None,
    days: int = Query(30, ge=1, le=90),
    status: str = Query("ALL", pattern="^(ALL|SUCCESS|FAILURE)$"),
    limit: int = Query(50, ge=1, le=200),
):
    from app.copilot.toolcalling import default_window_from_max_date
    resolved_mid = _resolved_merchant_id(merchant_id)
    from_date, to_date = default_window_from_max_date(engine, resolved_mid, days=days)
    result = list_transactions(
        engine,
        merchant_id=resolved_mid,
        from_date=from_date,
        to_date=to_date,
        status=status,
        payment_mode="ALL",
        limit=limit,
        source_table=Config.QUERY_SOURCE_TABLE,
    )
    return {"transactions": result}


@app.get("/api/v1/merchant/terminal-performance")
async def get_terminal_performance(
    merchant_id: Optional[str] = None,
    days: int = Query(30, ge=1, le=90),
    limit: int = Query(20, ge=1, le=50),
):
    from app.copilot.toolcalling import default_window_from_max_date
    resolved_mid = _resolved_merchant_id(merchant_id)
    from_date, to_date = default_window_from_max_date(engine, resolved_mid, days=days)
    result = terminal_performance(
        engine,
        merchant_id=resolved_mid,
        from_date=from_date,
        to_date=to_date,
        limit=limit,
        source_table=Config.QUERY_SOURCE_TABLE,
    )
    return {"terminals": result}


@app.get("/api/v1/merchant/chargebacks")
async def get_chargebacks(
    merchant_id: Optional[str] = None,
    days: int = Query(90, ge=7, le=365),
    status: str = Query("all", pattern="^(open|closed|all)$"),
    limit: int = Query(100, ge=1, le=200),
):
    from app.copilot.toolcalling import default_window_from_max_date
    resolved_mid = _resolved_merchant_id(merchant_id)
    from_date, to_date = default_window_from_max_date(engine, resolved_mid, days=days)
    rows_result = list_chargebacks(
        engine,
        merchant_id=resolved_mid,
        status=status,
        from_date=from_date,
        to_date=to_date,
        limit=limit,
    )
    summary_result = chargeback_summary(
        engine,
        merchant_id=resolved_mid,
        from_date=from_date,
        to_date=to_date,
    )
    refunds_result = list_refunds(
        engine,
        merchant_id=resolved_mid,
        from_date=str(from_date),
        to_date=str(to_date),
        limit=50,
    )
    return {
        "chargebacks": rows_result,
        "summary": summary_result,
        "refunds": refunds_result,
    }


@app.post("/api/v1/ask")
async def ask_endpoint(req: AskRequest):
    """Router endpoint — dispatches to the appropriate specialized agent based on intent.

    Handles fan-out for cross-domain queries (e.g. settlement + transaction analysis
    in the same question). Falls back to the general 28-tool agent for ambiguous intents.
    """
    merchant_id = _resolved_merchant_id(req.merchant_id)
    terminal_id = req.terminal_id or None

    session_key = build_session_key(
        request_type=RequestType.chat_turn,
        surface=Surface.web_chat,
        merchant_id=merchant_id,
        terminal_id=terminal_id,
        thread_scope=req.thread_scope or "default",
    )
    memory_svc = ChatMemoryService(engine=engine)
    session_bundle = memory_svc.load_session(
        session_key=session_key,
        merchant_id=merchant_id,
        terminal_id=terminal_id,
        thread_scope=req.thread_scope or "default",
    )
    history = memory_svc.merged_history(session_bundle, request_history=req.history or [])
    memory_context = memory_svc.agent_memory_context(session_bundle, prompt=req.prompt)

    try:
        result = route_and_execute(
            engine,
            merchant_id=merchant_id,
            prompt=req.prompt,
            terminal_id=terminal_id,
            history=history,
            memory_context=memory_context,
            context_object=req.context_object.model_dump() if req.context_object else None,
            debug=True,
        )
    except Exception as exc:
        logger.exception("Error in ask_endpoint (router)")
        raise HTTPException(status_code=500, detail=str(exc))

    memory_svc.remember_turn(
        session_key=session_key,
        merchant_id=merchant_id,
        terminal_id=terminal_id,
        thread_scope=req.thread_scope or "default",
        prompt=req.prompt,
        payload=result,
    )
    return result


@app.post("/api/v1/ask/settlement")
async def ask_settlement_endpoint(req: AskRequest):
    """Dedicated settlement agent endpoint for Surface 1 (Merchant App).

    Use this endpoint when the merchant opens DUX IQ from the settlements/payout
    tab. It runs a lighter agent (4 tools, max 3 steps) instead of the full
    general agent, reducing latency and server load.

    If req.context_object is provided with type="settlement", the agent is
    pre-seeded with that settlement's ID so the merchant can ask questions like
    "why is this less than expected?" without typing the settlement ID.
    """
    merchant_id = _resolved_merchant_id(req.merchant_id)
    terminal_id = req.terminal_id or None
    thread_scope = req.thread_scope or "settlement"

    session_key = build_session_key(
        request_type=RequestType.chat_turn,
        surface=Surface.web_chat,
        merchant_id=merchant_id,
        terminal_id=terminal_id,
        thread_scope=thread_scope,
    )

    memory_svc = ChatMemoryService(engine=engine)
    session_bundle = memory_svc.load_session(
        session_key=session_key,
        merchant_id=merchant_id,
        terminal_id=terminal_id,
        thread_scope=thread_scope,
    )
    history = memory_svc.merged_history(session_bundle, request_history=req.history or [])
    memory_context = memory_svc.agent_memory_context(session_bundle, prompt=req.prompt)

    # If context_object carries a settlement_id, inject it into memory so
    # follow-up turns also know which settlement is active.
    if req.context_object and req.context_object.type == "settlement" and req.context_object.id:
        memory_context.setdefault("selected_entities", {})["settlement_id"] = req.context_object.id

    try:
        result = run_settlement_agent_turn(
            engine,
            merchant_id=merchant_id,
            prompt=req.prompt,
            terminal_id=terminal_id,
            history=history,
            memory_context=memory_context,
            context_object=req.context_object.model_dump() if req.context_object else None,
            debug=True,
        )
    except Exception as exc:
        logger.exception("Error in ask_settlement_endpoint")
        raise HTTPException(status_code=500, detail=str(exc))

    memory_svc.remember_turn(
        session_key=session_key,
        merchant_id=merchant_id,
        terminal_id=terminal_id,
        thread_scope=thread_scope,
        prompt=req.prompt,
        payload=result,
    )
    return result


# ---------------------------------------------------------------------------
# Specialized agent direct endpoints
# ---------------------------------------------------------------------------

def _make_direct_agent_endpoint(agent_fn, thread_scope_default: str):
    """Build a direct agent endpoint handler. Shared pattern for all 4 new agents."""
    async def handler(req: AskRequest):
        merchant_id = _resolved_merchant_id(req.merchant_id)
        terminal_id = req.terminal_id or None
        thread_scope = req.thread_scope or thread_scope_default

        session_key = build_session_key(
            request_type=RequestType.chat_turn,
            surface=Surface.web_chat,
            merchant_id=merchant_id,
            terminal_id=terminal_id,
            thread_scope=thread_scope,
        )
        memory_svc = ChatMemoryService(engine=engine)
        session_bundle = memory_svc.load_session(
            session_key=session_key,
            merchant_id=merchant_id,
            terminal_id=terminal_id,
            thread_scope=thread_scope,
        )
        history = memory_svc.merged_history(session_bundle, request_history=req.history or [])
        memory_context = memory_svc.agent_memory_context(session_bundle, prompt=req.prompt)

        try:
            result = agent_fn(
                engine,
                merchant_id=merchant_id,
                prompt=req.prompt,
                terminal_id=terminal_id,
                history=history,
                memory_context=memory_context,
                context_object=req.context_object.model_dump() if req.context_object else None,
                debug=True,
            )
        except Exception as exc:
            logger.exception("Error in direct agent endpoint")
            raise HTTPException(status_code=500, detail=str(exc))

        memory_svc.remember_turn(
            session_key=session_key,
            merchant_id=merchant_id,
            terminal_id=terminal_id,
            thread_scope=thread_scope,
            prompt=req.prompt,
            payload=result,
        )
        return result
    return handler


@app.post("/api/v1/ask/transactions")
async def ask_transactions_endpoint(req: AskRequest):
    """Transaction & KPI agent — payment flows, success rates, failure analysis."""
    return await _make_direct_agent_endpoint(run_transaction_agent_turn, "transactions")(req)


@app.post("/api/v1/ask/disputes")
async def ask_disputes_endpoint(req: AskRequest):
    """Disputes agent — chargebacks, refunds, dispute resolution."""
    return await _make_direct_agent_endpoint(run_disputes_agent_turn, "disputes")(req)


@app.post("/api/v1/ask/terminals")
async def ask_terminals_endpoint(req: AskRequest):
    """Terminal health agent — device performance, geo drift, issue correlation."""
    return await _make_direct_agent_endpoint(run_terminal_agent_turn, "terminals")(req)


@app.post("/api/v1/ask/growth")
async def ask_growth_endpoint(req: AskRequest):
    """Growth & credit agent — lending offers, credit fit, intelligence signals."""
    return await _make_direct_agent_endpoint(run_growth_agent_turn, "growth")(req)


@app.get("/api/v1/copilot/proactive")
async def get_proactive_nudges(
    merchant_id: Optional[str] = None,
    terminal_id: Optional[str] = None,
    lane: str = Query("operations", pattern="^(operations|growth|all)$"),
    days: int = Query(30, ge=7, le=90),
):
    resolved_mid = _resolved_merchant_id(merchant_id)
    days_value = _coerce_int_param(days, 30)
    request = _canonical_request(
        request_type=RequestType.proactive_list,
        surface=Surface.proactive_inbox,
        merchant_id=resolved_mid,
        terminal_id=terminal_id,
        payload={"lane": lane, "days": days_value},
        window_label=f"{days_value}d",
    )
    return _CONTROL_PLANE_ROUTER.handle(request).payload


@app.post("/api/v1/copilot/proactive/refresh")
async def refresh_proactive_cards(req: ProactiveRefreshRequest):
    merchant_id = _resolved_merchant_id(req.merchant_id)
    try:
        request = _canonical_request(
            request_type=RequestType.proactive_refresh,
            surface=Surface.proactive_inbox,
            merchant_id=merchant_id,
            payload={"days": int(req.days), "force": bool(req.force)},
            window_label=f"{int(req.days)}d",
            job_name="refresh_proactive_cards",
        )
        return _CONTROL_PLANE_ROUTER.handle(request).payload
    except Exception as exc:
        logger.exception("Error refreshing proactive cards")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/v1/copilot/proactive/card/state")
async def set_proactive_card_state(req: ProactiveCardStateRequest):
    merchant_id = _resolved_merchant_id(req.merchant_id)
    request = _canonical_request(
        request_type=RequestType.proactive_card_state,
        surface=Surface.proactive_inbox,
        merchant_id=merchant_id,
        payload={"dedupe_key": req.dedupe_key, "state": req.state, "card_notes": req.card_notes},
        allow_write=True,
    )
    return _CONTROL_PLANE_ROUTER.handle(request).payload


@app.post("/api/v1/copilot/proactive/card/preview-action")
async def preview_proactive_card_action(req: ProactiveCardPreviewRequest):
    merchant_id = _resolved_merchant_id(req.merchant_id)
    request = _canonical_request(
        request_type=RequestType.proactive_action_preview,
        surface=Surface.proactive_inbox,
        merchant_id=merchant_id,
        payload={"dedupe_key": req.dedupe_key},
    )
    return _CONTROL_PLANE_ROUTER.handle(request).payload


@app.post("/api/v1/copilot/proactive/card/confirm-action")
async def confirm_proactive_card_action(req: ProactiveCardConfirmRequest):
    merchant_id = _resolved_merchant_id(req.merchant_id)
    request = _canonical_request(
        request_type=RequestType.proactive_action_confirm,
        surface=Surface.proactive_inbox,
        merchant_id=merchant_id,
        payload={"dedupe_key": req.dedupe_key, "confirmation_token": req.confirmation_token},
        allow_write=True,
    )
    return _CONTROL_PLANE_ROUTER.handle(request).payload


@app.post("/api/v1/actions/preview")
async def preview_action(req: ActionPreviewRequest):
    merchant_id = _resolved_merchant_id(req.merchant_id)
    request = _canonical_request(
        request_type=RequestType.action_preview,
        surface=Surface.action_center,
        merchant_id=merchant_id,
        payload={"action_type": req.action_type, "payload": req.payload},
    )
    return _CONTROL_PLANE_ROUTER.handle(request).payload


@app.post("/api/v1/actions/confirm")
async def confirm_action(req: ActionConfirmRequest):
    merchant_id = _resolved_merchant_id(req.merchant_id)
    request = _canonical_request(
        request_type=RequestType.action_confirm,
        surface=Surface.action_center,
        merchant_id=merchant_id,
        payload={"confirmation_token": req.confirmation_token},
        allow_write=True,
    )
    return _CONTROL_PLANE_ROUTER.handle(request).payload


@app.post("/api/v1/actions/status")
async def set_action_status(req: ActionStatusRequest):
    merchant_id = _resolved_merchant_id(req.merchant_id)
    request = _canonical_request(
        request_type=RequestType.action_status,
        surface=Surface.action_center,
        merchant_id=merchant_id,
        payload={"action_id": req.action_id, "status": req.status},
        allow_write=True,
    )
    return _CONTROL_PLANE_ROUTER.handle(request).payload


@app.post("/api/v1/actions/details")
async def set_action_details(req: ActionDetailsRequest):
    merchant_id = _resolved_merchant_id(req.merchant_id)
    request = _canonical_request(
        request_type=RequestType.action_details,
        surface=Surface.action_center,
        merchant_id=merchant_id,
        payload={
            "action_id": req.action_id,
            "owner": req.owner,
            "notes": req.notes,
            "blocked_reason": req.blocked_reason,
            "follow_up_date": req.follow_up_date,
        },
        allow_write=True,
    )
    return _CONTROL_PLANE_ROUTER.handle(request).payload


@app.post("/api/v1/actions/cleanup-legacy")
async def hide_legacy_actions(req: CleanupActionsRequest):
    merchant_id = _resolved_merchant_id(req.merchant_id)
    request = _canonical_request(
        request_type=RequestType.action_cleanup,
        surface=Surface.action_center,
        merchant_id=merchant_id,
        allow_write=True,
    )
    return _CONTROL_PLANE_ROUTER.handle(request).payload




# ---------------------------------------------------------------------------
# POS Terminal Error Analysis
# ---------------------------------------------------------------------------

@app.post("/api/v1/terminal/analyze-error")
async def analyze_terminal_error(
    file: UploadFile = File(...),
    merchant_id: Optional[str] = Form(None),
):
    """Upload a photo of a PAX POS terminal error screen for diagnosis.

    Returns the extracted error text, matched PAX error entries, and
    a structured diagnosis with troubleshooting steps.
    """
    resolved_mid = _resolved_merchant_id(merchant_id)
    try:
        image_bytes = await file.read()
        mime_type = file.content_type or "image/jpeg"

        result = analyze_pos_error_image(
            image_bytes=image_bytes,
            mime_type=mime_type,
            merchant_id=resolved_mid,
        )

        if not result["ok"]:
            raise HTTPException(status_code=422, detail=result.get("error", "Failed to analyze terminal error"))

        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error analyzing POS terminal error image")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/v1/terminal/error-categories")
async def list_error_categories():
    """Return all PAX terminal error categories."""
    categories = get_all_categories()
    result = []
    for cat in categories:
        errors = get_errors_by_category(cat)
        result.append({
            "category": cat,
            "count": len(errors),
            "errors": [
                {"message": e.message, "trigger": e.trigger, "flow": e.flow, "action": e.action}
                for e in errors
            ],
        })
    return {"categories": result}


@app.get("/api/v1/terminal/search-errors")
async def search_terminal_errors(q: str = Query(..., min_length=1), limit: int = Query(5, ge=1, le=20)):
    """Search PAX terminal errors by keyword."""
    matches = search_pax_errors(q, top_k=limit)
    return {
        "query": q,
        "results": [
            {"category": e.category, "message": e.message, "trigger": e.trigger, "flow": e.flow, "action": e.action}
            for e in matches
        ],
    }


@app.post("/api/v1/dispute/upload-receipt")
async def upload_dispute_receipt(
    file: UploadFile = File(...),
    merchant_id: Optional[str] = Form(None),
    context: Optional[str] = Form(None),
):
    resolved_mid = _resolved_merchant_id(merchant_id)
    try:
        image_bytes = await file.read()
        mime_type = file.content_type or "image/jpeg"
        
        ctx_dict = {}
        if context:
            import json
            try:
                ctx_dict = json.loads(context)
            except Exception:
                pass

        result = extract_receipt_fields(
            image_bytes=image_bytes,
            mime_type=mime_type,
            merchant_id=resolved_mid,
            context=ctx_dict,
        )
        
        if not result["ok"]:
            raise HTTPException(status_code=422, detail=result.get("error", "Failed to extract receipt data"))
            
        return {"status": "ok", "evidence": result}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error processing dispute receipt")
        raise HTTPException(status_code=500, detail=str(exc))

