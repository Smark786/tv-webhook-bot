from flask import Flask, request, jsonify
from SmartApi import SmartConnect
import pyotp
import time

app = Flask(__name__)

# ================== CONFIG FILL KARNA HAI ==================

API_KEY     = "DNKHyTmF"
CLIENT_CODE = "S354855"
PASSWORD    = "2786"
TOTP_KEY    = "YH4RJAHRVCNMHEQHFUU4VLY6RQ"

# sirf yahan tokens add / edit karte rehna
SYMBOL_TOKEN_MAP = {
    "ANANTRAJ": "13620",
    "SBIN": "3045",
    # "CUPID": "TOKEN_YAHAN",
}

# ===========================================================

def angel_login():
    """Har webhook pe fresh SmartAPI login."""
    smart = SmartConnect(api_key=API_KEY)

    totp_now = pyotp.TOTP(TOTP_KEY).now()
    print(f"[{time.strftime('%H:%M:%S')}] 🔐 TOTP generated:", totp_now)

    data = smart.generateSession(CLIENT_CODE, PASSWORD, totp_now)
    if not data.get("status"):
        print(f"[{time.strftime('%H:%M:%S')}] ❌ LOGIN FAILED:", data)
        raise Exception("Angel login failed")

    smart.setAccessToken(data["data"]["jwtToken"])
    print(f"[{time.strftime('%H:%M:%S')}] ✅ Angel login done, token set")
    return smart


@app.route("/webhook", methods=["POST"])
def webhook():
    ts = time.strftime('%H:%M:%S')
    try:
        data = request.get_json(force=True)
        print(f"\n{ts} ===============================================")
        print(f"{ts} 🔔 ALERT RECEIVED:", data)

        # -------- TradingView payload parse --------
        action = data["action"].upper()
        symbol = data["symbol"].upper()
        qty    = int(data["qty"])
        entry  = float(data.get("entry", 0) or 0)
        sl     = float(data.get("slPrice", 0) or 0)

        if symbol not in SYMBOL_TOKEN_MAP:
            print(f"{ts} ❌ Symbol {symbol} NOT in SYMBOL_TOKEN_MAP")
            return jsonify({"error": f"symbol {symbol} not mapped"}), 400

        token = SYMBOL_TOKEN_MAP[symbol]
        print(f"{ts} ✅ Symbol {symbol} → token {token}")

        # -------- Login --------
        smart = angel_login()

        # -------- ENTRY ORDER --------
        entry_order_payload = {
            "variety":         "NORMAL",
            "tradingsymbol":   f"{symbol}-EQ",
            "symboltoken":     token,
            "transactiontype": action,
            "exchange":        "NSE",
            "ordertype":       "LIMIT",
            "producttype":     "CNC",
            "duration":        "DAY",
            "price":           entry,
            "quantity":        qty,
        }
        print(f"{ts} 🧾 ENTRY ORDER PAYLOAD:", entry_order_payload)

        try:
            entry_resp = smart.placeOrder(entry_order_payload)
            print(f"{ts} 📩 RAW ENTRY RESPONSE:", entry_resp)
        except Exception as e:
            print(f"{ts} ❌ ENTRY API ERROR:", repr(e))
            entry_resp = None

        print(f"{ts} ✅ ENTRY RESPONSE:", entry_resp)

        # -------- SL ORDER (agar SL diya hai) --------
        sl_resp = None
        if sl > 0:
            sl_side = "SELL" if action == "BUY" else "BUY"

            sl_order_payload = {
                "variety":         "NORMAL",
                "tradingsymbol":   f"{symbol}-EQ",
                "symboltoken":     token,
                "transactiontype": sl_side,
                "exchange":        "NSE",
                "ordertype":       "STOPLOSS_MARKET",
                "producttype":     "CNC",
                "duration":        "DAY",
                "triggerprice":    sl,
                "quantity":        qty,
            }
            print(f"{ts} 🧾 SL ORDER PAYLOAD:", sl_order_payload)

            try:
                sl_resp = smart.placeOrder(sl_order_payload)
                print(f"{ts} 📩 RAW SL RESPONSE:", sl_resp)
            except Exception as e:
                print(f"{ts} ❌ SL API ERROR:", repr(e))
                sl_resp = None

            print(f"{ts} ✅ SL RESPONSE:", sl_resp)
        else:
            print(f"{ts} ⚠️ SL SKIPPED (slPrice <= 0)")

        return jsonify({
            "status": "sent_to_angel",
            "entry": entry_resp,
            "sl": sl_resp
        })

    except Exception as e:
        print(f"{ts} 🛑 UNHANDLED ERROR IN WEBHOOK:", str(e))
        return jsonify({"error": str(e)}), 500


@app.route("/")
def home():
    return "✅ Angel Webhook Server Running"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
