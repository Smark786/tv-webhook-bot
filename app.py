from flask import Flask, request, jsonify
import requests
import uuid

app = Flask(__name__)

# ==================== DHAN CONFIG ====================

# 👉 Yahan apna real Dhan access token & clientId daalna
DHAN_ACCESS_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJpc3MiOiJkaGFuIiwicGFydG5lcklkIjoiIiwiZXhwIjoxNzY0OTY4MDg2LCJpYXQiOjE3NjQ4ODE2ODYsInRva2VuQ29uc3VtZXJUeXBlIjoiU0VMRiIsIndlYmhvb2tVcmwiOiIiLCJkaGFuQ2xpZW50SWQiOiIxMTA3MDkwNTkyIn0.Z5HOjIt5UXpuJrGSenivv60TO6h5bW5cuKHYU_q00fgHjsl2GBO59s7jxHE8mta7LH19f3YPaNJIehL6wtmf2A"
DHAN_CLIENT_ID    = "1107090592"

DHAN_ORDERS_URL   = "https://api.dhan.co/v2/orders"


# ==================== HELPER: PLACE DHAN ORDER ====================

def place_dhan_order(payload):
    headers = {
        "Content-Type": "application/json",
        "access-token": DHAN_ACCESS_TOKEN
    }
    print("➡️ Sending order to Dhan:", payload)
    resp = requests.post(DHAN_ORDERS_URL, json=payload, headers=headers)
    print("⬅️ Dhan response:", resp.status_code, resp.text)
    return resp.status_code, resp.text


# ==================== WEBHOOK ENDPOINT ====================

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(force=True, silent=True)
    print("🚨 Alert received:", data)

    # Agar sirf ping / keep-alive ho to ignore kar do
    if data is None:
        return jsonify({"error": "No data"}), 400

    if data.get("ping") == "keep_alive":
        return jsonify({"status": "alive"})

    # ---- TradingView se aaya data ----
    side             = data.get("action")           # "BUY" / "SELL"
    security_id      = data.get("securityId")       # e.g. "11536"
    exchange_segment = data.get("exchangeSegment")  # e.g. "NSE_EQ"
    product_type     = data.get("productType")      # "CNC" / "INTRADAY"
    qty              = int(data.get("qty", 0) or 0)
    entry_price      = float(data.get("entry", 0) or 0)
    sl_price         = float(data.get("slPrice", 0) or 0)
    target_price     = float(data.get("targetPrice", 0) or 0)  # 0 = no target

    # ---------- BASIC VALIDATION ----------
    if not all([side, security_id, exchange_segment, product_type]) \
       or qty <= 0 or entry_price <= 0 or sl_price <= 0:
        print("❌ Invalid payload, ignoring.")
        return jsonify({"error": "Invalid payload"}), 400

    # Simple safety: max qty guard (optional)
    if qty > 2000:  # apni limit set karo
        print("❌ Qty too big, rejecting:", qty)
        return jsonify({"error": "qty too big"}), 400

    # Correlation id (tracking ke liye)
    corr_id = str(uuid.uuid4())

    orders_placed = []

    # ========== 1) ENTRY LIMIT ORDER ==========
    entry_payload = {
        "dhanClientId":      DHAN_CLIENT_ID,
        "correlationId":     corr_id + "-ENTRY",
        "transactionType":   side,                  # "BUY" / "SELL"
        "exchangeSegment":   exchange_segment,      # e.g. "NSE_EQ"
        "productType":       product_type,          # "CNC" / "INTRADAY"
        "orderType":         "LIMIT",
        "validity":          "DAY",
        "securityId":        security_id,
        "quantity":          qty,
        "disclosedQuantity": 0,
        "price":             entry_price,
        "triggerPrice":      0,
        "afterMarketOrder":  False,
        "amoTime":           "",
        "boProfitValue":     0,
        "boStopLossValue":   0
    }

    # ⚠️ REAL TRADE CALL: production me ye chalu rahega
    status, text = place_dhan_order(entry_payload)
    orders_placed.append({"leg": "ENTRY", "status": status, "resp": text})

    # ========== 2) STOP LOSS MARKET ORDER ==========
    # Long: BUY entry → SL = SELL STOP_LOSS_MARKET
    # Short: SELL entry → SL = BUY STOP_LOSS_MARKET
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
        "price":             0,          # SL-M mein price nahi
        "triggerPrice":      sl_price,   # yahi tumhara SL level
        "afterMarketOrder":  False,
        "amoTime":           "",
        "boProfitValue":     0,
        "boStopLossValue":   0
    }

    status, text = place_dhan_order(sl_payload)
    orders_placed.append({"leg": "SL", "status": status, "resp": text})

    # ========== 3) OPTIONAL TARGET LIMIT ORDER ==========
    if target_price > 0:
        tgt_side = "SELL" if side == "BUY" else "BUY"
        tgt_payload = {
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
            "afterMarketOrder":  False,
            "amoTime":           "",
            "boProfitValue":     0,
            "boStopLossValue":   0
        }

        status, text = place_dhan_order(tgt_payload)
        orders_placed.append({"leg": "TARGET", "status": status, "resp": text})

    return jsonify({"status": "ok", "orders": orders_placed})


@app.route("/", methods=["GET"])
def home():
    return "Webhook server running ✅"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
