# Merchant Onboarding and KYC

## Onboarding process
Merchant onboarding is the process of enrolling a business to accept electronic payments through an acquiring bank or payment aggregator. In India, this involves identity verification, business validation, risk assessment, and terminal/gateway provisioning.

## KYC requirements by entity type

### Sole proprietorship
- PAN card of proprietor
- Aadhaar card of proprietor
- Business address proof (utility bill, rental agreement, or GST registration certificate)
- Bank account proof (cancelled cheque or bank statement with account details)
- Shop & Establishment Certificate or Udyam Registration (MSME)
- GST certificate (if registered; not mandatory for turnover < Rs 40 lakh)

### Partnership firm
- Partnership deed
- PAN of firm and all partners
- Aadhaar of all partners
- Address proof of business premises
- Bank account in firm's name
- GST registration certificate

### Private limited / LLP
- Certificate of Incorporation
- MOA and AOA (for Pvt Ltd) or LLP Agreement
- Board resolution authorising the signatory
- PAN of company and directors
- Aadhaar of directors
- Business address proof
- Bank account in company name
- GST registration certificate

## KYC verification methods
- **V-CIP (Video-based Customer Identification Process)**: Remote KYC via video call with a bank officer. RBI-approved for digital onboarding.
- **CKYC (Central KYC)**: Centralised KYC registry. If the merchant has completed KYC with any financial institution, the CKYC record can be retrieved using the KYC Identifier (KIN).
- **Aadhaar eKYC**: OTP-based Aadhaar verification. Quick but provides only limited data (name, address, photo).
- **Physical KYC**: In-person verification at branch or merchant premises. Required for high-risk merchants.

## Risk categorisation at onboarding

### Low risk (MCC examples: grocery, fuel stations, pharmacies)
- Standard KYC
- No rolling reserve
- T+1 settlement
- Chargeback monitoring: monthly review

### Medium risk (MCC examples: restaurants, retail, e-commerce)
- Enhanced KYC (website/app review, business model assessment)
- 5% rolling reserve may apply
- T+1 settlement
- Chargeback monitoring: weekly review

### High risk (MCC examples: travel agents, jewelers, digital goods, crypto)
- Full due diligence (financials, references, site visit)
- 10% rolling reserve
- T+2 settlement initially, reduced to T+1 after 6-month review
- Chargeback monitoring: daily review
- Transaction velocity limits may apply

## Post-onboarding lifecycle
- **Activation**: Terminal installation (POS) or API integration (online). Test transaction to verify end-to-end flow.
- **Monitoring period**: First 90 days — acquirer monitors for unusual patterns, chargeback velocity, refund ratio.
- **Annual review**: KYC re-verification, agreement renewal, MDR renegotiation.
- **Dormancy**: If no transactions for 180+ days, merchant account may be deactivated. Reactivation requires fresh verification.

## MCC (Merchant Category Code)
- 4-digit code assigned to every merchant at onboarding.
- Determines: MDR tier, interchange rate, risk classification, regulatory treatment.
- Common MCCs in India:
  - **5411**: Grocery stores
  - **5812**: Eating places / restaurants
  - **5541**: Fuel stations
  - **5311**: Department stores
  - **5944**: Jewelry stores
  - **4722**: Travel agencies
  - **5999**: Miscellaneous retail
  - **7299**: Miscellaneous services
- MCC misclassification can result in: wrong MDR applied, transactions declined (restricted MCC for certain card types), regulatory issues.

## Common onboarding issues
- "Application rejected": Most common reason is document mismatch — PAN name doesn't match bank account name. Ensure all documents have consistent entity name.
- "Terminal not working after installation": SIM not activated, TID not mapped in acquirer's host, or terminal not registered with the network.
- "Settlement not starting": Account validation (penny drop) failed. Check IFSC code and account number.
