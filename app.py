from flask import Flask, request, jsonify
from SmartApi.smartConnect import SmartConnect
import pyotp
import time

app = Flask(__name__)

# ================= ANGEL CONFIG =================
API_KEY      = "DNKHyTmF"
CLIENT_ID    = "S354855"
PASSWORD     = "2786"
TOTP_SECRET  = "YH4RJAHRVCNMHEQHFUU4VLY6RQ"   # Google Authenticator ka secret

smart = None
last_login_time = 0
SESSION_TTL = 10 * 60    # 10 minutes

# ------------------------------------------------
def get_smart():
    """Ensure SmartConnect login fresh hai."""
    global smart, last_login_time

    now = time.time()
    if smart is not None and (now - last_login_time) < SESSION_TTL:
        return smart

    print("🔐 Angel login...")
    totp = pyotp.TOTP(TOTP_SECRET).now()
    sc = SmartConnect(api_key=API_KEY)
    data = sc.generateSession(CLIENT_ID, PASSWORD, totp)
    print("✅ LOGIN RESPONSE:", data)

    smart = sc
    last_login_time = now
    return smart


def safe_place_order(order_payload, leg_name):
    """Angel order place kare, error aaya to log kare."""
    sc = get_smart()
    try:
        print(f"📤 SENDING {leg_name} TO ANGEL:", order_payload)
        resp = sc.placeOrder(order_payload)
        print(f"✅ {leg_name} RESPONSE:", resp)
        return resp
    except Exception as e:
        print(f"❌ ANGEL API ERROR in {leg_name}: {e}")
        return None


@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True, silent=False)
        print("\n==============================")
        print("🚨 ALERT RECEIVED:", data)

        action  = data.get("action", "").upper()   # BUY / SELL
        symbol  = data.get("symbol")               # e.g. ANANTRAJ-EQ
        token   = data.get("token")                # e.g. 13620
        qty     = int(data.get("qty", 0) or 0)
        entry   = float(data.get("entry", 0) or 0)
        sl      = float(data.get("slPrice", 0) or 0)

        if not all([action, symbol, token]) or qty <= 0 or entry <= 0 or sl <= 0:
            print("⚠️ INVALID PAYLOAD, ignoring.")
            return jsonify({"status": "error", "msg": "invalid payload"}), 400

        # ----- ENTRY ORDER -----
        entry_order = {
            "variety":        "NORMAL",
            "tradingsymbol":  symbol,
            "symboltoken":    token,
            "transactiontype": action,        # BUY / SELL
            "exchange":       "NSE",
            "ordertype":      "LIMIT",
            "producttype":    "CNC",
            "duration":       "DAY",
            "price":          entry,
            "quantity":       qty
        }

        entry_resp = safe_place_order(entry_order, "ENTRY")

        # ----- SL-M ORDER -----
        sl_side = "SELL" if action == "BUY" else "BUY"
        sl_order = {
            "variety":        "NORMAL",
            "tradingsymbol":  symbol,
            "symboltoken":    token,
            "transactiontype": sl_side,
            "exchange":       "NSE",
            "ordertype":      "STOPLOSS_MARKET",
            "producttype":    "CNC",
            "duration":       "DAY",
            "triggerprice":   sl,
            "quantity":       qty
        }

        sl_resp = safe_place_order(sl_order, "SL")

        return jsonify({
            "status": "ok",
            "entry": entry_resp,
            "sl": sl_resp
        })

    except Exception as e:
        print("🛑 UNHANDLED ERROR IN WEBHOOK:", e)
        return jsonify({"status": "error", "msg": str(e)}), 500


@app.route("/")
def home():
    return "Angel webhook server running ✅"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
