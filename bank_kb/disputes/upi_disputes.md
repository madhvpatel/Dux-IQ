# UPI Disputes and Reversals

## UPI dispute framework
UPI disputes are governed by NPCI's Unified Dispute and Issue Resolution (UDIR) framework. Unlike card chargebacks which can take weeks, UPI disputes have strict timelines mandated by NPCI.

## Types of UPI disputes

### 1. Transaction not completed but amount debited
- Most common UPI complaint.
- Customer's account debited but merchant/beneficiary didn't receive funds.
- Cause: transaction timed out between debit at remitter bank and credit at beneficiary bank.
- **Auto-reversal**: NPCI mandates auto-reversal within **T+5 business days** if the beneficiary bank confirms non-credit. Since 2023, target is T+1 auto-reversal.
- Merchant impact: none if funds never reached merchant. If funds did reach merchant and customer disputes, acquirer will raise a reversal request.

### 2. Merchant fraud / service not rendered
- Customer claims they paid but didn't receive goods/services.
- Handled through bank's grievance process, then NPCI escalation.
- Timeline: 30 days for resolution. If unresolved, customer can escalate to Banking Ombudsman.

### 3. Duplicate transaction
- Customer charged twice for the same purchase.
- Merchant should void the duplicate and initiate refund via their dashboard/API.
- If merchant doesn't act, customer raises dispute with their bank.

## UPI response codes relevant to disputes

| Code | Meaning | Merchant action |
|------|---------|-----------------|
| U16 | VPA not found | Check customer VPA. Transaction will auto-fail. |
| U28 | REMITTER BANK NOT AVAILABLE | Retry. Customer's bank temporarily down. |
| U29 | DUPLICATE TRANSACTION | Do not process again. Original may have succeeded. Check with callback. |
| U30 | TRANSACTION LIMIT EXCEEDED | Customer hit their bank's UPI limit. Cannot retry same day. |
| U31 | INSUFFICIENT FUNDS | Customer issue. Inform customer to add funds. |
| U66 | DEVICE NOT REGISTERED | Customer needs to re-register UPI on their device. |
| U67 | TIMEOUT / NO RESPONSE FROM PSP | Most common issue. Retry is safe. Monitor callback for original. |
| U69 | REMITTER CBS OFFLINE | Customer's bank core banking is down. Wait and retry. |
| U91 | BENEFICIARY BANK DOWN | Your bank (payee side) is down. Escalate to your bank's UPI ops team. |

## Refund vs reversal
- **Refund**: Merchant-initiated. Merchant returns funds to customer voluntarily (return, cancellation). Processed as a new UPI credit transaction. Settles T+1.
- **Reversal**: System-initiated or dispute-initiated. Funds are pulled back from merchant via settlement adjustment. Merchant doesn't initiate.

## NPCI escalation path
1. Customer raises complaint with their bank (PSP app or bank branch).
2. Bank has 15 days to resolve.
3. If unresolved, customer escalates to NPCI via `https://www.npci.org.in/what-we-do/upi/dispute-redressal-mechanism`.
4. NPCI mediates between remitter and beneficiary banks.
5. If still unresolved after 30 days, customer can approach Banking Ombudsman (RBI).

## Merchant tips for reducing UPI disputes
- Always send payment confirmation (SMS/receipt) immediately after receiving UPI callback.
- For high-value transactions, verify the UPI transaction ID in your system before delivering goods.
- If a transaction shows "pending" for >5 minutes, do NOT deliver goods. Wait for final status callback.
- Maintain transaction logs with UPI reference ID, timestamp, amount, and customer VPA for at least 180 days.
