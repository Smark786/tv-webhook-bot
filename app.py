from flask import Flask, request, jsonify
from SmartApi import SmartConnect
from SmartApi.smartExceptions import DataException
import pyotp
import time

app = Flask(__name__)

# ---------------- Angel Credentials ----------------
API_KEY     = "DNKHyTmF"
CLIENT_CODE = "S354855"   # jaise: X12345
PASSWORD    = "2786"    # MPIN nahi, login password
TOTP_KEY    = "YH4RJAHRVCNMHEQHFUU4VLY6RQ"  # Google Authenticator ka secret

# ---------------- Symbol → Token Map ----------------
# TradingView se tum jo "symbol" bhejoge woh yahan key hoga.
# Naya stock => yaha ek line aur add kar dena.
SYMBOL_TOKEN_MAP = {
    "ANANTRAJ": "13620",
    "SBIN": "3045",
    # "HDFCBANK": "1333",  # example
}

# ---------------------------------------------------

def angel_login():
    """Har webhook pe fresh Angel login."""
    smart = SmartConnect(api_key=API_KEY)

    totp = pyotp.TOTP(TOTP_KEY).now()
    print(f"[{time.strftime('%H:%M:%S')}] 🔐 TOTP generated:", totp)

    data = smart.generateSession(
        CLIENT_CODE,
        PASSWORD,
        totp
    )

    if not data.get("status"):
        print(f"[{time.strftime('%H:%M:%S')}] ❌ Angel Login Failed:", data)
        raise Exception("Angel Login Failed")

    jwt = data["data"]["jwtToken"]
    smart.setAccessToken(jwt)
    print(f"[{time.strftime('%H:%M:%S')}] ✅ Angel login done, token set")
    return smart


@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
        print("\n" + "=" * 60)
        print(f"[{time.strftime('%H:%M:%S')}] 🔔 ALERT RECEIVED:", data)

        # ---- basic parsing ----
        action = data["action"].upper()          # BUY / SELL
        symbol = data["symbol"].upper()          # e.g. ANANTRAJ
        qty    = int(data["qty"])
        entry  = float(data.get("entry", 0))
        sl     = float(data.get("slPrice", 0))

        if symbol not in SYMBOL_TOKEN_MAP:
            msg = f"Symbol {symbol} not mapped in SYMBOL_TOKEN_MAP"
            print("❌", msg)
            return jsonify({"error": msg}), 400

        token = SYMBOL_TOKEN_MAP[symbol]
        print(f"[{time.strftime('%H:%M:%S')}] ✅ Symbol {symbol} → token {token}")

        # ✅ har baar naya login
        smart = angel_login()

        # -------- ENTRY ORDER --------
        entry_params = {
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

        print(f"[{time.strftime('%H:%M:%S')}] 📤 ENTRY ORDER:", entry_params)

        try:
            entry_order = smart.placeOrder(entry_params)
        except DataException as e:
            # yahi woh "Couldn't parse JSON..." waali error hai
            print(f"[{time.strftime('%H:%M:%S')}] ⚠️ Angel API ERROR in ENTRY (ignored):", e)
            entry_order = None

        print(f"[{time.strftime('%H:%M:%S')}] ✅ ENTRY RESPONSE:", entry_order)

        # -------- SL ORDER (agar SL diya hai) --------
        sl_order = None
        if sl > 0:
            sl_action = "SELL" if action == "BUY" else "BUY"

            sl_params = {
                "variety":         "NORMAL",
                "tradingsymbol":   f"{symbol}-EQ",
                "symboltoken":     token,
                "transactiontype": sl_action,
                "exchange":        "NSE",
                "ordertype":       "STOPLOSS_MARKET",
                "producttype":     "CNC",
                "duration":        "DAY",
                "triggerprice":    sl,
                "quantity":        qty,
            }

            print(f"[{time.strftime('%H:%M:%S')}] 📤 SL ORDER:", sl_params)

            try:
                sl_order = smart.placeOrder(sl_params)
            except DataException as e:
                print(f"[{time.strftime('%H:%M:%S')}] ⚠️ Angel API ERROR in SL (ignored):", e)
                sl_order = None

            print(f"[{time.strftime('%H:%M:%S')}] ✅ SL RESPONSE:", sl_order)
        else:
            print(f"[{time.strftime('%H:%M:%S')}] ⚠️ SL 0 hai, SL order skip kiya")

        return jsonify({
            "status": "order_sent",
            "entry":  entry_order,
            "sl":     sl_order
        })

    except Exception as e:
        print("❌ FATAL ERROR in webhook:", str(e))
        return jsonify({"error": str(e)}), 500


@app.route("/")
def home():
    return "✅ Angel Webhook Server Running"


if __name__ == "__main__":
    # local run ke liye; Render pe gunicorn chalega
    app.run(host="0.0.0.0", port=8000)
