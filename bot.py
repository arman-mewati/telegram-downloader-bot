import yt_dlp
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, CallbackQueryHandler, filters, ContextTypes

TOKEN = "8628787355:AAFClhBFZyfu8XkRNFiXxeVSjCJgoqoHm9o"

user_links = {}


# ---------------- ANTI SLEEP SERVER ---------------- #

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"AMM Reels Bot Running")


def run_server():
    server = HTTPServer(("0.0.0.0", 10000), Handler)
    server.serve_forever()


threading.Thread(target=run_server).start()


# ---------------- START ---------------- #

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    keyboard = [
        [InlineKeyboardButton("📥 Download Video", callback_data="download")],
        [InlineKeyboardButton("❓ Help", callback_data="help"),
         InlineKeyboardButton("ℹ️ About", callback_data="about")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    text = """
👋 Welcome to AMM Reels

Download videos from:
• Instagram
• Facebook
• Pinterest

Send video link to start.

Created by Arman Mamliya
"""

    await update.message.reply_text(text, reply_markup=reply_markup)


# ---------------- HELP ---------------- #

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "📌 How to use:\n\n"
        "1️⃣ Copy video link\n"
        "2️⃣ Send it here\n"
        "3️⃣ Choose quality\n"
        "4️⃣ Download video"
    )


# ---------------- ABOUT ---------------- #

async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "🤖 AMM Reels\n\n"
        "Instagram, Facebook & Pinterest downloader.\n\n"
        "Created by Arman Mamliya."
    )


# ---------------- BUTTON HANDLER ---------------- #

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    if query.data == "download":
        await query.edit_message_text("📎 Send video link.")

    elif query.data == "help":
        await query.edit_message_text("Send video link and choose quality.")

    elif query.data == "about":
        await query.edit_message_text("AMM Reels by Arman Mamliya")

    elif query.data == "hd":
        await download_video(query, user_id, "best")

    elif query.data == "sd":
        await download_video(query, user_id, "worst")

    elif query.data == "audio":
        await download_video(query, user_id, "audio")


# ---------------- DOWNLOAD FUNCTION ---------------- #

async def download_video(query, user_id, quality):

    url = user_links.get(user_id)

    if not url:
        await query.edit_message_text("Link expired. Send again.")
        return

    await query.edit_message_text("⬇️ Downloading...")

    try:

        if quality == "audio":

            ydl_opts = {
                'format': 'bestaudio/best',
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

            await query.message.reply_audio(audio=open("audio.mp3", "rb"))


        else:

            ydl_opts = {
                'format': quality,
                'outtmpl': 'video.mp4'
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            await query.edit_message_text("📤 Uploading video...")

            await query.message.reply_video(video=open("video.mp4", "rb"))


        await query.edit_message_text("✅ Download complete!")

    except Exception as e:

        await query.edit_message_text("⚠️ Download failed.")
        print(e)


# ---------------- LINK RECEIVER ---------------- #

async def downloader(update: Update, context: ContextTypes.DEFAULT_TYPE):

    url = update.message.text

    if "http" not in url:
        await update.message.reply_text("Send valid link.")
        return

    user_links[update.effective_user.id] = url

    keyboard = [
        [
            InlineKeyboardButton("HD Download", callback_data="hd"),
            InlineKeyboardButton("SD Download", callback_data="sd")
        ],
        [
            InlineKeyboardButton("Audio Only (MP3)", callback_data="audio")
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Select download quality:",
        reply_markup=reply_markup
    )


# ---------------- MAIN BOT ---------------- #

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("help", help_command))
app.add_handler(CommandHandler("about", about))
app.add_handler(CallbackQueryHandler(button))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, downloader))

print("Bot running...")

app.run_polling()
