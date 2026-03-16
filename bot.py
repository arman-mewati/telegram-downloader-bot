import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, CallbackQueryHandler, filters, ContextTypes

TOKEN = "YOUR_BOT_TOKEN"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    keyboard = [
        [InlineKeyboardButton("📥 Download", callback_data="download")],
        [InlineKeyboardButton("ℹ️ Help", callback_data="help"),
         InlineKeyboardButton("👨‍💻 About", callback_data="about")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    text = """
👋 Welcome to InstaFB Downloader Bot

📥 Download Instagram & Facebook Videos Easily
Click a button below to start.
"""

    await update.message.reply_text(text, reply_markup=reply_markup)


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    if query.data == "download":
        await query.edit_message_text("📎 Send Instagram or Facebook video link.")

    elif query.data == "help":
        await query.edit_message_text(
            "📌 How to use:\n\n1️⃣ Copy video link\n2️⃣ Send it here\n3️⃣ Bot will download video"
        )

    elif query.data == "about":
        await query.edit_message_text(
            "🤖 InstaFB Downloader Bot\nFast and free video downloader for Instagram & Facebook."
        )


async def downloader(update: Update, context: ContextTypes.DEFAULT_TYPE):

    url = update.message.text

    if "http" not in url:
        await update.message.reply_text("❌ Please send a valid video link.")
        return

    ydl_opts = {'format': 'best', 'outtmpl': 'video.mp4'}

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    await update.message.reply_video(video=open("video.mp4", "rb"))


app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, downloader))

app.run_polling()
