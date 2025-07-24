import asyncio
import os
import threading
from flask import Flask
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from telegram import Update, InputFile
import yt_dlp
import tempfile

# ================= TELEGRAM BOT COMMANDS =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Welcome to the Video Downloader Bot!\n"
        "👉 Send a YouTube, Terabox, or DiskWala link to get the video as a Telegram download."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    print(f"🔗 Received URL: {url}")

    if "youtube.com" in url or "youtu.be" in url:
        await download_youtube(update, context, url)

    elif "terabox" in url:
        await update.message.reply_text("📥 Terabox support coming soon.")

    elif "diskwala" in url:
        await update.message.reply_text("📥 DiskWala support coming soon.")

    else:
        await update.message.reply_text("❌ Unsupported link. Only YouTube, Terabox, and DiskWala are allowed.")

# ================= YOUTUBE DOWNLOAD HANDLER =================

async def download_youtube(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
    await update.message.reply_text("⏳ Downloading YouTube video... Please wait...")

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            ydl_opts = {
                'format': 'best[ext=mp4]/best',
                'outtmpl': os.path.join(tmpdir, '%(title).80s.%(ext)s'),
                'noplaylist': True,
                'quiet': True,
                'no_warnings': True,
                'cookies': 'cookies.txt',  # ✅ Use YouTube Premium/private cookies
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                file_path = ydl.prepare_filename(info)
                file_name = os.path.basename(file_path)
                file_size = os.path.getsize(file_path)

                print(f"✅ Downloaded: {file_name} ({file_size / 1024 / 1024:.2f} MB)")

                with open(file_path, 'rb') as f:
                    await update.message.reply_document(
                        document=InputFile(f, filename=file_name),
                        caption=f"📽️ {info.get('title', 'Video')} ({file_size // (1024 * 1024)} MB)"
                    )

    except Exception as e:
        print("❌ Error:", str(e))
        await update.message.reply_text(f"❌ Failed to download video:\n`{str(e)}`", parse_mode="Markdown")

# ================= TELEGRAM BOT SETUP =================

async def run_telegram_bot():
    token = "7823731827:AAFoCU1etlCutbNiASDOCQMtHRE2qJW9eKE"
    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🚀 Telegram bot started and polling updates.")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    await app.updater.idle()

# ================= FLASK SETUP FOR RENDER =================

flask_app = Flask(__name__)

@flask_app.route('/')
def index():
    return "✅ Telegram YouTube Downloader Bot is LIVE!"

# ================= RUN BOTH (TELEGRAM + FLASK) =================

def start_bot_thread():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_telegram_bot())

if __name__ == '__main__':
    threading.Thread(target=start_bot_thread, daemon=True).start()
    flask_app.run(host="0.0.0.0", port=10000)
