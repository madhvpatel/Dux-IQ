# Payout Holds and Delays

## Types of settlement holds

### 1. Risk hold
- **Trigger**: Chargeback ratio exceeds threshold (typically >1% of transaction count or >0.5% of volume), sudden spike in transaction volume, fraud alert from network.
- **Duration**: Until risk review is complete (3-15 business days).
- **Merchant impact**: 100% of settlements frozen. No partial release.
- **Resolution**: Merchant must provide: transaction receipts, delivery proofs, customer communication records. Risk team reviews and either releases funds or initiates investigation.
- **Merchant advice**: Maintain delivery proof for all high-value transactions. Respond to risk team queries within 24 hours — delays extend the hold.

### 2. Chargeback reserve (rolling reserve)
- **Trigger**: Applied at onboarding for high-risk MCCs (travel, e-commerce, digital goods) or after chargeback history exceeds threshold.
- **Mechanism**: Acquirer withholds 5-10% of each settlement as reserve. Released on a rolling basis after the reserve period (typically 90-180 days).
- **Example**: Rs 1,00,000 gross settlement, 10% reserve = Rs 10,000 held. After 90 days, the first day's reserve is released (assuming no chargebacks consumed it).
- **Merchant advice**: Factor reserve into cashflow planning. Monitor chargeback ratio to negotiate reserve reduction at next agreement renewal.

### 3. Documentation / compliance hold
- **Trigger**: KYC documents expired, GST registration lapsed, agreement not renewed, bank account details changed but not verified.
- **Duration**: Until documents are submitted and verified (1-5 business days after submission).
- **Merchant advice**: Track document expiry dates proactively. Submit renewal documents 30 days before expiry.

### 4. Technical hold
- **Trigger**: Settlement file generation failure, IFSC code changed (bank branch migration), account number validation failure (penny drop test failed).
- **Duration**: 1-3 business days after correction.
- **Common cause**: Bank mergers — IFSC codes change when banks merge (e.g., erstwhile Vijaya Bank branches migrated to Bank of Baroda IFSCs).
- **Merchant advice**: After any bank account change, confirm with acquirer that penny drop verification passed before the next settlement cycle.

### 5. Regulatory / legal hold
- **Trigger**: Court order, enforcement directorate notice, income tax department attachment, PMLA investigation.
- **Duration**: As per legal order. Acquirer has no discretion to release.
- **Merchant impact**: May affect all accounts under the same PAN/entity.

## Holiday calendar impact
- Settlements are not processed on bank holidays (national and state-specific).
- Long weekends and festival periods (Diwali, Christmas-New Year) can cause 3-5 day gaps.
- High-volume merchants should plan working capital for holiday periods.
- RBI holiday calendar is published annually. NPCI follows the same.

## Escalation path for delayed settlements
1. **Day 1-2**: Check acquirer's merchant portal for settlement status. Common statuses: Processed, In Transit, On Hold, Failed.
2. **Day 3**: Contact acquirer's merchant helpdesk with MID and expected settlement date.
3. **Day 5+**: Escalate to relationship manager. Request written confirmation of hold reason and expected release date.
4. **Day 10+**: If unresolved, file complaint on RBI's CMS (Complaint Management System) portal or NPCI's dispute resolution.
