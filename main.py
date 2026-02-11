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

# Config
BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_URL = os.getenv("DATABASE_URL")

if DB_URL and "postgres://" in DB_URL:
    DB_URL = DB_URL.replace("postgres://", "postgresql://", 1)

def get_db():
    # Force SSL and set a timeout
    return psycopg2.connect(DB_URL, sslmode='require', connect_timeout=10)

# --- BOT LOGIC ---
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🛡 **VANGUARD SAI-838 ONLINE.**\nSYSTEM IS ACTIVE. SEND TARGET.")

async def handle_bot_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = update.message.text.strip()
    wait_msg = await update.message.reply_text("🛰 **ANALYZING ARCHITECTURE...**")

    try:
        res = auditor.scan_website(target) if "." in target else auditor.scan_wallet(target)
        pdf = auditor.generate_report(res)

        # Log to Database
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("INSERT INTO vanguard_jobs (target, cost, status, pdf) VALUES (%s, %s, %s, %s)",
                        (target, res['cost'], 'PENDING', pdf))
            conn.commit()
            cur.close()
            conn.close()
            log_status = "Sync: OK"
        except:
            log_status = "Sync: Offline"

        await update.message.reply_document(
            document=open(f"static/{pdf}", 'rb'), 
            caption=f"✅ **INTEL CAPTURED**\nCost: ${res['cost']}\n{log_status}"
        )
    except Exception as e:
        await update.message.reply_text(f"⚠️ ERROR: {str(e)}")

# --- THE FIX FOR THE BOT THREAD ---
def run_bot_worker():
    """Handles the bot event loop correctly for PTB v20+"""
    async def main_bot():
        builder = ApplicationBuilder().token(BOT_TOKEN).build()
        builder.add_handler(CommandHandler("start", start_cmd))
        builder.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_bot_msg))

        async with builder:
            await builder.initialize()
            await builder.start()
            await builder.updater.start_polling(drop_pending_updates=True)
            print("🤖 VANGUARD BOT IS POLLING...")
            # Keep running until the thread is killed
            while True:
                await asyncio.sleep(3600)

    asyncio.run(main_bot())

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
        cur.close()
        conn.close()
        return render_template('index.html', jobs=jobs)
    except Exception as e:
        return f"<body style='background:black;color:red;'><h1>DB_ERROR</h1><p>{str(e)}</p></body>"

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
        cur.close()
        conn.close()
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
        cur.close()
        conn.close()
    except: pass
    return jsonify({"status": "FIXED", "pdf": new_pdf})

if __name__ == "__main__":
    if not os.path.exists('static'): os.makedirs('static')
    # Start bot in a background thread
    threading.Thread(target=run_bot_worker, daemon=True).start()

    # Start Flask
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
