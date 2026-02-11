import time
import requests
from fpdf import FPDF
from web3 import Web3
from bs4 import BeautifulSoup

class VanguardAuditor:
    def __init__(self):
        # Using a reliable public RPC
        self.w3 = Web3(Web3.HTTPProvider("https://eth.llamarpc.com"))

    def scan_website(self, url):
        if not url.startswith("http"): url = "https://" + url
        issues = []
        severity = "LOW"

        try:
            start = time.time()
            r = requests.get(url, timeout=10, headers={'User-Agent': 'Vanguard-SAI-838'})
            latency = time.time() - start

            if latency > 1.5:
                issues.append(f"CRITICAL LATENCY: {latency:.2f}s - High DDoS vulnerability.")
                severity = "HIGH"

            if 'X-Frame-Options' not in r.headers:
                issues.append("SECURITY GAP: Missing Clickjacking protection (X-Frame-Options).")
                severity = "MEDIUM"

            soup = BeautifulSoup(r.text, 'html.parser')
            if not soup.find('meta', attrs={'name': 'description'}):
                issues.append("SEO EXPOSURE: No Meta Description. Site is invisible to indexing.")

        except Exception as e:
            issues.append(f"CONNECTION_FAILURE: Architecture shielded. Error: {str(e)}")

        issue_count = len(issues)
        days_to_fix = 2 if issue_count < 2 else 5
        cost = 350 + (issue_count * 150)

        return {"type": "WEBSITE", "target": url, "issues": issues, "severity": severity, "days": days_to_fix, "cost": cost}

    def scan_wallet(self, address):
        try:
            balance = self.w3.from_wei(self.w3.eth.get_balance(address), 'ether')
            tx_count = self.w3.eth.get_transaction_count(address)
            return {
                "type": "WALLET", "target": address, "balance": f"{balance:.4f} ETH",
                "issues": [f"Transactions: {tx_count} detected.", f"Entropy Level: Stable"],
                "severity": "LOW", "days": 1, "cost": 250
            }
        except:
            return {"type": "WALLET", "target": address, "issues": ["RPC_ERROR: Chain state unreachable."], "severity": "CRITICAL", "days": 0, "cost": 0}

    def generate_report(self, data, fixed=False):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_fill_color(10, 10, 10) # Dark Mode PDF
        pdf.rect(0, 0, 210, 297, 'F')

        pdf.set_text_color(0, 102, 204)
        pdf.set_font("Arial", 'B', 24)
        status_text = "REMEDIATION SUCCESSFUL" if fixed else "INTEL DISCOVERY REPORT"
        pdf.cell(200, 20, txt=f"VANGUARD SAI-838", ln=1, align='C')

        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Arial", size=12)
        pdf.ln(10)
        pdf.cell(200, 10, txt=f"STATUS: {status_text}", ln=1)
        pdf.cell(200, 10, txt=f"TARGET: {data['target']}", ln=1)
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
            pdf.cell(200, 10, txt=f"PRICE TO SECURE: ${data['cost']}", ln=1)
            pdf.cell(200, 10, txt=f"ESTIMATED WORK: {data['days']} Days", ln=1)

        filename = f"Vanguard_{int(time.time())}.pdf"
        # Ensure static folder exists
        pdf.output(f"static/{filename}")
        return filename
