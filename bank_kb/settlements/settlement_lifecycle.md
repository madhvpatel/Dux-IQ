# Settlement Lifecycle

## What is settlement
Settlement is the process by which the acquiring bank transfers the merchant's collected funds (minus fees) to their registered bank account. It is the most critical financial operation for merchants — predictable settlements mean predictable cashflow.

## End-to-end flow

### 1. Transaction capture
- Transactions are authorised in real-time (card/UPI approval).
- At end of day (or per batch window), the terminal/gateway performs a **batch settlement** — sending all approved transactions to the acquirer for clearing.
- POS terminals auto-settle at a configured time (usually 11 PM - midnight). Online gateways settle continuously.

### 2. Clearing
- Acquirer sends transaction data to the respective network (Visa/MC/RuPay/NPCI).
- Network calculates interchange and routes funds from issuer to acquirer.
- For UPI: NPCI handles multilateral net settlement between participant banks.
- Clearing cycle: same day for UPI (via NPCI settlement windows), T+1 for most card networks.

### 3. Funding (payout to merchant)
- Acquirer receives cleared funds into its nodal/settlement account.
- Acquirer calculates: **Net payout = Gross amount - MDR - GST on MDR - Chargebacks - Adjustments**.
- Payout is initiated via NEFT/RTGS/IMPS to the merchant's registered bank account.
- Settlement cycle options:
  - **T+0 (same day)**: Premium service. Merchant receives funds on the same day as the transaction.
  - **T+1 (next business day)**: Standard for most merchants. Funds received next working day.
  - **T+2 (two business days)**: Older cycle, still used for some high-risk merchants.
  - **Weekly/Monthly**: Used for aggregator models or very small merchants.

### 4. Reconciliation
- Merchant should reconcile: (a) transactions captured vs transactions settled, (b) gross amount vs net payout, (c) deductions (MDR, chargebacks, adjustments) match expectations.
- Common reconciliation mismatches: timezone differences in cutoff, chargebacks deducted mid-cycle, currency conversion adjustments, GST rounding.

## Settlement holds and delays
- **Chargeback reserve**: Acquirer may hold 5-10% of settlement as rolling reserve for chargeback-prone merchants.
- **Risk hold**: If fraud is suspected or chargeback ratio exceeds threshold (typically 1%), acquirer may freeze settlements.
- **Documentation hold**: Pending KYC re-verification or agreement renewal.
- **Technical hold**: Settlement file generation failure, bank account validation failure (IFSC/account number mismatch).

## Key metrics for merchants
- **Settlement accuracy**: % of transactions that settle at the expected net amount.
- **Settlement timeliness**: % of settlements received within the stated cycle (T+0, T+1, etc.).
- **Shortfall rate**: Frequency and magnitude of settlements that are less than expected.
- A healthy merchant should see: >99% settlement accuracy, >98% timeliness, <0.5% shortfall rate.

## Common merchant complaints
- "My settlement is less than expected" — check: chargebacks deducted, MDR rate changes, GST adjustments, held transactions.
- "I didn't receive today's settlement" — check: bank holiday calendar, terminal batch settlement time, account validation status.
- "Settlement shows different amount than my POS total" — check: void/cancelled transactions, partial captures, pre-auth completions vs authorisations.
