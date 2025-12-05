from flask import Flask, request, jsonify
from SmartApi import SmartConnect   # 👈 NOTE: Capital S, A
import pyotp

app = Flask(__name__)

# ============ ANGEL ONE CREDENTIALS ============
# 👇 Sirf in 4 lines me apni details daalni hain

API_KEY   = "DNKHyTmF"
CLIENT_ID = "S354855"
PASSWORD  = "ahmed786"
TOTP_KEY  = "YH4RJAHRVCNMHEQHFUU4VLY6RQ"

# ===============================================

def angel_login():
    """Angel One SmartAPI login & session create karta hai."""
    global obj
    obj = SmartConnect(api_key=API_KEY)

    totp = pyotp.TOTP(TOTP_KEY).now()
    print("🔐 TOTP:", totp)

    login_data = obj.generateSession(CLIENT_ID, PASSWORD, totp)
    print("✅ LOGIN:", login_data)
    return login_data

# App start hote hi login
obj = None
angel_login()

# ============ WEBHOOK ROUTE ============

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

        # productType (default CNC / delivery)
        product_raw = data.get("productType", "CNC").upper()
        if product_raw in ("INTRA", "INTRADAY"):
            product_type = "INTRADAY"
        else:
            product_type = "CNC"

        side = "BUY" if action == "BUY" else "SELL"

        # --------- ENTRY ORDER (LIMIT) ----------
        print("📌 ENTRY:", symbol, entry, qty, product_type)

        entry_order = {
            "variety": "NORMAL",
            "tradingsymbol": symbol,
            "symboltoken": token,
            "transactiontype": side,
            "exchange": "NSE",
            "ordertype": "LIMIT",
            "producttype": product_type,
            "duration": "DAY",
            "price": entry,
            "quantity": qty
        }
        entry_resp = obj.placeOrder(entry_order)
        print("ENTRY RESP:", entry_resp)

        # --------- SL-M ORDER ----------
        print("📌 SL-M:", sl_price)

        sl_order = {
            "variety": "NORMAL",
            "tradingsymbol": symbol,
            "symboltoken": token,
            "transactiontype": "SELL" if side == "BUY" else "BUY",
            "exchange": "NSE",
            "ordertype": "STOPLOSS_MARKET",
            "producttype": product_type,
            "duration": "DAY",
            "triggerprice": sl_price,
            "quantity": qty
        }
        sl_resp = obj.placeOrder(sl_order)
        print("SL RESP:", sl_resp)

        return jsonify({"status": "OK", "entry": entry_resp, "sl": sl_resp})

    except Exception as e:
        print("❌ ERROR in webhook:", e)
        return jsonify({"error": str(e)}), 500


@app.route("/")
def home():
    return "✅ Angel One Webhook Running"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
