# Chargeback Lifecycle

## What is a chargeback
A chargeback is a forced reversal of a card transaction initiated by the cardholder's issuing bank. The funds are debited from the merchant's settlement and returned to the cardholder. Chargebacks exist to protect consumers from fraud and merchant misconduct, but they are frequently misused (friendly fraud).

## Chargeback flow

### Stage 1: First chargeback (Retrieval/Dispute)
1. Cardholder contacts their bank claiming the transaction is fraudulent, not received, or defective.
2. Issuer raises a chargeback through the card network (Visa/MC/RuPay).
3. Acquirer receives the chargeback and debits the amount from the merchant's next settlement.
4. Merchant is notified with: chargeback amount, reason code, deadline for response, ARN (Acquirer Reference Number).
5. **Deadline**: Merchant typically has **7-15 calendar days** to respond with evidence (varies by network).

### Stage 2: Representment
1. Merchant submits evidence (compelling evidence) through the acquirer's dispute portal.
2. Required evidence depends on reason code:
   - **Fraud (10.4 Visa / 4837 MC)**: Signed receipt, delivery proof, AVS/CVV match, 3DS authentication log.
   - **Not received (13.1 Visa / 4855 MC)**: Shipping tracking, delivery confirmation, signed POD.
   - **Not as described (13.3 Visa / 4853 MC)**: Product description as shown to customer, return policy, communication logs.
   - **Duplicate (12.6 Visa / 4834 MC)**: Show that transactions are different (different dates, items, or amounts).
3. Acquirer submits representment to issuer via network.
4. Issuer reviews and either accepts (chargeback reversed, merchant wins) or escalates.

### Stage 3: Pre-arbitration
1. If issuer rejects representment, they can file pre-arbitration.
2. Merchant can: accept the loss, or escalate to full arbitration.
3. **Cost warning**: Arbitration has filing fees — Rs 25,000-50,000 (Visa) or Rs 15,000-40,000 (MC). Merchant pays if they lose.

### Stage 4: Arbitration
1. Card network reviews all evidence and makes a binding decision.
2. Decision is final. Losing party pays the arbitration fee.
3. Very few chargebacks reach this stage (<1% of all disputes).

## Chargeback reason codes (most common in India)

### Visa
- **10.4**: Fraud — card-present / card-not-present
- **13.1**: Merchandise/services not received
- **13.3**: Not as described or defective
- **12.6**: Duplicate processing
- **11.1**: Card recovery bulletin (stolen card)
- **13.7**: Cancelled merchandise/services

### Mastercard
- **4837**: No-cardholder-authorization (fraud)
- **4855**: Goods/services not provided
- **4853**: Cardholder dispute — not as described
- **4834**: Duplicate transaction
- **4863**: Cardholder does not recognise transaction

### RuPay
- RuPay follows a simplified dispute framework managed by NPCI.
- Common categories: fraud, non-receipt, ATM disputes.
- Timeline: 45-day window for cardholder to raise dispute, 15-day window for merchant response.

## Key timelines

| Stage | Visa | Mastercard | RuPay |
|-------|------|------------|-------|
| Cardholder to raise dispute | 120 days from transaction | 120 days | 45 days |
| Merchant response deadline | 7-15 days | 7-18 days | 15 days |
| Pre-arbitration | 30 days | 45 days | N/A |
| Arbitration decision | 30-60 days | 30-60 days | NPCI decides |

## Chargeback metrics
- **Chargeback ratio**: Chargebacks / Total transactions (count-based). Threshold: Visa monitors at >0.9%, enforcement at >1.8%. Mastercard EFM threshold: >1.5%.
- **Chargeback-to-sales ratio**: Chargeback amount / Total sales amount. Healthy: <0.5%.
- Exceeding thresholds triggers: monitoring program enrollment, increased reserves, potential termination.

## Merchant best practices
- Respond to every chargeback within deadline — even if evidence is weak. No-response = automatic loss.
- Use clear billing descriptors — "SHOPNAME*CITY" — so customers recognise the charge on their statement.
- Enable 3D Secure (3DS) for online transactions — shifts fraud liability to issuer.
- Keep transaction receipts for 540 days (maximum dispute window including arbitration).
- Track chargeback reasons: if >50% are "not received," the problem is fulfillment, not fraud.
