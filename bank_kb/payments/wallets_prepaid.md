# Wallets and Prepaid Instruments (PPI)

## What are PPIs
Prepaid Payment Instruments are payment methods where the value is loaded in advance. Regulated by RBI under the PPI Master Directions. Categories:
- **Closed-loop PPI**: Usable only at the issuing merchant (e.g., gift cards, store credits). Cannot be used for fund transfer. No KYC required.
- **Semi-closed PPI (wallets)**: Usable at any merchant that accepts them. Cannot withdraw cash. Examples: Paytm Wallet, PhonePe Wallet, Amazon Pay. Full KYC required for balance above Rs 10,000.
- **Open-loop PPI (prepaid cards)**: Work like debit cards on Visa/MC/RuPay. Can be used at any POS/online merchant. Cash withdrawal allowed at ATMs. Full KYC mandatory.

## Wallet payments at merchant POS
- Most wallet payments at physical stores now route through UPI (wallet linked to UPI).
- Some merchants still accept direct wallet payments via QR or app-to-app integration.
- Settlement: same as UPI settlement if routed via UPI rails. Direct wallet settlements depend on the wallet provider's terms.

## Prepaid card acceptance
- Accepted at any POS terminal that supports the card network (Visa/MC/RuPay).
- Some MCCs are restricted for prepaid cards (e.g., money transfer, gambling). Decline code 57 if attempted.
- Lower average ticket size than debit/credit cards.
- Higher decline rate due to insufficient balance (no overdraft facility).

## MDR on wallets/PPI
- Wallet-via-UPI: follows UPI MDR rules (zero MDR for eligible merchants).
- Prepaid card transactions: MDR similar to debit cards, typically 0.5% - 1.0%.
- Interchange on prepaid cards is generally lower than credit cards.

## Key regulations
- RBI mandates interoperability: wallets must be usable across merchants, not just the issuer's ecosystem.
- Full KYC wallets: max balance Rs 2,00,000, monthly transaction limit Rs 2,00,000.
- Minimum KYC wallets: max balance Rs 10,000, monthly limit Rs 10,000.
- PPI issuers must maintain an escrow/nodal account with a scheduled bank.

## Merchant considerations
- Wallet refunds typically process faster (instant to wallet) than card refunds (3-7 business days).
- For subscription businesses, wallet auto-debit requires e-mandate registration similar to UPI AutoPay.
- Gift card (closed-loop PPI) breakage (unused balance) is revenue for the merchant — track expiry policies.
