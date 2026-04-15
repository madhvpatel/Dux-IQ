# NEFT, RTGS, and IMPS

## NEFT (National Electronic Funds Transfer)
- Batch-based settlement system operated by RBI.
- Settlements happen in half-hourly batches, 24x7 (since Dec 2019).
- No minimum or maximum transaction limit.
- Used primarily for: merchant refunds, vendor payments, bulk payouts, salary disbursements.
- Settlement finality: within the same batch (typically 15-30 minutes).
- Merchant relevance: acquirers may use NEFT for T+1/T+2 settlement payouts to merchant bank accounts.

## RTGS (Real Time Gross Settlement)
- Real-time, one-to-one settlement operated by RBI.
- Minimum amount: Rs 2,00,000. No upper limit.
- Available 24x7 (since Dec 2020).
- Used for: high-value settlements, inter-bank transfers, large merchant payouts.
- Settlement finality: immediate and irrevocable.
- Merchant relevance: large merchants receiving daily settlements above Rs 2 lakh may receive via RTGS for faster availability.

## IMPS (Immediate Payment Service)
- Real-time fund transfer by NPCI.
- Available 24x7 including holidays.
- Transaction limit: up to Rs 5,00,000 per transaction (bank-specific limits may be lower).
- Used for: instant refunds, same-day merchant payouts, P2P transfers.
- Settlement finality: immediate.
- Merchant relevance: some acquirers offer IMPS-based instant settlement for eligible merchants.

## Comparison for merchant payouts

| Feature | NEFT | RTGS | IMPS |
|---------|------|------|------|
| Speed | 15-30 min | Instant | Instant |
| Availability | 24x7 | 24x7 | 24x7 |
| Min amount | None | Rs 2 lakh | Rs 1 |
| Max amount | No limit | No limit | Rs 5 lakh |
| Cost to bank | Rs 2-5 | Rs 20-30 | Rs 5-15 |
| Best for | Bulk/scheduled payouts | High-value payouts | Instant/small payouts |

## NACH (National Automated Clearing House)
- NPCI's bulk/recurring payment system.
- Used for: EMI collections, insurance premiums, subscription debits, loan repayments.
- Mandate-based: customer pre-authorises debits.
- Settlement: T+1 typically.
- Merchant relevance: merchants with subscription/recurring models use NACH for auto-debits.
