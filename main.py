import os
import threading
import asyncio
import psycopg2
import time
import requests
from flask import Flask, render_template, request, jsonify
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from auditor import VanguardAuditor
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
auditor = VanguardAuditor()

# --- SYSTEM CONFIG ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_URL = os.getenv("DATABASE_URL")
if DB_URL and "postgres://" in DB_URL:
    DB_URL = DB_URL.replace("postgres://", "postgresql://", 1)

# CENTRAL BRAIN CONFIG
ICEGODS_HUB_URL = "https://icegods-db-service.onrender.com/api/ingest"
ICEGODS_KEY = "ICE-GODS-VANGUARD-838-GOLD"

def get_db():
    return psycopg2.connect(DB_URL, sslmode='require', connect_timeout=10)

def sync_to_icegods_hub(target, cost, severity):
    """ Uplinks intercepted intel to the Central IceGods Brain. """
    payload = {
        "bot_name": "VANGUARD-SAI-838",
        "target": target,
        "intel_data": {
            "cost": cost,
            "severity": severity
        }
    }
    headers = {
        "X-ICEGODS-KEY": ICEGODS_KEY,
        "Content-Type": "application/json"
    }
    try:
        requests.post(ICEGODS_HUB_URL, json=payload, headers=headers, timeout=5)
        print(f"📡 NEURAL SYNC COMPLETE: {target}")
    except Exception as e:
        print(f"⚠️ NEURAL SYNC FAILED: {e}")

# --- TELEGRAM BOT LOGIC ---
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🛡 **VANGUARD SAI-838: ONLINE**\nWAR-ROOM LINKED. SEND TARGET URL OR WALLET.")

async def handle_bot_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = update.message.text.strip()
    wait_msg = await update.message.reply_text("🛰 **VANGUARD: ANALYZING ARCHITECTURE...**")
    
    try:
        # 1. Perform deep scan
        res = auditor.scan_website(target) if "." in target else auditor.scan_wallet(target)
        
        # 2. TRIGGER NEURAL LINK TO CENTRAL BRAIN
        sync_to_icegods_hub(target, res['cost'], res['severity'])
        
        # 3. Generate Report
        pdf_name = auditor.generate_report(res)
        
        # 4. Log to Supabase (Local War Room)
        db_sync = "OFFLINE"
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("INSERT INTO vanguard_jobs (target, cost, status, pdf) VALUES (%s, %s, %s, %s)",
                        (target, res['cost'], 'PENDING', pdf_name))
            conn.commit()
            cur.close(); conn.close()
            db_sync = "ONLINE"
        except Exception as e:
            print(f"Local DB Error: {e}")

        await update.message.reply_document(
            document=open(f"static/{pdf_name}", 'rb'), 
            caption=f"✅ **INTEL CAPTURED**\nExposure: ${res['cost']}\nWar-Room Sync: {db_sync}"
        )
        await wait_msg.delete()
    except Exception as e:
        await update.message.reply_text(f"⚠️ SCAN ERROR: {str(e)}")

# --- ASYNC BOT THREAD (The Render Fix) ---
def run_bot_worker():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    async def start_bot():
        application = ApplicationBuilder().token(BOT_TOKEN).build()
        application.add_handler(CommandHandler("start", start_cmd))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_bot_msg))
        async with application:
            await application.initialize()
            await application.start()
            await application.updater.start_polling(drop_pending_updates=True)
            print("🤖 VANGUARD BOT: POLLING ACTIVE")
            while True: await asyncio.sleep(1)
    loop.run_until_complete(start_bot())

# --- DASHBOARD ROUTES ---
@app.route('/')
def index():
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS vanguard_jobs (id SERIAL PRIMARY KEY, target TEXT, cost INT, status TEXT, pdf TEXT)")
        conn.commit()
        cur.execute("SELECT * FROM vanguard_jobs ORDER BY id DESC")
        jobs = cur.fetchall()
        cur.close(); conn.close()
        return render_template('index.html', jobs=jobs)
    except Exception as e:
        return f"<body style='background:black;color:red;padding:20px;font-family:monospace;'><h1>DB_CONNECTION_FAILURE</h1><p>{str(e)}</p></body>"

@app.route('/api/audit', methods=['POST'])
def api_audit():
    target = request.json.get('target')
    res = auditor.scan_website(target) if "." in target else auditor.scan_wallet(target)
    pdf = auditor.generate_report(res)
    sync_to_icegods_hub(target, res['cost'], res['severity'])
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("INSERT INTO vanguard_jobs (target, cost, status, pdf) VALUES (%s, %s, %s, %s)",
                    (target, res['cost'], 'PENDING', pdf))
        conn.commit()
        cur.close(); conn.close()
    except: pass
    return jsonify({"status": "FOUND", "cost": res['cost'], "pdf": pdf})

@app.route('/api/fix', methods=['POST'])
def api_fix():
    target = request.json.get('target')
    res = auditor.scan_website(target) if "." in target else auditor.scan_wallet(target)
    new_pdf = auditor.generate_report(res, fixed=True)
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("UPDATE vanguard_jobs SET status='FIXED', pdf=%s WHERE target=%s", (new_pdf, target))
        conn.commit()
        cur.close(); conn.close()
    except: pass
    return jsonify({"status": "FIXED", "pdf": new_pdf})

if __name__ == "__main__":
    if not os.path.exists('static'): os.makedirs('static')
    threading.Thread(target=run_bot_worker, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)