from flask import Flask, request, jsonify
import requests
import pyotp
from SmartApi import SmartConnect
import time

app = Flask(__name__)

# ================== ANGEL / SMARTAPI CONFIG ==================

API_KEY      = "DNKHyTmF"
CLIENT_CODE  = "S354855"   # jaise: "S123456"
CLIENT_PIN   = "2786"    # jo app login me use karte ho
TOTP_SECRET  = "YH4RJAHRVCNMHEQHFUU4VLY6RQ" # Google Authenticator ka secret

# Angel REST ORDER endpoint
ANGEL_ORDER_URL = "https://apiconnect.angelbroking.com/rest/secure/angelbroking/order/v1/placeOrder"

# Global login variables
smart      = None
JWT_TOKEN  = None


# ================== LOGIN HELPER ==================

def angel_login():
    """
    SmartAPI login + JWT token generate.
    Har baar naya TOTP banega.
    """
    global smart, JWT_TOKEN

    print(f"[{time.strftime('%H:%M:%S')}] 🔐 Logging in to Angel SmartAPI...")

    # SmartAPI client
    smart = SmartConnect(api_key=API_KEY)

    # TOTP generate from secret
    totp = pyotp.TOTP(TOTP_SECRET).now()
    print(f"[{time.strftime('%H:%M:%S')}] TOTP generated.")

    # generateSession with clientcode + PIN/password + totp
    data = smart.generateSession(CLIENT_CODE, CLIENT_PIN, totp)
    print(f"[{time.strftime('%H:%M:%S')}] LOGIN RESPONSE:", data)

    if not data.get("status"):
        raise Exception(f"Login failed: {data}")

    JWT_TOKEN = data["data"]["jwtToken"]
    print(f"[{time.strftime('%H:%M:%S')}] ✅ Login OK, JWT token set.")


def ensure_login():
    """
    Agar JWT_TOKEN missing hai to login kar lo.
    (Simple guard – chaho to expiry check bhi laga sakte ho.)
    """
    global JWT_TOKEN
    if JWT_TOKEN is None:
        angel_login()


# ================== DIRECT REST ORDER HELPER ==================

def place_angel_order(order_payload):
    """
    Angel REST placeOrder ko direct call karta hai.
    SmartAPI SDK use nahi kar rahe, sirf requests.post.
    """
    ensure_login()

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-UserType": "USER",
        "X-SourceID": "WEB",
        "X-ClientLocalIP": "127.0.0.1",
        "X-ClientPublicIP": "127.0.0.1",
        "X-MACAddress": "AA:BB:CC:DD:EE:FF",  # dummy, allowed
        "X-PrivateKey": API_KEY,
        "Authorization": f"Bearer {JWT_TOKEN}",
    }

    print(f"\n[{time.strftime('%H:%M:%S')}] 📤 SENDING ORDER TO ANGEL REST:")
    print(order_payload)

    try:
        resp = requests.post(
            ANGEL_ORDER_URL,
            json=order_payload,
            headers=headers,
            timeout=10,
        )
        print(f"[{time.strftime('%H:%M:%S')}] 📥 ANGEL RESPONSE {resp.status_code}: {resp.text}")
        return resp.status_code, resp.text
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] ❌ REQUEST ERROR:", e)
        return 500, str(e)


# ================== WEBHOOK ==================

@app.route("/webhook", methods=["POST"])
def webhook():
    """
    TradingView se alert receive karega:
    {
      "action": "BUY",
      "symbol": "SBIN",
      "token":  "3045",
      "qty":    1,
      "entry":  620,
      "slPrice":610
    }
    """

    try:
        data = request.get_json(force=True)
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] ❌ ERROR reading JSON:", e)
        return jsonify({"status": "error", "msg": "bad json"}), 400

    print("\n" + "=" * 60)
    print(f"[{time.strftime('%H:%M:%S')}] 🚨 NEW WEBHOOK HIT =====")
    print(f"[{time.strftime('%H:%M:%S')}] 🔔 ALERT RECEIVED:", data)

    # Basic fields
    side   = str(data.get("action", "")).upper()  # BUY / SELL
    symbol = data.get("symbol")                   # e.g. "SBIN"
    token  = str(data.get("token"))               # e.g. "3045"
    qty    = int(data.get("qty", 0) or 0)
    entry  = float(data.get("entry", 0) or 0)
    sl     = float(data.get("slPrice", 0) or 0)

    if not all([side in ("BUY", "SELL"), symbol, token]) or qty <= 0 or entry <= 0 or sl <= 0:
        print(f"[{time.strftime('%H:%M:%S')}] ❌ INVALID PAYLOAD, ignoring.")
        return jsonify({"status": "error", "msg": "invalid payload"}), 400

    # Angel format tradingsymbol: "SBIN-EQ"
    trading_symbol = symbol + "-EQ"

    print(f"[{time.strftime('%H:%M:%S')}] 🎯 ENTRY: {trading_symbol} {entry} x {qty} CNC")

    # ================== 1) ENTRY LIMIT ORDER ==================
    entry_payload = {
        "variety":         "NORMAL",
        "tradingsymbol":   trading_symbol,
        "symboltoken":     token,
        "transactiontype": side,
        "exchange":        "NSE",
        "ordertype":       "LIMIT",
        "producttype":     "CNC",   # cash delivery
        "duration":        "DAY",
        "price":           entry,
        "triggerprice":    0,
        "quantity":        qty
    }

    status1, resp1 = place_angel_order(entry_payload)

    # ================== 2) SL-M ORDER ==================
    sl_side = "SELL" if side == "BUY" else "BUY"
    print(f"[{time.strftime('%H:%M:%S')}] 🛡️ SL-M: {sl} ({sl_side})")

    sl_payload = {
        "variety":         "NORMAL",
        "tradingsymbol":   trading_symbol,
        "symboltoken":     token,
        "transactiontype": sl_side,
        "exchange":        "NSE",
        "ordertype":       "STOPLOSS_MARKET",
        "producttype":     "CNC",
        "duration":        "DAY",
        "price":           0,
        "triggerprice":    sl,
        "quantity":        qty
    }

    status2, resp2 = place_angel_order(sl_payload)

    return jsonify({
        "status": "ok",
        "entry":  {"code": status1, "resp": resp1},
        "sl":     {"code": status2, "resp": resp2},
    })


@app.route("/")
def home():
    return "Angel One webhook server running ✅"


# Render / gunicorn import pe bhi login ho sake, isliye yahan nahi
if __name__ == "__main__":
    # Local run ke liye – Render pe gunicorn handle karega
    angel_login()
    app.run(host="0.0.0.0", port=8000, debug=True)
