from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)
import sqlite3
import os
import logging

# ========= تنظیمات =========
TOKEN = "7918632227:AAGdu_PHP2bJVEZRRt2T6IlWU3B_xokPKzA"
ADMINS = [601668306, 8588773170]  # آیدی عددی ادمین‌ها

# تنظیمات وب‌هوک - برای Render
PORT = int(os.environ.get('PORT', 8443))  # پورت پیش‌فرض Render
WEBHOOK_URL = os.environ.get('WEBHOOK_URL', '')  # در Render تنظیم می‌شود
WEBHOOK_PATH = f"/{TOKEN}"  # مسیر وب‌هوک

# فعال‌سازی لاگ‌گیری
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
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
        ],
        [
            InlineKeyboardButton("📊 وضعیت", callback_data="status")
        ]
    ]

    await update.message.reply_text(
        "🎛 پنل مدیریت ربات\n\n"
        f"📱 حالت: {'🟢 وب‌هوک' if WEBHOOK_URL else '🔵 Polling'}\n"
        f"🌐 پورت: {PORT}",
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
        await query.edit_message_text("⛔ فورواد متوقف شد")
    
    elif query.data == "status":
        source, target, active = get_settings()
        status_text = "📊 وضعیت ربات:\n\n"
        status_text += f"🎯 وضعیت فورواد: {'🟢 فعال' if active else '🔴 غیرفعال'}\n"
        
        if source:
            try:
                chat = await context.bot.get_chat(source)
                status_text += f"📥 گروه: {chat.title}\n"
            except:
                status_text += "📥 گروه: ⚠️ خطا در دریافت\n"
        else:
            status_text += "📥 گروه: ⭕ تنظیم نشده\n"
            
        if target:
            try:
                chat = await context.bot.get_chat(target)
                status_text += f"📤 چنل: {chat.title}\n"
            except:
                status_text += "📤 چنل: ⚠️ خطا در دریافت\n"
        else:
            status_text += "📤 چنل: ⭕ تنظیم نشده\n"
            
        await query.edit_message_text(
            status_text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="back")]])
        )
    
    elif query.data == "back":
        keyboard = [
            [
                InlineKeyboardButton("📥 تنظیم گروه", callback_data="set_group"),
                InlineKeyboardButton("📤 تنظیم چنل", callback_data="set_channel")
            ],
            [
                InlineKeyboardButton("▶️ شروع فورواد", callback_data="start_fw"),
                InlineKeyboardButton("⏹ توقف فورواد", callback_data="stop_fw")
            ],
            [
                InlineKeyboardButton("📊 وضعیت", callback_data="status")
            ]
        ]
        await query.edit_message_text(
            "🎛 پنل مدیریت ربات",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

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
    except:
        await update.message.reply_text("❌ پیدا نشد یا ربات دسترسی ندارد")
        return

    if mode == "set_group":
        if chat.type not in ["group", "supergroup"]:
            await update.message.reply_text("❌ این یوزرنیم گروه نیست")
            return

        save_settings(source=chat.id)
        context.user_data["mode"] = None
        await update.message.reply_text(
            f"✅ گروه «{chat.title}» با موفقیت وصل شد"
        )

    elif mode == "set_channel":
        if chat.type != "channel":
            await update.message.reply_text("❌ این یوزرنیم چنل نیست")
            return

        save_settings(target=chat.id)
        context.user_data["mode"] = None
        await update.message.reply_text(
            f"✅ چنل «{chat.title}» با موفقیت وصل شد"
        )

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
        logger.error(f"Forward error: {e}")

# ========= تابع راه‌اندازی وب‌هوک =========
async def setup_webhook(application):
    if WEBHOOK_URL:
        webhook_url = f"{WEBHOOK_URL}{WEBHOOK_PATH}"
        await application.bot.set_webhook(url=webhook_url)
        logger.info(f"Webhook set to: {webhook_url}")
    else:
        await application.bot.delete_webhook()
        logger.info("Running in polling mode")

# ========= اجرا =========
def main():
    # ساخت اپلیکیشن
    app = ApplicationBuilder().token(TOKEN).build()

    # اضافه کردن handlerها
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, capture_username))
    app.add_handler(MessageHandler(filters.ALL & filters.ChatType.GROUPS, forward))

    # تنظیم وب‌هوک
    if WEBHOOK_URL:
        # حالت وب‌هوک برای Render
        from telegram.ext import Defaults
        
        logger.info("Starting in webhook mode...")
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            webhook_url=WEBHOOK_URL + WEBHOOK_PATH,
            secret_token=TOKEN[:16],  # رمز امنیتی برای وب‌هوک
            drop_pending_updates=True
        )
    else:
        # حالت Polling برای اجرای محلی
        logger.info("Starting in polling mode...")
        app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
