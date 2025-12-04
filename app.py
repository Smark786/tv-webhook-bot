from flask import Flask, request, jsonify
import requests
import uuid

app = Flask(__name__)

# ==================== DHAN CONFIG ====================

# ✅ YAHAN APNA REAL DHAN TOKEN & CLIENT ID DAALO
DHAN_ACCESS_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJpc3MiOiJkaGFuIiwicGFydG5lcklkIjoiIiwiZXhwIjoxNzY0OTY4MDg2LCJpYXQiOjE3NjQ4ODE2ODYsInRva2VuQ29uc3VtZXJUeXBlIjoiU0VMRiIsIndlYmhvb2tVcmwiOiIiLCJkaGFuQ2xpZW50SWQiOiIxMTA3MDkwNTkyIn0.Z5HOjIt5UXpuJrGSenivv60TO6h5bW5cuKHYU_q00fgHjsl2GBO59s7jxHE8mta7LH19f3YPaNJIehL6wtmf2A"
DHAN_CLIENT_ID    = "1107090592"

DHAN_ORDERS_URL   = "https://api.dhan.co/v2/orders"

# ==================== HELPER FUNCTION ====================

def place_dhan_order(payload):
    headers = {
        "Content-Type": "application/json",
        "access-token": DHAN_ACCESS_TOKEN
    }

    print("➡️ CALLING DHAN API WITH PAYLOAD:")
    print(payload)

    try:
        resp = requests.post(
            DHAN_ORDERS_URL,
            json=payload,
            headers=headers,
            timeout=10
        )
        print("⬅️ DHAN RESPONSE:", resp.status_code, resp.text)
        return resp.status_code, resp.text
    except Exception as e:
        print("❌ DHAN EXCEPTION:", repr(e))
        return None, str(e)

# ==================== WEBHOOK ====================

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(force=True, silent=True)
    print("🚨 Alert mila:", data)

    if data is None:
        return jsonify({"error": "No data"}), 400

    if data.get("ping") == "keep_alive":
        return jsonify({"status": "alive"})

    # TradingView data
    side             = data.get("action")           # BUY / SELL
    security_id      = data.get("securityId")       # Dhan securityId
    exchange_segment = data.get("exchangeSegment")  # NSE_EQ
    product_type     = data.get("productType")      # CNC / INTRADAY
    qty              = int(data.get("qty", 0))
    entry_price      = float(data.get("entry", 0))
    sl_price         = float(data.get("slPrice", 0))
    target_price     = float(data.get("targetPrice", 0))

    # Basic validation
    if not all([side, security_id, exchange_segment, product_type]) \
       or qty <= 0 or entry_price <= 0 or sl_price <= 0:
        print("❌ Invalid payload")
        return jsonify({"error": "Invalid payload"}), 400

    corr_id = str(uuid.uuid4())

    # ================= ENTRY ORDER =================

    print("📌 Making ENTRY order")

    entry_payload = {
        "dhanClientId":    DHAN_CLIENT_ID,
        "correlationId":   corr_id + "-ENTRY",
        "transactionType": side,
        "exchangeSegment": exchange_segment,
        "productType":     product_type,
        "orderType":       "LIMIT",
        "validity":        "DAY",
        "securityId":      security_id,
        "quantity":        qty,
        "price":           entry_price,
        "afterMarketOrder": False
    }

    place_dhan_order(entry_payload)

    # ================= SL-M ORDER =================

    print("📌 Making SL order")

    sl_side = "SELL" if side == "BUY" else "BUY"

    sl_payload = {
        "dhanClientId":    DHAN_CLIENT_ID,
        "correlationId":   corr_id + "-SL",
        "transactionType": sl_side,
        "exchangeSegment": exchange_segment,
        "productType":     product_type,
        "orderType":       "STOP_LOSS_MARKET",
        "validity":        "DAY",
        "securityId":      security_id,
        "quantity":        qty,
        "triggerPrice":    sl_price,
        "afterMarketOrder": False
    }

    place_dhan_order(sl_payload)

    # ================= OPTIONAL TARGET =================

    if target_price > 0:
        print("📌 Making TARGET order")

        tgt_side = "SELL" if side == "BUY" else "BUY"

        tgt_payload = {
            "dhanClientId":    DHAN_CLIENT_ID,
            "correlationId":   corr_id + "-TARGET",
            "transactionType": tgt_side,
            "exchangeSegment": exchange_segment,
            "productType":     product_type,
            "orderType":       "LIMIT",
            "validity":        "DAY",
            "securityId":      security_id,
            "quantity":        qty,
            "price":           target_price,
            "afterMarketOrder": False
        }

        place_dhan_order(tgt_payload)

    return jsonify({"status": "orders sent"})

# ==================== ROOT ====================

@app.route("/", methods=["GET"])
def home():
    return "Webhook server running ✅"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
