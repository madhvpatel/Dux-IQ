# MDR Rules and Pricing

## What is MDR
Merchant Discount Rate (MDR) is the fee charged to the merchant on every electronic payment transaction. It is deducted from the settlement amount before payout. MDR compensates the payment ecosystem: acquirer, issuer, and network.

## MDR components

### Card transactions
**MDR = Interchange + Network fee + Acquirer markup**
- **Interchange**: Paid by acquirer to issuer. Set by the card network (Visa/MC/RuPay). Varies by card type, MCC, and transaction mode (contactless vs chip).
- **Network fee (scheme fee)**: Paid to Visa/MC/RuPay for processing. Typically 0.05% - 0.15%.
- **Acquirer markup**: The acquirer's margin. Negotiable between acquirer and merchant. Typically 0.10% - 0.50%.

### UPI transactions
- **Zero MDR**: Government directive (Jan 2020) mandates zero MDR on UPI and RuPay debit card transactions for merchants with annual turnover up to Rs 20 crore.
- Merchants above Rs 20 crore turnover: MDR may be negotiated bilaterally with the acquirer, but the market rate remains near zero due to competitive pressure.
- Subsidy: Government reimburses acquiring banks and PSPs for UPI processing costs through the Payments Infrastructure Development Fund (PIDF).

## MDR rate table (typical Indian market, 2024-25)

| Payment mode | MDR range | GST on MDR |
|-------------|-----------|------------|
| RuPay debit (< Rs 20 Cr) | 0.00% | None |
| UPI (< Rs 20 Cr) | 0.00% | None |
| Visa/MC debit | 0.40% - 0.90% | 18% |
| RuPay credit | 0.80% - 1.50% | 18% |
| Visa/MC credit | 1.20% - 2.50% | 18% |
| Premium/corporate credit | 2.00% - 3.00% | 18% |
| International cards | 2.50% - 3.50% | 18% |
| Prepaid cards | 0.50% - 1.20% | 18% |
| Wallets (via UPI) | 0.00% | None |
| AEPS (Aadhaar Enabled) | Rs 1 - Rs 3 flat | 18% |

## How MDR affects settlement
- Settlement payout = Gross transaction amount - MDR - GST on MDR.
- Example: Rs 10,000 credit card transaction at 2.0% MDR:
  - MDR = Rs 200
  - GST on MDR (18%) = Rs 36
  - Net payout = Rs 10,000 - Rs 200 - Rs 36 = **Rs 9,764**
- GST-registered merchants can claim Input Tax Credit (ITC) on the GST component.

## MDR negotiation factors
Merchants with higher volumes or lower risk get better MDR rates. Key factors:
1. **Monthly transaction volume**: Higher volume = lower MDR. Volume tiers are usually Rs 1L, 5L, 25L, 1Cr, 5Cr+.
2. **Average ticket size**: Higher ticket = slightly lower MDR percentage.
3. **Chargeback ratio**: High chargebacks = higher MDR or surcharge.
4. **MCC risk**: Low-risk MCCs (grocery, fuel, utilities) get lower rates. High-risk MCCs (travel, digital goods, jewelry) get higher rates.
5. **Card mix**: Predominantly debit card merchants get lower blended MDR than credit card-heavy merchants.

## Surcharge rules
- **RBI prohibits merchants from adding surcharge on card/UPI payments** (as of Jan 2020 directive).
- Merchants cannot pass MDR to the customer as a separate line item.
- Violation can result in: penalty from acquirer, merchant termination, regulatory action.
- Exception: Government payments (utility bills, taxes) may have convenience fees, which are different from MDR surcharge.

## Common merchant MDR complaints
- "My MDR rate changed without notice": Check agreement — acquirers can update rates with 30-day notice. Also check if card mix shifted (more credit cards = higher blended MDR).
- "International card MDR is too high": International interchange is set by networks and is higher. Acquirer has limited ability to reduce. Consider if international cards are a significant share.
- "I should have zero MDR on all transactions": Zero MDR only applies to UPI and RuPay debit for merchants under Rs 20 Cr turnover. Credit cards, Visa/MC debit, and international cards always carry MDR.
