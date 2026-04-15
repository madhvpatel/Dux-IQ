# Card Payments (Debit, Credit, Prepaid)

## Card networks in India
- **RuPay**: NPCI's domestic card network. Dominates debit cards (70%+ of debit card issuance). Lower interchange for acquirers.
- **Visa / Mastercard**: International networks. Higher interchange but broader international acceptance.
- **Amex / Diners**: Closed-loop networks. Merchant must be separately onboarded; not all acquirers support them.

## Transaction flow (POS)
1. Customer taps/dips/swipes card at terminal.
2. Terminal sends authorisation request to acquirer processor.
3. Acquirer routes to card network (Visa/MC/RuPay).
4. Network routes to issuing bank for approval.
5. Issuer checks: balance/limit, PIN/OTP, fraud rules, card status.
6. Response travels back: Issuer -> Network -> Acquirer -> Terminal.
7. Entire round-trip: typically 3-8 seconds.

## EMV chip vs contactless vs magstripe
- **EMV chip (dip)**: Most secure. Card is inserted; chip generates a unique cryptogram per transaction. Mandatory for all new cards.
- **Contactless (tap)**: NFC-based. Transactions up to Rs 5,000 don't require PIN (RBI mandate). Above Rs 5,000 requires PIN. Faster checkout.
- **Magstripe (swipe)**: Legacy. Being phased out. Higher fraud risk. Some issuers still allow for fallback when chip fails.

## MDR (Merchant Discount Rate)
- MDR is the fee charged to the merchant per card transaction.
- Components: Interchange (to issuer) + Network fee (to Visa/MC/RuPay) + Acquirer margin.
- Typical ranges:
  - **Debit card RuPay**: 0% MDR (as per govt directive for turnover < Rs 20 Cr).
  - **Debit card Visa/MC**: 0.40% - 0.90%.
  - **Credit card**: 1.20% - 2.50% depending on card type and merchant category.
  - **Commercial/corporate cards**: Higher, often 2.0% - 3.0%.
- MDR is deducted from settlement amount. GST (18%) applies on MDR.

## Tokenization
- RBI mandated card-on-file tokenization from Oct 2022. Merchants cannot store full card numbers.
- Cards are replaced with device-specific tokens issued by the card network.
- Token requestor: the entity (merchant/aggregator) requesting the token.
- Impact on merchants: returning customers must re-tokenize if they switch devices.
- Tokenized transactions have equal or better approval rates than raw card transactions.

## Common decline reasons
- **51 — Insufficient funds**: Most common. Customer issue.
- **55 — Incorrect PIN**: Customer entered wrong PIN. 3 consecutive wrong PINs = card blocked.
- **57 — Transaction not permitted**: Card type restriction (e.g., international card blocked for domestic, or prepaid card not allowed for this MCC).
- **91 — Issuer unavailable**: Bank's switch is down. Retry after 2-5 minutes.
- **14 — Invalid card number**: Card number failed Luhn check or not found in issuer's database.
- **05 — Do not honour**: Generic decline. Could be risk rules, velocity checks, or account issues.

## Merchant tips
- If card decline rate exceeds 15%, investigate: (1) are most declines code 51? (Customer mix issue, not terminal.) (2) are declines code 91? (Issuer outage — temporary.) (3) are declines code 57/58? (Terminal misconfiguration.)
- Contactless transactions have 2-3% higher success rates than chip transactions due to fewer PIN entry errors.
- For high-value transactions, ensure the terminal supports EMV with online PIN verification.
