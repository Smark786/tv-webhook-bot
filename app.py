from flask import Flask, request, jsonify
import requests, uuid

app = Flask(__name__)

# ===== DHAN CONFIG =====
DHAN_ACCESS_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJpc3MiOiJkaGFuIiwicGFydG5lcklkIjoiIiwiZXhwIjoxNzY0OTY4MDg2LCJpYXQiOjE3NjQ4ODE2ODYsInRva2VuQ29uc3VtZXJUeXBlIjoiU0VMRiIsIndlYmhvb2tVcmwiOiIiLCJkaGFuQ2xpZW50SWQiOiIxMTA3MDkwNTkyIn0.Z5HOjIt5UXpuJrGSenivv60TO6h5bW5cuKHYU_q00fgHjsl2GBO59s7jxHE8mta7LH19f3YPaNJIehL6wtmf2A"
DHAN_CLIENT_ID    = "1107090592"
DHAN_ORDERS_URL   = "https://api.dhan.co/v2/orders"


def place_dhan_order(payload):
    headers = {
        "Content-Type": "application/json",
        "access-token": DHAN_ACCESS_TOKEN
    }
    print("➡️ CALLING DHAN API WITH PAYLOAD:")
    print(payload)

    resp = requests.post(DHAN_ORDERS_URL, json=payload, headers=headers)
    print("⬅️ DHAN RESPONSE:", resp.status_code, resp.text)
    return resp.status_code, resp.text


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    print("🚨 Alert mila:", data)

    if data.get("ping") == "keep_alive":
        return jsonify({"status": "alive"})

    side        = data["action"]
    security_id = data["securityId"]
    exch        = data["exchangeSegment"]
    product     = data["productType"]
    qty         = int(data["qty"])
    entry       = float(data["entry"])
    sl          = float(data["slPrice"])
    target      = float(data.get("targetPrice", 0))

    cid = str(uuid.uuid4())

    # ===== ENTRY ORDER =====
    entry_payload = {
        "dhanClientId":      DHAN_CLIENT_ID,
        "correlationId":     cid + "-ENTRY",
        "transactionType":   side,
        "exchangeSegment":   exch,
        "productType":       product,
        "orderType":         "LIMIT",
        "validity":          "DAY",
        "securityId":        security_id,
        "quantity":          qty,
        "disclosedQuantity": 0,
        "price":             entry,
        "triggerPrice":      0,
        "afterMarketOrder":  False,
        "amoTime": ""
    }
    place_dhan_order(entry_payload)

    # ===== SL-M ORDER =====
    sl_side = "SELL" if side == "BUY" else "BUY"

    sl_payload = {
        "dhanClientId":      DHAN_CLIENT_ID,
        "correlationId":     cid + "-SL",
        "transactionType":   sl_side,
        "exchangeSegment":   exch,
        "productType":       product,
        "orderType":         "STOP_LOSS_MARKET",
        "validity":          "DAY",
        "securityId":        security_id,
        "quantity":          qty,
        "disclosedQuantity": 0,
        "price":             0,
        "triggerPrice":      sl,
        "afterMarketOrder":  False,
        "amoTime": ""
    }
    place_dhan_order(sl_payload)

    # ===== OPTIONAL TARGET =====
    if target > 0:
        tgt_side = "SELL" if side == "BUY" else "BUY"
        tgt_payload = {
            "dhanClientId":      DHAN_CLIENT_ID,
            "correlationId":     cid + "-TARGET",
            "transactionType":   tgt_side,
            "exchangeSegment":   exch,
            "productType":       product,
            "orderType":         "LIMIT",
            "validity":          "DAY",
            "securityId":        security_id,
            "quantity":          qty,
            "disclosedQuantity": 0,
            "price":             target,
            "triggerPrice":      0,
            "afterMarketOrder":  False,
            "amoTime": ""
        }
        place_dhan_order(tgt_payload)

    return jsonify({"status": "OK"})


@app.route("/")
def home():
    return "Webhook server running ✅"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
