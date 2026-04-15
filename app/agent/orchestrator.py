"""
orchestrator.py — Strong-model orchestrator for DUX IQ.

Replaces the 8B router + general fallback with a single planning + execution +
synthesis loop using llama-3.3-70b-versatile.

Flow:
  1. Plan     — classify the query, identify which agents are needed, decide execution order
  2. Execute  — run agents (parallel if independent, sequential if dependent)
  3. Synthesize — compose one coherent answer from all specialist reports

This is only invoked when intent_scoring.py cannot resolve the query with high
confidence (needs_llm=True). High-confidence single-domain queries bypass this
entirely and go straight to the specialist.
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agent.domain_graph import DOMAIN_GRAPH, get_graph_context
from app.agent.handoff import AGENT_REGISTRY
from app.copilot.toolcalling import _make_llm, _invoke_with_rate_limit

logger = logging.getLogger("agent.orchestrator")

# ---------------------------------------------------------------------------
# Planner prompt
# ---------------------------------------------------------------------------

PLANNER_SYSTEM_PROMPT = f"""You are the orchestrator for DUX IQ, a merchant intelligence platform.

Your job is to read the merchant's question and produce a structured execution plan.

{get_graph_context()}

== AVAILABLE AGENTS ==
settlement, transaction, disputes, terminal, growth

== QUERY CLASSES ==
- single    : one domain is sufficient to answer the question
- multi     : the question genuinely spans two domains (e.g. payout drop + chargebacks)
- social    : greeting, thanks, identity question, casual chat ("hi", "thanks", "who are you")
- out_of_scope : weather, sports, politics, anything unrelated to merchant business

== RULES ==
- For "social" and "out_of_scope" set agents to [] and execution to "none"
- Only use "multi" when BOTH domains are truly needed — do not over-fan-out
- Maximum 2 agents for multi; pick the most relevant primary
- Use the investigation paths from the domain graph to guide your choices
- For "multi", prefer "parallel" unless one agent's output feeds the next

Respond ONLY with valid JSON — no explanation, no markdown:
{{
  "query_class": "single|multi|social|out_of_scope",
  "agents": ["<primary>"] or ["<primary>", "<secondary>"],
  "execution": "parallel|sequential|none",
  "plan": "<one sentence explaining why you chose these agents>"
}}

Examples:
User: show my recent settlements
{{"query_class": "single", "agents": ["settlement"], "execution": "none", "plan": "Settlement lookup — single domain."}}

User: why did my payout drop and chargebacks spike?
{{"query_class": "multi", "agents": ["settlement", "disputes"], "execution": "parallel", "plan": "Payout reduction may be driven by chargeback deductions — need both settlement deduction breakdown and disputes reason codes."}}

User: my terminals keep going offline and success rate dropped
{{"query_class": "multi", "agents": ["terminal", "transaction"], "execution": "parallel", "plan": "Terminal health issues directly depress transaction success rate — both domains needed."}}

User: am I eligible for a loan?
{{"query_class": "single", "agents": ["growth"], "execution": "none", "plan": "Credit eligibility is a growth domain question."}}

User: hi there
{{"query_class": "social", "agents": [], "execution": "none", "plan": "Greeting — answer directly."}}

User: what's the weather?
{{"query_class": "out_of_scope", "agents": [], "execution": "none", "plan": "Weather is out of scope for a merchant intelligence platform."}}
"""

SOCIAL_PROMPT = """You are DUX IQ, a friendly merchant intelligence assistant.
Respond warmly and briefly. For identity questions, explain you help merchants understand
their payments, settlements, and business performance. For out-of-scope questions, decline
kindly and redirect to what you can help with.
Return ONLY valid JSON:
{
  "answer": "...",
  "follow_ups": ["What can I help you with today?"],
  "clarifying_question": null,
  "action_preview": null
}"""

SYNTHESIS_PROMPT = """You are the orchestrator for DUX IQ synthesising reports from specialist agents.

Produce ONE coherent answer to the merchant's question using all specialist findings.

Rules:
- Answer the merchant's question directly — lead with the key insight
- Weave specialist findings together naturally; do not list them separately
- Credit each domain naturally (e.g. "Your transaction data shows X, while settlement records show Y")
- Highlight connections between domains when they exist (e.g. terminal issues → lower success rate → lower payout)
- Use plain merchant-friendly language; no jargon
- Never repeat the same fact twice
- If findings contradict, note it and explain the most likely interpretation

Return ONLY valid JSON:
{
  "answer": "...",
  "follow_ups": ["...", "..."],
  "claims": [],
  "clarifying_question": null,
  "action_preview": null
}"""

VALID_AGENTS = set(DOMAIN_GRAPH["agents"].keys())


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


# ---------------------------------------------------------------------------
# Plan step
# ---------------------------------------------------------------------------

def _plan(prompt: str) -> dict[str, Any]:
    """Ask the strong model to classify the query and produce an execution plan."""
    try:
        llm = _make_llm(0.0)
        raw = _invoke_with_rate_limit(llm, [
            SystemMessage(content=PLANNER_SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ])
        plan = _extract_json(getattr(raw, "content", str(raw)))
        # Validate
        query_class = str(plan.get("query_class") or "single").strip()
        agents = [a for a in list(plan.get("agents") or []) if a in VALID_AGENTS]
        execution = str(plan.get("execution") or "none").strip()
        if query_class not in {"single", "multi", "social", "out_of_scope"}:
            query_class = "single"
        return {
            "query_class": query_class,
            "agents": agents,
            "execution": execution,
            "plan": str(plan.get("plan") or ""),
        }
    except Exception as exc:
        logger.warning("Orchestrator planner failed: %s — defaulting to single/general", exc)
        return {"query_class": "single", "agents": [], "execution": "none", "plan": ""}


# ---------------------------------------------------------------------------
# Social / out-of-scope step
# ---------------------------------------------------------------------------

def _answer_social(prompt: str, merchant_id: str) -> dict[str, Any]:
    """Produce a direct LLM answer for greetings and out-of-scope queries."""
    try:
        llm = _make_llm(0.3)
        raw = _invoke_with_rate_limit(llm, [
            SystemMessage(content=SOCIAL_PROMPT),
            HumanMessage(content=prompt),
        ])
        result = _extract_json(getattr(raw, "content", str(raw)))
    except Exception:
        result = {}

    return {
        "answer": str(result.get("answer") or "Hi! I'm DUX IQ, your merchant intelligence assistant. How can I help?"),
        "sources": [],
        "follow_ups": list(result.get("follow_ups") or ["What can I help you with today?"]),
        "clarifying_question": None,
        "validation_status": "clean",
        "display_notice": None,
        "action_preview": None,
        "structured_result": None,
        "answer_sections": {"executive_summary": "", "key_findings": [], "next_best_action": None, "caveats": []},
        "scope": {"merchant_id": merchant_id},
        "agent_name": "orchestrator",
        "handoff_chain": ["orchestrator"],
        "trace": {"agent": "orchestrator", "query_class": "social", "agents_invoked": []},
    }


# ---------------------------------------------------------------------------
# Synthesis step
# ---------------------------------------------------------------------------

def _synthesize(
    responses: list[dict[str, Any]],
    prompt: str,
    merchant_id: str,
    plan: dict[str, Any],
) -> dict[str, Any]:
    """Merge multiple agent reports into one coherent answer."""
    all_sources: list[str] = []
    all_follow_ups: list[str] = []
    handoff_chain: list[str] = []
    agent_summaries = []

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

    payload = {
        "merchant_question": prompt,
        "execution_plan": plan.get("plan", ""),
        "specialist_reports": agent_summaries,
    }

    try:
        llm = _make_llm(0.1)
        raw = _invoke_with_rate_limit(llm, [
            SystemMessage(content=SYNTHESIS_PROMPT),
            HumanMessage(content=json.dumps(payload, ensure_ascii=False, indent=2, default=str)),
        ])
        merged = _extract_json(getattr(raw, "content", str(raw)))
    except Exception as exc:
        logger.warning("Orchestrator synthesis failed: %s", exc)
        merged = {}

    answer = str(merged.get("answer") or " ".join(r.get("answer", "") for r in responses if r.get("answer")))
    follow_ups = [str(f) for f in list(merged.get("follow_ups") or []) if str(f).strip()] or all_follow_ups[:4]

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
        "agent_name": "orchestrator",
        "handoff_chain": list(dict.fromkeys(handoff_chain)),
        "trace": {
            "agent": "orchestrator",
            "query_class": plan.get("query_class"),
            "plan": plan.get("plan"),
            "agents_invoked": [r.get("agent_name") for r in responses],
            "tool_calls": [],
        },
    }


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def orchestrate(
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
    """
    Full orchestration cycle: plan → execute → synthesize.

    Called when intent_scoring cannot resolve the query with high confidence,
    or when the query is detected as genuinely cross-domain.
    """
    plan = _plan(prompt)

    logger.info(
        "\n┌─ ORCHESTRATOR ──────────────────────────\n"
        "│  query_class : %s\n"
        "│  agents      : %s\n"
        "│  execution   : %s\n"
        "│  plan        : %s\n"
        "└─────────────────────────────────────────",
        plan["query_class"], plan["agents"], plan["execution"], plan["plan"],
    )

    query_class = plan["query_class"]
    agents = plan["agents"]

    # Social / out-of-scope — answer directly
    if query_class in {"social", "out_of_scope"} or not agents:
        return _answer_social(prompt, merchant_id)

    # Single agent
    if len(agents) == 1 or query_class == "single":
        agent_name = agents[0] if agents else None
        if not agent_name:
            return _answer_social(prompt, merchant_id)

        agent_fn = AGENT_REGISTRY.get(agent_name)
        if not agent_fn:
            logger.warning("Orchestrator: agent '%s' not in registry", agent_name)
            return _answer_social(prompt, merchant_id)

        result = agent_fn(
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
        # Tag with orchestrator trace
        result.setdefault("trace", {})["orchestrator_plan"] = plan
        return result

    # Multi-agent
    if plan["execution"] == "sequential":
        # Sequential: run primary first, pass its answer as context to secondary
        responses: list[dict[str, Any]] = []
        for agent_name in agents:
            enriched_prompt = prompt
            if responses:
                prior = responses[-1].get("answer", "")
                enriched_prompt = f"{prompt}\n\nContext from prior analysis: {prior}"
            resp = _run_agent(
                agent_name, engine, merchant_id, enriched_prompt,
                terminal_id, history, memory_context, context_object, debug
            )
            responses.append(resp)
    else:
        # Parallel fan-out
        responses = []
        with ThreadPoolExecutor(max_workers=len(agents)) as executor:
            futures = {
                executor.submit(
                    _run_agent, name, engine, merchant_id, prompt,
                    terminal_id, history, memory_context, context_object, debug
                ): name
                for name in agents
            }
            for future in as_completed(futures):
                name = futures[future]
                try:
                    responses.append(future.result())
                except Exception as exc:
                    logger.warning("Orchestrator: agent '%s' failed: %s", name, exc)
                    responses.append({
                        "answer": f"The {name} specialist encountered an error.",
                        "agent_name": name,
                        "sources": [],
                        "follow_ups": [],
                    })

    return _synthesize(responses, prompt, merchant_id, plan)
