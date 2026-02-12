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

BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_URL = os.getenv("DATABASE_URL")
if DB_URL and "postgres://" in DB_URL:
    DB_URL = DB_URL.replace("postgres://", "postgresql://", 1)

def get_db():
    return psycopg2.connect(DB_URL, sslmode='require', connect_timeout=10)

# --- BOT HANDLERS ---
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🛡 **VANGUARD SAI-838 ONLINE.**\nSYSTEM IS ACTIVE. SEND TARGET.")

async def handle_bot_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = update.message.text.strip()
    wait_msg = await update.message.reply_text("🛰 **ANALYZING...**")
    try:
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

        await update.message.reply_document(document=open(f"static/{pdf}", 'rb'), caption=f"✅ **INTEL CAPTURED**")
    except Exception as e:
        await update.message.reply_text(f"⚠️ ERROR: {str(e)}")

# --- THE FIX: CLEAN ASYNC STARTUP ---
def run_bot_worker():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def start_bot():
        # Build application
        application = ApplicationBuilder().token(BOT_TOKEN).build()

        # Add Handlers
        application.add_handler(CommandHandler("start", start_cmd))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_bot_msg))

        # PROPER STARTUP FOR V20+
        await application.initialize()
        await application.start()
        await application.updater.start_polling(drop_pending_updates=True)
        print("🤖 VANGUARD BOT IS POLLING...")

        # Keep it running
        while True:
            await asyncio.sleep(1)

    loop.run_until_complete(start_bot())

# --- WEB ROUTES ---
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
        return f"<h1>DB_ERROR</h1><p>{str(e)}</p>"

# ... (Keep /api/audit and /api/fix routes as they were) ...

if __name__ == "__main__":
    if not os.path.exists('static'): os.makedirs('static')
    # Use threading to start the async bot
    threading.Thread(target=run_bot_worker, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
