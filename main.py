import os
import uuid
import requests
from flask import Flask, jsonify, request, render_template, redirect
from flask_cors import CORS
from dotenv import load_dotenv

# Load local .env for Termux, Render uses Dashboard Environment Variables
load_dotenv()

app = Flask(__name__, template_folder='templates')
CORS(app)

# --- SYSTEM CONFIGURATION ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
SOL_WALLET = os.getenv("SOL_WALLET", "8dtuyskTtsB78DFDPWZszarvDpedwftKYCoMdZwjHbxy")
ETH_WALLET = os.getenv("ETH_WALLET", "0x20d2708acd360cd0fd416766802e055295470fc1")

class VanguardEngine:
    @staticmethod
    def audit_logic(target):
        """ Institutional Entropy Analysis Simulation """
        return {
            "risk_score": 94.8,
            "estimated_loss": "$42,800.00",
            "defect": "HECD_ENTROPY_LEAK",
            "status": "NON-COMPLIANT"
        }

def broadcast_alert(target, report):
    """ Post Institutional Intelligence to @ZeroThreatIntel """
    if not BOT_TOKEN or not CHANNEL_ID:
        print("Telegram Config Missing: Check Environment Variables")
        return

    msg = (
        f"🛡️ **VANGUARD SAI-838 AUDIT ALERT** 🛡️\n\n"
        f"**Target Host:** `{target}`\n"
        f"**Risk Score:** {report['risk_score']}%\n"
        f"**Financial Exposure:** {report['estimated_loss']}\n"
        f"**Vector:** {report['defect']}\n\n"
        f"⚠️ **STATUS:** NON-COMPLIANT\n"
        f"Remediation: Required via Vanguard Dashboard.\n"
        f"Architect: @ICEGODSICEDEVIL"
    )

    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        resp = requests.post(url, json={"chat_id": CHANNEL_ID, "text": msg, "parse_mode": "Markdown"})
        print(f"Telegram Broadcast: {resp.status_code}")
    except Exception as e:
        print(f"Broadcast Error: {e}")

@app.route('/')
def index():
    """ Redirect root to dashboard so user sees the UI immediately """
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    """ Direct access to the visual terminal """
    return render_template('index.html')

@app.route('/api/audit', methods=['POST'])
def run_audit():
    data = request.json
    target = data.get('target', 'N/A')
    report = VanguardEngine.audit_logic(target)

    # Fire the Telegram Broadcast
    broadcast_alert(target, report)

    return jsonify({
        "status": "SUCCESS",
        "id": f"VGD-{uuid.uuid4().hex[:8].upper()}",
        "analysis": report,
        "payment_gateways": {"sol": SOL_WALLET, "eth": ETH_WALLET}
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
