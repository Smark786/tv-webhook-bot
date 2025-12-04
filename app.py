from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(force=True, silent=True)
    print("🚨 Alert mila:", data)
    return jsonify({"status": "ok", "received": data})

@app.route("/", methods=["GET"])
def home():
    return "Webhook server running ✅"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
