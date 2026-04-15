# Representment — Winning Chargebacks

## What is representment
Representment is the merchant's formal response to a chargeback, presenting evidence that the original transaction was legitimate. It is the single most impactful action a merchant can take to recover disputed funds. Average representment win rate across Indian merchants: 30-45%.

## Evidence requirements by dispute type

### Fraud (Visa 10.4, MC 4837)
**Goal**: Prove the legitimate cardholder authorised the transaction.
- 3D Secure authentication log (strongest evidence — shifts liability to issuer).
- AVS (Address Verification Service) match result.
- CVV/CVC match confirmation.
- IP address and device fingerprint matching cardholder's known profile.
- Delivery to cardholder's billing address.
- Prior undisputed transactions from the same card/device.

### Not received (Visa 13.1, MC 4855)
**Goal**: Prove goods/services were delivered.
- Shipping tracking number with carrier confirmation of delivery.
- Signed proof of delivery (POD) — physical signature or OTP-based delivery confirmation.
- GPS/timestamp from delivery agent at drop location.
- For digital goods: download/access logs showing customer used the product.
- For services: appointment records, check-in timestamps, service completion reports.

### Not as described (Visa 13.3, MC 4853)
**Goal**: Prove goods/services matched what was advertised.
- Product listing as shown to customer at time of purchase (screenshot with timestamp).
- Customer accepted return/refund policy at checkout.
- Communication showing customer was offered resolution (replacement/repair/refund).
- If customer returned item: inspection report showing item was as described.

### Duplicate (Visa 12.6, MC 4834)
**Goal**: Prove each charge represents a separate transaction.
- Two separate invoices/receipts with different items or different dates.
- If truly duplicate: proof that refund was already processed for the duplicate.
- Terminal batch records showing distinct transaction entries.

### Cancelled / refund not processed (Visa 13.6, MC 4841)
**Goal**: Prove cancellation policy was disclosed and either not applicable, or refund was processed.
- Cancellation/refund policy as displayed to customer.
- Proof that customer didn't follow the cancellation procedure.
- If refund was issued: refund transaction reference, ARN, and date.

## Formatting best practices
- Submit evidence as a single, clear PDF — not multiple loose files.
- Include a cover letter summarising: transaction date, amount, what was sold, why the chargeback is invalid.
- Highlight the most relevant evidence. Reviewers at the issuer spend <2 minutes per case.
- Redact sensitive data (full card number, Aadhaar) — only last 4 digits of card needed.
- Maximum file size: typically 5-10 MB per submission (check acquirer portal limits).

## Common mistakes that lose cases
1. **No response**: Automatic loss. Always respond, even with partial evidence.
2. **Wrong evidence for the reason code**: Sending delivery proof for a fraud dispute doesn't help — fraud disputes question whether the cardholder authorised the payment, not whether goods were delivered.
3. **Late response**: Submitting after the deadline = automatic loss. No exceptions.
4. **Generic template responses**: Issuers recognise copy-paste defenses. Tailor evidence to the specific transaction.
5. **Missing the refund angle**: If you already refunded the customer, submit the refund ARN. The chargeback becomes a double recovery attempt and is easily overturned.

## Win rate benchmarks (Indian market)
- Fraud disputes (with 3DS): 70-80% win rate (liability shift).
- Fraud disputes (without 3DS): 15-25% win rate.
- Not received (with delivery proof): 60-70% win rate.
- Not received (without delivery proof): <10% win rate.
- Not as described: 25-35% win rate (subjective, harder to prove).
- Duplicate: 80-90% win rate (easy to demonstrate with two receipts or refund proof).
