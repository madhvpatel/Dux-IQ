"""
pax_errors.py — PAX POS terminal error knowledge base.

Structured from ICICI Bank PAX POS Terminal Error Messages Reference (April 2026).
Each error has: message, trigger condition, transaction flow, recommended action, and category.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PaxError:
    category: str
    message: str
    trigger: str
    flow: str
    action: str


# ── Full PAX error catalogue ─────────────────────────────────────────────────

PAX_ERRORS: list[PaxError] = [
    # 1. Amount & Input Validation
    PaxError("Amount & Input Validation", "Enter Amount", "Merchant taps Proceed without entering any amount.", "Sale / Pre-Auth / Cash@POS", "Enter a non-zero transaction amount and tap Proceed."),
    PaxError("Amount & Input Validation", "Enter valid amount", "Amount field contains '0.00', starts with '0', or is left blank.", "Sale / Pre-Auth / Cash@POS", "Enter a valid amount greater than zero."),
    PaxError("Amount & Input Validation", "Transaction exceeds limit", "Entered amount is greater than the per-transaction limit configured on the terminal.", "Sale / Tip / Pre-Auth / Auth Completion", "Reduce the amount. For large transactions contact the acquirer to increase limits."),
    PaxError("Amount & Input Validation", "Daily Transaction limit exceeds", "Accumulated daily transaction total will be exceeded by this transaction.", "Sale / Tip", "Retry after midnight reset, or contact the acquirer to review daily limits."),
    PaxError("Amount & Input Validation", "Amount should be in multiples of 100", "Cash@POS transaction amount is not a multiple of ₹100.", "Cash@POS", "Re-enter the amount as a multiple of ₹100 (e.g., ₹500, ₹1000)."),
    PaxError("Amount & Input Validation", "Amount should be less than 2000", "Cash@POS transaction amount exceeds ₹2000 maximum limit.", "Cash@POS", "Enter an amount ≤ ₹2000 for Cash@POS transactions."),
    PaxError("Amount & Input Validation", "Enter valid tip amount", "Tip field contains only a decimal point or tip value is less than ₹1.", "Sale (Tip enabled)", "Enter a valid numeric tip amount ≥ ₹1."),
    PaxError("Amount & Input Validation", "Tip amount too large", "Entered tip exceeds the maximum tip percentage configured for the terminal.", "Sale (Tip enabled)", "Enter a tip within the allowed percentage of the base amount shown."),
    PaxError("Amount & Input Validation", "Enter Invoice Number", "Auth Completion screen submitted without entering an invoice number.", "Auth Completion", "Enter the invoice number from the original Pre-Auth transaction receipt."),
    PaxError("Amount & Input Validation", "Enter valid invoice number", "Invoice number entered is empty or less than 6 characters long.", "Auth Completion", "Enter a valid invoice number (minimum 6 characters)."),
    PaxError("Amount & Input Validation", "Kindly use a Credit Card for Pre Auth Payments", "A debit or non-credit card is presented for a Pre-Auth transaction.", "Pre-Auth", "Ask the customer to present a Credit Card for Pre-Auth."),

    # 2. Card Reading Errors
    PaxError("Card Reading", "Read Card Failed, Please Retry", "Card data could not be read after a swipe, chip insert, or tap attempt.", "All card transactions", "Try again. If the card is dirty, clean it gently. Try a different entry method (insert vs. swipe)."),
    PaxError("Card Reading", "Failed to Read Card", "Terminal completely failed to read the card after all retries.", "All card transactions", "Try a different card or contact the issuer."),
    PaxError("Card Reading", "The Card Is IC Card, Please Insert Card!", "Customer swiped a chip card. Terminal requires chip insertion for EMV compliance.", "All card transactions", "Remove the card and re-insert it chip-first into the slot."),
    PaxError("Card Reading", "Card number is not valid", "Manual card entry: the PAN entered fails the check or has invalid length.", "Manual Card Entry", "Re-enter the card number carefully. Verify it from the physical card."),
    PaxError("Card Reading", "Please enter a valid expiry date and try again", "Manual card entry: expiry date is empty, wrong format, or already passed.", "Manual Card Entry", "Enter the expiry date exactly as printed on the card in MM/YY format."),
    PaxError("Card Reading", "Fallback transactions are disabled", "EMV chip read failed and magnetic stripe fallback is disabled by acquirer policy.", "Sale / Refund (chip card)", "Try re-inserting the chip. If chip is damaged, contact the acquirer to enable fallback."),
    PaxError("Card Reading", "Mag-Stripe transactions are disabled", "Customer swiped a card but magnetic stripe transactions are disabled.", "Sale / Refund", "Insert the chip or tap the card. If the card has no chip, contact the acquirer."),
    PaxError("Card Reading", "Contact PreProc Fail", "EMV contact chip pre-processing failed before any transaction data was sent.", "All chip card transactions", "Remove and reinsert the card. If persistent, try a different card."),
    PaxError("Card Reading", "Clss PreProc Fail", "EMV contactless pre-processing failed.", "Contactless transactions", "Retry the tap. If it keeps failing, try inserting the chip instead."),
    PaxError("Card Reading", "No supported trans method", "None of the allowed card entry methods (swipe/chip/tap) are available.", "All card transactions", "Contact support to verify terminal card method configuration."),
    PaxError("Card Reading", "No PIN", "Terminal cannot find or connect to the external PIN pad device.", "PIN-required transactions", "Check PIN pad cable/connection. Restart the terminal."),

    # 3. PIN & Password Errors
    PaxError("PIN & Password", "Wrong Pin Attempts left", "Customer entered an incorrect PIN. Remaining attempt count is shown.", "Sale / Refund / EMI (debit/credit card with PIN)", "Customer should enter the correct PIN. After all attempts are exhausted the card may get blocked by the issuer."),
    PaxError("PIN & Password", "Failed to read pin", "PIN entry device timed out or failed to capture the PIN.", "All PIN-required card transactions", "Ask the customer to retry PIN entry transaction."),
    PaxError("PIN & Password", "Please enter valid card pin", "Customer submitted the PIN entry screen without entering any PIN.", "All PIN-required transactions", "Customer should enter their card PIN before confirming."),

    # 4. Network & Host Communication
    PaxError("Network & Host Communication", "Timeout", "Terminal sent the transaction but no response arrived within the timeout period.", "All online transactions", "Check network signal. Retry the transaction. If persistent, contact the payment host/acquirer."),
    PaxError("Network & Host Communication", "Connect Error", "Terminal failed to establish a TCP/IP connection to the host server.", "All online transactions", "Verify Wi-Fi/SIM connectivity and IP settings. Retry."),
    PaxError("Network & Host Communication", "Send Error", "Terminal connected to host but failed to transmit the transaction data.", "All online transactions", "Check network stability. Retry."),
    PaxError("Network & Host Communication", "Receive Error", "Terminal transmitted the request but failed to receive the response.", "All online transactions", "Check network stability. Retry. Contact support if persistent."),
    PaxError("Network & Host Communication", "Open Communication Channel Error", "The communication socket/channel could not be opened to the host.", "All online transactions", "Verify APN or IP/port configuration. Contact support."),
    PaxError("Network & Host Communication", "No Internet Connection", "Terminal's internet connectivity check returned false before initiating a transaction.", "Sale / Void / Refund / UPI", "Connect the terminal to Wi-Fi or ensure SIM data is active. Retry."),
    PaxError("Network & Host Communication", "Net connection unavailable", "Network was lost during a Void or TID/MID registration attempt.", "Void / Terminal Registration", "Restore network connectivity and retry the operation."),
    PaxError("Network & Host Communication", "Net connection unavailable, reversal failed", "Reversal triggered but network was unavailable — reversal could not reach the host.", "Post-transaction reversal", "Restore connectivity. Retry transaction. Contact support if unresolved."),
    PaxError("Network & Host Communication", "Network Connection Failure", "Slow or intermittent network detected, causing the transaction to fail connectivity checks.", "All online transactions", "Check signal strength. Switch between Wi-Fi and cellular. Retry."),
    PaxError("Network & Host Communication", "Connection Failure, Please Retry", "API/Retrofit call failed at the network layer during any data request.", "Report downloads / EMI / Brand EMI", "Retry. Check network. Contact support if recurring."),
    PaxError("Network & Host Communication", "Unable to reach server", "ICICI server returned a non-200 HTTP response. HTTP error code is prepended.", "Void / UPI / E-Receipt / Brand EMI", "Note the HTTP error code and contact ICICI server support."),
    PaxError("Network & Host Communication", "Unexpected error is occurred", "Catch-all: exception during API call, null response body, or unknown failure.", "Void / Settlement / SMS Pay / Brand EMI / Report", "Retry. If it recurs, collect logs and contact ICICI support."),

    # 5. Data Protocol & Unpack Errors
    PaxError("Data Protocol", "Pack Error", "Terminal failed to pack/encode the request message before sending.", "All online card transactions", "Retry. If persistent, may indicate configuration corruption — contact support."),
    PaxError("Data Protocol", "Unpack Error", "Terminal received a host response but failed to decode it.", "All online card transactions", "Retry. Contact the acquirer/host support."),
    PaxError("Data Protocol", "Illegal Packet", "Response packet structure is invalid/does not conform to the protocol.", "All online card transactions", "Contact the payment host — there may be a protocol mismatch."),
    PaxError("Data Protocol", "Unpack Process Code Error", "Process code in the host response doesn't match expected value.", "All online card transactions", "Contact host support."),
    PaxError("Data Protocol", "Unpack Amount Error", "Amount field in the host response could not be parsed.", "All online card transactions", "Contact host/acquirer support."),
    PaxError("Data Protocol", "Unpack Terminal ID Error", "Terminal ID in host response did not match.", "All online card transactions", "Verify Terminal ID configuration. Contact support."),
    PaxError("Data Protocol", "Unpack Merchant ID Error", "Merchant ID in host response did not match.", "All online card transactions", "Verify Merchant ID configuration. Contact support."),

    # 6. Transaction State & Host Response
    PaxError("Transaction State", "Host Reject", "Payment host explicitly rejected the transaction request.", "All online transactions", "Check the response/error code. Contact the acquirer."),
    PaxError("Transaction State", "Host Approval, Card Denied Please Contact Issuer", "Host approved but the card issuer denied the transaction.", "Sale / EMI", "Customer should call their card-issuing bank to understand the denial reason."),
    PaxError("Transaction State", "Transaction Cancelled", "User pressed the Cancel button during the transaction.", "All transactions", "Retry if payment is still required."),
    PaxError("Transaction State", "Transaction Timeout", "PIN pad did not receive input within the timeout window.", "PIN entry / chip processing", "Retry. If the PIN pad keeps timing out, check its configuration."),
    PaxError("Transaction State", "Transaction Failed", "Generic transaction failure with no specific error detail.", "Sale / Tip", "Retry. If it persists, check card and network."),
    PaxError("Transaction State", "Unsupported Transaction", "Requested transaction type is not supported by the terminal or acquirer configuration.", "Any transaction type", "Contact support."),
    PaxError("Transaction State", "No Free Space, Please Settle Now", "Terminal's local storage is full. Cannot store any new transactions.", "Any transaction", "Settle immediately to free storage."),
    PaxError("Transaction State", "Last Batch Up Break, Please Click Settle Continue", "Previous settlement was interrupted. Terminal needs to resume it.", "Settlement", "Go to Settlement menu → Settle Continue."),
    PaxError("Transaction State", "Amount Exceed", "Transaction amount exceeds the acquirer's maximum allowed limit.", "Sale / Refund / EMI", "Reduce the amount or process as multiple transactions."),
    PaxError("Transaction State", "Unsupported Function", "The operation or function attempted is not supported.", "Any transaction / Management", "Contact support. The function may not be enabled on this terminal."),

    # 7. Card Validation
    PaxError("Card Validation", "Unsupported Card", "Card BIN does not match any supported card scheme in the terminal's AID list.", "All card transactions", "Use a supported card type (Visa, Mastercard, RuPay, Amex, JCB)."),
    PaxError("Card Validation", "Error Card PAN", "Primary Account Number (PAN) is invalid — fails Luhn check.", "All card transactions", "Try re-reading the card. If persistent, the card may be damaged."),
    PaxError("Card Validation", "Card Expired", "Card expiry date has passed.", "All card transactions", "Customer should use a valid, non-expired card."),
    PaxError("Card Validation", "This card is not eligible for the offer", "Card BIN is not in the eligible range for the selected offer/EMI plan.", "Offers / Bank EMI / Brand EMI", "Use an eligible ICICI Bank card or select a different offer."),
    PaxError("Card Validation", "Invalid QR Code", "QR code scanned is not a valid payment QR.", "Bharat QR / UPI QR scan", "Ensure the customer is using the correct UPI/Bharat QR code."),

    # 8. Void Transaction
    PaxError("Void Transaction", "Enter valid invoice number", "Merchant submitted Void invoice entry with an invalid value.", "Void", "Enter the correct invoice/trace number from the original receipt."),
    PaxError("Void Transaction", "No Internet Connection", "Void initiated but network connectivity check failed.", "Void (online validation step)", "Connect the terminal to the internet and retry."),

    # 9. Reversal
    PaxError("Reversal", "Reversal successful", "Automatic reversal after interrupted transaction was confirmed successful.", "Post-transaction reversal", "No action needed. The reversal is complete."),
    PaxError("Reversal", "Net connection unavailable, reversal failed", "Auto-reversal triggered but no network was available.", "Post-transaction reversal", "Restore network and retry the reversal."),

    # 10. Parameter & Configuration
    PaxError("Parameter & Configuration", "Parameter Error", "A configuration parameter required to complete the transaction is missing or invalid.", "Any transaction", "Perform a parameter update from the management menu. Contact support if it fails."),
    PaxError("Parameter & Configuration", "Parameter Need Update, Please Settle!", "Terminal parameters have expired and a pending batch must be settled first.", "Parameter download / Startup", "Complete batch settlement, then perform parameter download."),
    PaxError("Parameter & Configuration", "Parameter Update Fail, Please Check Log", "Parameter download from host completed but failed to apply.", "Parameter download", "Check the terminal's log file. Verify network. Contact support."),
    PaxError("Parameter & Configuration", "Param List Empty!", "Parameter download returned an empty parameter list from the server.", "Parameter download", "Retry. Contact the server/host support."),
    PaxError("Parameter & Configuration", "Insert Param List fail!", "Parameters were downloaded but terminal failed to save them.", "Parameter download", "Retry. May indicate storage issue — contact support."),
    PaxError("Parameter & Configuration", "Parse Param List fail!", "Parameter data received could not be decoded/parsed.", "Parameter download", "Contact host support — response format may be incorrect."),
    PaxError("Parameter & Configuration", "Backup Param List fail!", "Terminal failed to create a backup of the parameter list.", "Parameter download", "Check terminal storage. Contact support."),

    # 11. Offers & Brand EMI
    PaxError("Offers & Brand EMI", "No offers available", "Offer fetch API returned zero offers for the presented card or merchant.", "Offers / Bank EMI", "No offers exist for this card. Proceed with a regular sale."),
    PaxError("Offers & Brand EMI", "No Offers Found", "Offer search by amount or card returned no matching offers.", "Offers (amount-based search)", "Try a different amount or card. Proceed without offers."),

    # 12. Printer & E-Chargeslip
    PaxError("Printer & E-Chargeslip", "E-Chargeslip could not sent due to an error", "E-Chargeslip API call to ICICI server returned an error response.", "Post-transaction E-Chargeslip", "Retry sending the e-chargeslip. Contact support if persistent."),

    # 13. UPI / QR Payment
    PaxError("UPI / QR Payment", "Unable to reach server", "UPI transaction API returned a non-200 HTTP status.", "UPI QR payment", "Note the HTTP code. Contact ICICI UPI server support."),
    PaxError("UPI / QR Payment", "Net connection unavailable, reversal failed", "UPI reversal could not be sent due to no network.", "UPI sale post-processing", "Restore network and retry reversal."),

    # 14. Terminal Registration
    PaxError("Terminal Registration", "Please enter valid terminal ID", "TID/MID registration screen submitted with an invalid or empty Terminal ID.", "Terminal Registration", "Enter a valid Terminal ID as provided by ICICI."),
    PaxError("Terminal Registration", "Please enter valid merchant ID", "TID/MID registration screen submitted with an invalid or empty Merchant ID.", "Terminal Registration", "Enter a valid Merchant ID as provided by ICICI."),
    PaxError("Terminal Registration", "Net connection unavailable", "TID/MID registration submitted but no network is available.", "Terminal Registration", "Connect to internet and retry the registration."),

    # 15. Notification
    PaxError("Notification", "Notifications not found", "Notification list API returned an empty result.", "Notification screen", "No action required. Notifications will appear when sent by the server."),
]


# ── Lookup helpers ────────────────────────────────────────────────────────────

def _normalize(text: str) -> str:
    """Lowercase, strip punctuation for fuzzy matching."""
    import re
    return re.sub(r"[^a-z0-9 ]", "", text.lower()).strip()


def lookup_pax_error(message: str) -> list[PaxError]:
    """Exact substring match against known PAX error messages."""
    norm = _normalize(message)
    if not norm:
        return []
    matches = []
    for err in PAX_ERRORS:
        if _normalize(err.message) in norm or norm in _normalize(err.message):
            matches.append(err)
    return matches


def search_pax_errors(query: str, top_k: int = 5) -> list[PaxError]:
    """Simple keyword search across message + trigger + category fields."""
    tokens = set(_normalize(query).split())
    if not tokens:
        return []

    scored: list[tuple[int, PaxError]] = []
    for err in PAX_ERRORS:
        haystack = _normalize(f"{err.message} {err.trigger} {err.category} {err.flow}")
        score = sum(1 for t in tokens if t in haystack)
        if score > 0:
            scored.append((score, err))

    scored.sort(key=lambda x: -x[0])
    return [err for _, err in scored[:top_k]]


def get_all_categories() -> list[str]:
    """Return distinct error categories in document order."""
    seen: set[str] = set()
    cats: list[str] = []
    for err in PAX_ERRORS:
        if err.category not in seen:
            seen.add(err.category)
            cats.append(err.category)
    return cats


def get_errors_by_category(category: str) -> list[PaxError]:
    """Return all errors in a given category."""
    return [e for e in PAX_ERRORS if e.category == category]
