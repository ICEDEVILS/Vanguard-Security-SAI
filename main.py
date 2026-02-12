import os
import threading
import asyncio
import psycopg2
import time
from flask import Flask, render_template, request, jsonify
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from auditor import VanguardAuditor
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
auditor = VanguardAuditor()

# --- CONFIGURATION ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_URL = os.getenv("DATABASE_URL")

# Force Python-friendly URL and SSL
if DB_URL and "postgres://" in DB_URL:
    DB_URL = DB_URL.replace("postgres://", "postgresql://", 1)

def get_db():
    # Use sslmode='require' for Supabase
    return psycopg2.connect(DB_URL, sslmode='require', connect_timeout=10)

# --- TELEGRAM BOT LOGIC ---
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🛡 **VANGUARD SAI-838 ONLINE.**\nSYSTEM IS ACTIVE. SEND TARGET.")

async def handle_bot_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = update.message.text.strip()
    wait_msg = await update.message.reply_text("🛰 **VANGUARD: ANALYZING...**")

    try:
        # Run the audit engine
        res = auditor.scan_website(target) if "." in target else auditor.scan_wallet(target)
        pdf_name = auditor.generate_report(res)

        # Sync with Database (War Room)
        db_status = "Sync Error"
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("INSERT INTO vanguard_jobs (target, cost, status, pdf) VALUES (%s, %s, %s, %s)",
                        (target, res['cost'], 'PENDING', pdf_name))
            conn.commit()
            cur.close(); conn.close()
            db_status = "Intel Synced."
        except Exception as e:
            print(f"DB Sync Fail: {e}")

        await update.message.reply_document(
            document=open(f"static/{pdf_name}", 'rb'), 
            caption=f"✅ **INTEL CAPTURED**\nExposure: ${res['cost']}\nDB Status: {db_status}"
        )
        await wait_msg.delete()
    except Exception as e:
        await update.message.reply_text(f"⚠️ SYSTEM ERROR: {str(e)}")

# --- THE BOT THREAD (Fixed for PTB v20+) ---
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
            print("🤖 VANGUARD BOT POLLING STARTED...")
            while True:
                await asyncio.sleep(1)

    loop.run_until_complete(start_bot())

# --- DASHBOARD ROUTES ---
@app.route('/')
def index():
    try:
        conn = get_db()
        cur = conn.cursor()
        # Initialize the War Room Table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS vanguard_jobs (
                id SERIAL PRIMARY KEY,
                target TEXT,
                cost INT,
                status TEXT,
                pdf TEXT
            )
        """)
        conn.commit()
        cur.execute("SELECT * FROM vanguard_jobs ORDER BY id DESC")
        jobs = cur.fetchall()
        cur.close(); conn.close()
        return render_template('index.html', jobs=jobs)
    except Exception as e:
        return f"<div style='background:black;color:red;padding:20px;font-family:monospace;'><h1>DB_CONNECTION_ERROR</h1><p>{str(e)}</p></div>"

@app.route('/api/audit', methods=['POST'])
def api_audit():
    target = request.json.get('target')
    res = auditor.scan_website(target) if "." in target else auditor.scan_wallet(target)
    pdf = auditor.generate_report(res)
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

# --- SYSTEM INITIALIZER ---
if __name__ == "__main__":
    if not os.path.exists('static'): os.makedirs('static')

    # 1. Start Bot Intelligence in Background
    threading.Thread(target=run_bot_worker, daemon=True).start()

    # 2. Start Web Terminal
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
