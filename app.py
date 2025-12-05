from flask import Flask, request, jsonify
import requests, uuid

app = Flask(__name__)

DHAN_ACCESS_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJpc3MiOiJkaGFuIiwicGFydG5lcklkIjoiIiwiZXhwIjoxNzY0OTY4MDg2LCJpYXQiOjE3NjQ4ODE2ODYsInRva2VuQ29uc3VtZXJUeXBlIjoiU0VMRiIsIndlYmhvb2tVcmwiOiIiLCJkaGFuQ2xpZW50SWQiOiIxMTA3MDkwNTkyIn0.Z5HOjIt5UXpuJrGSenivv60TO6h5bW5cuKHYU_q00fgHjsl2GBO59s7jxHE8mta7LH19f3YPaNJIehL6wtmf2A"
DHAN_CLIENT_ID    = "1107090592"

URL = "https://api.dhan.co/v2/orders"

HEADERS = {
    "Content-Type": "application/json",
    "access-token": DHAN_ACCESS_TOKEN
}

def place_order(payload):
    print("➡️ DHAN PAYLOAD:", payload)
    r = requests.post(URL, json=payload, headers=HEADERS)
    print("⬅️ DHAN RESPONSE:", r.status_code, r.text)
    return r.text

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    print("🚨 ALERT RECEIVED:", data)

    cid = str(uuid.uuid4())

    side   = data["action"]
    secid  = data["securityId"]
    qty    = int(data["qty"])
    entry  = float(data["entry"])
    sl     = float(data["slPrice"])

    # ✅ ENTRY
    entry_payload = {
        "dhanClientId": DHAN_CLIENT_ID,
        "correlationId": cid,
        "securityId": secid,
        "exchangeSegment": "NSE",
        "transactionType": side,
        "quantity": qty,
        "orderType": "LIMIT",
        "productType": "INTRA",
        "price": entry,
        "afterMarketOrder": False
    }

    place_order(entry_payload)

    # ✅ SL-M
    sl_payload = {
        "dhanClientId": DHAN_CLIENT_ID,
        "correlationId": cid + "-SL",
        "securityId": secid,
        "exchangeSegment": "NSE",
        "transactionType": "SELL" if side == "BUY" else "BUY",
        "quantity": qty,
        "orderType": "STOP_LOSS_MARKET",
        "productType": "INTRA",
        "triggerPrice": sl,
        "afterMarketOrder": False
    }

    place_order(sl_payload)

    return jsonify({"status": "OK"})

@app.route("/")
def home():
    return "✅ Dhan webhook live"
