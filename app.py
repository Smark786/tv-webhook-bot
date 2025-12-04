from flask import Flask, request, jsonify
import requests, uuid, time

# Flask App Initialization
app = Flask(__name__)

# ====================================================================
# ===== DHAN CONFIG (Replace with your actual values) ================
# ====================================================================
DHAN_ACCESS_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJpc3MiOiJkaGFuIiwicGFydG5lcklkIjoiIiwiZXhwIjoxNzY0OTY4MDg2LCJpYXQiOjE3NjQ4ODE2ODYsInRva2VuQ29uc3VtZXJUeXBlIjoiU0VMRiIsIndlYmhvb2tVcmwiOiIiLCJkaGFuQ2xpZW50SWQiOiIxMTA3MDkwNTkyIn0.Z5HOjIt5UXpuJrGSenivv60TO6h5bW5cuKHYU_q00fgHjsl2GBO59s7jxHE8mta7LH19f3YPaNJIehL6wtmf2A"  # <-- Yahan apna token daalo
DHAN_CLIENT_ID    = "1107090592"    # <-- Yahan apna client ID daalo
DHAN_ORDERS_URL   = "https://api.dhan.co/v2/orders"
# ====================================================================

# Common headers for Dhan API calls
DHAN_HEADERS = {
    "Content-Type": "application/json",
    "access-token": DHAN_ACCESS_TOKEN
}

def place_dhan_order(payload):
    """Dhan API par order place karta hai aur response print karta hai."""
    print(f"\n[{time.strftime('%H:%M:%S')}] ➡️ CALLING DHAN API WITH PAYLOAD:")
    print(payload)

    # API Call
    try:
        resp = requests.post(DHAN_ORDERS_URL, json=payload, headers=DHAN_HEADERS, timeout=10)
        
        # Check for non-200 status codes
        if resp.status_code != 200:
            print(f"[{time.strftime('%H:%M:%S')}] ❌ DHAN RESPONSE ERROR ({resp.status_code}): {resp.text}")
        else:
            print(f"[{time.strftime('%H:%M:%S')}] ✅ DHAN RESPONSE SUCCESS: {resp.text}")
            
        return resp.status_code, resp.text
        
    except requests.exceptions.RequestException as e:
        print(f"[{time.strftime('%H:%M:%S')}] 🚨 REQUEST EXCEPTION: {e}")
        return 500, str(e)


@app.route("/webhook", methods=["POST"])
def webhook():
    """TradingView se alerts receive karne ke liye webhook endpoint."""
    try:
        # Request data ko JSON format mein parse karna
        data = request.get_json(force=True)
        print(f"\n\n[{time.strftime('%H:%M:%S')}] ===============================================")
        print(f"[{time.strftime('%H:%M:%S')}] 🚨 Naya Alert mila:")
        print(data)
        print(f"[{time.strftime('%H:%M:%S')}] ===============================================")

        # Keep-alive check
        if data.get("ping") == "keep_alive":
            print(f"[{time.strftime('%H:%M:%S')}] Keep-alive ping received.")
            return jsonify({"status": "alive"})

        # Required fields check
        required_fields = ["action", "securityId", "exchangeSegment", "productType", "qty", "entry", "slPrice"]
        if not all(field in data for field in required_fields):
            print(f"[{time.strftime('%H:%M:%S')}] ❌ ERROR: Missing required fields in alert payload.")
            return jsonify({"status": "error", "message": "Missing required fields"}), 400


        # Extracting data from the alert
        side        = data["action"].upper() # BUY or SELL
        security_id = data["securityId"]
        exch        = data["exchangeSegment"]
        product     = data["productType"]
        qty         = int(data["qty"])
        entry       = float(data["entry"])
        sl          = float(data["slPrice"])
        target      = float(data.get("targetPrice", 0)) # Target optional hai, 0 agar nahi mila toh

        # Generating a unique correlation ID
        cid = str(uuid.uuid4())

        # ==========================================================
        # 1. ===== ENTRY ORDER (LIMIT Order) ========================
        # ==========================================================
        # LIMIT order ke liye sirf 'price' field ki zaroorat hai. 'triggerPrice' aur 'amoTime' hata diye gaye hain.
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
            "price":             entry, # Required for LIMIT
            "afterMarketOrder":  False,
        }
        place_dhan_order(entry_payload)

        # ==========================================================
        # 2. ===== SL ORDER (STOP_LOSS_MARKET Order) ===============
        # ==========================================================
        sl_side = "SELL" if side == "BUY" else "BUY"
        # STOP_LOSS_MARKET order ke liye sirf 'triggerPrice' ki zaroorat hai. 'price' aur 'amoTime' hata diye gaye hain.

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
            "triggerPrice":      sl, # Required for STOP_LOSS_MARKET
            "afterMarketOrder":  False,
        }
        place_dhan_order(sl_payload)

        # ==========================================================
        # 3. ===== OPTIONAL TARGET ORDER (LIMIT Order) =============
        # ==========================================================
        if target > 0:
            tgt_side = "SELL" if side == "BUY" else "BUY"
            # LIMIT order ke liye sirf 'price' field ki zaroorat hai. 'triggerPrice' aur 'amoTime' hata diye gaye hain.
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
                "price":             target, # Required for LIMIT
                "afterMarketOrder":  False,
            }
            place_dhan_order(tgt_payload)

        return jsonify({"status": "OK", "cid": cid})

    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] 🛑 UNHANDLED EXCEPTION IN WEBHOOK: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/")
def home():
    """Simple health check endpoint."""
    return "Dhan Webhook server running. Waiting for TradingView alerts... ✅"


if __name__ == "__main__":
    # Security ke liye debug=False rakho jab production mein ho
    app.run(host="0.0.0.0", port=8000, debug=True)
