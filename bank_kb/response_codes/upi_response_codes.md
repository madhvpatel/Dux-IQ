# UPI Response Codes

## Overview
UPI transactions return response codes defined by NPCI. These indicate the result of a payment attempt and help diagnose failures. The codes are alphanumeric, prefixed with "U" for UPI-specific codes.

## Success

| Code | Meaning | Notes |
|------|---------|-------|
| 00 / SUCCESS | Transaction successful | Payment completed. Callback received. |
| S | SUCCESS | Alternate success indicator in some PSP responses. |

## Customer-side failures

| Code | Meaning | Retry? | Merchant advice |
|------|---------|--------|-----------------|
| U30 | TRANSACTION LIMIT EXCEEDED | No | Customer hit daily/monthly UPI limit (bank-specific, typically Rs 1-2 lakh/day). "Try again tomorrow or use a different payment method." |
| U31 | INSUFFICIENT FUNDS IN ACCOUNT | No | "Please ensure sufficient balance and try again." |
| U66 | DEVICE NOT REGISTERED | No | Customer's UPI app not registered on this device. They need to re-register. |
| U14 | ENCRYPTION ERROR | No | Customer's UPI app needs update. |
| U09 | REQUEST TIME OUT — CUSTOMER | No | Customer didn't approve the collect request in time (60-second window). |
| U78 | PSP IS NOT REGISTERED | No | Customer's UPI app (PSP) has an issue. They should update or re-install. |

## Bank-side failures (remitter — customer's bank)

| Code | Meaning | Retry? | Notes |
|------|---------|--------|-------|
| U28 | REMITTER BANK NOT AVAILABLE | Yes (after 5 min) | Customer's bank CBS is temporarily down. |
| U69 | REMITTER CBS OFFLINE | Yes (after 5 min) | Same as U28 — core banking system offline. |
| U67 | TIMEOUT / NO RESPONSE FROM PSP | Yes | Most common failure code. Customer's bank didn't respond in time. Usually intermittent. |
| U08 | REMITTER BANK DECLINED | No | Customer's bank declined for unspecified reason. Customer should contact their bank. |

## Bank-side failures (beneficiary — merchant's bank)

| Code | Meaning | Retry? | Notes |
|------|---------|--------|-------|
| U91 | BENEFICIARY BANK DOWN | Yes (after 5 min) | Merchant's bank is temporarily unavailable. If prolonged, escalate to bank UPI ops. |
| U10 | BENEFICIARY BANK NOT AVAILABLE | Yes | Similar to U91. |

## Transaction-level issues

| Code | Meaning | Retry? | Notes |
|------|---------|--------|-------|
| U16 | VPA NOT FOUND / INVALID VPA | No | Customer entered wrong VPA. Verify the VPA and retry with correct value. |
| U12 | INVALID TRANSACTION / RESTRICTED CODE | No | Transaction type not allowed. Check merchant VPA configuration. |
| U29 | DUPLICATE TRANSACTION | No | Same transaction submitted twice within dedup window (typically 5 minutes). Original may have succeeded — check status. |
| U17 | PSP ORGID MISMATCH | No | Technical error in UPI app configuration. Customer needs to update their app. |

## System / NPCI failures

| Code | Meaning | Retry? | Notes |
|------|---------|--------|-------|
| U68 | NPCI SYSTEM ERROR | Yes (after 2 min) | NPCI infrastructure issue. Usually resolves quickly. |
| U70 | NPCI SYSTEM DECLINES | Yes | NPCI rate limiting or system protection. Back off and retry. |
| U22 | REMITTER CBS NOT AVAILABLE | Yes | Variant of U28. |

## Deemed success / pending states

| Code | Meaning | Action |
|------|---------|--------|
| PENDING | Transaction in progress | Wait for callback. Do NOT initiate a new transaction. Status will resolve to success or failure within 48 hours (NPCI mandate). |
| DEEMED | Deemed approved by NPCI | Funds debited from customer but credit to merchant pending. Will settle automatically. Merchant can deliver goods/services. |

## Auto-reversal rules
- If a transaction is debited from customer but not credited to merchant within the NPCI timeout window:
  - Beneficiary bank must confirm non-credit within **T+1 business day**.
  - NPCI initiates auto-reversal to customer within **T+5 business days** (target: same day since 2023).
  - Merchant is not debited (funds never reached merchant's account).

## Failure rate benchmarks
- Industry average UPI success rate: **96-98%** (2024-25).
- If merchant's UPI success rate drops below 95%: investigate beneficiary bank health (U91), check VPA configuration, review timeout patterns (U67).
- Most UPI failures (60%+) are U67/U28/U69 (timeout/bank unavailable) — temporary and not merchant's fault.

## How agents should use this
When a merchant reports UPI payment failures:
1. Check the specific response code from the transaction record.
2. Determine if it's customer-side, bank-side, or system-side.
3. If retryable: advise how long to wait.
4. If persistent (same code, multiple transactions): check if it's a bank outage (all transactions failing) vs customer-specific issue (one customer failing).
5. For U91 lasting >30 minutes: recommend merchant contact their bank's UPI operations team for status update.
