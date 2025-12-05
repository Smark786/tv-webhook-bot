from flask import Flask, request, jsonify
from SmartApi.smartConnect import SmartConnect
import pyotp
import requests
import time

app = Flask(__name__)

# ================= ANGEL CONFIG (FILL THESE) =================
ANGEL_API_KEY     = "DNKHyTmF"
ANGEL_CLIENT_ID   = "S354855"
ANGEL_PASSWORD    = "2786"
ANGEL_TOTP_SECRET = "YH4RJAHRVCNMHEQHFUU4VLY6RQ"
# =============================================================

# Angel ScripMaster JSON – yahi se saare symbol-token aayenge
SCRIP_MASTER_URL = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"

# In-memory map: "ANANTRAJ" -> "13620"
SYMBOL_TOKEN_MAP = {}

# SmartAPI session globals
smart = None
last_login_time = 0  # seconds timestamp


# ================= SCRIP MASTER LOADER =================
def load_scrip_master():
    """
    Angel ke OpenAPIScripMaster JSON se
    saare NSE EQ symbols ka map banaata hai:
    'ANANTRAJ' -> '13620'
    """
    global SYMBOL_TOKEN_MAP
    try:
        print("📥 Loading ScripMaster from Angel URL...")
        resp = requests.get(SCRIP_MASTER_URL, timeout=20)
        resp.raise_for_status()
        data = resp.json()

        tmp_map = {}
        count = 0

        for row in data:
            # Typical keys: symbol, token, exch_seg, instrumenttype
            exch = (row.get("exch_seg") or "").upper()
            inst = (row.get("instrumenttype") or "").upper()
            symbol_full = (row.get("symbol") or "").upper()
            token = row.get("token")

            # Sirf NSE cash stocks chahiye
            if exch == "NSE" and inst == "EQ" and symbol_full and token:
                # "ANANTRAJ-EQ" -> "ANANTRAJ"
                base_symbol = symbol_full.split("-")[0]
                tmp_map[base_symbol] = str(token)
                count += 1

        SYMBOL_TOKEN_MAP = tmp_map
        print(f"✅ Loaded {count} NSE EQ symbols into SYMBOL_TOKEN_MAP")

    except Exception as e:
        print("❌ ERROR loading ScripMaster:", e)


def get_token_for_symbol(symbol: str):
    """
    TradingView se aaya plain symbol, jaise 'ANANTRAJ'.
    Uska token map se nikalta hai.
    """
    if not SYMBOL_TOKEN_MAP:
        load_scrip_master()

    symbol = symbol.upper()
    token = SYMBOL_TOKEN_MAP.get(symbol)
    return token


# ================= ANGEL LOGIN HELPER =================
def ensure_angel_login(force: bool = False):
    """
    SmartAPI login maintain karta hai.
    1 ghante se purana ho to naya login karega.
    """
    global smart, last_login_time

    now = time.time()
    if smart is not None and not force and (now - last_login_time) < 3300:
        # < 55 minutes, old login still ok
        return

    print("🔐 Doing fresh Angel SmartAPI login...")
    smart = SmartConnect(api_key=ANGEL_API_KEY)

    # TOTP generate
    totp = pyotp.TOTP(ANGEL_TOTP_SECRET).now()

    data = smart.generateSession(ANGEL_CLIENT_ID, ANGEL_PASSWORD, totp)
    if not data.get("status"):
        print("❌ Angel login failed:", data)
        raise Exception("Angel login failed")

    last_login_time = now
    print("✅ Fresh Angel login done")


# ================= WEBHOOK ENDPOINT =================
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({"error": "Invalid JSON"}), 400

    print("\n===============================")
    print("🚨 NEW WEBHOOK HIT")
    print("ALERT RECEIVED:", data)
    print("===============================")

    # --- Basic fields from TradingView ---
    action = (data.get("action") or "").upper()      # BUY / SELL
    symbol = (data.get("symbol") or "").upper()      # e.g. ANANTRAJ
    qty     = int(data.get("qty", 0) or 0)
    entry   = float(data.get("entry", 0) or 0)
    sl      = float(data.get("slPrice", 0) or 0)

    if not action or not symbol or qty <= 0 or entry <= 0 or sl <= 0:
        return jsonify({"error": "Missing/invalid fields"}), 400

    # --- Token from ScripMaster map ---
    token = get_token_for_symbol(symbol)
    if not token:
        print(f"❌ Symbol {symbol} not found in ScripMaster map")
        return jsonify({"error": f"Symbol {symbol} not mapped"}), 400

    print(f"✅ Symbol {symbol} -> token {token}")

    # --- Ensure Angel Login ---
    try:
        ensure_angel_login()
    except Exception as e:
        return jsonify({"error": f"Angel login failed: {e}"}), 500

    # Common things
    side_entry = "BUY" if action == "BUY" else "SELL"
    side_sl    = "SELL" if side_entry == "BUY" else "BUY"
    trading_symbol = f"{symbol}-EQ"  # ScripMaster style

    entry_resp = None
    sl_resp = None

    # =================== PLACE ENTRY LIMIT ===================
    try:
        order_params_entry = {
            "variety": "NORMAL",
            "tradingsymbol": trading_symbol,
            "symboltoken": token,
            "transactiontype": side_entry,
            "exchange": "NSE",
            "ordertype": "LIMIT",
            "producttype": "CNC",     # cash delivery
            "duration": "DAY",
            "price": entry,
            "squareoff": "0",
            "stoploss": "0",
            "quantity": qty,
        }

        print("📨 SENDING ENTRY ORDER TO ANGEL REST:", order_params_entry)
        entry_resp = smart.placeOrder(order_params_entry)
        print("✅ ENTRY RESPONSE:", entry_resp)

    except Exception as e:
        print("❌ ENTRY EXCEPTION:", e)

    # =================== PLACE SL-M ORDER ===================
    try:
        order_params_sl = {
            "variety": "NORMAL",
            "tradingsymbol": trading_symbol,
            "symboltoken": token,
            "transactiontype": side_sl,
            "exchange": "NSE",
            "ordertype": "STOPLOSS_MARKET",
            "producttype": "CNC",
            "duration": "DAY",
            "triggerprice": sl,
            "price": 0,
            "squareoff": "0",
            "stoploss": "0",
            "quantity": qty,
        }

        print("📨 SENDING SL-M ORDER TO ANGEL REST:", order_params_sl)
        sl_resp = smart.placeOrder(order_params_sl)
        print("✅ SL RESPONSE:", sl_resp)

    except Exception as e:
        print("❌ SL EXCEPTION:", e)

    return jsonify({
        "status": "ok",
        "symbol": symbol,
        "token": token,
        "entryResponse": entry_resp,
        "slResponse": sl_resp
    })


@app.route("/", methods=["GET"])
def home():
    return "Angel webhook server running ✅"


if __name__ == "__main__":
    # App start hote hi ScripMaster load kar lo
    load_scrip_master()
    app.run(host="0.0.0.0", port=8000)
