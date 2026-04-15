"""Schema registry — fetched once at server startup, used to build agent system prompts.

Call build(engine) once during startup.
Then call get_table_schema(table_name) anywhere to get a formatted schema block.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text

logger = logging.getLogger("schema_registry")

# ---------------------------------------------------------------------------
# Tables managed by each agent domain
# ---------------------------------------------------------------------------

AGENT_TABLES: dict[str, list[str]] = {
    "settlement":  ["settlements"],
    "transaction": ["transaction_features"],
    "disputes":    ["chargebacks", "refunds"],
    "terminal":    ["terminal_health_snapshots", "transaction_features"],
    "growth":      ["transaction_features", "settlements"],
}

# Columns worth sampling distinct values from (enum-like)
_SAMPLE_COLS: dict[str, list[str]] = {
    "settlements": [
        "settlement_status", "payment_mode", "settlement_cycle",
    ],
    "transaction_features": [
        "status", "payment_mode", "response_code",
        "card_network", "card_type",
    ],
    "chargebacks": [
        "chargeback_stage", "chargeback_reason_code",
        "card_network", "chargeback_type", "resolution_outcome",
    ],
    "refunds": [
        "refund_status", "refund_type",
    ],
    "terminal_health_snapshots": [
        "printer_status",
    ],
}

# Human-readable notes for every column — injected into agent system prompts so the
# LLM understands what each field means and how to use it correctly in SQL.
_COL_NOTES: dict[str, dict[str, str]] = {
    "settlements": {
        # Identifiers & scope
        "settlement_id":           "unique settlement batch identifier — use in WHERE to look up a specific payout",
        "mid":                     "merchant identifier — ALWAYS filter: mid = :mid (never query without this)",
        "tid":                     "terminal ID this settlement covers — NULL means merchant-wide batch",
        # Amounts
        "gross_amount":            "total transaction value processed before any fee deductions",
        "mdr_deducted":            "merchant discount rate fee charged by the acquirer (typically 0.5–2% of gross)",
        "gst_on_mdr":              "18% GST levied on the MDR amount — NOT on gross amount",
        "tds_deducted":            "tax deducted at source by the bank (1% of gross for most merchants)",
        "chargeback_deductions":   "amount withheld or clawed back due to open or lost chargebacks",
        "reserve_held":            "rolling reserve withheld by the bank (typically 5–10% of gross, released after 90–180 days)",
        "net_settlement_amount":   "final amount actually paid to the merchant = gross − MDR − GST − TDS − chargebacks − reserve",
        # Status & timing
        "settlement_status":       "SETTLED = paid out; PENDING = queued; HELD = blocked (see hold_reason); FAILED = processing error",
        "hold_reason":             "explains why settlement_status = HELD — e.g. 'KYC pending', 'fraud flag', 'excess chargebacks'",
        "settlement_date":         "date the payout was (or is expected to be) credited to merchant's bank account",
        "settlement_cycle":        "T+1 = next-day payout; T+2 = two-day payout — affects how quickly merchant receives funds",
        "payment_mode":            "dominant payment mode in this batch: UPI, CARD, WALLET, NETBANKING, CASH",
        "p_date":                  "partition date — primary column for date range filtering (use p_date >= :d1 AND p_date < :d2)",
    },

    "transaction_features": {
        # Identifiers & scope
        "transaction_fact_id":     "unique transaction row ID — use in WHERE to look up a specific transaction",
        "merchant_id":             "merchant identifier — ALWAYS filter: merchant_id = :mid (never query without this)",
        "terminal_id":             "which POS device processed the transaction — join with terminal_health_snapshots on tid",
        # Amounts & outcome
        "amount_rupees":           "transaction amount in INR — use SUM for GMV, AVG for ticket size",
        "status":                  "SUCCESS = payment completed and funds captured; FAILED = payment declined or errored",
        "response_code":           "'00' = approved and successful; any other value = declined — common codes: '51' insufficient funds, '05' do not honour, '14' invalid card, '91' issuer unavailable, '96' system error",
        # Payment details
        "payment_mode":            "how the customer paid: UPI, CARD, WALLET, NETBANKING, CASH — useful for failure breakdown by mode",
        "card_network":            "VISA, MASTERCARD, RUPAY, AMEX — only populated for CARD transactions",
        "card_type":               "CREDIT, DEBIT, PREPAID — only populated for CARD transactions",
        # Timing
        "p_date":                  "transaction date (date only) — primary column for date range filtering",
        "initiated_at":            "full timestamp when customer initiated the payment — use for hour/minute-level analysis",
        "completed_at":            "full timestamp when transaction was completed or declined — NULL if still in flight",
        "hour_of_day":             "0–23 integer derived from initiated_at — use for peak hour analysis without EXTRACT()",
        "day_of_week":             "0=Monday … 6=Sunday — use for day-of-week patterns without EXTRACT()",
    },

    "chargebacks": {
        # Identifiers & scope
        "chargeback_id":           "unique chargeback record ID — use in WHERE to look up a specific dispute",
        "mid":                     "merchant identifier — ALWAYS filter: mid = :mid",
        # Amounts & parties
        "chargeback_amount":       "disputed amount in INR — this is the value the merchant may lose if the chargeback is lost",
        "card_network":            "network that owns the dispute process: VISA, MASTERCARD, RUPAY, AMEX",
        "chargeback_type":         "FIRST_CHARGEBACK = initial dispute; SECOND_CHARGEBACK = re-opened after merchant response",
        # Reason
        "chargeback_reason_code":  "standardised code explaining why customer disputed — e.g. '4853' item not received, '4837' no cardholder authorisation, '10.4' fraud",
        # Lifecycle
        "chargeback_stage":        "OPEN = awaiting merchant response; RESPONDED = merchant submitted evidence; ESCALATED = arbitration; CLOSED = resolved",
        "filed_date":              "date the chargeback was raised by the issuing bank",
        "response_due_date":       "CRITICAL deadline — merchant must submit evidence by this date to contest the chargeback; missing it means automatic loss",
        "resolution_outcome":      "WON = merchant kept the funds; LOST = funds returned to customer; NULL = still in progress",
        "p_date":                  "partition date — use for date range filtering alongside filed_date",
    },

    "refunds": {
        # Identifiers & scope
        "refund_id":               "unique refund record ID",
        "mid":                     "merchant identifier — ALWAYS filter: mid = :mid",
        # Amounts
        "refund_amount":           "amount refunded to the customer in INR — this is deducted from the merchant's settlement",
        # Classification
        "refund_type":             "FULL = entire transaction reversed; PARTIAL = portion of the transaction refunded",
        "refund_status":           "PENDING = initiated but not yet processed; PROCESSED = credited to customer; FAILED = could not be processed",
        # Timing
        "refund_date":             "date the refund was initiated by the merchant",
        "p_date":                  "partition date — use for date range filtering",
    },

    "terminal_health_snapshots": {
        # Identifiers & scope
        "snapshot_id":             "unique snapshot row ID",
        "tid":                     "terminal device identifier — join with transaction_features on terminal_id to correlate health with failures",
        "mid":                     "merchant identifier — ALWAYS filter: mid = :mid",
        "captured_at":             "timestamp when this health snapshot was recorded — use for time-series health analysis",
        # Hardware health
        "battery_status":          "battery charge percentage (0–100); below 20 = critical, device may shut down mid-transaction",
        "ram_rom_utilization":     "memory usage percentage (0–100); above 85 may cause app crashes or slow transaction processing",
        "printer_status":          "OK = printer ready; LOW_PAPER = paper running out; NO_PAPER = cannot print receipts; ERROR = hardware fault",
        # Network & location flags (all boolean)
        "low_network_strength":    "TRUE when cellular/WiFi signal is below acceptable threshold — primary cause of UPI and online payment failures",
        "quick_battery_drainage":  "TRUE when battery is depleting faster than normal — indicates hardware degradation, needs replacement",
        "latitude_longitude_deviation": "TRUE when terminal's GPS location has drifted significantly from its registered merchant address — possible theft, misplacement, or SIM swap",
        # Raw GPS (used by geo_drift_check tool)
        "latitude":                "GPS latitude of the terminal at snapshot time — used by geo_drift_check for haversine distance calculation",
        "longitude":               "GPS longitude of the terminal at snapshot time — used by geo_drift_check for haversine distance calculation",
    },
}

# ---------------------------------------------------------------------------
# Module-level cache
# ---------------------------------------------------------------------------

_schemas: dict[str, str] = {}   # table_name → formatted schema block
_loaded: bool = False


def build(engine: Any) -> None:
    """Fetch schema from DB and populate the module-level cache.

    Call this once during server startup before handling any requests.
    """
    global _schemas, _loaded
    _schemas = {}

    all_tables = {t for tables in AGENT_TABLES.values() for t in tables}

    for table in sorted(all_tables):
        try:
            _schemas[table] = _build_table_schema(engine, table)
            logger.info("schema_registry: loaded schema for %s", table)
        except Exception as exc:
            logger.warning("schema_registry: failed to load %s — %s", table, exc)
            _schemas[table] = f"[schema unavailable for {table}: {exc}]"

    _loaded = True
    logger.info("schema_registry: ready (%d tables)", len(_schemas))


def get_table_schema(table: str) -> str:
    """Return the formatted schema block for a single table."""
    if not _loaded:
        return f"[schema_registry not initialised — call build(engine) at startup]"
    return _schemas.get(table, f"[unknown table: {table}]")


def get_agent_schema(agent: str) -> str:
    """Return combined schema block for all tables owned by an agent."""
    tables = AGENT_TABLES.get(agent, [])
    blocks = [get_table_schema(t) for t in tables]
    return "\n\n".join(blocks)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_table_schema(engine: Any, table: str) -> str:
    columns = _fetch_columns(engine, table)
    samples = _fetch_samples(engine, table)
    notes = _COL_NOTES.get(table, {})

    lines: list[str] = [f"Table: {table}"]
    lines.append("-" * (len(table) + 7))

    for col_name, data_type in columns:
        note = notes.get(col_name, "")
        sample = samples.get(col_name)
        parts = [f"  {col_name:<40} {data_type}"]
        if note:
            parts.append(f"    -- {note}")
        if sample:
            vals = ", ".join(str(v) for v in sample if v is not None and str(v).strip())
            if vals:
                parts.append(f"    -- values: {vals}")
        lines.append("\n".join(parts))

    return "\n".join(lines)


def _fetch_columns(engine: Any, table: str) -> list[tuple[str, str]]:
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = :t
                ORDER BY ordinal_position
            """),
            {"t": table},
        ).mappings().all()
    return [(r["column_name"], r["data_type"]) for r in rows]


def _fetch_samples(engine: Any, table: str) -> dict[str, list]:
    cols = _SAMPLE_COLS.get(table, [])
    result: dict[str, list] = {}
    with engine.connect() as conn:
        for col in cols:
            try:
                rows = conn.execute(
                    text(f"SELECT DISTINCT {col} FROM {table} WHERE {col} IS NOT NULL LIMIT 20"),
                ).scalars().all()
                cleaned = [v for v in rows if v is not None and str(v).strip()]
                if cleaned:
                    result[col] = cleaned
            except Exception:
                pass
    return result
