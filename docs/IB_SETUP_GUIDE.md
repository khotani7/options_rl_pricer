# Interactive Brokers Setup Guide - Step by Step

## Overview

This guide walks you through setting up Interactive Brokers for automated paper trading.

**Timeline**: ~30 minutes
**Cost**: $0 (paper trading is free)
**Difficulty**: Easy

---

## Step 1: Create Interactive Brokers Account (If You Don't Have One)

### 1.1 Sign Up

1. Go to https://www.interactivebrokers.com
2. Click **"Open Account"**
3. Choose **Individual Account**
4. Fill in your information:
   - Name, address, SSN
   - Employment info
   - Financial information
   - Trading experience (be honest!)

**Important**: You don't need to fund the account to use paper trading!

### 1.2 Wait for Approval

- Usually takes 1-2 business days
- You'll receive an email when approved
- You can request paper trading access immediately after approval

---

## Step 2: Enable Paper Trading

### 2.1 Access Account Management

1. Log into your IB account
2. Go to https://www.interactivebrokers.com/portal
3. Click **"Account Management"** (top right)

### 2.2 Request Paper Trading Account

1. In Account Management, navigate:
   ```
   Settings & Account Settings → Paper Trading Account
   ```

2. Click **"Request Paper Trading Account"**

3. Fill out the form:
   - Account type: Individual
   - Starting balance: $1,000,000 (default)
   - Click **"Submit"**

4. You'll receive paper trading credentials **immediately** via email

5. **Save these credentials!**
   ```
   Username: [Your paper account username]
   Password: [Your paper account password]
   ```

---

## Step 3: Download and Install IB Gateway

**Choose**: IB Gateway (recommended) or Trader Workstation (TWS)

### IB Gateway (Lightweight, Recommended)

1. Download from: https://www.interactivebrokers.com/en/trading/ibgateway-stable.php

2. Select your OS:
   - **macOS**: Download DMG
   - **Windows**: Download EXE
   - **Linux**: Download SH

3. Install:
   - **macOS**: Open DMG → Drag to Applications → Open
   - **Windows**: Run EXE → Follow installer
   - **Linux**: `chmod +x ibgateway-*.sh && ./ibgateway-*.sh`

### Trader Workstation (Full-Featured Alternative)

If you prefer the full TWS:
- Download: https://www.interactivebrokers.com/en/trading/tws.php
- Heavier but has full UI for manual trading

---

## Step 4: Configure IB Gateway for API Access

### 4.1 Launch IB Gateway

1. Open IB Gateway application
2. **Login with PAPER TRADING credentials** (from Step 2.2)
   - Username: Your paper username (different from live!)
   - Password: Your paper password
   - Trading Mode: **IB API** (not Live Trading)

3. Click **Login**

### 4.2 Configure API Settings

**First time only:**

1. After login, click **Configure** → **Settings** (or gear icon ⚙️)

2. Navigate to **API → Settings**

3. Configure these settings:

   **✓ Enable ActiveX and Socket Clients**
   ```
   ☑ Enable ActiveX and Socket Clients
   ```

   **✓ Socket Port**
   ```
   Port: 7497  (for paper trading)

   Note: 7496 = live trading, 7497 = paper trading
   ```

   **✓ Trusted IP Addresses**
   ```
   Add: 127.0.0.1

   This allows connections from your local machine
   ```

   **✓ Master API client ID** (optional)
   ```
   Leave as 0 (or set to 1)
   ```

   **✓ Read-Only API**
   ```
   ☐ Unchecked (we need to place orders)
   ```

   **✓ Download open orders on connection**
   ```
   ☑ Checked (recommended)
   ```

4. Click **OK**

5. **Restart IB Gateway** for changes to take effect

### 4.3 Verify Settings

1. Launch IB Gateway again
2. Login with paper credentials
3. You should see in the status:
   ```
   ✓ API: Listening on port 7497
   ```

---

## Step 5: Install Python Library

### 5.1 Install ib_insync

```bash
cd /Users/kabirhotani/Downloads/options_rl_pricer
pip install ib_insync
```

### 5.2 Verify Installation

```bash
python -c "import ib_insync; print('✓ ib_insync installed:', ib_insync.__version__)"
```

Expected output:
```
✓ ib_insync installed: 0.9.86
```

---

## Step 6: Test Connection

### 6.1 Make Sure IB Gateway is Running

1. Launch IB Gateway
2. Login with paper trading credentials
3. Verify it says "API: Listening on port 7497"

### 6.2 Run Test Connection Script

Create a test file:

```bash
cat > test_ib_connection.py << 'EOF'
"""Test IB connection"""
from ib_insync import IB

# Create IB instance
ib = IB()

print("Connecting to IB Gateway...")
try:
    # Connect to IB
    ib.connect('127.0.0.1', 7497, clientId=1)

    print("✓ Connected successfully!")
    print(f"✓ Connection status: {ib.isConnected()}")

    # Get account info
    account_values = ib.accountValues()

    for av in account_values:
        if av.tag == 'NetLiquidation':
            print(f"✓ Paper Account Value: ${float(av.value):,.2f}")
            break

    # Get account summary
    print(f"✓ Account: {ib.managedAccounts()}")

    # Disconnect
    ib.disconnect()
    print("✓ Disconnected successfully")
    print("\n🎉 Connection test PASSED!")

except Exception as e:
    print(f"✗ Connection FAILED: {e}")
    print("\nTroubleshooting:")
    print("1. Is IB Gateway running?")
    print("2. Did you login with PAPER credentials?")
    print("3. Is API enabled in settings?")
    print("4. Is port 7497 configured?")
    print("5. Is 127.0.0.1 in Trusted IPs?")
EOF

python test_ib_connection.py
```

### 6.3 Expected Output

```
Connecting to IB Gateway...
✓ Connected successfully!
✓ Connection status: True
✓ Paper Account Value: $1,000,000.00
✓ Account: ['DU123456']
✓ Disconnected successfully

🎉 Connection test PASSED!
```

### 6.4 If Connection Fails

**Common Issues:**

1. **"Connection refused" error**
   - IB Gateway not running
   - Wrong port (should be 7497 for paper)
   - Firewall blocking connection

2. **"API not enabled" error**
   - Go to Configure → Settings → API
   - Check "Enable ActiveX and Socket Clients"
   - Restart Gateway

3. **"Untrusted IP" error**
   - Add 127.0.0.1 to Trusted IPs
   - Restart Gateway

4. **"Already connected" error**
   - Use different clientId (1, 2, 3...)
   - Or restart Gateway

---

## Step 7: Test Order Placement (Paper Trading)

### 7.1 Test Placing an Option Order

```bash
cat > test_option_order.py << 'EOF'
"""Test placing a paper option order"""
from ib_insync import IB, Option, LimitOrder
import time

ib = IB()

print("Connecting to IB...")
ib.connect('127.0.0.1', 7497, clientId=1)

print("✓ Connected!\n")

# Create an option contract
print("Creating AAPL option contract...")
contract = Option(
    symbol='AAPL',
    lastTradeDateOrContractMonth='20261002',  # Oct 2, 2026
    strike=315,
    right='P',  # Put
    exchange='SMART',
    currency='USD'
)

# Qualify the contract (get full details)
print("Qualifying contract...")
qualified = ib.qualifyContracts(contract)

if not qualified:
    print("✗ Could not qualify contract")
    ib.disconnect()
    exit(1)

contract = qualified[0]
print(f"✓ Contract: {contract.symbol} {contract.strike}{contract.right} {contract.lastTradeDateOrContractMonth}")

# Get market data
print("\nGetting market data...")
ticker = ib.reqMktData(contract, '', False, False)

# Wait for data
time.sleep(2)
ib.sleep(1)

if ticker.bid > 0 and ticker.ask > 0:
    print(f"✓ Bid: ${ticker.bid:.2f}")
    print(f"✓ Ask: ${ticker.ask:.2f}")
    print(f"✓ Mid: ${(ticker.bid + ticker.ask)/2:.2f}")
else:
    print("⚠️  No market data (this is normal after hours)")

# Create a limit order (won't actually fill, just testing)
print("\nPlacing limit order (test only)...")
order = LimitOrder(
    action='BUY',
    totalQuantity=1,
    lmtPrice=1.00  # Far below market, won't fill
)

# Place order
trade = ib.placeOrder(contract, order)
print(f"✓ Order placed! Order ID: {trade.order.orderId}")
print(f"✓ Order status: {trade.orderStatus.status}")

# Wait a moment
time.sleep(2)

# Cancel the order
print("\nCancelling order...")
ib.cancelOrder(order)
time.sleep(1)

print("✓ Order cancelled")

# Disconnect
ib.disconnect()
print("\n🎉 Order test COMPLETE!")
print("\nYou're ready to run the automated trader!")
EOF

python test_option_order.py
```

### 7.2 Expected Output

```
Connecting to IB...
✓ Connected!

Creating AAPL option contract...
Qualifying contract...
✓ Contract: AAPL 315P 20261002

Getting market data...
✓ Bid: $8.10
✓ Ask: $8.50
✓ Mid: $8.30

Placing limit order (test only)...
✓ Order placed! Order ID: 1
✓ Order status: Submitted

Cancelling order...
✓ Order cancelled

🎉 Order test COMPLETE!

You're ready to run the automated trader!
```

---

## Step 8: Run Your Automated Trader

### 8.1 Start in Mock Mode (No IB Required)

First, test without IB connection:

```bash
python run_trader.py --mode mock --tickers AAPL
```

This simulates trading without connecting to IB.

### 8.2 Start in Paper Mode (Real IB Connection)

Once IB Gateway is running and connected:

```bash
python run_trader.py --mode paper --tickers AAPL XOM JPM
```

**What happens:**
1. Connects to IB paper account
2. Scans for edge opportunities every 15 minutes
3. Places limit orders when edge > 3%
4. Monitors positions
5. Stops if daily loss > 2%
6. Logs everything to `outputs/trading_log_paper.json`

### 8.3 Monitor the Trader

**In the terminal:**
```
======================================================================
Starting Automated Options Trader
======================================================================
Mode: PAPER
Tickers: AAPL, XOM, JPM
Scan interval: 15 minutes
Max positions: 10
Min edge: 3.0%
======================================================================

✓ Connected to IB on 127.0.0.1:7497
✓ Account value: $1,000,000.00
✓ Trader is now active

[14:30:15] Scanning for opportunities...
  Scanning AAPL...
    No opportunities found
  Scanning XOM...
  → Found opportunity: SELL_PUT
    PUT $160 exp 2026-09-04 (4d)
    Edge: 3.5% | Market: $4.85
    ✓ Order placed: SELL 1x XOM 160P 20260904 @ $4.90
    ✓ Order 1 filled @ $4.88
    ✓ Trade executed successfully
```

**To stop:**
```
Press Ctrl+C

Stopping trader...
✓ Trading log saved to outputs/trading_log_paper.json
✓ Trader stopped
```

---

## Step 9: Review Performance

### 9.1 Check Trading Log

```bash
cat outputs/trading_log_paper.json | python -m json.tool | tail -20
```

### 9.2 Check IB Gateway

1. Open TWS or IB Gateway
2. Go to **Account** → **Portfolio**
3. See your paper positions

---

## Common Issues & Solutions

### Issue: "Connection refused"

**Solution:**
```bash
# 1. Check if IB Gateway is running
ps aux | grep gateway

# 2. Verify port
# IB Gateway → Configure → API → Settings
# Port should be 7497 (paper)

# 3. Try different client ID
python run_trader.py --mode paper --client-id 2
```

### Issue: "API not enabled"

**Solution:**
1. IB Gateway → Configure → Settings → API
2. Check ☑ "Enable ActiveX and Socket Clients"
3. Click OK
4. Restart IB Gateway

### Issue: "Contract not found"

**Solution:**
- Market is closed (options only trade during market hours)
- Or expiry date doesn't exist
- Try using a current expiry date

### Issue: "Orders not filling"

**Solution:**
- This is normal for paper trading with limit orders far from market
- The system uses realistic limit prices
- If you want guaranteed fills, switch to market orders:
  ```python
  # In trading_config.py
  use_limit_orders=False
  ```

### Issue: "Trader keeps disconnecting"

**Solution:**
1. Keep IB Gateway window open
2. Don't let computer sleep
3. Increase connection timeout:
   ```python
   ib.connect('127.0.0.1', 7497, clientId=1, timeout=20)
   ```

---

## IB Gateway Best Practices

### Daily Startup Routine

```bash
# 1. Start IB Gateway
open -a "IB Gateway"  # macOS
# or double-click IB Gateway icon

# 2. Login with PAPER credentials

# 3. Verify API is listening
# Look for: "API: Listening on port 7497"

# 4. Start trader
python run_trader.py --mode paper --tickers AAPL XOM JPM

# 5. Monitor
tail -f outputs/trading_log_paper.json
```

### Auto-Restart IB Gateway

IB Gateway needs to restart daily. Use this script:

```bash
cat > restart_ib.sh << 'EOF'
#!/bin/bash
# Auto-restart IB Gateway and trader

# Kill existing Gateway
pkill -f gateway

# Wait
sleep 5

# Start Gateway (you'll need to login manually)
open -a "IB Gateway"

# Wait for login
echo "Please login to IB Gateway..."
read -p "Press Enter when Gateway is running..."

# Start trader
python run_trader.py --mode paper --tickers AAPL XOM JPM
EOF

chmod +x restart_ib.sh
```

---

## Next Steps

### ✅ Checklist

- [ ] IB account created
- [ ] Paper trading enabled
- [ ] IB Gateway installed
- [ ] API configured (port 7497)
- [ ] ib_insync installed
- [ ] Connection test passed
- [ ] Order test passed
- [ ] Automated trader running

### Once Everything Works

1. **Let it run for 1 week**
   - Monitor daily
   - Review all trades
   - Check for errors

2. **Analyze performance**
   ```bash
   # Review trading log
   python -c "
   import json
   with open('outputs/trading_log_paper.json') as f:
       trades = json.load(f)
   print(f'Total trades: {len(trades)}')
   print(f'Avg edge: {sum(t[\"edge_score\"] for t in trades)/len(trades):.1f}%')
   "
   ```

3. **Refine parameters**
   - Adjust `--min-edge` if too many/few trades
   - Adjust `--scan-interval` for more frequent scans
   - Add/remove tickers

4. **After 1 month of successful paper trading**
   - Consider switching to live (with small capital!)
   - Start with `--max-positions 2`
   - Start with `--max-daily-loss 1.0`

---

## Live Trading (Advanced)

⚠️ **Only after 1+ month successful paper trading!**

### Switch to Live

```bash
# Change port to 7496 (live)
python run_trader.py --mode live --port 7496 --max-positions 2
```

**Differences:**
- Port: 7497 → 7496
- Real money at risk
- Real commissions ($0.65+/contract)
- Real slippage
- Emotional stress

**Start small:**
- Max 2-3 positions
- 1% max daily loss
- Monitor continuously

---

## Support

**IB Support:**
- Phone: 877-442-2757 (US)
- Chat: https://www.interactivebrokers.com/portal
- Hours: 24/7

**API Documentation:**
- IB API: https://interactivebrokers.github.io/tws-api/
- ib_insync: https://ib-insync.readthedocs.io/

**Common Questions:**
- Check TRADING_GUIDE.md
- Check QUICKSTART.md

---

## Security Notes

1. **Never share your credentials**
2. **Use paper trading first**
3. **Keep API access local only (127.0.0.1)**
4. **Don't commit passwords to git**
5. **Use strong passwords**
6. **Enable 2FA on IB account**

---

## Summary

You should now have:
- ✅ IB paper trading account
- ✅ IB Gateway configured
- ✅ API access enabled
- ✅ Python connection working
- ✅ Automated trader running

**Next:**
```bash
python run_trader.py --mode paper --tickers AAPL
```

Let it run and monitor performance!

🎉 **Happy Paper Trading!**
