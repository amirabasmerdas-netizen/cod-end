import os
import sqlite3
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ========= تنظیمات =========
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")

ADMINS = [601668306, 8588773170]
PORT = int(os.environ.get("PORT", 10000))
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = os.environ.get("RENDER_EXTERNAL_URL")

# ========= دیتابیس =========
db = sqlite3.connect("db.sqlite", check_same_thread=False)
cur = db.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS settings (
    id INTEGER PRIMARY KEY,
    source INTEGER,
    target INTEGER,
    active INTEGER
)
""")
db.commit()

def is_admin(uid: int) -> bool:
    return uid in ADMINS

def get_settings():
    cur.execute("SELECT source, target, active FROM settings WHERE id=1")
    row = cur.fetchone()
    return row if row else (None, None, 0)

def save_settings(source=None, target=None, active=None):
    s, t, a = get_settings()
    cur.execute(
        "INSERT OR REPLACE INTO settings (id, source, target, active) VALUES (1, ?, ?, ?)",
        (
            source if source is not None else s,
            target if target is not None else t,
            active if active is not None else a,
        ),
    )
    db.commit()

# ========= اپلیکیشن =========
app = Application.builder().token(TOKEN).build()

# ========= /start =========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ دسترسی نداری")
        return

    keyboard = [
        [
            InlineKeyboardButton("📥 تنظیم گروه", callback_data="set_group"),
            InlineKeyboardButton("📤 تنظیم چنل", callback_data="set_channel"),
        ],
        [
            InlineKeyboardButton("▶️ شروع فورواد", callback_data="start_fw"),
            InlineKeyboardButton("⏹ توقف فورواد", callback_data="stop_fw"),
        ],
    ]

    await update.message.reply_text(
        "🎛 پنل مدیریت ربات",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

# ========= دکمه‌ها =========
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    if query.data == "set_group":
        context.user_data["mode"] = "set_group"
        await query.edit_message_text("📥 یوزرنیم گروه را ارسال کن (@group)")

    elif query.data == "set_channel":
        context.user_data["mode"] = "set_channel"
        await query.edit_message_text("📤 یوزرنیم چنل را ارسال کن (@channel)")

    elif query.data == "start_fw":
        save_settings(active=1)
        await query.edit_message_text("✅ فورواد فعال شد")

    elif query.data == "stop_fw":
        save_settings(active=0)
        await query.edit_message_text("⛔ فورواد متوقف شد")

# ========= گرفتن یوزرنیم =========
async def capture_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if update.message.chat.type != "private":
        return

    mode = context.user_data.get("mode")
    if not mode:
        return

    text = update.message.text.strip()
    if not text.startswith("@"):
        await update.message.reply_text("❌ باید با @ شروع شود")
        return

    try:
        chat = await context.bot.get_chat(text)
    except:
        await update.message.reply_text("❌ پیدا نشد یا دسترسی ندارم")
        return

    if mode == "set_group" and chat.type in ["group", "supergroup"]:
        save_settings(source=chat.id)
        context.user_data["mode"] = None
        await update.message.reply_text(f"✅ گروه «{chat.title}» ثبت شد")

    elif mode == "set_channel" and chat.type == "channel":
        save_settings(target=chat.id)
        context.user_data["mode"] = None
        await update.message.reply_text(f"✅ چنل «{chat.title}» ثبت شد")

    else:
        await update.message.reply_text("❌ نوع چت اشتباه است")

# ========= فورواد سریع =========
async def forward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    source, target, active = get_settings()

    if not active or not update.message:
        return

    if update.message.chat_id != source:
        return

    try:
        await update.message.forward(chat_id=target)
    except Exception as e:
        print("Forward error:", e)

# ========= هندلرها =========
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(buttons))
app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, capture_username))
app.add_handler(MessageHandler(filters.ALL & filters.ChatType.GROUPS, forward))

# ========= Flask برای Webhook =========
flask_app = Flask(__name__)

@flask_app.post(WEBHOOK_PATH)
async def webhook():
    update = Update.de_json(request.json, app.bot)
    await app.process_update(update)
    return "OK"

# ========= اجرای Render =========
if __name__ == "__main__":
    app.bot.set_webhook(f"{WEBHOOK_URL}{WEBHOOK_PATH}")
    flask_app.run(host="0.0.0.0", port=PORT)
