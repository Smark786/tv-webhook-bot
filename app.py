from flask import Flask, request, jsonify
from SmartApi import SmartConnect
from SmartApi.smartExceptions import DataException, GeneralException
import pyotp

app = Flask(__name__)

# ============ ANGEL ONE CREDENTIALS ============
# 👇 Sirf in 4 lines me apni details bharo

API_KEY   = "DNKHyTmF"
CLIENT_ID = "S354855"
PASSWORD  = "2786"              # Yahan MPIN hi rahega
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

# ============ HELPER: SAFE PLACE ORDER ============

def safe_place_order(order_params, leg_name):
    """placeOrder ko safely call karta hai aur error handle karta hai."""
    try:
        print(f"➡️ Placing {leg_name} order with:", order_params)
        resp = obj.placeOrder(order_params)
        print(f"✅ {leg_name} RESPONSE:", resp)
        # SmartAPI kabhi object/dict deta hai, to use string bana kar bhej rahe
        return {"ok": True, "response": str(resp)}
    except (DataException, GeneralException) as e:
        print(f"❌ {leg_name} DataException:", repr(e))
        return {"ok": False, "error": repr(e)}
    except Exception as e:
        print(f"❌ {leg_name} UNKNOWN ERROR:", repr(e))
        return {"ok": False, "error": repr(e)}

# ============ WEBHOOK ROUTE ============

@app.route("/webhook", methods=["POST"])
def webhook():
    print("===== NEW WEBHOOK HIT =====")
    data = request.get_json(silent=True, force=True)
    print("🚨 ALERT RECEIVED:", data)

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
            "transactiontype": side,          # BUY / SELL
            "exchange": "NSE",
            "ordertype": "LIMIT",
            "producttype": product_type,      # CNC / INTRADAY
            "duration": "DAY",
            "price": entry,
            "quantity": qty
        }
        entry_result = safe_place_order(entry_order, "ENTRY")

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
        sl_result = safe_place_order(sl_order, "SL-M")

        # ✅ Hamesha JSON response do (TradingView ko ye chahiye)
        return jsonify({
            "status": "ok",
            "entry": entry_result,
            "sl": sl_result
        }), 200

    except Exception as e:
        # Agar kuch bhi fatka to bhi JSON hi return hoga
        print("🛑 FATAL ERROR in webhook:", repr(e))
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 200   # 200 rakho, warna TV error dikhayega


@app.route("/")
def home():
    return "✅ Angel One Webhook Running (safe JSON response)"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
