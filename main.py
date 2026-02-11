import os
import threading
import asyncio
import psycopg2
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
DB_URL = os.getenv("DATABASE_URL").replace("postgres://", "postgresql://", 1)

def get_db():
    return psycopg2.connect(DB_URL, sslmode='require')

# --- BOT LOGIC ---
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🛡 **VANGUARD SAI-838 ONLINE.**\nReady for target acquisition.")

async def handle_bot_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = update.message.text.strip()
    await update.message.reply_text(f"🛰 **ANALYZING: {target}**")

    # Run scan
    res = auditor.scan_website(target) if "." in target else auditor.scan_wallet(target)
    pdf = auditor.generate_report(res)

    # Log to Database
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO vanguard_jobs (target, cost, status, pdf) VALUES (%s, %s, %s, %s)",
                (target, res['cost'], 'PENDING', pdf))
    conn.commit()
    cur.close()
    conn.close()

    await update.message.reply_document(document=open(f"static/{pdf}", 'rb'), caption=f"✅ **INTEL CAPTURED**\nCost to fix: ${res['cost']}")

def run_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    bot = Application.builder().token(BOT_TOKEN).build()
    bot.add_handler(CommandHandler("start", start_cmd))
    bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_bot_msg))
    bot.run_polling(drop_pending_updates=True)

# --- DASHBOARD ROUTES ---
@app.route('/')
def index():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS vanguard_jobs (id SERIAL PRIMARY KEY, target TEXT, cost INT, status TEXT, pdf TEXT)")
    conn.commit()
    cur.execute("SELECT * FROM vanguard_jobs ORDER BY id DESC")
    jobs = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('index.html', jobs=jobs)

@app.route('/api/audit', methods=['POST'])
def api_audit():
    target = request.json.get('target')
    res = auditor.scan_website(target) if "." in target else auditor.scan_wallet(target)
    pdf = auditor.generate_report(res)
    return jsonify({"status": "FOUND", "cost": res['cost'], "pdf": pdf})

@app.route('/api/fix', methods=['POST'])
def api_fix():
    target = request.json.get('target')
    # Simulation: In a real world, you'd run script to patch
    res = auditor.scan_website(target) if "." in target else auditor.scan_wallet(target)
    new_pdf = auditor.generate_report(res, fixed=True)

    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE vanguard_jobs SET status='FIXED', pdf=%s WHERE target=%s", (new_pdf, target))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"status": "FIXED", "pdf": new_pdf})

if __name__ == "__main__":
    if not os.path.exists('static'): os.makedirs('static')
    threading.Thread(target=run_bot, daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
