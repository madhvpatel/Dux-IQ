# RBI Payment Aggregator & Payment Gateway Guidelines

## Overview
RBI issued the PA-PG framework (March 2020, updated 2021-2024) to regulate entities that facilitate online payment processing. Key distinction:
- **Payment Aggregator (PA)**: Handles funds — pools merchant collections before settlement. Requires RBI authorisation. Examples: Razorpay, PayU, CCAvenue.
- **Payment Gateway (PG)**: Technology-only — provides the transaction processing interface but does not handle funds. Funds flow directly between merchant and acquiring bank. Does not require separate RBI license.

## Key requirements for Payment Aggregators

### Capital requirements
- Net worth: Rs 25 crore at the time of application, Rs 25 crore on an ongoing basis.
- Must be a company incorporated in India under the Companies Act.

### Escrow account
- PA must maintain an escrow account (Nodal Account) with a scheduled commercial bank.
- All merchant collections must flow through this escrow.
- Settlement to merchants must happen within **T+1 business day** of the transaction.
- PA cannot use merchant funds for its own purposes or earn interest on them.

### Merchant onboarding obligations
- PAs must perform due diligence on merchants before onboarding: KYC verification, business verification, website/app review.
- Risk categorisation at onboarding: Low, Medium, High risk based on MCC, business type, volume.
- Ongoing monitoring: transaction patterns, chargeback ratios, fraud indicators.
- PAs must de-board merchants that violate terms (illegal products, excessive fraud, unlicensed activities).

### Data security
- PCI-DSS compliance is mandatory.
- Card data must not be stored by the PA or merchant (tokenization mandate applies).
- PA must implement fraud detection and risk management framework.

## Impact on merchants
- Merchants must onboard with an RBI-authorised PA or directly with an acquiring bank.
- Settlement timelines are guaranteed (T+1 max from PA).
- Refund timelines: PA must process refunds within 5 business days of merchant-initiated request.
- Merchants can work with multiple PAs but must maintain separate MIDs with each.
- PA must provide merchants with: transaction reports, settlement reports, chargeback notifications.

## Direct bank acquiring vs PA acquiring
- **Direct bank acquiring**: Merchant has a direct relationship with the acquiring bank. Lower fees, faster settlements, but requires separate integration per bank.
- **PA acquiring**: PA handles integration complexity. Merchant gets one API for multiple payment modes. Slightly higher fees but simpler operations.
- For POS merchants, acquiring is typically direct with the bank (bank provides the terminal). PA model is more common for online/e-commerce.

## Recent regulatory updates (2023-2024)
- RBI allowed PAs to onboard merchants for UPI payments (previously restricted to banks).
- PAs must report cyber incidents to CERT-In within 6 hours.
- Customer data localisation: all payment data must be stored in India. Processing can happen abroad but data must return within 24 hours.
- Digital lending guidelines impact PAs that offer credit at checkout: lending partnerships must be with RBI-regulated entities.
