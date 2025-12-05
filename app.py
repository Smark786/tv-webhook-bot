from flask import Flask, request, jsonify
from dhanhq import DhanContext, dhanhq
import uuid

app = Flask(__name__)

# =============== DHAN SETUP ===============

DHAN_CLIENT_ID    = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJpc3MiOiJkaGFuIiwicGFydG5lcklkIjoiIiwiZXhwIjoxNzY0OTY4MDg2LCJpYXQiOjE3NjQ4ODE2ODYsInRva2VuQ29uc3VtZXJUeXBlIjoiU0VMRiIsIndlYmhvb2tVcmwiOiIiLCJkaGFuQ2xpZW50SWQiOiIxMTA3MDkwNTkyIn0.Z5HOjIt5UXpuJrGSenivv60TO6h5bW5cuKHYU_q00fgHjsl2GBO59s7jxHE8mta7LH19f3YPaNJIehL6wtmf2A"
DHAN_ACCESS_TOKEN = "1107090592"

dhan_context = DhanContext(DHAN_CLIENT_ID, DHAN_ACCESS_TOKEN)
dhan = dhanhq(dhan_context)

# =============== WEBHOOK ===================

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    print("🚨 ALERT:", data)

    try:
        action    = data["action"].upper()      # BUY / SELL
        security  = str(data["securityId"])
        qty       = int(data["qty"])
        entry     = float(data["entry"])
        sl_price  = float(data["slPrice"])

        # ----- productType decide karo -----
        # default: CASH (CNC)
        product_raw = data.get("productType", "CNC").upper()

        if product_raw in ("CNC", "DELIVERY"):
            prod_type = dhan.CNC          # 🚀 CASH / DELIVERY
        elif product_raw in ("INTRA", "INTRADAY"):
            prod_type = dhan.INTRA        # agar tum INTRA bhejo to intraday
        else:
            prod_type = dhan.CNC          # safety: default CNC

        # ---------- ENTRY ORDER (LIMIT) ----------
        print("📌 Placing ENTRY order (CNC by default)")

        entry_resp = dhan.place_order(
            security_id=security,
            exchange_segment=dhan.NSE,                           # Equity cash
            transaction_type=dhan.BUY if action == "BUY" else dhan.SELL,
            quantity=qty,
            order_type=dhan.LIMIT,
            product_type=prod_type,                              # CNC / INTRA
            price=entry
        )

        print("ENTRY RESPONSE:", entry_resp)

        # ---------- SL-M ORDER (STOP LOSS) ----------
        print("📌 Placing SL-M order for stop loss")

        sl_resp = dhan.place_order(
            security_id=security,
            exchange_segment=dhan.NSE,
            transaction_type=dhan.SELL if action == "BUY" else dhan.BUY,
            quantity=qty,
            order_type=dhan.STOP_LOSS_MARKET,
            product_type=prod_type,          # same: CNC position ka SL bhi CNC hi
            trigger_price=sl_price,
            price=0
        )

        print("SL RESPONSE:", sl_resp)

        return jsonify({"status": "OK"})

    except Exception as e:
        print("❌ ERROR:", e)
        return jsonify({"error": str(e)}), 500


@app.route("/")
def home():
    return "✅ Dhan SDK Webhook (CNC default) Running"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
