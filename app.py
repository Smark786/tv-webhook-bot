from flask import Flask, request, jsonify
from SmartApi import SmartConnect
import pyotp
import time

app = Flask(__name__)

# =====================================================
#  ANGEL ONE CREDENTIALS  (YAHAN APNI DETAILS BHARO)
# =====================================================
API_KEY     = "DNKHyTmF"
CLIENT_CODE = "S354855"
PASSWORD    = "2786"
TOTP_KEY    = "YH4RJAHRVCNMHEQHFUU4VLY6RQ"   # Google Authenticator se jo secret milta hai

# =====================================================
#  SYMBOL → TOKEN MAP  (YAHAN NAYA STOCK ADD KAR SAKTE HO)
# =====================================================
SYMBOL_TOKEN_MAP = {
    # ---- NSE CASH EXAMPLE ----
    "ANANTRAJ": {
        "tradingsymbol": "ANANTRAJ-EQ",
        "token": "13620",
        "exchange": "NSE",
        "producttype": "CNC",      # delivery
    },

    # ---- MCX CRUDEOIL EXAMPLE ----
    "CRUDEOIL": {
        "tradingsymbol": "CRUDEOILCOM",
        "token": "294",
        "exchange": "MCX",
        "producttype": "NRML",     # overnight / positional
    },
}

# =====================================================
#  ANGEL LOGIN HELPER
# =====================================================
def angel_login():
    """
    Har webhook pe fresh Angel login karega
    taaki 'Invalid Token' waali problem na aaye.
    """
    print("🔐 Angel login start...")
    smart = SmartConnect(api_key=API_KEY)

    # TOTP generate
    totp = pyotp.TOTP(TOTP_KEY).now()
    print("🔢 TOTP generated:", totp)

    data = smart.generateSession(
        CLIENT_CODE,
        PASSWORD,
        totp
    )

    if not data.get("status"):
        # Agar login fail ho gaya
        print("❌ Angel login failed:", data)
        raise Exception("Angel login failed")

    jwt_token = data["data"]["jwtToken"]
    smart.setAccessToken(jwt_token)

    print("✅ Angel login done, token set")
    return smart

# =====================================================
#  WEBHOOK ENDPOINT
# =====================================================
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        payload = request.get_json(force=True, silent=True)
        print("\n" + "=" * 60)
        print(time.strftime("%H:%M:%S"), "🔔 ALERT RECEIVED:", payload)

        if not payload:
            print("❌ No JSON payload")
            return jsonify({"error": "No JSON payload"}), 400

        # --------- TradingView se fields read karo ----------
        action = payload.get("action", "").upper()   # BUY / SELL
        symbol = payload.get("symbol", "").upper()   # e.g. ANANTRAJ, CRUDEOIL
        qty     = int(payload.get("qty", 0) or 0)
        entry   = float(payload.get("entry", 0) or 0)
        sl      = float(payload.get("slPrice", 0) or 0)

        # Basic validation
        if not action or not symbol or qty <= 0 or entry <= 0:
            print("❌ Invalid alert data:", payload)
            return jsonify({"error": "Invalid alert data"}), 400

        # --------- Symbol mapping check ----------
        if symbol not in SYMBOL_TOKEN_MAP:
            print("❌ Symbol", symbol, "not mapped in SYMBOL_TOKEN_MAP")
            return jsonify({"error": f"Symbol {symbol} not mapped"}), 400

        sym_cfg = SYMBOL_TOKEN_MAP[symbol]
        tradingsymbol = sym_cfg["tradingsymbol"]
        token         = sym_cfg["token"]
        exchange      = sym_cfg["exchange"]
        producttype   = sym_cfg["producttype"]

        print("✅ Mapped", symbol, "→", tradingsymbol, "| token", token, "| exch", exchange)

        # --------- Angel login ---------
        smart = angel_login()

        # =================================================
        # 1) ENTRY ORDER
        # =================================================
        entry_order_payload = {
            "variety": "NORMAL",
            "tradingsymbol": tradingsymbol,
            "symboltoken": token,
            "transactiontype": action,       # BUY / SELL
            "exchange": exchange,            # NSE / MCX
            "ordertype": "LIMIT",
            "producttype": producttype,      # CNC / NRML / MIS
            "duration": "DAY",
            "price": entry,
            "quantity": qty,
        }

        print("📨 ENTRY ORDER PAYLOAD:", entry_order_payload)

        try:
            raw_entry_resp = smart.placeOrder(entry_order_payload)
            print("📩 RAW ENTRY RESPONSE:", raw_entry_resp)
        except Exception as e:
            # SmartAPI kabhi-kabhi empty response de deta hai -> JSON parse error
            print("⚠️ ANGEL API ERROR in ENTRY (ignored):", str(e))
            raw_entry_resp = None

        print("✅ ENTRY RESPONSE:", raw_entry_resp)

        # =================================================
        # 2) STOPLOSS ORDER
        # =================================================
        if sl > 0:
            sl_side = "SELL" if action == "BUY" else "BUY"

            sl_order_payload = {
                "variety": "NORMAL",
                "tradingsymbol": tradingsymbol,
                "symboltoken": token,
                "transactiontype": sl_side,
                "exchange": exchange,
                "ordertype": "STOPLOSS_MARKET",
                "producttype": producttype,
                "duration": "DAY",
                "triggerprice": sl,
                "quantity": qty,
            }

            print("📨 SL ORDER PAYLOAD:", sl_order_payload)

            try:
                raw_sl_resp = smart.placeOrder(sl_order_payload)
                print("📩 RAW SL RESPONSE:", raw_sl_resp)
            except Exception as e:
                print("⚠️ ANGEL API ERROR in SL (ignored):", str(e))
                raw_sl_resp = None

            print("✅ SL RESPONSE:", raw_sl_resp)
        else:
            print("ℹ️ SL not provided, skipping SL order")

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        print("🛑 UNHANDLED ERROR in webhook:", str(e))
        return jsonify({"error": str(e)}), 500

# Simple health check
@app.route("/", methods=["GET"])
def home():
    return "✅ Angel Webhook Server Running"

# Local run (Render gunicorn use karega)
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
