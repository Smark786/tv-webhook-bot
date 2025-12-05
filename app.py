from flask import Flask, request, jsonify
from SmartApi.smartConnect import SmartConnect
import pyotp
import time

app = Flask(__name__)

# ============ ANGEL CONFIG (FILL ONLY THIS) ============
API_KEY     = "DNKHyTmF"
CLIENT_ID   = "S354855"
PASSWORD    = "2786"
TOTP_SECRET = "YH4RJAHRVCNMHEQHFUU4VLY6RQ"
# ======================================================

smart = None
last_login = 0


def angel_login():
    global smart, last_login

    # 55 min session valid
    if smart and (time.time() - last_login) < 3300:
        return

    print("🔐 Logging in Angel One...")
    smart = SmartConnect(api_key=API_KEY)
    totp = pyotp.TOTP(TOTP_SECRET).now()

    data = smart.generateSession(CLIENT_ID, PASSWORD, totp)
    if not data.get("status"):
        raise Exception("Angel login failed")

    last_login = time.time()
    print("✅ Fresh Angel login done")


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    print("🚨 ALERT RECEIVED:", data)

    try:
        action = data["action"].upper()
        symbol = data["symbol"]
        token  = data["token"]
        qty    = int(data["qty"])
        entry  = float(data["entry"])
        sl     = float(data["slPrice"])
    except Exception:
        return jsonify({"error": "Invalid payload"}), 400

    try:
        angel_login()
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    side_entry = "BUY" if action == "BUY" else "SELL"
    side_sl    = "SELL" if side_entry == "BUY" else "BUY"

    # ========= ENTRY =========
    entry_order = {
        "variety": "NORMAL",
        "tradingsymbol": symbol,
        "symboltoken": token,
        "transactiontype": side_entry,
        "exchange": "NSE",
        "ordertype": "LIMIT",
        "producttype": "CNC",
        "duration": "DAY",
        "price": entry,
        "quantity": qty
    }

    print("📨 ENTRY ORDER:", entry_order)
    entry_resp = smart.placeOrder(entry_order)
    print("✅ ENTRY RESPONSE:", entry_resp)

    # ========= SL =========
    sl_order = {
        "variety": "NORMAL",
        "tradingsymbol": symbol,
        "symboltoken": token,
        "transactiontype": side_sl,
        "exchange": "NSE",
        "ordertype": "STOPLOSS_MARKET",
        "producttype": "CNC",
        "duration": "DAY",
        "triggerprice": sl,
        "quantity": qty
    }

    print("📨 SL ORDER:", sl_order)
    sl_resp = smart.placeOrder(sl_order)
    print("✅ SL RESPONSE:", sl_resp)

    return jsonify({
        "status": "ok",
        "entry": entry_resp,
        "sl": sl_resp
    })


@app.route("/")
def home():
    return "Webhook running ✅"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
