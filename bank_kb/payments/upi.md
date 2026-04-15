# UPI (Unified Payments Interface)

## What it is
UPI is India's real-time interbank payment system operated by NPCI (National Payments Corporation of India). It enables instant fund transfers between bank accounts via mobile devices using a Virtual Payment Address (VPA) like `merchant@bankname`.

## How it works for merchants
- **UPI QR (Static/Dynamic)**: Merchant displays a QR code. Customer scans and pays. Static QR has no amount pre-filled; dynamic QR includes the amount.
- **UPI Intent**: Customer clicks a payment link or button that opens their UPI app with pre-filled details.
- **UPI Collect**: Merchant sends a collect request to the customer's VPA. Customer approves in their UPI app.
- **UPI AutoPay (Mandates)**: Recurring payments. Customer pre-authorises a mandate for a fixed or variable amount, up to a cap. Mandate types: one-time, daily, weekly, monthly, quarterly, yearly. Amounts above Rs 15,000 require additional factor authentication (AFA) per debit.

## Settlement for UPI
- UPI transactions settle via NPCI to the acquiring bank's nodal account.
- Standard settlement cycle: **T+1** (next business day). Some acquirers offer T+0 for eligible merchants.
- Settlement amount = Gross collection minus MDR (if applicable) and applicable GST on MDR.
- Since Jan 2020, **zero MDR** applies to UPI transactions for merchants with turnover up to Rs 20 crore (per RBI/MEITY directive). Larger merchants may still have negotiated MDR.

## UPI Lite
- Small-value payments (up to Rs 500 per transaction, Rs 2,000 wallet limit) that don't require a PIN.
- Near-offline capability. Debits happen from a pre-loaded on-device wallet; credits settle later.
- Reduces issuer declines for low-value payments.

## Common UPI failure scenarios
- **Timeout / No response from beneficiary bank**: UPI response code U66, U67 — retry is safe.
- **Insufficient funds**: Response code U31.
- **Transaction limit exceeded**: Response code U30 — customer's daily/monthly limit hit.
- **Beneficiary bank down**: U91 — issuer or switch inoperative.
- **Duplicate transaction**: U29 — same transaction submitted twice within the dedup window.
- **VPA not found**: U16 — customer entered wrong VPA.

## Key numbers
- UPI processes **12-14 billion transactions per month** (as of 2024-25).
- Average ticket size: Rs 1,500-1,800.
- Peak hours: 10 AM - 1 PM, 5 PM - 9 PM IST.
- Transaction timeout: 30 seconds (NPCI mandate).

## Merchant tips
- If UPI success rate drops below 95%, check: (1) beneficiary bank health, (2) customer VPA validity, (3) network connectivity at POS.
- For high-value UPI transactions, prefer dynamic QR over collect requests — higher completion rates.
- Monitor `callback_delay` — if callbacks from NPCI take >5 seconds consistently, escalate to the bank's UPI ops team.
