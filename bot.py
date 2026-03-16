import yt_dlp
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes

TOKEN = "8628787355:AAFClhBFZyfu8XkRNFiXxeVSjCJgoqoHm9o"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send Instagram or Facebook video link.")

async def downloader(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text

    if "http" not in url:
        await update.message.reply_text("Please send a valid video link.")
        return

    ydl_opts = {
        'format': 'best',
        'outtmpl': 'video.mp4'
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    await update.message.reply_video(video=open("video.mp4","rb"))

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, downloader))

app.run_polling()
