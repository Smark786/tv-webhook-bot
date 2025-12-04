from flask import Flask, request, jsonify
import requests
import uuid

app = Flask(__name__)

# ==================== DHAN CONFIG ====================

DHAN_ACCESS_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJpc3MiOiJkaGFuIiwicGFydG5lcklkIjoiIiwiZXhwIjoxNzY0OTY4MDg2LCJpYXQiOjE3NjQ4ODE2ODYsInRva2VuQ29uc3VtZXJUeXBlIjoiU0VMRiIsIndlYmhvb2tVcmwiOiIiLCJkaGFuQ2xpZW50SWQiOiIxMTA3MDkwNTkyIn0.Z5HOjIt5UXpuJrGSenivv60TO6h5bW5cuKHYU_q00fgHjsl2GBO59s7jxHE8mta7LH19f3YPaNJIehL6wtmf2A"
DHAN_CLIENT_ID    = "1107090592"

DHAN_ORDERS_URL   = "https://api.dhan.co/v2/orders"

# ==================== DHAN ORDER HELPER ====================

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
        print("❌ DHAN EXCEPTION:", e)
        return None, str(e)

# ==================== WEBHOOK ====================

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    print("🚨 Alert mila:", data)

    if data.get("ping") == "keep_alive":
        return jsonify({"status": "alive"})

    side             = data["action"]
    security_id      = data["securityId"]
    exchange_segment = data["exchangeSegment"]
    product_type     = data["productType"]
    qty              = int(data["qty"])
    entry_price      = float(data["entry"])
    sl_price         = float(data["slPrice"])
    target_price     = float(data.get("targetPrice", 0))

    corr_id = str(uuid.uuid4())

    # ========== ENTRY ORDER ==========
    print("📌 Making ENTRY order")
    entry_payload = {
        "dhanClientId":      DHAN_CLIENT_ID,
        "correlationId":     corr_id + "-ENTRY",
        "transactionType":   side,                  # BUY / SELL
        "exchangeSegment":   exchange_segment,
        "productType":       product_type,
        "orderType":         "LIMIT",
        "validity":          "DAY",
        "securityId":        security_id,
        "quantity":          qty,
        "disclosedQuantity": 0,
        "price":             entry_price,
        "triggerPrice":      0,
        "afterMarketOrder":  False
    }

    place_dhan_order(entry_payload)

    # ========== SL-M ORDER ==========
    print("📌 Making SL order")
    sl_side = "SELL" if side == "BUY" else "BUY"

    sl_payload = {
        "dhanClientId":      DHAN_CLIENT_ID,
        "correlationId":     corr_id + "-SL",
        "transactionType":   sl_side,
        "exchangeSegment":   exchange_segment,
        "productType":       product_type,
        "orderType":         "STOP_LOSS_MARKET",
        "validity":          "DAY",
        "securityId":        security_id,
        "quantity":          qty,
        "disclosedQuantity": 0,
        "price":             0,
        "triggerPrice":      sl_price,
        "afterMarketOrder":  False
    }

    place_dhan_order(sl_payload)

    # ========== OPTIONAL TARGET ==========
    if target_price > 0:
        print("📌 Making TARGET order")
        tgt_side = "SELL" if side == "BUY" else "BUY"

        target_payload = {
            "dhanClientId":      DHAN_CLIENT_ID,
            "correlationId":     corr_id + "-TARGET",
            "transactionType":   tgt_side,
            "exchangeSegment":   exchange_segment,
            "productType":       product_type,
            "orderType":         "LIMIT",
            "validity":          "DAY",
            "securityId":        security_id,
            "quantity":          qty,
            "disclosedQuantity": 0,
            "price":             target_price,
            "triggerPrice":      0,
            "afterMarketOrder":  False
        }

        place_dhan_order(target_payload)

    return jsonify({"status": "OK"})

# ==================== ROOT ====================

@app.route("/")
def home():
    return "Webhook server running ✅"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
