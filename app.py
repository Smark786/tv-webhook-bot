from flask import Flask, request, jsonify
from SmartApi.smartConnect import SmartConnect
import pyotp, time

app = Flask(__name__)

API_KEY     = "DNKHyTmF"
CLIENT_ID   = "S354855"
PASSWORD    = "2786"
TOTP_SECRET = "YH4RJAHRVCNMHEQHFUU4VLY6RQ"

smart = None
last_login = 0


def angel_login():
    global smart, last_login
    if smart and (time.time() - last_login) < 3300:
        return

    print("🔐 Angel login...")
    smart = SmartConnect(api_key=API_KEY)
    totp = pyotp.TOTP(TOTP_SECRET).now()
    data = smart.generateSession(CLIENT_ID, PASSWORD, totp)

    if not data.get("status"):
        raise Exception("Angel login failed")

    last_login = time.time()
    print("✅ Login OK")


def safe_place_order(order):
    try:
        resp = smart.placeOrder(order)
        print("✅ Angel raw response:", resp)
        return resp
    except Exception as e:
        print("❌ Angel API ERROR (ignored):", str(e))
        return None


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    print("🚨 ALERT RECEIVED:", data)

    try:
        angel_login()
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    symbol = data["symbol"]
    token  = data["token"]
    qty    = int(data["qty"])
    entry  = float(data["entry"])
    sl     = float(data["slPrice"])
    action = data["action"].upper()

    side_entry = "BUY" if action == "BUY" else "SELL"
    side_sl    = "SELL" if side_entry == "BUY" else "BUY"

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
    entry_resp = safe_place_order(entry_order)

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
    sl_resp = safe_place_order(sl_order)

    return jsonify({
        "status": "received",
        "entry_response": entry_resp,
        "sl_response": sl_resp
    })


@app.route("/")
def home():
    return "✅ Angel Webhook Live"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
