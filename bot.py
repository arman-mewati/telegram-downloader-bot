import yt_dlp
import threading
import time
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, CallbackQueryHandler, filters, ContextTypes

# 🔐 Secure Token (Environment Variable)
TOKEN = os.getenv("BOT_TOKEN")

user_links = {}

# ----------- ANTI SLEEP SERVER ----------- #

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"AMM Reels Running")

def run_server():
    server = HTTPServer(("0.0.0.0", 10000), Handler)
    server.serve_forever()

threading.Thread(target=run_server).start()

# ----------- START ----------- #

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    keyboard = [
        [InlineKeyboardButton("📥 Download Video", callback_data="download")]
    ]

    await update.message.reply_text(
        "👋 Welcome to AMM Reels\n\n"
        "Send any video link:\n"
        "Instagram | Facebook | Pinterest | YouTube",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ----------- BUTTON HANDLER ----------- #

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "download":
        await query.edit_message_text("📎 Send video link")

    elif query.data.startswith("video_"):
        quality = query.data.split("_")[1]
        await download_video(query, user_id, quality)

    elif query.data.startswith("audio_"):
        quality = query.data.split("_")[1]
        await download_audio(query, user_id, quality)

# ----------- VIDEO DOWNLOAD ----------- #

async def download_video(query, user_id, quality):

    url = user_links.get(user_id)
    filename = f"video_{int(time.time())}.mp4"

    await query.edit_message_text("⬇️ Downloading video...")

    try:

        if quality == "1080":
            fmt = "bestvideo[height<=1080]+bestaudio/best"
        elif quality == "720":
            fmt = "bestvideo[height<=720]+bestaudio/best"
        else:
            fmt = "bestvideo[height<=480]+bestaudio/best"

        ydl_opts = {
            'format': fmt,
            'outtmpl': filename
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        await query.edit_message_text("📤 Uploading video...")

        await query.message.reply_video(open(filename, "rb"))

        os.remove(filename)

        await query.edit_message_text("✅ Done!")

    except Exception as e:
        await query.edit_message_text("❌ Failed")
        print(e)

# ----------- AUDIO DOWNLOAD ----------- #

async def download_audio(query, user_id, quality):

    url = user_links.get(user_id)

    await query.edit_message_text("🎵 Extracting audio...")

    try:

        filename = f"audio_{int(time.time())}.%(ext)s"

        ydl_opts = {
            'format': 'bestaudio',
            'outtmpl': filename,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': quality,
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
            InlineKeyboardButton("1080p", callback_data="video_1080"),
            InlineKeyboardButton("720p", callback_data="video_720"),
            InlineKeyboardButton("480p", callback_data="video_480")
        ],
        [
            InlineKeyboardButton("MP3 128kbps", callback_data="audio_128"),
            InlineKeyboardButton("MP3 192kbps", callback_data="audio_192"),
            InlineKeyboardButton("MP3 320kbps", callback_data="audio_320")
        ]
    ]

    await update.message.reply_text(
        "🎬 Select quality:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ----------- MAIN ----------- #

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, downloader))

print("Bot running...")

app.run_polling()
