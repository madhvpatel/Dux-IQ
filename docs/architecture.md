# DUX IQ — System & Agent Architecture

> **Version**: 2.0.0
> **Stack**: FastAPI · PostgreSQL · LangChain · Groq (llama-3.1-8b-instant) · Expo / React Native

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Component Map](#2-component-map)
3. [API Layer](#3-api-layer)
4. [Request Lifecycle](#4-request-lifecycle)
5. [Intent Routing](#5-intent-routing)
6. [Agent Architecture](#6-agent-architecture)
7. [SQL-First Design](#7-sql-first-design)
8. [Schema Registry](#8-schema-registry)
9. [Tool Calling Loop](#9-tool-calling-loop)
10. [LLM Provider Layer](#10-llm-provider-layer)
11. [Handoff System](#11-handoff-system)
12. [Validation Layer](#12-validation-layer)
13. [Data Layer](#13-data-layer)
14. [Mobile Frontend](#14-mobile-frontend)
15. [Test Infrastructure](#15-test-infrastructure)
16. [Worked Example — "How much GST did I pay last month?"](#16-worked-example)

---

## 1. System Overview

DUX IQ is a merchant intelligence platform that lets payment terminal merchants ask natural language questions about their settlements, transactions, disputes, and terminals. It answers by generating SQL against live PostgreSQL data via Groq-hosted LLMs — responses arrive in 2–5 seconds.

```
Merchant App (Expo / React Native)
        │
        ▼
  FastAPI (:8000)
        │
        ├─── Control Plane Router
        │         │
        │         ├── Intent Scorer  (lexical → entity → memory → TF-IDF)
        │         │
        │         └── Agent Router   (single agent or fan-out)
        │                   │
        │         ┌─────────┼─────────────────────┐
        │         ▼         ▼                     ▼
        │    Settlement  Transaction   Disputes / Terminal / Growth
        │      Agent       Agent              Agents
        │         │         │                     │
        │         └─────────┴─────────────────────┘
        │                   │
        │         LangChain Tool Calling Loop
        │         (SQL tools + computation tools)
        │                   │
        │         Groq API (llama-3.1-8b-instant)
        │                   │
        │         PostgreSQL (transaction_features, settlements,
        │                     chargebacks, refunds, terminal_health_snapshots)
        │
        └─── Composer LLM → Validation Layer → JSON Response
```

**Key design decisions (v2.0):**
- **SQL-first agents**: each agent generates and executes its own SQL rather than calling narrow pre-built tool functions — the LLM sees real column names and sample enum values injected from the live DB at startup
- **Groq replaces Ollama**: ~10–20× faster inference; configurable via `GROQ_MODEL` env var; falls back to Ollama when no Groq key is set
- **Schema Registry**: built once at server startup from `information_schema`, injected into every agent system prompt — prompts are always in sync with the actual DB schema

---

## 2. Component Map

| Layer | File(s) | Responsibility |
|-------|---------|---------------|
| **API** | `app/api/server.py` | HTTP endpoints, request parsing, response shaping |
| **Control Plane** | `app/application/control_plane/` | Canonical request routing, session memory |
| **Intent Scorer** | `app/intelligence/intent_scoring.py` | 4-axis intent classification |
| **Router** | `app/agent/router.py` | Agent dispatch, fan-out, merge |
| **Schema Registry** | `app/agent/schema_registry.py` | Live DB schema → agent system prompts |
| **Agents** | `app/agent/*.py` | 5 domain agents + general fallback |
| **Handoff** | `app/agent/handoff.py` | Cross-agent delegation with depth cap |
| **LLM Factory** | `app/copilot/toolcalling.py` `_make_llm()` | Returns ChatGroq or ChatOllama based on config |
| **Tool Factory** | `app/copilot/toolcalling.py` `make_X_tools()` | Builds SQL tool + computation tools per domain |
| **Tools** | `app/copilot/tools.py` | All callable functions (SQL executor + domain computations) |
| **Repositories** | `app/data/*/repository.py` | Pure SQL query functions used by data endpoints |
| **Validation** | `app/intelligence/chat_reasoning.py` | Claim verification against tool evidence |
| **Frontend** | `IQ/frontend/` | Expo/React Native app (iOS/Android) |
| **Test Suite** | `tests/duxiq_query_bank_test.py` | 40-query evaluation harness with streaming + JSONL logging |

---

## 3. API Layer

### Chat endpoints

| Method | Path | Agent | Max Steps |
|--------|------|-------|-----------|
| `POST` | `/api/v1/ask` | **Router** (auto-selects or fan-out) | — |
| `POST` | `/api/v1/ask/settlement` | Settlement agent | 2 |
| `POST` | `/api/v1/ask/transactions` | Transaction agent | 2 |
| `POST` | `/api/v1/ask/disputes` | Disputes agent | 2 |
| `POST` | `/api/v1/ask/terminals` | Terminal agent | 2 |
| `POST` | `/api/v1/ask/growth` | Growth agent | 2 |

All chat endpoints accept the same `AskRequest` body:

```json
{
  "merchant_id": "100000000121215",
  "prompt": "How much GST did I pay last month?",
  "terminal_id": null,
  "thread_scope": "default",
  "history": [
    { "role": "user", "content": "..." },
    { "role": "assistant", "content": "..." }
  ],
  "context_object": {
    "type": "settlement",
    "id": "261",
    "metadata": { "amount": 24882, "status": "HELD" }
  },
  "debug": false
}
```

`context_object` carries what the merchant is currently looking at on screen (e.g. a settlement they tapped). The agent uses it to pre-seed context before the first LLM turn.

### Data endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/merchants/options` | List of merchants in DB |
| `GET` | `/api/v1/merchant/snapshot` | Dashboard summary (KPIs, settlements, profile) |
| `GET` | `/api/v1/merchant/transactions` | Paginated transaction list |
| `GET` | `/api/v1/merchant/terminal-performance` | Per-terminal success rates |
| `GET` | `/api/v1/merchant/chargebacks` | Chargebacks + summary + refunds |
| `GET` | `/api/v1/merchant/terminals` | Terminal ID list |

### Response envelope (all chat endpoints)

```json
{
  "answer": "...",
  "follow_ups": ["...", "..."],
  "sources": ["settlement:261", "cashflow:MID:30d"],
  "agent_name": "settlement",
  "handoff_chain": ["settlement"],
  "validation_status": "clean",
  "display_notice": null,
  "trace": {
    "tool_calls": [{ "name": "query_settlements", "args": { "query": "SELECT ..." } }]
  }
}
```

---

## 4. Request Lifecycle

```
POST /api/v1/ask
        │
        ▼
  [1] ControlPlaneRouter.handle()
      — Resolves merchant_id
      — Loads session memory (ChatMemoryService)
      — Builds memory_context {last_intent, last_route, active_settlement_id, ...}
        │
        ▼
  [2] route_and_execute()
      — Calls score_intent(prompt, memory_context)
      — Picks agent OR triggers fan-out
        │
        ├── Single agent path ────────────────────────────────────────────────┐
        │   — run_X_agent_turn(engine, merchant_id=..., prompt=..., ...)      │
        │                                                                     │
        └── Fan-out path ─────────────────────────────────────────────────────┤
            — ThreadPoolExecutor → 2 agents in parallel                       │
            — _merge_responses() — LLM composer combines both answers         │
                                                                              │
        ◄─────────────────────────────────────────────────────────────────────┘
        │
        ▼
  [3] Inside each agent:
      a. Build ToolContext(engine, merchant_id, terminal_id)
      b. Anchor date window: MAX(p_date) for this merchant
      c. Build tool list (make_X_tools) — SQL tool + computation tools
      d. Inject schema_registry context into system prompt (built at startup)
      e. Inject context_object prefix into user message if present
      f. invoke_with_tools(streaming=False) → LLM loop (up to max_steps=2)
        │
        ▼
  [4] Composer LLM call (_make_llm)
      — Takes tool calls + results + agent draft
      — Produces structured JSON: answer, follow_ups, claims
        │
        ▼
  [5] validate_reasoning_output()
      — Cross-checks every number in claims against tool evidence
      — Returns validation_status: clean | partial | unverified
        │
        ▼
  [6] ChatMemoryService.remember_turn()
      — Persists this turn to session for continuity
        │
        ▼
  [7] JSON response → mobile app
```

---

## 5. Intent Routing

### The scorer: four axes in order

`score_intent(prompt, memory_context)` runs four detection passes and returns as soon as confidence ≥ 0.80.

```
┌─────────────────────────────────────────────────────────────────────────┐
│  AXIS 1 — Lexical  (deterministic, compiled regex, ~60 patterns)        │
│  "shortfall / payout short / deduction"     → exact_shortfall   0.89   │
│  "settlement / list / show settlements"     → recent_settlements 0.94   │
│  "failed txn / payment failure"             → why_payments_failing 0.88 │
│  "terminal / pos device" + "fail / health"  → terminal_expansion 0.87   │
│  "chargeback / dispute / cb"                → recent_chargebacks  0.90   │
│  "loan / credit / overdraft"                → lending_eligibility 0.88   │
├─────────────────────────────────────────────────────────────────────────┤
│  AXIS 2 — Entity signals  (ID patterns in message)                      │
│  "settlement:261" or "settlement #261"      → recent_settlements 0.92   │
│  "chargeback:4"                             → recent_chargebacks  0.92   │
│  "tx:8734" or "transaction:8734"            → recent_transactions 0.91   │
│  "tid:EP070270"                             → terminal_expansion  0.88   │
├─────────────────────────────────────────────────────────────────────────┤
│  AXIS 3 — Session memory  (continuation detection)                      │
│  "same window / again / tell me more"                                   │
│  + memory_context.last_intent is set → inherit at 0.82                 │
├─────────────────────────────────────────────────────────────────────────┤
│  AXIS 4 — Semantic TF-IDF  (last resort, cosine similarity)             │
│  Score scaled to [0.60, 0.85]. Fires only if score ≥ 0.15.             │
└─────────────────────────────────────────────────────────────────────────┘
        │
        ▼
  confidence < 0.80 → route_chat_intent() → LLM classifies intent
```

### Intent → Agent mapping

```python
INTENT_TO_AGENT = {
    "recent_settlements":       "settlement",
    "settlement_total":         "settlement",
    "exact_shortfall":          "settlement",
    "recent_transactions":      "transaction",
    "why_payments_failing":     "transaction",
    "success_rate_drop":        "transaction",
    "business_overview":        "transaction",
    "what_changed":             "transaction",
    "operational_risks":        "transaction",
    "recent_chargebacks":       "disputes",
    "recent_refunds":           "disputes",
    "terminal_expansion":       "terminal",
    "top_growth_opportunities": "growth",
    "lending_eligibility":      "growth",
}
```

### Fan-out pairs

When two intents **both** score above 0.40, two agents run in parallel:

| Trigger pair | Agents run in parallel |
|---|---|
| `recent_settlements` + `recent_transactions` | settlement + transaction |
| `success_rate_drop` + `terminal_expansion` | transaction + terminal |
| `why_payments_failing` + `recent_chargebacks` | transaction + disputes |
| `exact_shortfall` + `recent_transactions` | settlement + transaction |

Answers are merged by a third LLM call using `MERGER_PROMPT`.

---

## 6. Agent Architecture

### The mesh

```
                         AGENT_REGISTRY
                 ┌────────────────────────────┐
                 │  "settlement"  → fn        │
                 │  "transaction" → fn        │
                 │  "disputes"    → fn        │
                 │  "terminal"    → fn        │
                 │  "growth"      → fn        │
                 └────────────────────────────┘
                              ▲
                 register_agent() called at module bottom of each agent file
```

Each agent is a Python function with the same signature:

```python
def run_X_agent_turn(
    engine,
    *,
    merchant_id: str,
    prompt: str,
    terminal_id: str | None = None,
    history: list[dict] | None = None,
    memory_context: dict | None = None,
    context_object: dict | None = None,
    debug: bool = False,
    _handoff_depth: int = 0,
) -> dict
```

### The 5 agents and their tool sets

#### Settlement Agent
**Domain**: Payouts, deductions, MDR, GST, TDS, reserve, cashflow

| Tool | Type | What it does |
|------|------|-------------|
| `query_settlements` | SQL | Agent-generated SQL against `settlements` table |
| `explain_settlement_shortfall` | Computation | Attributes payout shortfall across MDR, GST, TDS, chargebacks, reserve |
| `cashflow_snapshot` | Computation | Pre-built counts by status (pending/settled/held/failed) + totals |

**Handoff targets**: transaction, terminal | **Max steps**: 2

---

#### Transaction Agent
**Domain**: Payment KPIs, failure rates, success rates, trend comparison

| Tool | Type | What it does |
|------|------|-------------|
| `query_transactions` | SQL | Agent-generated SQL against `transaction_features` table |
| `compute_kpis` | Computation | Aggregated success rate, GMV grouped by day/hour/payment_mode/response_code |
| `compare_kpis` | Computation | Period A vs Period B comparison |
| `verify_failure_drivers` | Computation | Top 5 failure reasons by response code or payment mode |
| `end_to_end_analysis` | Computation | Bundled: KPIs + failures + terminal performance in one call |

**Handoff targets**: settlement, disputes | **Max steps**: 2

---

#### Disputes Agent
**Domain**: Chargebacks, refunds, dispute status and deadlines

| Tool | Type | What it does |
|------|------|-------------|
| `query_disputes` | SQL | Agent-generated SQL against `chargebacks` and `refunds` tables |

**Handoff targets**: transaction, settlement | **Max steps**: 2

---

#### Terminal Agent
**Domain**: Device health, geographic drift, failure correlation

| Tool | Type | What it does |
|------|------|-------------|
| `query_terminals` | SQL | Agent-generated SQL against `terminal_health_snapshots` and `transaction_features` |
| `geo_drift_check` | Computation | Haversine distance from anchor; flags location anomalies |
| `terminal_issue_correlator` | Computation | Joins health flags (network/battery/geo) with payment failure rates |

**Handoff targets**: transaction, settlement | **Max steps**: 2

---

#### Growth Agent
**Domain**: Lending offers, credit eligibility, proactive signals

| Tool | Type | What it does |
|------|------|-------------|
| `query_growth_data` | SQL | Agent-generated SQL against `transaction_features` and `settlements` for revenue/volume signals |
| `get_merchant_lending_offers` | Computation | LACR and overdraft scoring, eligibility limits |
| `assess_credit_fit` | Computation | Fit band (likely/possible/unlikely) against policy knobs |
| `intelligence_probe` | Computation | Top 8 proactive recommendations with impact estimate |

**Handoff targets**: transaction, settlement | **Max steps**: 2

---

## 7. SQL-First Design

Prior to v2.0, agents called narrow pre-built tool functions (`list_settlements`, `get_transaction_detail`, etc.) that ran fixed parameterised queries. This required multiple round-trips and limited the questions agents could answer.

**v2.0 approach**: each domain gets one SQL tool. The LLM writes the query.

```
Merchant asks: "Which hour of the day has the most failed UPI transactions?"

Old approach (v1):
  1. list_transactions(status=FAILED, payment_mode=UPI)   → fetches rows
  2. LLM groups rows in its head                          → error-prone, slow

New approach (v2):
  1. query_transactions(
       query="""
         SELECT hour_of_day, COUNT(*) AS failures
         FROM transaction_features
         WHERE merchant_id = :mid
           AND p_date >= :d1 AND p_date < :d2
           AND status = 'FAILED'
           AND payment_mode = 'UPI'
         GROUP BY hour_of_day ORDER BY failures DESC LIMIT 5
       """)
     → single DB round-trip, exact answer
```

### SQL safety guarantees

Every SQL tool:
1. Pre-populates `{"mid": merchant_id, "d1": default_from, "d2": default_to}` in the parameters dict before calling the executor — the LLM cannot override the merchant scope
2. Routes through `sql_database()` in `tools.py` which enforces read-only `SELECT` statements only
3. Returns rows as a JSON-serialisable dict for downstream processing

---

## 8. Schema Registry

`app/agent/schema_registry.py` — built once at server startup, cached in memory.

```
server.py:
  engine = create_engine(Config.DATABASE_URL)
  schema_registry.build(engine)          ← runs once on startup
                 │
                 ▼
  For each table in {settlements, transaction_features,
                     chargebacks, refunds, terminal_health_snapshots}:

    1. SELECT column_name, data_type
       FROM information_schema.columns
       WHERE table_name = :t
       ORDER BY ordinal_position

    2. For enum-like columns (settlement_status, payment_mode, response_code, ...):
       SELECT DISTINCT column FROM table LIMIT 20

    3. Build formatted block:
       Table: settlements
       ──────────────────
         settlement_id          character varying
         mid                    character varying   -- merchant identifier — always filter: mid = :mid
         net_settlement_amount  numeric             -- final payout amount after all deductions
         settlement_status      character varying   -- values: SETTLED, PENDING, HELD, FAILED
         ...
```

At request time, `_build_system_prompt()` in each agent calls `get_agent_schema("X")` which returns the pre-built schema block. **The LLM sees real column names and real enum values** — no guessing, no hallucinated column names.

```
== DATABASE SCHEMA ==
Table: settlements
──────────────────
  settlement_id          character varying
  mid                    character varying   -- merchant identifier — always filter: mid = :mid
  net_settlement_amount  numeric             -- final payout amount after all deductions
  settlement_status      character varying   -- values: SETTLED, PENDING, HELD, FAILED
  ...

== TOOLS ==
- query_settlements: write SQL to query the settlements table
- explain_settlement_shortfall: attribute a payout shortfall...
...

== SQL RULES ==
- ALWAYS include mid = :mid in every WHERE clause
- Use :d1 and :d2 for date bounds
- Prefer one aggregation query over multiple row-fetch queries
```

---

## 9. Tool Calling Loop

`invoke_with_tools()` in `app/copilot/toolcalling.py`:

```
INPUT:
  system    — agent's dynamic system prompt (includes live DB schema)
  user      — JSON dict: merchant_id, prompt, screen_context, default_window, history
  tools     — list of LangChain BaseTool objects (SQL tool + computation tools)
  max_steps — 2 (reduced from 3-4 in v1 — SQL-first needs fewer steps)
  streaming — bool: if True, tokens stream to stdout via StreamingStdOutCallbackHandler

STEP 0:  llm = _make_llm(temperature).bind_tools(tools)
STEP 1:  messages = [SystemMessage(system), HumanMessage(json.dumps(user))]

LOOP (up to max_steps):
  ┌─────────────────────────────────────────────────────┐
  │  LLM inference: ai = llm.invoke(messages)           │
  │  messages.append(ai)                                │
  │                                                     │
  │  if ai.tool_calls is empty:                         │
  │      break  ← LLM is done, final_text = ai.content │
  │                                                     │
  │  for each tool_call in ai.tool_calls:               │
  │      tool = find tool by name                       │
  │      result = tool.invoke(args)      [try/except]   │
  │      messages.append(ToolMessage(result, id))       │
  │                                                     │
  │      LOG:  ┌─ TOOL CALL ──────────────────────┐    │
  │            │  tool:   query_settlements        │    │
  │            │  sql:    SELECT settlement_id...  │    │
  │            │  rows:   12 returned              │    │
  │            └──────────────────────────────────┘    │
  └─────────────────────────────────────────────────────┘

OUTPUT: (all_tool_calls[], all_results[], final_text)
```

The structured user message handed to the LLM:

```json
{
  "merchant_id": "100000000121215",
  "prompt": "How much GST did I pay last month?",
  "screen_context": "",
  "default_window": { "from_date": "2026-03-01", "to_date": "2026-04-01" },
  "active_settlement_id": null,
  "history": [{ "role": "user", "content": "..." }],
  "memory_context": { "last_intent": "exact_shortfall", "last_route": "settlement" }
}
```

---

## 10. LLM Provider Layer

`_make_llm(temperature, streaming)` in `app/copilot/toolcalling.py` is the single factory for all LLM instances across the system:

```python
def _make_llm(temperature: float, streaming: bool = False):
    callbacks = [StreamingStdOutCallbackHandler()] if streaming else []
    if Config.GROQ_API_KEY:
        return ChatGroq(
            model=Config.GROQ_MODEL,        # default: llama-3.1-8b-instant
            api_key=Config.GROQ_API_KEY,
            temperature=temperature,
            streaming=streaming,
            callbacks=callbacks,
        )
    # Fallback: local Ollama
    return ChatOllama(
        model=Config.OLLAMA_MODEL,
        base_url=Config.OLLAMA_BASE_URL,
        temperature=temperature,
        callbacks=callbacks,
    )
```

Used in two places:
1. **`invoke_with_tools`** — the tool-calling loop (bound to tools with `.bind_tools()`)
2. **Each agent's composer call** — the second LLM call that formats the final structured JSON answer

### Provider configuration

```
GROQ_API_KEY     Set → uses Groq (fast, cloud)
GROQ_MODEL       Model name (default: llama-3.1-8b-instant)
OLLAMA_MODEL     Fallback model if no Groq key (default: qwen3:8b)
OLLAMA_BASE_URL  Ollama endpoint (default: http://localhost:11434)
```

### Latency comparison

| Provider | Model | Avg latency / query |
|----------|-------|-------------------|
| Ollama (local) | qwen3:8b | 60–300s |
| Groq | llama-3.1-8b-instant | 2–5s |
| Groq | llama-3.3-70b-versatile | 4–10s |

---

## 11. Handoff System

Agents can delegate to peer agents via a `handoff_to_agent` tool injected at call time.

```
Settlement agent is mid-turn. Merchant asks:
"Show me the transactions that made up settlement 261."

Settlement agent generates:
  tool_call("handoff_to_agent", {
    "target": "transaction",
    "reason": "Merchant wants transaction breakdown for settlement 261"
  })

make_handoff_tool() checks:
  1. target "transaction" in allowed_targets? ✓
  2. current_depth (0) < MAX_HANDOFF_DEPTH (2)? ✓
  3. Calls AGENT_REGISTRY["transaction"](engine, merchant_id=..., _handoff_depth=1)
  4. Returns "[transaction specialist]: The transactions were..."

Settlement agent receives peer answer as a ToolMessage and incorporates it.
```

**Depth cap**: `_handoff_depth` is incremented on each recursive call. At depth ≥ 2 the handoff returns an error string — no infinite loops.

**Allowed handoffs by agent**:

| Agent | Can call |
|-------|----------|
| Settlement | transaction, terminal |
| Transaction | settlement, disputes |
| Disputes | transaction, settlement |
| Terminal | transaction, settlement |
| Growth | transaction, settlement |

**Handoff chain** visible in every response:
```json
"handoff_chain": ["settlement", "transaction"]
```

---

## 12. Validation Layer

After the composer LLM produces structured JSON, every claim is verified:

```
CLAIMS (from composer):
  [
    { "text": "GST on MDR was ₹1,800", "evidence_ids": ["settlement:9"], "kind": "metric" },
    { "text": "Settlement #9 was processed on 16 Feb 2026", "kind": "status" }
  ]

validate_reasoning_output():

  1. NUMBER CHECK
     — Extract standalone numbers from claim text
     — Exclude alphanumeric IDs (e.g. EP070270)
     — Flatten all numbers from tool results + session history
     — For each extracted number: within 5% of any evidence number? → pass / fail

  2. EVIDENCE ID CHECK
     — For each evidence_id: is it in known_sources? → pass / fail

RESULT:
  "clean"      — all claims verified
  "partial"    — ≥1 verified, ≥1 unverified
  "unverified" — nothing verified
  + display_notice attached if partial/unverified (shown as warning banner in app)
```

---

## 13. Data Layer

### Core tables (real column names from live DB)

| Table | Key Columns |
|-------|-------------|
| `transaction_features` | `transaction_fact_id`, `merchant_id`, `terminal_id`, `payment_mode`, `status`, `response_code`, `amount_rupees`, `p_date`, `initiated_at`, `completed_at`, `card_network`, `card_type`, `hour_of_day`, `day_of_week` |
| `settlements` | `settlement_id`, `mid`, `tid`, `settlement_date`, `settlement_cycle`, `gross_amount`, `mdr_deducted`, `gst_on_mdr`, `tds_deducted`, `chargeback_deductions`, `reserve_held`, `net_settlement_amount`, `settlement_status`, `hold_reason`, `payment_mode`, `p_date` |
| `chargebacks` | `chargeback_id`, `mid`, `chargeback_amount`, `chargeback_reason_code`, `chargeback_stage`, `filed_date`, `response_due_date`, `resolution_outcome`, `card_network`, `chargeback_type`, `p_date` |
| `refunds` | `refund_id`, `mid`, `refund_amount`, `refund_status`, `refund_type`, `refund_date`, `p_date` |
| `terminal_health_snapshots` | `snapshot_id`, `tid`, `mid`, `captured_at`, `battery_status`, `ram_rom_utilization`, `low_network_strength`, `quick_battery_drainage`, `latitude_longitude_deviation`, `printer_status`, `latitude`, `longitude` |

### Agent → table ownership

| Agent | Tables |
|-------|--------|
| Settlement | `settlements` |
| Transaction | `transaction_features` |
| Disputes | `chargebacks`, `refunds` |
| Terminal | `terminal_health_snapshots`, `transaction_features` |
| Growth | `transaction_features`, `settlements` |

### Configuration knobs (`config.py`)

```
DATABASE_URL                    PostgreSQL connection string
GROQ_API_KEY                    Groq API key (enables fast cloud LLM)
GROQ_MODEL                      Groq model name (default: llama-3.1-8b-instant)
OLLAMA_MODEL                    Fallback local model (default: qwen3:8b)
QUERY_SOURCE_TABLE              Fact table name (default: transaction_features)
TIME_ANCHOR_MODE                "system" | "data_max"
CREDIT_MIN_SUCCESS_GMV_30D      Credit policy: minimum monthly GMV
CREDIT_MIN_SUCCESS_RATE_PCT_30D Credit policy: minimum success rate
CREDIT_MAX_CHARGEBACKS_30D      Credit policy: max chargebacks allowed
```

---

## 14. Mobile Frontend

Built with Expo SDK 54 / React Native 0.81.5 / Expo Router (file-based navigation).

### Screen → API mapping

| Screen | Data source | Chat agent |
|--------|-------------|------------|
| Dashboard | `GET /merchant/snapshot` | `/ask` (router) |
| Transactions | `GET /merchant/transactions` | `/ask/transactions` |
| Settlements | `GET /merchant/snapshot` (settlements.rows) | `/ask/settlement` |
| Terminals | `GET /merchant/terminal-performance` | `/ask/terminals` |
| Disputes | `GET /merchant/chargebacks` | `/ask/disputes` |
| Profile | `GET /merchant/snapshot` (merchant_profile) | — |

### App structure

```
IQ/frontend/
├── app/
│   ├── login.tsx                  ← merchant selection (fetches /merchants/options)
│   ├── _layout.tsx                ← root layout + MerchantProvider
│   └── (tabs)/
│       ├── index.tsx              ← dashboard
│       ├── transactions.tsx       ← real tx list + DuxIQChat
│       ├── settlements.tsx        ← settlement rows + DuxIQChat
│       ├── terminals.tsx          ← terminal health + DuxIQChat
│       ├── disputes.tsx           ← chargebacks + evidence upload + DuxIQChat
│       └── profile.tsx
├── src/
│   ├── components/DuxIQChat.tsx   ← reusable chat sheet
│   ├── context/MerchantContext.tsx ← shared merchantId across all tabs
│   └── services/api.ts            ← all API call functions
```

### Context injection flow

```
User taps settlement #261
  ↓
DuxIQChat opens with props:
  context_object = { type: "settlement", id: "261",
                     metadata: { amount: 24882, status: "HELD" } }
  ↓
POST /api/v1/ask/settlement
  ↓
Agent builds prefix:
  "The merchant is currently viewing settlement #261.
   Displayed amount: ₹24,882. Status: HELD.
   Call query_settlements with settlement_id=261 before answering."
  ↓
Agent writes SQL:
  SELECT * FROM settlements WHERE mid = :mid AND settlement_id = '261'
```

### Dispute resolution flow

1. Merchant taps a chargeback row → sees deadline, reason code, status
2. Taps "Upload Evidence" → `EvidenceSheet` modal opens
3. Picks image via `expo-image-picker` (lazy-loaded to avoid native module crash)
4. Image `POST /api/v1/dispute/upload-receipt` → OCR extracts fields
5. Extracted receipt data displayed for review
6. DuxIQChat available on same screen for guidance ("What documents do I need to win this?")

---

## 15. Test Infrastructure

`tests/duxiq_query_bank_test.py` — evaluates the full system against 40 representative queries.

### Query bank coverage

| Domain | Simple | Complex | Total |
|--------|--------|---------|-------|
| Settlement | 5 | 3 | 8 |
| Transaction | 6 | 5 | 11 |
| Disputes | 4 | 3 | 7 |
| Terminal | 4 | 3 | 7 |
| Growth | 3 | 2 | 5 |
| Router (cross-domain) | 0 | 3 | 3 |
| **Total** | **22** | **19** | **41** |

### Rate limiting strategy

Groq free tier: 30 RPM. Each agent turn uses 2–3 LLM calls (tool loop + composer).

```
Per query: ~3 LLM calls
Rate limit: 30 RPM = 2s per call minimum
Safety buffer: 12s inter-query sleep
→ Full run: ~41 × 12s ≈ 8 minutes
Exponential backoff on 429: 15s → 30s → 60s → 120s (max 4 retries)
```

### Streaming

When `streaming=True` is passed to `invoke_with_tools`, `_make_llm()` attaches `StreamingStdOutCallbackHandler`. Tokens print to terminal as Groq returns them — you can watch the model decide which SQL to write and how to compose the answer.

### Log output

Every query produces a JSONL record in `test_logs/`:

```json
{
  "ts": "2026-04-10T14:22:01",
  "domain": "settlement",
  "complexity": "complex",
  "prompt": "My payout this week was less than last week...",
  "agent_name": "settlement",
  "latency_s": 3.4,
  "answer": "Your payout dropped by ₹18,400 this week...",
  "sql_queries": [
    {
      "tool": "query_settlements",
      "sql": "SELECT settlement_date, gross_amount, mdr_deducted... FROM settlements WHERE mid = :mid AND p_date >= :d1",
      "params": { "mid": "M001", "d1": "2026-03-01", "d2": "2026-04-01" }
    }
  ],
  "tool_calls": [...],
  "tool_results": [...],
  "validation_status": "clean"
}
```

### Running

```bash
cd "/path/to/New_demo_copy"

# Full run (~8 min)
python -m tests.duxiq_query_bank_test

# Simple queries only (~4 min smoke test)
python -m tests.duxiq_query_bank_test --simple-only

# Single domain
python -m tests.duxiq_query_bank_test --domain settlement

# Specific merchant
python -m tests.duxiq_query_bank_test --merchant M001
```

---

## 16. Worked Example

### Question: "How much GST did I pay last month?"

Complete path from merchant typing the question to the answer appearing on screen.

---

### Step 1 — HTTP request

```
POST /api/v1/ask
{
  "merchant_id": "100000000121215",
  "prompt": "How much GST did I pay last month?",
  "history": [],
  "context_object": null
}
```

---

### Step 2 — Intent scoring

`score_intent("How much GST did I pay last month?", memory_context={})`:

- **Axis 1** — "GST" not a direct trigger. No strong lexical match.
- **Axis 2** — No entity IDs found.
- **Axis 3** — No session memory.
- **Axis 4** — TF-IDF: "GST paid last month" overlaps with settlement exemplars. Score ≈ 0.73 (below 0.80).

→ Falls through to `route_chat_intent()` → LLM classifies as `"exact_shortfall"` → mapped to **settlement agent**.

---

### Step 3 — Date window anchoring

```sql
SELECT MAX(p_date) FROM transaction_features WHERE merchant_id = '100000000121215'
-- Returns: 2026-03-31
-- Window: 2026-03-01 → 2026-04-01
```

---

### Step 4 — System prompt built

`_build_system_prompt()` calls `get_agent_schema("settlement")`:

```
== DATABASE SCHEMA ==
Table: settlements
──────────────────
  settlement_id          character varying
  mid                    character varying   -- merchant identifier — always filter: mid = :mid
  gst_on_mdr             numeric             -- 18% GST charged on MDR
  net_settlement_amount  numeric             -- final payout amount after all deductions
  settlement_status      character varying   -- values: SETTLED, PENDING, HELD, FAILED
  p_date                 date                -- use for date range filtering
  ...

== SQL RULES ==
- ALWAYS include mid = :mid in every WHERE clause
- Use :d1 and :d2 for date bounds
```

---

### Step 5 — LLM generates SQL (step 1 of tool loop)

The model calls `query_settlements`:

```sql
SELECT SUM(gst_on_mdr) AS total_gst
FROM settlements
WHERE mid = :mid
  AND p_date >= :d1
  AND p_date < :d2
```

Parameters pre-filled: `{ "mid": "100000000121215", "d1": "2026-03-01", "d2": "2026-04-01" }`

---

### Step 6 — SQL executed

`sql_database()` in `tools.py` runs the query. Result:

```json
{ "rows": [{ "total_gst": 4320.00 }], "row_count": 1 }
```

ToolMessage appended: `{"total_gst": 4320.00}`.

---

### Step 7 — LLM synthesises (step 2: no more tool calls)

Model sees the result and returns:

```
"You paid ₹4,320 in GST on MDR last month (March 2026)."
```

No further tool calls → loop exits. `final_text = "You paid ₹4,320..."`.

---

### Step 8 — Composer LLM call

`_make_llm(0.1)` formats into structured JSON:

```json
{
  "answer": "You paid ₹4,320 in GST on MDR last month (March 2026). This is 18% of your total MDR of ₹24,000 for the period.",
  "follow_ups": [
    "Break down MDR deductions by settlement.",
    "Compare my GST this month to last month.",
    "What is my total deductions-to-payout ratio?"
  ],
  "claims": [
    { "text": "GST on MDR was ₹4,320", "evidence_ids": ["query_settlements:1"], "kind": "metric" }
  ]
}
```

---

### Step 9 — Validation and response

`validate_reasoning_output()` checks ₹4,320 against tool result → found → `"clean"`.

Final response dispatched:

```json
{
  "answer": "You paid ₹4,320 in GST on MDR last month (March 2026)...",
  "follow_ups": ["Break down MDR deductions...", "..."],
  "agent_name": "settlement",
  "handoff_chain": ["settlement"],
  "validation_status": "clean",
  "trace": {
    "tool_calls": [{ "name": "query_settlements", "args": { "query": "SELECT SUM(gst_on_mdr)..." } }]
  }
}
```

**Total latency**: ~3–4 seconds (Groq) vs 60–120 seconds (Ollama).
