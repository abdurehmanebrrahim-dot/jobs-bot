import json, os, threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import ReplyKeyboardMarkup
from telegram.ext import (Application, CommandHandler,
                          MessageHandler, filters)

TOKEN = os.environ["TOKEN"]
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
TZ = timezone(timedelta(hours=3))

class Ping(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")
    def log_message(self, *a):
        pass

def run_web():
    port = int(os.environ.get("PORT", 10000))
    HTTPServer(("0.0.0.0", port), Ping).serve_forever()

threading.Thread(target=run_web, daemon=True).start()

JOBS_FILE, SUBS_FILE, USERS_FILE = "jobs.json", "subs.json", "users.json"

def load(p, d):
    if os.path.exists(p):
        try:
            with open(p) as f:
                return json.load(f)
        except Exception:
            pass
    return d

def save(p, data):
    with open(p, "w") as f:
        json.dump(data, f)

def register(u):
    users = load(USERS_FILE, {})
    if str(u.id) not in users:
        users[str(u.id)] = {"name": u.full_name, "username": u.username or ""}
        save(USERS_FILE, users)

def job_text(j):
    return (f"💼 {j['title']}\n🏢 {j['company']}\n"
            f"📍 {j['place']}\n🔗 {j['link']}\n📅 {j['date']}")

async def start(update, context):
    register(update.effective_user)
    kb = [["💼 ስራዎች", "🔔 ማሳወቂያ"], ["ዕርዳታ"]]
    await update.message.reply_text(
        "ሰላም! እዚህ አዳዲስ የስራ ማስታወቂያዎችን ያገኛሉ።",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))

async def jobs(update, context):
    items = load(JOBS_FILE, [])[-5:][::-1]
    if not items:
        await update.message.reply_text("እስካሁን ስራ አልተለጠፈም።")
        return
    for j in items:
        await update.message.reply_text(job_text(j))

async def alert(update, context):
    subs = load(SUBS_FILE, [])
    cid = update.effective_chat.id
    if cid in subs:
        subs.remove(cid)
        msg = "🔕 ማሳወቂያ ተቋርጧል።"
    else:
        subs.append(cid)
        msg = "🔔 ተመዝግበዋል! አዲስ ስራ ሲመጣ ይላክልዎታል።"
    save(SUBS_FILE, subs)
    await update.message.reply_text(msg)

async def help_cmd(update, context):
    await update.message.reply_text(
        "💼 ስራዎች — የቅርብ ጊዜ 5 ስራዎች\n"
        "🔔 ማሳወቂያ — አዲስ ስራ ሲመጣ መልእክት (ለመመዝገብ/ለማቋረጥ)")

async def post(update, context):
    if update.effective_user.id != ADMIN_ID:
        return
    raw = update.message.text.partition(" ")[2]
    parts = [p.strip() for p in raw.split("|")]
    if len(parts) != 4:
        await update.message.reply_text(
            "ቅርጸት:\n/post ርዕስ | ድርጅት | ቦታ | ሊንክ")
        return
    j = {"title": parts[0], "company": parts[1], "place": parts[2],
         "link": parts[3],
         "date": datetime.now(TZ).strftime("%Y-%m-%d")}
    all_jobs = load(JOBS_FILE, [])
    all_jobs.append(j)
    save(JOBS_FILE, all_jobs)
    sent = 0
    for cid in load(SUBS_FILE, []):
        try:
            await context.bot.send_message(cid, "🆕 አዲስ ስራ\n\n" + job_text(j))
            sent += 1
        except Exception as e:
            print("send error:", e)
    await update.message.reply_text(f"✅ ተለጥፏል። ለ{sent} ሰው ተልኳል።")

async def users_cmd(update, context):
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_text(
        f"👥 ተጠቃሚዎች: {len(load(USERS_FILE, {}))}\n"
        f"🔔 የተመዘገቡ: {len(load(SUBS_FILE, []))}\n"
        f"💼 ስራዎች: {len(load(JOBS_FILE, []))}")

async def echo(update, context):
    register(update.effective_user)
    acts = {"💼 ስራዎች": jobs, "🔔 ማሳወቂያ": alert, "ዕርዳታ": help_cmd}
    fn = acts.get(update.message.text)
    if fn:
        await fn(update, context)
    else:
        await update.message.reply_text("ከታች ያሉትን አዝራሮች ይጠቀሙ ወይም /start ይጫኑ።")

app = Application.builder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("post", post))
app.add_handler(CommandHandler("users", users_cmd))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
print("Bot started")
app.run_polling()
