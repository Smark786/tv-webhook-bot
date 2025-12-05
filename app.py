from flask import Flask, request, jsonify
import requests
import pyotp
import time

# =========================================================
#  ANGEL CONFIG  🔑  (Yahan apne real values daalo)
# =========================================================

ANGEL_API_KEY   = "DNKHyTmF"        # SmartAPI portal se
ANGEL_CLIENT_ID = "S354855"      # jaise: X12345
ANGEL_PASSWORD  = "2786"       # Trading password (MPIN nahi)
TOTP_SECRET     = "YH4RJAHRVCNMHEQHFUU4VLY6RQ"    # Google Authenticator secret (base32)

# >>> IMPORTANT: upar ke 4 values REAL daalna. <<<

# Angel REST endpoints (SmartAPI v1)
ANGEL_ORDER_URL = "https://apiconnect.angelbroking.com/rest/secure/angelbroking/order/v1/placeOrder"
ANGEL_LOGIN_URL = "https://apiconnect.angelbroking.com/rest/auth/angelbroking/user/v1/loginByPassword"

# Flask app
app = Flask(__name__)

# Global in-memory tokens
JWT_TOKEN = None
FEED_TOKEN = None
CLIENT_LOCAL_IP = "127.0.0.1"
CLIENT_PUBLIC_IP = "127.0.0.1"
MAC_ADDRESS = "AA:BB:CC:DD:EE:FF"   # koi bhi dummy chalega

# =========================================================
#  SYMBOL → TOKEN MAP  (yahan dheere-dheere stocks add karo)
# =========================================================
#  Format:
#  "TRADINGVIEW_SYMBOL": {"symbol": "SBIN-EQ", "token": "3045"}
#  tum TradingView me jo "symbol" field bhejte ho woh left-side key hogi.

SYMBOL_MAP = {
    "ANANTRAJ": {
        "symbol": "ANANTRAJ-EQ",
        "token":  "13620"
    },
    # example:
    # "SBIN": { "symbol": "SBIN-EQ", "token": "3045" },
    # "HDFCBANK": { "symbol": "HDFCBANK-EQ", "token": "1333" },
}


# =========================================================
#  HELPER: login to Angel (direct REST)
# =========================================================
def angel_login():
    """
    Password + TOTP se direct REST login.
    JWT_TOKEN global variable me set ho jayega.
    """
    global JWT_TOKEN, FEED_TOKEN

    # fresh TOTP
    totp = pyotp.TOTP(TOTP_SECRET).now()
    print(f"[{time.strftime('%H:%M:%S')}] 🔐 Generating TOTP:", totp)

    payload = {
        "clientcode": ANGEL_CLIENT_ID,
        "password": ANGEL_PASSWORD,
        "totp": totp
    }

    headers = {
        "Content-Type": "application/json",
        "X-PrivateKey": ANGEL_API_KEY
    }

    print(f"[{time.strftime('%H:%M:%S')}] 🔑 Logging in to Angel REST...")
    resp = requests.post(ANGEL_LOGIN_URL, json=payload, headers=headers, timeout=10)

    print(f"[{time.strftime('%H:%M:%S')}] 🔑 LOGIN HTTP:", resp.status_code, resp.text[:500])

    if resp.status_code != 200:
        print(f"[{time.strftime('%H:%M:%S')}] ❌ Login failed (HTTP {resp.status_code})")
        JWT_TOKEN = None
        return False

    try:
        data = resp.json()
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] ❌ Login JSON parse error:", e)
        JWT_TOKEN = None
        return False

    if not data.get("status"):
        print(f"[{time.strftime('%H:%M:%S')}] ❌ Login status false:", data)
        JWT_TOKEN = None
        return False

    d = data.get("data", {}) or {}
    JWT_TOKEN = d.get("jwtToken")
    FEED_TOKEN = d.get("feedToken")

    print(f"[{time.strftime('%H:%M:%S')}] ✅ Login OK, JWT set.")
    return True


# =========================================================
#  HELPER: place order via REST
# =========================================================
def place_order_rest(variety, tradingsymbol, symboltoken,
                     transactiontype, exchange, ordertype,
                     producttype, duration, price, triggerprice, quantity):
    """
    Angel REST placeOrder call.
    Sare params string/number form me pass karo.
    """
    if JWT_TOKEN is None:
        print(f"[{time.strftime('%H:%M:%S')}] ⚠️ No JWT, doing fresh login...")
        if not angel_login():
            print(f"[{time.strftime('%H:%M:%S')}] ❌ Login failed, aborting order.")
            return None

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-PrivateKey": ANGEL_API_KEY,
        "X-SourceID": "WEB",
        "X-ClientLocalIP": CLIENT_LOCAL_IP,
        "X-ClientPublicIP": CLIENT_PUBLIC_IP,
        "X-MACAddress": MAC_ADDRESS,
        "X-UserType": "USER",
        "Authorization": f"Bearer {JWT_TOKEN}",
    }

    payload = {
        "variety": variety,               # "NORMAL"
        "tradingsymbol": tradingsymbol,   # "ANANTRAJ-EQ"
        "symboltoken": str(symboltoken),  # "13620"
        "transactiontype": transactiontype,  # "BUY"/"SELL"
        "exchange": exchange,             # "NSE"
        "ordertype": ordertype,           # "LIMIT" / "STOPLOSS_MARKET"
        "producttype": producttype,       # "CNC"
        "duration": duration,             # "DAY"
        "price": str(price),
        "triggerprice": str(triggerprice),
        "squareoff": "0",
        "stoploss": "0",
        "quantity": str(quantity),
        "disclosedquantity": "0"
    }

    print(f"[{time.strftime('%H:%M:%S')}] 📤 SENDING TO ANGEL REST: {payload}")
    resp = requests.post(ANGEL_ORDER_URL, json=payload, headers=headers, timeout=10)

    print(f"[{time.strftime('%H:%M:%S')}] 📥 ANGEL RESPONSE HTTP {resp.status_code}: {resp.text}")

    try:
        return resp.json()
    except Exception:
        return {"raw": resp.text, "status_code": resp.status_code}


# =========================================================
#  WEBHOOK ENDPOINT  🔔
# =========================================================
@app.route("/webhook", methods=["POST"])
def webhook():
    global JWT_TOKEN

    try:
        data = request.get_json(force=True, silent=False)
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] ❌ JSON decode error:", e)
        return jsonify({"error": "invalid json"}), 400

    print("\n" + "=" * 60)
    print(f"[{time.strftime('%H:%M:%S')}] 🚨 NEW WEBHOOK HIT =====")
    print(f"[{time.strftime('%H:%M:%S')}] 🛎️ ALERT RECEIVED:", data)

    if not data:
        return jsonify({"error": "empty payload"}), 400

    action = data.get("action", "").upper()   # BUY / SELL
    symbol_key = data.get("symbol", "").upper()
    qty = int(data.get("qty", 0) or 0)
    entry = float(data.get("entry", 0) or 0)
    sl_price = float(data.get("slPrice", 0) or 0)

    # Basic checks
    if action not in ("BUY", "SELL") or qty <= 0 or entry <= 0 or sl_price <= 0 or not symbol_key:
        print(f"[{time.strftime('%H:%M:%S')}] ❌ Invalid payload fields.")
        return jsonify({"error": "invalid fields"}), 400

    # Symbol map lookup
    info = SYMBOL_MAP.get(symbol_key)
    if not info:
        print(f"[{time.strftime('%H:%M:%S')}] ❌ Symbol {symbol_key} not configured in SYMBOL_MAP.")
        return jsonify({"error": "symbol not configured"}), 400

    tradingsymbol = info["symbol"]
    token = info["token"]

    print(f"[{time.strftime('%H:%M:%S')}] ✅ Resolved {symbol_key} → {tradingsymbol}, token {token}")

    # =================== ENTRY ORDER (LIMIT) ===================
    entry_resp = place_order_rest(
        variety="NORMAL",
        tradingsymbol=tradingsymbol,
        symboltoken=token,
        transactiontype=action,
        exchange="NSE",
        ordertype="LIMIT",
        producttype="CNC",
        duration="DAY",
        price=entry,
        triggerprice=0,
        quantity=qty,
    )

    print(f"[{time.strftime('%H:%M:%S')}] ✅ ENTRY RESPONSE:", entry_resp)

    # =================== SL ORDER (SL-M) =======================
    sl_side = "SELL" if action == "BUY" else "BUY"

    sl_resp = place_order_rest(
        variety="NORMAL",
        tradingsymbol=tradingsymbol,
        symboltoken=token,
        transactiontype=sl_side,
        exchange="NSE",
        ordertype="STOPLOSS_MARKET",
        producttype="CNC",
        duration="DAY",
        price=0,
        triggerprice=sl_price,
        quantity=qty,
    )

    print(f"[{time.strftime('%H:%M:%S')}] ✅ SL RESPONSE:", sl_resp)

    return jsonify({
        "status": "ok",
        "entry": entry_resp,
        "sl": sl_resp
    }), 200


@app.route("/", methods=["GET"])
def home():
    return "Angel webhook server running ✅"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
