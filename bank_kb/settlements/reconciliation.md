# Reconciliation

## What is reconciliation
Reconciliation is the process of matching transaction records across systems to ensure accuracy. For merchants, it means verifying that every payment collected at the terminal/gateway matches what was settled into their bank account, with all deductions accounted for.

## Levels of reconciliation

### 1. Transaction-level reconciliation
- Match each transaction at POS/gateway against the acquirer's transaction report.
- Fields to match: transaction ID, amount, date/time, card type, response code.
- Common mismatches: timezone offset (terminal local time vs acquirer UTC), duplicate transactions, void not reflected.

### 2. Settlement-level reconciliation
- Match acquirer's settlement report against bank account credit.
- Key formula: **Bank credit = Gross settled amount - MDR - GST on MDR - Chargebacks - Adjustments + Refund reversals**
- Common mismatches: settlement split across multiple UTRs, partial settlement (some transactions held), rounding differences on GST.

### 3. Cross-system reconciliation (for large merchants)
- Match POS/billing system records against acquirer reports against bank statements against accounting system.
- Requires unique transaction identifiers (RRN, ARN, UTR) to trace across systems.

## Key identifiers

| Identifier | Full name | Who assigns | Purpose |
|-----------|-----------|-------------|---------|
| **RRN** | Retrieval Reference Number | Acquirer | Unique ID for a card transaction in the network |
| **ARN** | Acquirer Reference Number | Acquirer/Network | Used to trace a transaction through Visa/MC for disputes |
| **UTR** | Unique Transaction Reference | Remitting bank | Identifies the NEFT/RTGS/IMPS transfer for settlement payout |
| **UPI Txn ID** | UPI Transaction ID | NPCI | Unique ID for a UPI transaction across PSPs |
| **MID** | Merchant ID | Acquirer | Identifies the merchant account |
| **TID** | Terminal ID | Acquirer | Identifies a specific terminal |

## Common reconciliation issues

### Shortfall (settled < expected)
1. Chargeback deducted from settlement batch.
2. MDR rate higher than merchant expected (check agreement vs actual).
3. GST on MDR not factored in merchant's calculation.
4. Transactions voided after batch close but before settlement.
5. Currency conversion adjustment on international cards.

### Excess (settled > expected)
1. Chargeback reversal credited (merchant won the dispute).
2. Refund reversal (refund was rejected by issuer, funds returned to merchant).
3. Adjustment credit from acquirer (previous shortfall correction).

### Missing transactions
1. Terminal didn't batch-settle (connectivity issue at batch time).
2. Transaction timed out — authorised but not captured.
3. Transaction in "pending" state — awaiting issuer confirmation.

## GST on MDR
- 18% GST applies on the MDR amount.
- Example: Transaction Rs 10,000, MDR 1.5% = Rs 150, GST on MDR = Rs 27. Net payout = Rs 9,823.
- For zero-MDR transactions (RuPay debit, UPI < Rs 20 Cr turnover), no GST applies.
- Acquirer issues a monthly tax invoice for MDR + GST. Merchant can claim input tax credit (ITC) if GST-registered.

## Best practices for merchants
- Reconcile daily, not monthly. Catching a mismatch on day 1 is easier than untangling 30 days of data.
- Maintain a mapping of TID to physical terminal location — helps trace missing transactions.
- Keep void/refund records separately — they reduce gross but shouldn't be treated as "missing."
- For multi-location merchants: reconcile per-TID first, then aggregate. Per-TID reconciliation catches terminal-specific issues.
