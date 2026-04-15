"""
handoff.py — Agent registry and handoff tool factory for DUX IQ multi-agent mesh.

Each specialized agent registers itself at import time via register_agent().
When an agent encounters an out-of-domain question, it calls the `handoff_to_agent`
LangChain tool, which synchronously invokes the target agent and returns its answer.

Depth cap (2): A → B → C is allowed; A → B → C → D is not, preventing infinite loops.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Callable

from langchain_core.tools import BaseTool, tool

logger = logging.getLogger("agent.handoff")

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

# Maps agent name → callable with signature:
#   (engine, *, merchant_id, prompt, terminal_id, history, memory_context,
#    context_object, debug, _handoff_depth) -> dict
AGENT_REGISTRY: dict[str, Callable[..., dict[str, Any]]] = {}

_MAX_HANDOFF_DEPTH = 2


def register_agent(name: str, fn: Callable[..., dict[str, Any]]) -> None:
    """Register a named agent function. Called at module import by each agent file."""
    AGENT_REGISTRY[name] = fn
    logger.debug("Registered agent: %s", name)


# ---------------------------------------------------------------------------
# Handoff tool factory
# ---------------------------------------------------------------------------

def make_handoff_tool(
    *,
    allowed_targets: list[str],
    engine: Any,
    merchant_id: str,
    terminal_id: str | None,
    context_object: dict[str, Any] | None,
    history: list[dict[str, Any]] | None,
    current_depth: int = 0,
) -> BaseTool:
    """Return a LangChain tool that lets the calling agent invoke a peer agent.

    Parameters
    ----------
    allowed_targets:
        Which agent names this agent is permitted to hand off to.
        Prevents accidental circular references at the schema level.
    current_depth:
        Current handoff depth. Passed through from the calling agent's
        ``_handoff_depth`` parameter. Capped at _MAX_HANDOFF_DEPTH.
    """
    valid_targets_str = ", ".join(f'"{t}"' for t in allowed_targets)
    _description = (
        f"Hand off the current question to a specialist agent when it is outside your domain. "
        f"target: MUST be one of [{valid_targets_str}] — do not use any other value. "
        f"reason: the question or context to pass to the specialist. "
        f"Returns the specialist's answer as a plain string."
    )

    @tool("handoff_to_agent", description=_description)
    def handoff_to_agent(target: str, reason: str) -> str:
        target = str(target or "").strip().lower()
        if target not in allowed_targets:
            return f"Handoff target '{target}' is not allowed from this agent. Available: {', '.join(allowed_targets)}"

        if current_depth >= _MAX_HANDOFF_DEPTH:
            return "Maximum handoff depth reached. I cannot delegate further. Please try rephrasing your question."

        agent_fn = AGENT_REGISTRY.get(target)
        if not agent_fn:
            return f"Agent '{target}' is not available."

        logger.info(
            "\n┌─ HANDOFF ─────────────────────────────────\n"
            "│  target : %s  depth=%d\n│  reason : %s\n"
            "└───────────────────────────────────────────",
            target, current_depth + 1, reason
        )

        try:
            result = agent_fn(
                engine,
                merchant_id=merchant_id,
                prompt=reason,
                terminal_id=terminal_id,
                history=history or [],
                memory_context=None,
                context_object=context_object or {},
                debug=False,
                _handoff_depth=current_depth + 1,
            )
            answer = str(result.get("answer") or "No answer from specialist.")
            agent_name = result.get("agent_name", target)
            return f"[{agent_name} specialist]: {answer}"
        except Exception as exc:
            logger.warning("Handoff to '%s' failed: %s", target, exc)
            return f"The {target} specialist encountered an error: {exc}"

    return handoff_to_agent
