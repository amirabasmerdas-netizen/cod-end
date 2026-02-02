import os
import sqlite3
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# ========= تنظیمات =========
TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    raise ValueError("لطفا متغیر محیطی BOT_TOKEN را ست کنید")

ADMINS = [601668306, 8588773170]

# ========= logging =========
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

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

def is_admin(user_id):
    return user_id in ADMINS

def get_settings():
    cur.execute("SELECT source, target, active FROM settings WHERE id=1")
    row = cur.fetchone()
    return row if row else (None, None, 0)

def save_settings(source=None, target=None, active=None):
    s, t, a = get_settings()
    cur.execute("""
    INSERT OR REPLACE INTO settings (id, source, target, active)
    VALUES (1, ?, ?, ?)
    """, (
        source if source is not None else s,
        target if target is not None else t,
        active if active is not None else a
    ))
    db.commit()

# ========= /start → پنل =========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ دسترسی نداری")
        return

    keyboard = [
        [
            InlineKeyboardButton("📥 تنظیم گروه", callback_data="set_group"),
            InlineKeyboardButton("📤 تنظیم چنل", callback_data="set_channel")
        ],
        [
            InlineKeyboardButton("▶️ شروع فورواد", callback_data="start_fw"),
            InlineKeyboardButton("⏹ توقف فورواد", callback_data="stop_fw")
        ]
    ]

    await update.message.reply_text(
        "🎛 پنل مدیریت ربات",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ========= دکمه‌ها =========
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    if query.data == "set_group":
        context.user_data["mode"] = "set_group"
        await query.edit_message_text("📥 یوزرنیم گروه را ارسال کن (مثال: @mygroup)")

    elif query.data == "set_channel":
        context.user_data["mode"] = "set_channel"
        await query.edit_message_text("📤 یوزرنیم چنل را ارسال کن (مثال: @mychannel)")

    elif query.data == "start_fw":
        save_settings(active=1)
        await query.edit_message_text("✅ فورواد فعال شد")

    elif query.data == "stop_fw":
        save_settings(active=0)
        await query.edit_message_text("⏹ فورواد متوقف شد")

# ========= گرفتن @username (فقط چت خصوصی) =========
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
        await update.message.reply_text("❌ یوزرنیم باید با @ شروع شود")
        return

    try:
        chat = await context.bot.get_chat(text)
    except Exception as e:
        await update.message.reply_text("❌ پیدا نشد یا ربات دسترسی ندارد")
        logger.error("Error getting chat: %s", e)
        return

    if mode == "set_group":
        if chat.type not in ["group", "supergroup"]:
            await update.message.reply_text("❌ این یوزرنیم گروه نیست")
            return

        save_settings(source=chat.id)
        context.user_data["mode"] = None
        await update.message.reply_text(f"✅ گروه «{chat.title}» با موفقیت وصل شد")

    elif mode == "set_channel":
        if chat.type != "channel":
            await update.message.reply_text("❌ این یوزرنیم چنل نیست")
            return

        save_settings(target=chat.id)
        context.user_data["mode"] = None
        await update.message.reply_text(f"✅ چنل «{chat.title}» با موفقیت وصل شد")

# ========= فورواد همه پیام‌ها =========
async def forward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    source, target, active = get_settings()
    if not active or not update.message:
        return
    if update.message.chat_id != source:
        return
    try:
        await update.message.forward(chat_id=target)
    except Exception as e:
        logger.error("Forward error: %s", e)

# ========= راه‌اندازی ربات =========
async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, capture_username))
    app.add_handler(MessageHandler(filters.ALL & filters.ChatType.GROUPS, forward))

    # polling (برای تست محلی راحت)
    await app.run_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
