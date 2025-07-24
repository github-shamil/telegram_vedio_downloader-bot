import asyncio
import os
import threading
import logging
import tempfile
from flask import Flask
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
import yt_dlp

# Enable logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = "7823731827:AAFoCU1etlCutbNiASDOCQMtHRE2qJW9eKE"
COOKIES_PATH = os.path.join(os.path.dirname(__file__), "cookies.txt")
QUALITY_MAP = {}

# =================== Telegram Handlers ===================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *Welcome to the Video Downloader Bot!*\n"
        "🎥 Send a YouTube link and choose quality to download.",
        parse_mode="Markdown"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    logger.info(f"🔹 Received: {url}")

    if "youtube.com" in url or "youtu.be" in url:
        await present_qualities(update, context, url)
    else:
        await update.message.reply_text("❌ Unsupported link.\nCurrently only YouTube links are supported.")

async def present_qualities(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
    try:
        ydl_opts = {
            "quiet": True,
            "cookiefile": COOKIES_PATH,
            "skip_download": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        formats = info.get("formats", [])
        QUALITY_MAP[update.message.chat_id] = {}

        buttons = []
        for f in formats:
            if f.get("ext") == "mp4" and f.get("filesize") and f.get("format_note"):
                fmt_id = f["format_id"]
                size_mb = round(f["filesize"] / (1024 * 1024), 1)
                label = f'{f["format_note"]} - {size_mb}MB'
                QUALITY_MAP[update.message.chat_id][fmt_id] = f
                buttons.append([InlineKeyboardButton(label, callback_data=f"{fmt_id}|{url}")])

        if not buttons:
            await update.message.reply_text("❌ No downloadable formats found.")
            return

        await update.message.reply_text(
            "🔽 Choose video quality:",
            reply_markup=InlineKeyboardMarkup(buttons[:10])  # Limit to 10
        )

    except Exception as e:
        logger.error("❌ Error fetching qualities: %s", str(e))
        await update.message.reply_text(
            "❌ Failed to fetch video formats.\n"
            "If it's a YouTube link, 429 errors may require a cookies.txt file."
        )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    fmt_id, url = query.data.split("|")
    chat_id = query.message.chat_id
    await query.edit_message_text("📥 Downloading selected quality...")

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            ydl_opts = {
                "format": fmt_id,
                "outtmpl": os.path.join(tmpdir, "%(title)s.%(ext)s"),
                "noplaylist": True,
                "cookiefile": COOKIES_PATH,
                "quiet": True,
                "no_warnings": True,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                file_path = ydl.prepare_filename(info)
                file_name = os.path.basename(file_path)

                file_size = os.path.getsize(file_path)
                if file_size > 2 * 1024 * 1024 * 1024:
                    await context.bot.send_message(chat_id, "❌ File too large to send via Telegram.")
                    return

                with open(file_path, "rb") as f:
                    await context.bot.send_document(
                        chat_id=chat_id,
                        document=InputFile(f, filename=file_name),
                        caption=f'{info.get("title", "Video")} ({round(file_size / (1024*1024), 1)} MB)'
                    )

    except Exception as e:
        logger.error("❌ Download error: %s", str(e))
        await context.bot.send_message(chat_id=chat_id, text=f"❌ Failed to download.\n{str(e)}")

# =================== Telegram Bot Setup ===================

async def run_telegram_bot():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_handler))
    logger.info("✅ Telegram bot polling started.")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()

# =================== Flask App ===================

flask_app = Flask(__name__)

@flask_app.route("/")
def index():
    return "🤖 Telegram Video Downloader Bot is LIVE!"

# =================== Entry Point ===================

def start_bot_thread():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(run_telegram_bot())
    loop.run_forever()

if __name__ == "__main__":
    threading.Thread(target=start_bot_thread, daemon=True).start()
    flask_app.run(host="0.0.0.0", port=10000)
