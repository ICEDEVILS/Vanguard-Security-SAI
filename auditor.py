import time
import requests
from fpdf import FPDF
from web3 import Web3
from bs4 import BeautifulSoup

class VanguardAuditor:
    def __init__(self):
        self.w3 = Web3(Web3.HTTPProvider("https://eth.llamarpc.com"))

    def scan_website(self, url):
        if not url.startswith("http"): url = "https://" + url
        issues = []
        severity = "LOW"

        try:
            start = time.time()
            r = requests.get(url, timeout=10)
            latency = time.time() - start

            if latency > 1.5:
                issues.append(f"CRITICAL LATENCY: {latency:.2f}s - Server vulnerable to DDoS/Inbound saturation.")
                severity = "HIGH"

            if 'X-Frame-Options' not in r.headers:
                issues.append("SECURITY GAP: Missing Clickjacking protection (X-Frame-Options).")
                severity = "MEDIUM"

            if 'Content-Security-Policy' not in r.headers:
                issues.append("VULNERABILITY: No CSP defined. Cross-Site Scripting (XSS) risk is HIGH.")
                severity = "CRITICAL"

        except:
            issues.append("CONNECTION_FAILURE: Target architecture hidden or shielded.")

        # Logic for Job Quote
        issue_count = len(issues)
        days_to_fix = 2 if issue_count < 2 else 5
        cost = 350 + (issue_count * 150)

        return {"type": "WEBSITE", "target": url, "issues": issues, "severity": severity, "days": days_to_fix, "cost": cost}

    def scan_wallet(self, address):
        try:
            balance = self.w3.from_wei(self.w3.eth.get_balance(address), 'ether')
            tx_count = self.w3.eth.get_transaction_count(address)
            risk = "HIGH" if tx_count < 5 else "LOW"

            return {
                "type": "WALLET", "target": address, "balance": f"{balance:.4f} ETH",
                "issues": [f"Entropy Check: {tx_count} transactions found.", f"Risk Level: {risk}"],
                "severity": "MEDIUM" if risk == "HIGH" else "LOW",
                "days": 1, "cost": 200
            }
        except:
            return {"type": "WALLET", "target": address, "issues": ["RPC_ERROR: Cannot map chain state."], "severity": "CRITICAL", "days": 0, "cost": 0}

    def generate_report(self, data, fixed=False):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_fill_color(10, 10, 10)
        pdf.rect(0, 0, 210, 297, 'F')
        pdf.set_text_color(0, 102, 204)

        pdf.set_font("Arial", 'B', 24)
        status_text = "REMEDIATION SUCCESSFUL" if fixed else "VULNERABILITY DISCOVERY"
        pdf.cell(200, 20, txt=f"VANGUARD SAI-838: {status_text}", ln=1, align='C')

        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Arial", size=12)
        pdf.ln(10)
        pdf.cell(200, 10, txt=f"TARGET: {data['target']}", ln=1)
        pdf.cell(200, 10, txt=f"TYPE: {data['type']}", ln=1)
        pdf.cell(200, 10, txt=f"TIMESTAMP: {time.ctime()}", ln=1)
        pdf.ln(10)

        pdf.set_text_color(200, 0, 0)
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(200, 10, txt="FINDINGS:", ln=1)
        pdf.set_font("Arial", size=10)
        pdf.set_text_color(255, 255, 255)
        for issue in data['issues']:
            pdf.multi_cell(0, 10, txt=f"> {issue}")

        pdf.ln(10)
        if not fixed:
            pdf.set_text_color(255, 255, 0)
            pdf.cell(200, 10, txt=f"REMEDIATION QUOTE: ${data['cost']}", ln=1)
            pdf.cell(200, 10, txt=f"TIME TO FIX: {data['days']} Days", ln=1)

        filename = f"Vanguard_{int(time.time())}.pdf"
        pdf.output(f"static/{filename}")
        return filename
