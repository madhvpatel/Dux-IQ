"""
domain_graph.py — Merchant domain knowledge graph for DUX IQ.

Encodes entity relationships, agent capabilities, and investigation paths so the
orchestrator can reason about multi-domain queries without guessing from scratch.

This is intentionally a plain Python data structure — no graph DB required.
The orchestrator reads get_graph_context() as a compact text block injected into
its system prompt, giving it grounded knowledge about the merchant domain.
"""
from __future__ import annotations

DOMAIN_GRAPH: dict = {
    "agents": {
        "settlement": {
            "handles": [
                "payouts", "disbursements", "net settlement amount", "deductions",
                "MDR", "GST on MDR", "TDS", "shortfall", "held settlements",
                "settlement status", "payout schedule",
            ],
            "key_entities": ["settlement_id", "net_amount", "gross_amount", "deductions", "p_date", "status"],
            "sample_questions": [
                "Why did my payout drop?",
                "What are my deductions this month?",
                "Show my recent settlements",
                "What is my MDR?",
                "Why is my settlement on hold?",
            ],
        },
        "transaction": {
            "handles": [
                "payment success rate", "approval rate", "GMV", "failed payments",
                "decline codes", "payment modes", "KPIs", "what changed",
                "sales drop", "revenue decline", "business overview", "UPI vs card split",
            ],
            "key_entities": ["transaction_id", "status", "amount", "payment_mode", "failure_code", "terminal_id", "p_date"],
            "sample_questions": [
                "Why are payments failing?",
                "What is my success rate?",
                "What changed this month?",
                "How is my business doing overall?",
                "Which payment mode has the most failures?",
            ],
        },
        "disputes": {
            "handles": [
                "chargebacks", "refunds", "dispute resolution", "reason codes",
                "unauthorized transactions", "fraud", "chargeback rate",
            ],
            "key_entities": ["chargeback_id", "reason_code", "amount", "status", "refund_id", "dispute_date"],
            "sample_questions": [
                "Show my recent chargebacks",
                "Why did chargebacks go up?",
                "How many refunds this month?",
                "What are my top dispute reason codes?",
            ],
        },
        "terminal": {
            "handles": [
                "POS device health", "battery level", "network signal", "geographic drift",
                "device failures", "terminal performance", "offline terminals",
                "printer status", "RAM/ROM utilization",
            ],
            "key_entities": ["tid", "battery_status", "low_network_strength", "latitude_longitude_deviation", "failure_rate"],
            "sample_questions": [
                "Which terminal has the worst failure rate?",
                "Are any terminals showing battery issues?",
                "Show terminals with weak network signal",
                "Which terminal caused the most failures?",
            ],
        },
        "growth": {
            "handles": [
                "loans", "working capital", "credit eligibility", "cash advance",
                "growth opportunities", "business health score", "expansion",
            ],
            "key_entities": ["loan_offer", "credit_score", "eligibility_flag", "revenue_trend", "health_score"],
            "sample_questions": [
                "Am I eligible for a loan?",
                "What are my top growth opportunities?",
                "What is my business health score?",
                "How much working capital can I get?",
            ],
        },
    },

    "relationships": [
        {
            "from": "settlement", "to": "transaction", "type": "aggregates",
            "description": "Settlement net amount = transaction GMV minus MDR, GST, TDS, and reserve deductions",
        },
        {
            "from": "settlement", "to": "disputes", "type": "reduced_by",
            "description": "Chargeback reversals and refund reserves are deducted from settlement payouts",
        },
        {
            "from": "transaction", "to": "terminal", "type": "processed_by",
            "description": "Every transaction flows through a specific terminal; terminal health directly affects transaction success rate",
        },
        {
            "from": "transaction", "to": "disputes", "type": "triggers",
            "description": "Disputed or unauthorized transactions generate chargebacks; high failure rate often correlates with chargeback spike",
        },
        {
            "from": "settlement", "to": "growth", "type": "signals",
            "description": "Settlement frequency and net amounts are key inputs to credit eligibility scoring",
        },
        {
            "from": "transaction", "to": "growth", "type": "signals",
            "description": "Transaction volume, GMV trend, and success rate inform growth offer sizing",
        },
    ],

    # Investigation paths tell the orchestrator which agents to involve for common complex queries
    # and in what order — primary does the heavy lifting, supporting agents provide context.
    "investigation_paths": {
        "payout_drop": {
            "primary": "settlement",
            "supporting": ["transaction", "disputes"],
            "execution": "parallel",
            "reasoning": (
                "Payout = gross GMV - MDR - GST - TDS - chargebacks - reserve. "
                "Settlement agent checks deduction breakdown. Transaction agent checks if GMV itself dropped. "
                "Disputes agent checks if chargeback deductions increased."
            ),
        },
        "payment_failure": {
            "primary": "transaction",
            "supporting": ["terminal"],
            "execution": "parallel",
            "reasoning": (
                "Payment failures have two root causes: issuer/network declines (transaction agent) "
                "or device-level issues — battery, signal loss, geo drift (terminal agent)."
            ),
        },
        "chargeback_spike": {
            "primary": "disputes",
            "supporting": ["transaction"],
            "execution": "parallel",
            "reasoning": (
                "Chargebacks link back to specific transactions. Disputes agent identifies reason codes; "
                "transaction agent finds the originating transaction patterns."
            ),
        },
        "terminal_and_revenue": {
            "primary": "terminal",
            "supporting": ["transaction"],
            "execution": "parallel",
            "reasoning": (
                "Terminal health issues directly depress transaction success rate. "
                "Terminal agent diagnoses device health; transaction agent quantifies revenue impact."
            ),
        },
        "business_overview": {
            "primary": "transaction",
            "supporting": ["settlement", "disputes"],
            "execution": "parallel",
            "reasoning": (
                "Full business picture: GMV + success rate (transaction), payout health (settlement), "
                "dispute exposure (disputes)."
            ),
        },
        "growth_with_context": {
            "primary": "growth",
            "supporting": ["transaction", "settlement"],
            "execution": "sequential",
            "reasoning": (
                "Credit eligibility depends on revenue signals. Transaction and settlement data "
                "should be fetched first to inform the growth agent."
            ),
        },
    },
}

# Maps fine-grained intent_scoring intents to agent names
INTENT_TO_AGENT: dict[str, str] = {
    "recent_settlements": "settlement",
    "settlement_total": "settlement",
    "exact_shortfall": "settlement",
    "recent_transactions": "transaction",
    "why_payments_failing": "transaction",
    "success_rate_drop": "transaction",
    "what_changed": "transaction",
    "business_overview": "transaction",
    "operational_risks": "transaction",
    "recent_chargebacks": "disputes",
    "recent_refunds": "disputes",
    "terminal_expansion": "terminal",
    "lending_eligibility": "growth",
    "top_growth_opportunities": "growth",
}

# Social intents — answer directly, no agent dispatch needed
SOCIAL_INTENTS = {"general", "social_ack", "assistant_identity", "out_of_scope"}


def get_graph_context() -> str:
    """Return a compact text representation of the domain graph for LLM context injection."""
    lines = ["== MERCHANT DOMAIN GRAPH =="]

    lines.append("\nAGENTS AND THEIR DOMAINS:")
    for agent, info in DOMAIN_GRAPH["agents"].items():
        lines.append(f"  {agent}: {', '.join(info['handles'][:6])}")

    lines.append("\nKEY ENTITY RELATIONSHIPS:")
    for rel in DOMAIN_GRAPH["relationships"]:
        lines.append(f"  {rel['from']} → {rel['to']}: {rel['description']}")

    lines.append("\nINVESTIGATION PATHS FOR COMPLEX QUERIES:")
    for path_name, path in DOMAIN_GRAPH["investigation_paths"].items():
        supporting = f" + supporting: [{', '.join(path['supporting'])}]" if path["supporting"] else ""
        lines.append(f"  {path_name}: primary={path['primary']}{supporting} ({path['execution']})")
        lines.append(f"    reason: {path['reasoning']}")

    return "\n".join(lines)
