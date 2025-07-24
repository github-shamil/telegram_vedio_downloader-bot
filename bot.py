import asyncio
import os
import threading
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
import tempfile

COOKIES_PATH = os.path.join(os.path.dirname(__file__), 'cookies.txt')
QUALITY_MAP = {}

# =============== Telegram Bot Handlers ===============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *Welcome to the Video Downloader Bot!*\n"
        "👉 Send a YouTube, Terabox, or DiskWala link.\n"
        "🎞️ You'll be asked to pick a video quality.",
        parse_mode="Markdown"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    print("🔹 Received:", url)

    if "youtube.com" in url or "youtu.be" in url:
        await present_qualities(update, context, url)

    elif "terabox" in url:
        await update.message.reply_text("📥 Terabox support coming soon.")

    elif "diskwala" in url:
        await update.message.reply_text("📥 DiskWala support coming soon.")

    else:
        await update.message.reply_text("❌ Unsupported link.")

async def present_qualities(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
    try:
        ydl_opts = {
            'quiet': True,
            'cookiefile': COOKIES_PATH,
            'skip_download': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        formats = info.get('formats', [])
        buttons = []
        QUALITY_MAP[update.message.chat_id] = {}

        for f in formats:
            if f.get("ext") == "mp4" and f.get("filesize") and f.get("format_note"):
                quality = f["format_note"]
                fmt_id = f["format_id"]
                size = round(f["filesize"] / (1024 * 1024), 1)
                button_text = f"{quality} - {size}MB"
                callback_data = f"{fmt_id}|{url}"
                QUALITY_MAP[update.message.chat_id][fmt_id] = f
                buttons.append([InlineKeyboardButton(button_text, callback_data=callback_data)])

        if not buttons:
            await update.message.reply_text("❌ No downloadable formats found.")
            return

        reply_markup = InlineKeyboardMarkup(buttons[:10])  # Limit to first 10
        await update.message.reply_text("🔽 Choose video quality:", reply_markup=reply_markup)

    except Exception as e:
        print("❌ Error in present_qualities:", str(e))
        await update.message.reply_text("❌ Failed to fetch video formats.")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    fmt_id, url = query.data.split("|")
    chat_id = query.message.chat_id

    await query.edit_message_text("📥 Downloading selected quality...")

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            ydl_opts = {
                'format': fmt_id,
                'outtmpl': os.path.join(tmpdir, '%(title)s.%(ext)s'),
                'noplaylist': True,
                'cookiefile': COOKIES_PATH,
                'quiet': True,
                'no_warnings': True,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                file_path = ydl.prepare_filename(info)
                file_name = os.path.basename(file_path)
                file_size = os.path.getsize(file_path)

                with open(file_path, 'rb') as f:
                    await context.bot.send_document(
                        chat_id=chat_id,
                        document=InputFile(f, filename=file_name),
                        caption=f"{info.get('title', 'Video')} ({round(file_size / (1024*1024), 1)} MB)"
                    )

    except Exception as e:
        print("❌ Download error:", str(e))
        await context.bot.send_message(chat_id=chat_id, text=f"❌ Failed to download.\n{str(e)}")

# =============== Telegram Bot Setup ===============

async def run_telegram_bot():
    token = "7823731827:AAFoCU1etlCutbNiASDOCQMtHRE2qJW9eKE"
    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("✅ Telegram bot polling started.")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()

# =============== Flask App ===============

flask_app = Flask(__name__)

@flask_app.route('/')
def index():
    return "🤖 Telegram Video Downloader Bot is LIVE!"

# =============== Launch Everything ===============

def start_bot_thread():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(run_telegram_bot())
    loop.run_forever()

if __name__ == '__main__':
    threading.Thread(target=start_bot_thread, daemon=True).start()
    flask_app.run(host="0.0.0.0", port=10000)
