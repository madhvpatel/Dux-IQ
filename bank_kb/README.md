# Bank Knowledge Base

This folder is the **source of truth** for bank offerings and Indian payments domain knowledge used by the copilot (agentic RAG via TF-IDF + BM25 hybrid search).

- Add/update Markdown files here.
- Run `kb_reindex` (via tool or CLI) to refresh the local search index.

## Structure

- `services/` — bank products the agent can recommend (instant settlement, chargeback assist, smart routing, merchant credit, settlement cycles)
- `payments/` — payment method deep dives (UPI, cards, NEFT/RTGS/IMPS, wallets/PPI)
- `settlements/` — settlement lifecycle, reconciliation, payout holds and delays
- `disputes/` — chargeback lifecycle, UPI disputes, representment guide
- `compliance/` — RBI PA-PG guidelines, tokenization mandate, MDR rules
- `merchants/` — onboarding/KYC, MCC codes, risk categorisation
- `terminals/` — POS terminal types, management, troubleshooting
- `response_codes/` — ISO 8583 card response codes, UPI response codes
- `glossary.md` — Indian payments terminology reference

## Authoring tips

- Keep each topic in its own file for clean chunking.
- Include: what it is, how it works, merchant impact, common issues, actionable advice.
- Structure with headings — the chunker splits on `#` headings for TF-IDF indexing.
- Prefer plain text + tables; avoid PDFs.
