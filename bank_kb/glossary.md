# Indian Payments Glossary

## Institutions and regulators

| Term | Full form | Role |
|------|-----------|------|
| **RBI** | Reserve Bank of India | Central bank. Regulates all payment systems in India. |
| **NPCI** | National Payments Corporation of India | Operates UPI, IMPS, NACH, RuPay, BBPS, AePS, FASTag. Promoted by RBI. |
| **SEBI** | Securities and Exchange Board of India | Regulates capital markets. Relevant for investment-related payments. |
| **CERT-In** | Indian Computer Emergency Response Team | National cybersecurity agency. PA/PGs must report incidents within 6 hours. |
| **UIDAI** | Unique Identification Authority of India | Issues Aadhaar. Relevant for eKYC and AePS. |
| **GSTN** | Goods and Services Tax Network | GST compliance platform. Relevant for MDR tax invoices. |

## Payment systems

| Term | Full form | What it is |
|------|-----------|------------|
| **UPI** | Unified Payments Interface | Real-time P2P/P2M payment system by NPCI. Uses VPA. |
| **IMPS** | Immediate Payment Service | Real-time fund transfer by NPCI. Up to Rs 5 lakh. |
| **NEFT** | National Electronic Funds Transfer | Batch-based fund transfer by RBI. 24x7 since Dec 2019. |
| **RTGS** | Real Time Gross Settlement | High-value real-time transfer by RBI. Min Rs 2 lakh. |
| **NACH** | National Automated Clearing House | Bulk/recurring payment system by NPCI. Used for EMIs, subscriptions. |
| **AEPS** | Aadhaar Enabled Payment System | Aadhaar + biometric based payment at micro-ATMs. For financial inclusion. |
| **BBPS** | Bharat Bill Payment System | Centralised bill payment system by NPCI. Utility bills, taxes, etc. |
| **BharatQR** | — | Interoperable QR code standard accepting Visa/MC/RuPay/UPI in one QR. |
| **FASTag** | — | RFID-based highway toll payment by NPCI. |

## Transaction and settlement terms

| Term | Meaning |
|------|---------|
| **MID** | Merchant ID — unique identifier assigned by acquirer to each merchant account. |
| **TID** | Terminal ID — unique identifier for each POS terminal. |
| **VPA** | Virtual Payment Address — UPI identifier like `shop@bankname`. |
| **MDR** | Merchant Discount Rate — fee deducted from merchant per transaction. |
| **Interchange** | Fee paid by acquirer to issuer per card transaction. Set by card network. |
| **T+0 / T+1 / T+2** | Settlement cycle. T = transaction date. T+1 = next business day. |
| **UTR** | Unique Transaction Reference — identifies NEFT/RTGS/IMPS transfers. |
| **RRN** | Retrieval Reference Number — unique ID for card transactions. |
| **ARN** | Acquirer Reference Number — used to trace transactions in Visa/MC network. |
| **BIN** | Bank Identification Number — first 6-8 digits of card number identifying the issuer. |
| **MCC** | Merchant Category Code — 4-digit code classifying the merchant's business type. |
| **PAN** | Primary Account Number — the 16-digit card number (or Permanent Account Number for tax). |
| **EMV** | Europay-Mastercard-Visa — chip card standard. |
| **NFC** | Near Field Communication — technology behind contactless tap payments. |
| **3DS** | 3D Secure — additional authentication layer for online card payments (OTP/biometric). |
| **CVV/CVC** | Card Verification Value/Code — 3-digit security code on the back of the card. |

## Dispute terms

| Term | Meaning |
|------|---------|
| **Chargeback** | Forced reversal of a transaction by the issuing bank on behalf of the cardholder. |
| **Representment** | Merchant's formal evidence submission to contest a chargeback. |
| **Pre-arbitration** | Second-level dispute escalation before final arbitration by the card network. |
| **Arbitration** | Final binding decision by the card network on a disputed transaction. |
| **Friendly fraud** | Cardholder disputes a legitimate transaction (intentionally or by mistake). |
| **First chargeback rights** | Initial period where issuer can raise a chargeback without need for prior retrieval request. |
| **UDIR** | Unified Dispute and Issue Resolution — NPCI's framework for UPI disputes. |

## Compliance and security terms

| Term | Meaning |
|------|---------|
| **PCI-DSS** | Payment Card Industry Data Security Standard — mandatory for all entities handling card data. |
| **PCI PTS** | PCI PIN Transaction Security — hardware security standard for POS terminals. |
| **PA** | Payment Aggregator — entity that pools merchant payments (RBI-regulated). |
| **PG** | Payment Gateway — technology provider for payment processing (not separately regulated). |
| **KYC** | Know Your Customer — identity verification process. |
| **CKYC** | Central KYC — centralised identity registry across financial institutions. |
| **V-CIP** | Video Customer Identification Process — remote video KYC approved by RBI. |
| **Tokenization** | Replacing card PAN with a unique token for storage. RBI mandated from Oct 2022. |
| **DUKPT** | Derived Unique Key Per Transaction — encryption key management scheme used in POS terminals. |
| **TMS** | Terminal Management System — remote terminal configuration and key management platform. |
| **Nodal account** | Escrow bank account where Payment Aggregators pool merchant collections before settlement. |
| **Rolling reserve** | Percentage of settlement withheld by acquirer as chargeback buffer, released after a holding period. |
| **Penny drop** | Small-value (Rs 1) test transfer to verify merchant bank account details before activation. |

## Business metrics

| Term | Meaning | Healthy range |
|------|---------|---------------|
| **Success rate** | Approved transactions / Total attempted transactions | >95% for cards, >96% for UPI |
| **Chargeback ratio** | Chargebacks / Total transactions (count) | <1.0% (Visa monitoring starts at 0.9%) |
| **Refund rate** | Refund amount / Gross transaction amount | <5% (varies by industry) |
| **Settlement accuracy** | Correctly settled transactions / Total transactions | >99% |
| **Terminal uptime** | Hours terminal is online / Total operating hours | >99% |
| **Average ticket size** | Total transaction value / Number of transactions | Varies by MCC |
