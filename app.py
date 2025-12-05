from flask import Flask, request, jsonify
from smartapi import SmartConnect
import pyotp

app = Flask(__name__)

# ============ ANGEL ONE CREDENTIALS ============

API_KEY   = "DNKHyTmF"        # 🔹 SmartAPI se mila API key
CLIENT_ID = "S354855"      # 🔹 Angel ka client id (login id)
PASSWORD  = "ahmed786"       # 🔹 Trading password
TOTP_KEY  = "YH4RJAHRVCNMHEQHFUU4VLY6RQ"    # 🔹 Google Authenticator ka secret (base32)

# ============ LOGIN ============

def angel_login():
    """Angel One SmartAPI login & session create."""
    global obj
    obj = SmartConnect(api_key=API_KEY)

    # TOTP generate
    totp = pyotp.TOTP(TOTP_KEY).now()
    print("🔐 Generating session with TOTP:", totp)

    login_data = obj.generateSession(CLIENT_ID, PASSWORD, totp)
    print("✅ Login success:", login_data)

    return login_data

# Pehle se login karlo jab app start ho
obj = None
angel_login()

# ============ WEBHOOK ============

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    print("🚨 ALERT:", data)

    try:
        action   = data["action"].upper()      # BUY / SELL
        symbol   = data["symbol"]              # e.g. SBIN
        token    = str(data["token"])          # e.g. "3045"
        qty      = int(data["qty"])
        entry    = float(data["entry"])
        sl_price = float(data["slPrice"])

        # CNC / INTRADAY choose karne ka option (default CNC)
        product_raw = data.get("productType", "CNC").upper()
        if product_raw in ("INTRA", "INTRADAY"):
            product_type = "INTRADAY"
        else:
            product_type = "CNC"   # default: CASH / DELIVERY

        direction = "BUY" if action == "BUY" else "SELL"

        # ---------- ENTRY ORDER ----------
        print("📌 Placing ENTRY order:", symbol, entry, qty, product_type)

        entry_order = {
            "variety": "NORMAL",
            "tradingsymbol": symbol,
            "symboltoken": token,
            "transactiontype": direction,         # BUY / SELL
            "exchange": "NSE",
            "ordertype": "LIMIT",
            "producttype": product_type,          # CNC / INTRADAY
            "duration": "DAY",
            "price": entry,
            "quantity": qty
        }

        entry_resp = obj.placeOrder(entry_order)
        print("ENTRY RESPONSE:", entry_resp)

        # ---------- SL ORDER (STOPLOSS MARKET) ----------
        print("📌 Placing SL-M order:", sl_price)

        sl_order = {
            "variety": "NORMAL",
            "tradingsymbol": symbol,
            "symboltoken": token,
            "transactiontype": "SELL" if direction == "BUY" else "BUY",
            "exchange": "NSE",
            "ordertype": "STOPLOSS_MARKET",
            "producttype": product_type,
            "duration": "DAY",
            "triggerprice": sl_price,
            "quantity": qty
        }

        sl_resp = obj.placeOrder(sl_order)
        print("SL RESPONSE:", sl_resp)

        return jsonify({"status": "OK", "entry": entry_resp, "sl": sl_resp})

    except Exception as e:
        print("❌ ERROR in webhook:", e)
        return jsonify({"error": str(e)}), 500


@app.route("/")
def home():
    return "✅ Angel One Webhook (CNC default) Running"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
