import yt_dlp
import threading
import time
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, CallbackQueryHandler, filters, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")

user_links = {}

# ----------- ANTI SLEEP ----------- #
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Running")

def run_server():
    HTTPServer(("0.0.0.0", 10000), Handler).serve_forever()

threading.Thread(target=run_server).start()

# ----------- START ----------- #
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to AMM Reels\n\n"
        "Send Instagram / Facebook / Pinterest link"
    )

# ----------- BUTTON HANDLER ----------- #
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    url = user_links.get(user_id)

    if query.data == "video":
        await download_video(query, url)

    elif query.data == "audio":
        await download_audio(query, url)

# ----------- VIDEO DOWNLOAD ----------- #
async def download_video(query, url):

    filename = f"video_{int(time.time())}.mp4"

    await query.edit_message_text("⬇️ Downloading video...")

    try:
        ydl_opts = {
            'format': 'best',
            'outtmpl': filename
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        await query.edit_message_text("📤 Uploading...")

        await query.message.reply_video(open(filename, "rb"))

        os.remove(filename)

        await query.edit_message_text("✅ Done!")

    except Exception as e:
        await query.edit_message_text("❌ Failed")
        print(e)

# ----------- AUDIO DOWNLOAD ----------- #
async def download_audio(query, url):

    await query.edit_message_text("🎵 Extracting audio...")

    try:
        ydl_opts = {
            'format': 'bestaudio',
            'outtmpl': 'audio.%(ext)s',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        await query.edit_message_text("📤 Uploading audio...")

        await query.message.reply_audio(
            audio=open("audio.mp3", "rb"),
            title="AMM Reels",
            performer="AMM Reels"
        )

        os.remove("audio.mp3")

        await query.edit_message_text("✅ Done!")

    except Exception as e:
        await query.edit_message_text("❌ Failed")
        print(e)

# ----------- LINK RECEIVER ----------- #
async def downloader(update: Update, context: ContextTypes.DEFAULT_TYPE):

    url = update.message.text

    if "http" not in url:
        await update.message.reply_text("❌ Send valid link")
        return

    user_links[update.effective_user.id] = url

    keyboard = [
        [
            InlineKeyboardButton("🎬 Video", callback_data="video"),
            InlineKeyboardButton("🎵 MP3", callback_data="audio")
        ]
    ]

    await update.message.reply_text(
        "Select option:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ----------- MAIN ----------- #
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, downloader))

app.run_polling()
