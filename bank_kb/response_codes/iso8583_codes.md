# ISO 8583 Response Codes (Card Transactions)

## Overview
ISO 8583 response codes are two-character codes returned by the issuing bank to indicate the result of a card authorization request. These flow from issuer -> network -> acquirer -> terminal. The merchant sees these as decline/approval reasons.

## Success codes

| Code | Meaning | Merchant action |
|------|---------|-----------------|
| 00 | Approved | Transaction successful. Print receipt. |
| 08 | Honour with identification | Approved but verify cardholder ID. Rare in India. |
| 10 | Partial approval | Only part of the amount was approved. Common for prepaid cards. Ask customer for alternate payment for the balance. |
| 11 | Approved (VIP) | Approved. No special action. |
| 85 | No reason to decline | Approved. Used for account verification (zero-value auth). |

## Customer-related declines

| Code | Meaning | Category | Merchant advice to customer |
|------|---------|----------|----------------------------|
| 51 | Insufficient funds | Balance | "Please check your account balance or try a different card." |
| 55 | Incorrect PIN | Authentication | "Please re-enter your PIN carefully." 3 wrong attempts = card blocked. |
| 61 | Exceeds withdrawal limit | Limit | "Your daily transaction limit has been reached. Try tomorrow or contact your bank to increase the limit." |
| 65 | Activity count limit exceeded | Velocity | "You've exceeded the number of transactions allowed today." |
| 75 | PIN tries exceeded | Security | "Your card PIN is blocked due to multiple wrong attempts. Please contact your bank." |
| N4 | Exceeds issuer withdrawal limit | Limit | Same as 61. Some issuers use this instead. |

## Card-related declines

| Code | Meaning | Category | What it means |
|------|---------|----------|---------------|
| 14 | Invalid card number | Card data | Card number failed Luhn check or not in issuer's database. Possible keying error. |
| 41 | Lost card — pick up | Security | Card reported lost. Do NOT return the card if physically present. |
| 43 | Stolen card — pick up | Security | Card reported stolen. Do NOT return the card. |
| 54 | Expired card | Card status | Card past expiry date. Customer needs a replacement from their bank. |
| 57 | Transaction not permitted to cardholder | Restriction | Card type not allowed for this transaction (e.g., international card blocked, prepaid card restricted for this MCC). |
| 62 | Restricted card | Restriction | Card has geographic or usage restrictions set by issuer. |

## Issuer / network declines

| Code | Meaning | Category | Merchant action |
|------|---------|----------|-----------------|
| 05 | Do not honour | Generic | Generic decline. Could be risk rules, velocity limits, or account issues. Customer should contact their bank. |
| 06 | Error | System | Processing error at issuer. Retry once. If persists, try a different payment method. |
| 12 | Invalid transaction | Config | Transaction type not supported by issuer. Check terminal configuration. |
| 13 | Invalid amount | Validation | Amount format error. Check terminal settings (decimal handling). |
| 58 | Transaction not permitted to terminal | Config | Terminal not authorized for this transaction type. Contact acquirer to enable. |
| 91 | Issuer or switch inoperative | Outage | Issuer's system is down. Retry in 2-5 minutes. If widespread, it's a bank outage — wait. |
| 92 | Financial institution not found | Routing | Transaction couldn't be routed to the issuer. Possible network issue. |
| 96 | System malfunction | System | Generic system error. Retry. If persists, contact acquirer. |

## Fraud-related declines

| Code | Meaning | Category | Notes |
|------|---------|----------|-------|
| N1 | Suspected fraud | Risk | Issuer's fraud detection flagged the transaction. Customer must contact their bank. |
| N7 | CVV2 mismatch | Authentication | For online transactions. Customer entered wrong CVV. |
| 04 | Pick up card | Security | Issuer wants the card confiscated. Usually fraud-related. |
| 07 | Pick up card — special conditions | Security | Fraud confirmed. Card should not be returned. |

## Special codes

| Code | Meaning | Notes |
|------|---------|-------|
| 01 | Refer to card issuer | Merchant should call the issuer's authorization center for voice auth. Rare today. |
| 03 | Invalid merchant | MID not recognized by issuer's system. Contact acquirer. |
| 15 | No such issuer | BIN (first 6 digits of card) not recognized. Could be a new card range not yet configured. |
| 30 | Format error | Message format error between acquirer and issuer. Technical issue — contact acquirer. |
| 68 | Response received too late | Authorization timed out. Transaction status uncertain. DO NOT retry without checking — may result in duplicate. |

## How agents should use this
When a merchant asks "why did this transaction fail?" — look up the response code from the transaction record and provide:
1. The meaning in plain language.
2. Whether it's a customer issue, merchant issue, or system issue.
3. What the merchant should do (retry, ask customer to call bank, contact acquirer, etc.).
4. Whether the issue is temporary (retry is safe) or persistent (needs resolution).
