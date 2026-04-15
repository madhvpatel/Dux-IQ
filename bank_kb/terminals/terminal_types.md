# POS Terminal Types and Management

## Terminal categories

### Countertop POS
- Fixed-location device with wired (Ethernet) or wireless (GPRS/WiFi) connectivity.
- Accepts: chip, swipe, contactless, UPI QR.
- Best for: retail stores, restaurants, billing counters with fixed checkout points.
- Common brands in India: PAX (A920, A80), Ingenico (Move/3500, Desk/3500), Verifone (V240m).
- Power: AC adapter with battery backup (2-4 hours).

### Mobile POS (mPOS)
- Compact card reader that pairs with a smartphone/tablet via Bluetooth.
- Accepts: chip, swipe, contactless (NFC-enabled models).
- Best for: delivery agents, field sales, small merchants, kirana stores.
- Lower cost: device Rs 2,000-5,000 vs Rs 10,000-25,000 for countertop.
- Limitation: depends on phone's internet connectivity and battery.

### Android POS (Smart POS)
- Android-based touchscreen terminal. Runs custom apps.
- Accepts: all card types + UPI QR + BharatQR + wallets.
- Can run merchant apps: inventory, billing, loyalty.
- Best for: restaurants (order management), retail chains (integrated billing), QSR.
- Examples: PAX A920 Pro, Ingenico AXIUM, Worldline Yumi.

### Soundbox / QR standee
- Not a card terminal. Only accepts UPI/QR payments.
- Plays audio confirmation when payment is received ("Paytm se Rs 500 prapt hua").
- Near-zero cost for merchant. No card acceptance.
- Best for: tea stalls, auto-rickshaws, small shops, street vendors.

## Terminal lifecycle

### Provisioning
1. Acquirer assigns TID (Terminal ID) and MID (Merchant ID).
2. Terminal is configured with: acquirer host IP/port, encryption keys (DUKPT/Master-Session), merchant parameters.
3. SIM card inserted (for GPRS models).
4. Terminal performs key injection (TMS download) to load encryption keys.
5. Test transaction: Rs 1 authorization + void to verify end-to-end connectivity.

### Daily operations
- **Batch settlement**: Terminal sends all day's approved transactions to acquirer at end of day. Auto-configured (usually 11 PM) or manual trigger.
- **Key download**: Periodic encryption key refresh via TMS (Terminal Management System). Automatic.
- **App update**: Firmware and payment app updates pushed via TMS. Usually overnight.

### Maintenance
- **Paper roll**: Thermal printer needs roll replacement. Average: 1 roll per 100-150 receipts.
- **SIM data**: GPRS SIM has a monthly data plan. Typical usage: 50-100 MB/month for standard transaction volume.
- **Battery**: Replace when battery backup drops below 1 hour. Typical battery life: 2-3 years.
- **Tamper detection**: PCI PTS certified terminals have tamper switches. If the terminal detects physical tampering, it wipes keys and becomes inoperable. Requires return to acquirer for re-injection.

## Common terminal issues

### Connectivity
- **"No Network" / "Communication Error"**: Check SIM balance, GPRS signal strength, APN configuration. If WiFi: verify SSID/password, check router.
- **"Host not responding"**: Acquirer's host may be down. Try again in 5 minutes. If persistent, call acquirer helpdesk.
- **Slow transactions (>15 seconds)**: Weak GPRS signal. Move terminal to better signal area or switch to WiFi/Ethernet.

### Transaction failures
- **"Card read error"**: Dirty/damaged chip contacts. Clean card chip with dry cloth. If persists, try magstripe fallback or manual entry (if enabled).
- **"Invalid merchant"**: TID/MID not active on acquirer's host. Contact acquirer to verify terminal registration status.
- **"PIN pad error"**: PIN entry device malfunction. Restart terminal. If persists, terminal needs replacement.

### Certification
- All POS terminals in India must be certified by: PCI PTS (Payment Card Industry PIN Transaction Security) for hardware security, EMV L1/L2 for chip card processing, NPCI for RuPay/UPI acceptance.
- Terminals without valid certification cannot be deployed.
- Certification renewal: every 3 years for PCI PTS.

## Terminal metrics to monitor
- **Uptime**: % of operating hours terminal is online. Target: >99%.
- **Transaction success rate per TID**: If one terminal has significantly lower success rate, investigate hardware/connectivity issues.
- **Average response time**: Card tap-to-approval time. Healthy: <5 seconds. If >10 seconds consistently, check connectivity.
- **Batch settlement frequency**: Should be daily. Missed batch = transactions not settled = merchant cashflow delay.
