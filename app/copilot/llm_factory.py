"""
llm_factory.py — Centralised LLM constructor.

Returns ChatGroq when GROQ_API_KEY is set, ChatOllama otherwise.
Kept dependency-free from the rest of app.copilot to avoid circular imports.
"""
from __future__ import annotations

from config import Config


def make_llm(temperature: float = 0.2, streaming: bool = False):
    """Return a ChatGroq or ChatOllama instance based on config."""
    if Config.GROQ_API_KEY:
        from langchain_groq import ChatGroq
        return ChatGroq(
            model=Config.GROQ_MODEL,
            api_key=Config.GROQ_API_KEY,
            temperature=temperature,
            streaming=streaming,
        )
    from langchain_ollama import ChatOllama
    return ChatOllama(
        model=Config.OLLAMA_MODEL,
        base_url=Config.OLLAMA_BASE_URL,
        temperature=temperature,
    )
