import yt_dlp
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, CallbackQueryHandler, filters, ContextTypes

TOKEN = "8628787355:AAFClhBFZyfu8XkRNFiXxeVSjCJgoqoHm9o"


# ---------------- WEB SERVER (ANTI SLEEP) ---------------- #

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"AMM Reels Bot is running")


def run_server():
    server = HTTPServer(("0.0.0.0", 10000), Handler)
    server.serve_forever()


threading.Thread(target=run_server).start()


# ---------------- START COMMAND ---------------- #

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    keyboard = [
        [InlineKeyboardButton("📥 Download", callback_data="download")],
        [InlineKeyboardButton("❓ Help", callback_data="help"),
         InlineKeyboardButton("ℹ️ About", callback_data="about")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    text = """
👋 Welcome to AMM Reels

Download Instagram Reels & Facebook videos instantly.

Send video link and get video in seconds.

Created by Arman Mamliya
"""

    await update.message.reply_text(text, reply_markup=reply_markup)


# ---------------- HELP ---------------- #

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "📌 How to use:\n\n"
        "1️⃣ Copy Instagram or Facebook video link\n"
        "2️⃣ Send it here\n"
        "3️⃣ Bot will download video instantly"
    )


# ---------------- ABOUT ---------------- #

async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "🤖 AMM Reels\n\n"
        "Fast Instagram & Facebook video downloader.\n\n"
        "Created by Arman Mamliya."
    )


# ---------------- BUTTON HANDLER ---------------- #

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    if query.data == "download":
        await query.edit_message_text("📎 Send Instagram or Facebook video link.")

    elif query.data == "help":
        await query.edit_message_text(
            "📌 How to use:\n\n"
            "1️⃣ Copy video link\n"
            "2️⃣ Send it here\n"
            "3️⃣ Bot will download video"
        )

    elif query.data == "about":
        await query.edit_message_text(
            "🤖 AMM Reels\n\n"
            "Fast Instagram & Facebook video downloader.\n\n"
            "Created by Arman Mamliya."
        )


# ---------------- VIDEO DOWNLOADER ---------------- #

async def downloader(update: Update, context: ContextTypes.DEFAULT_TYPE):

    url = update.message.text

    if "http" not in url:
        await update.message.reply_text("❌ Please send a valid video link.")
        return

    msg = await update.message.reply_text("⏳ Processing link...")

    try:

        await msg.edit_text("⬇️ Downloading video...")

        ydl_opts = {
            'format': 'best',
            'outtmpl': 'video.mp4'
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        await msg.edit_text("📤 Uploading video...")

        await update.message.reply_video(video=open("video.mp4", "rb"))

        await msg.edit_text("✅ Download complete!")

    except:
        await msg.edit_text("⚠️ Failed to download video.")


# ---------------- MAIN BOT ---------------- #

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("help", help_command))
app.add_handler(CommandHandler("about", about))
app.add_handler(CallbackQueryHandler(button))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, downloader))

print("Bot is running...")

app.run_polling()
