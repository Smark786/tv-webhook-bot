from flask import Flask, request, jsonify
from SmartApi import SmartConnect
import pyotp
import time
import os

app = Flask(__name__)

# ---------------- Angel Credentials ----------------
API_KEY     = "DNKHyTmF"
CLIENT_CODE = "S354855"
PASSWORD    = "2786"
TOTP_KEY    = "YH4RJAHRVCNMHEQHFUU4VLY6RQ"

# ---------------- Symbol → Token Map ----------------
SYMBOL_TOKEN_MAP = {
    "ANANTRAJ": "13620",
    "SBIN": "3045"
}

# ---------------------------------------------------

def angel_login():
    smart = SmartConnect(api_key=API_KEY)
    totp = pyotp.TOTP(TOTP_KEY).now()

    data = smart.generateSession(
        CLIENT_CODE,
        PASSWORD,
        totp
    )

    if not data["status"]:
        raise Exception("Angel Login Failed")

    smart.setAccessToken(data["data"]["jwtToken"])
    return smart


@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json()
        print("🔔 ALERT RECEIVED:", data)

        action = data["action"].upper()
        symbol = data["symbol"].upper()
        qty = int(data["qty"])
        entry = float(data.get("entry", 0))
        sl = float(data.get("slPrice", 0))

        if symbol not in SYMBOL_TOKEN_MAP:
            return jsonify({"error": "Symbol not mapped"}), 400

        token = SYMBOL_TOKEN_MAP[symbol]

        # ✅ LOGIN EVERY TIME (IMPORTANT)
        smart = angel_login()
        print("✅ Fresh Angel login done")

        # -------- ENTRY ORDER --------
        entry_order = smart.placeOrder({
            "variety": "NORMAL",
            "tradingsymbol": f"{symbol}-EQ",
            "symboltoken": token,
            "transactiontype": action,
            "exchange": "NSE",
            "ordertype": "LIMIT",
            "producttype": "CNC",
            "duration": "DAY",
            "price": entry,
            "quantity": qty
        })

        print("✅ ENTRY RESPONSE:", entry_order)

        # -------- SL ORDER --------
        if sl > 0:
            sl_action = "SELL" if action == "BUY" else "BUY"

            sl_order = smart.placeOrder({
                "variety": "NORMAL",
                "tradingsymbol": f"{symbol}-EQ",
                "symboltoken": token,
                "transactiontype": sl_action,
                "exchange": "NSE",
                "ordertype": "STOPLOSS_MARKET",
                "producttype": "CNC",
                "duration": "DAY",
                "triggerprice": sl,
                "quantity": qty
            })

            print("✅ SL RESPONSE:", sl_order)

        return jsonify({"status": "order_sent"})

    except Exception as e:
        print("❌ ERROR:", str(e))
        return jsonify({"error": str(e)}), 500


@app.route("/")
def home():
    return "✅ Angel Webhook Server Running"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
