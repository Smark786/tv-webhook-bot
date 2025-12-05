from flask import Flask, request, jsonify
import requests
import uuid
import time

app = Flask(__name__)

# ================== DHAN CONFIG ==================

DHAN_ACCESS_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJpc3MiOiJkaGFuIiwicGFydG5lcklkIjoiIiwiZXhwIjoxNzY0OTY4MDg2LCJpYXQiOjE3NjQ4ODE2ODYsInRva2VuQ29uc3VtZXJUeXBlIjoiU0VMRiIsIndlYmhvb2tVcmwiOiIiLCJkaGFuQ2xpZW50SWQiOiIxMTA3MDkwNTkyIn0.Z5HOjIt5UXpuJrGSenivv60TO6h5bW5cuKHYU_q00fgHjsl2GBO59s7jxHE8mta7LH19f3YPaNJIehL6wtmf2A"   # <- yahan apna token
DHAN_CLIENT_ID    = "1107090592"      # <- yahan apna client id

DHAN_ORDERS_URL   = "https://api.dhan.co/v2/orders"

DHAN_HEADERS = {
    "Content-Type": "application/json",
    "access-token": DHAN_ACCESS_TOKEN
}

# ================== HELPER ==================

def place_dhan_order(payload):
    """Dhan API ko order bhejta hai."""
    ts = time.strftime("%H:%M:%S")
    print(f"\n[{ts}] ➡️ DHAN PAYLOAD:")
    print(payload)

    resp = requests.post(
        DHAN_ORDERS_URL,
        json=payload,
        headers=DHAN_HEADERS,
        timeout=10
    )

    print(f"[{ts}] ⬅️ DHAN RESPONSE: {resp.status_code} {resp.text}")
    return resp.status_code, resp.text

# ================== WEBHOOK ==================

@app.route("/webhook", methods=["POST"])
def webhook():
    ts = time.strftime("%H:%M:%S")
    try:
        data = request.get_json(force=True)
        print(f"\n[{ts}] 🚨 ALERT RECEIVED:")
        print(data)

        # --------- Basic fields from TradingView ----------
        side_raw    = data.get("action", "").upper()      # BUY / SELL
        sec_id_raw  = data.get("securityId")
        qty_raw     = data.get("qty")
        entry_raw   = data.get("entry")
        sl_raw      = data.get("slPrice")
        product_raw = data.get("productType", "INTRADAY").upper()

        # --------- Basic validation ----------
        if side_raw not in ("BUY", "SELL"):
            return jsonify({"error": "invalid action"}), 400

        if not sec_id_raw:
            return jsonify({"error": "securityId missing"}), 400

        try:
            qty = int(qty_raw)
            entry_price = float(entry_raw)
            sl_price = float(sl_raw)
        except (TypeError, ValueError):
            return jsonify({"error": "qty/entry/slPrice invalid"}), 400

        if qty <= 0 or entry_price <= 0 or sl_price <= 0:
            return jsonify({"error": "qty/price <= 0"}), 400

        # --------- Map productType to Dhan format ----------
        if product_raw in ("INTRA", "INTRADAY"):
            product_type = "INTRADAY"
        elif product_raw == "CNC":
            product_type = "CNC"
        else:
            product_type = "INTRADAY"  # default

        # Dhan expects securityId as string
        security_id = str(sec_id_raw)

        correlation_id = str(uuid.uuid4())

        # ================== 1) ENTRY LIMIT ORDER ==================
        print(f"[{ts}] 📌 Making ENTRY order")

        entry_payload = {
            "dhanClientId":    DHAN_CLIENT_ID,
            "correlationId":   correlation_id + "-ENTRY",
            "transactionType": side_raw,          # BUY / SELL
            "exchangeSegment": "NSE_EQ",          # stocks ke liye
            "productType":     product_type,      # INTRADAY / CNC
            "orderType":       "LIMIT",
            "validity":        "DAY",
            "securityId":      security_id,
            "quantity":        qty,
            # docs ke mutabik price required for LIMIT
            "price":           entry_price,
            # optional fields, lekin safe:
            "disclosedQuantity": "",
            "triggerPrice":      "",
            "afterMarketOrder":  False,
            "amoTime":           "",
            "boProfitValue":     "",
            "boStopLossValue":   ""
        }

        status_e, text_e = place_dhan_order(entry_payload)

        # ================== 2) SL-M ORDER ==================
        print(f"[{ts}] 📌 Making SL-M order")

        sl_side = "SELL" if side_raw == "BUY" else "BUY"

        sl_payload = {
            "dhanClientId":    DHAN_CLIENT_ID,
            "correlationId":   correlation_id + "-SL",
            "transactionType": sl_side,
            "exchangeSegment": "NSE_EQ",
            "productType":     product_type,
            "orderType":       "STOP_LOSS_MARKET",
            "validity":        "DAY",
            "securityId":      security_id,
            "quantity":        qty,
            "disclosedQuantity": "",
            "price":           0,          # SL-M ke liye 0
            "triggerPrice":    sl_price,   # docs: yahi actual SL level
            "afterMarketOrder": False,
            "amoTime":          "",
            "boProfitValue":    "",
            "boStopLossValue":  ""
        }

        status_sl, text_sl = place_dhan_order(sl_payload)

        return jsonify({
            "status": "OK",
            "entry_status": status_e,
            "sl_status": status_sl
        })

    except Exception as e:
        print(f"[{ts}] 🛑 UNHANDLED EXCEPTION IN WEBHOOK: {e}")
        return jsonify({"error": str(e)}), 500

# ================== HEALTH ==================

@app.route("/", methods=["GET"])
def home():
    return "Dhan Webhook server running ✅"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
