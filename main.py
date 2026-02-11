import os
import threading
import asyncio
import psycopg2
import time
from flask import Flask, render_template, request, jsonify
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from auditor import VanguardAuditor
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
auditor = VanguardAuditor()

# Config
BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_URL = os.getenv("DATABASE_URL")

# Fix for Render/Supabase URL format
if DB_URL and "postgres://" in DB_URL:
    DB_URL = DB_URL.replace("postgres://", "postgresql://", 1)

def get_db():
    # Supabase REQUIRES sslmode=require
    return psycopg2.connect(DB_URL, sslmode='require', connect_timeout=10)

# --- BOT LOGIC ---
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🛡 **VANGUARD SAI-838 ONLINE.**\nTARGETING SYSTEM ENABLED. SEND URL OR WALLET.")

async def handle_bot_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = update.message.text.strip()
    wait_msg = await update.message.reply_text("🛰 **VANGUARD: SCANNING ARCHITECTURE...**")

    try:
        # Run scan
        res = auditor.scan_website(target) if "." in target else auditor.scan_wallet(target)
        pdf = auditor.generate_report(res)

        # Log to Database
        db_log_status = "Unlogged"
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("INSERT INTO vanguard_jobs (target, cost, status, pdf) VALUES (%s, %s, %s, %s)",
                        (target, res['cost'], 'PENDING', pdf))
            conn.commit()
            cur.close()
            conn.close()
            db_log_status = "Logged to War Room."
        except Exception as e:
            print(f"DB Log Fail: {e}")
            db_log_status = "Captured (DB Sync Pending)"

        await update.message.reply_document(
            document=open(f"static/{pdf}", 'rb'), 
            caption=f"✅ **INTEL CAPTURED**\nCost: ${res['cost']}\nStatus: {db_log_status}"
        )
    except Exception as e:
        await update.message.reply_text(f"⚠️ SYSTEM ERROR: {str(e)}")

def run_bot():
    if not BOT_TOKEN: return
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        bot = Application.builder().token(BOT_TOKEN).build()
        bot.add_handler(CommandHandler("start", start_cmd))
        bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_bot_msg))
        print("🤖 BOT POLLING...")
        bot.run_polling(drop_pending_updates=True, close_loop=False)
    except Exception as e:
        print(f"BOT ERROR: {e}")

# --- DASHBOARD ROUTES ---
@app.route('/')
def index():
    try:
        conn = get_db()
        cur = conn.cursor()
        # Initialize table if needed
        cur.execute("CREATE TABLE IF NOT EXISTS vanguard_jobs (id SERIAL PRIMARY KEY, target TEXT, cost INT, status TEXT, pdf TEXT)")
        conn.commit()
        cur.execute("SELECT * FROM vanguard_jobs ORDER BY id DESC")
        jobs = cur.fetchall()
        cur.close()
        conn.close()
        return render_template('index.html', jobs=jobs)
    except Exception as e:
        return f"<div style='background:black;color:red;padding:20px;font-family:monospace;'><h1>DATABASE_CONNECTION_ERROR</h1><p>{str(e)}</p></div>"

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
    threading.Thread(target=run_bot, daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
