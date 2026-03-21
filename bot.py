import os
import json
import time
import uuid
import asyncio
import logging
import tempfile
from pathlib import Path

import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

# -------------------------------
# Configuration & Setup
# -------------------------------
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(id_) for id_ in os.getenv("ADMIN_IDS", "").split(",") if id_]
FORCE_CHANNEL = os.getenv("FORCE_CHANNEL")   # e.g. "@my_channel" or "-1001234567890"

# User database (JSON file)
USERS_FILE = "users.json"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Helper functions for user database
def load_users():
    """Load user IDs from JSON file."""
    if not os.path.exists(USERS_FILE):
        return set()
    with open(USERS_FILE, "r") as f:
        data = json.load(f)
        return set(data.get("users", []))

def save_users(users):
    """Save user IDs to JSON file."""
    with open(USERS_FILE, "w") as f:
        json.dump({"users": list(users)}, f)

# Global set of user IDs (cached for performance)
user_ids = load_users()

def add_user(user_id):
    """Add user to the set and save if new."""
    if user_id not in user_ids:
        user_ids.add(user_id)
        save_users(user_ids)
        logger.info(f"New user added: {user_id}")

# -------------------------------
# Force Join Check
# -------------------------------
async def is_user_member(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    """Check if user is a member of the force‑join channel."""
    if not FORCE_CHANNEL:
        return True  # no channel configured
    try:
        member = await context.bot.get_chat_member(chat_id=FORCE_CHANNEL, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        logger.error(f"Failed to check membership for {user_id}: {e}")
        return False

async def force_join_required(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send message asking user to join the channel."""
    chat_id = update.effective_chat.id
    keyboard = [[InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{FORCE_CHANNEL.lstrip('@')}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            "🔒 *Access Restricted*\n\n"
            "You must join our channel to use this bot.\n"
            "Click the button below and try again!"
        ),
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )

# -------------------------------
# Download Helpers with Progress
# -------------------------------
class ProgressHook:
    """Helper to update a message with download progress."""
    def __init__(self, context, chat_id, message_id):
        self.context = context
        self.chat_id = chat_id
        self.message_id = message_id
        self.last_percent = 0

    def __call__(self, d):
        if d["status"] == "downloading":
            percent = d.get("_percent_str", "0%").strip("%")
            try:
                percent = float(percent)
            except:
                percent = 0
            # Update only if progress increased by at least 5% to avoid spam
            if percent - self.last_percent >= 5:
                self.last_percent = percent
                asyncio.create_task(
                    self.context.bot.edit_message_text(
                        chat_id=self.chat_id,
                        message_id=self.message_id,
                        text=f"⬇️ Downloading... {percent:.1f}%",
                    )
                )
        elif d["status"] == "finished":
            asyncio.create_task(
                self.context.bot.edit_message_text(
                    chat_id=self.chat_id,
                    message_id=self.message_id,
                    text="📤 Processing and uploading...",
                )
            )

async def download_video(chat_id, url, message_id, context):
    """Download video as MP4 and send it."""
    # Unique filename
    temp_dir = tempfile.gettempdir()
    filename = os.path.join(temp_dir, f"video_{uuid.uuid4().hex}.mp4")

    ydl_opts = {
        "format": "best[ext=mp4]/best",
        "outtmpl": filename,
        "progress_hooks": [ProgressHook(context, chat_id, message_id)],
        "quiet": True,
        "no_warnings": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        # Send the video
        with open(filename, "rb") as video_file:
            await context.bot.send_video(chat_id=chat_id, video=video_file)
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="✅ Video sent successfully!",
        )
    except Exception as e:
        logger.error(f"Video download error: {e}")
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="❌ Failed to download video. Please check the link and try again.",
        )
    finally:
        if os.path.exists(filename):
            os.remove(filename)

async def download_audio(chat_id, url, message_id, context):
    """Download audio as MP3 and send it."""
    temp_dir = tempfile.gettempdir()
    # yt-dlp will produce a temp file, we'll rename later
    out_template = os.path.join(temp_dir, f"audio_{uuid.uuid4().hex}.%(ext)s")

    ydl_opts = {
        "format": "bestaudio",
        "outtmpl": out_template,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
        "progress_hooks": [ProgressHook(context, chat_id, message_id)],
        "quiet": True,
        "no_warnings": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title", "AMM Reels")
            # Find the final mp3 file
            base = out_template.replace(".%(ext)s", "")
            mp3_file = base + ".mp3"
            if not os.path.exists(mp3_file):
                # sometimes the extension is different; try to find any .mp3
                for f in os.listdir(temp_dir):
                    if f.startswith(os.path.basename(base)) and f.endswith(".mp3"):
                        mp3_file = os.path.join(temp_dir, f)
                        break
        # Send the audio
        with open(mp3_file, "rb") as audio_file:
            await context.bot.send_audio(
                chat_id=chat_id,
                audio=audio_file,
                title=title,
                performer="AMM Reels",
            )
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="✅ Audio sent successfully!",
        )
    except Exception as e:
        logger.error(f"Audio download error: {e}")
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="❌ Failed to extract audio. Please check the link and try again.",
        )
    finally:
        # Clean up any leftover files (both original and processed)
        for f in os.listdir(temp_dir):
            if f.startswith(os.path.basename(out_template).split(".%(ext)s")[0]):
                try:
                    os.remove(os.path.join(temp_dir, f))
                except:
                    pass

# -------------------------------
# Handlers
# -------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Welcome message with inline buttons."""
    user_id = update.effective_user.id
    add_user(user_id)

    # Force join check
    if not await is_user_member(context, user_id):
        await force_join_required(update, context)
        return

    welcome_text = (
        "✨ *Welcome to AMM Reels Bot* ✨\n\n"
        "I can download videos and audio from:\n"
        "• Instagram\n"
        "• Facebook\n"
        "• Pinterest\n\n"
        "Just send me a link and choose what you want!\n\n"
        "🔗 *Tips:*\n"
        "• Use /help for more info\n"
        "• Admin: /stats, /broadcast"
    )
    keyboard = [
        [InlineKeyboardButton("📖 Help", callback_data="help")],
        [InlineKeyboardButton("👨‍💻 Developer", url="https://t.me/your_username")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help command."""
    help_text = (
        "🆘 *How to use*\n\n"
        "1. Send a valid link from Instagram, Facebook, or Pinterest.\n"
        "2. Choose *Video* or *MP3* from the inline buttons.\n"
        "3. Wait for the download and upload (progress shown).\n\n"
        "*Admin commands:*\n"
        "• /stats – show total users\n"
        "• /broadcast <message> – send message to all users"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle video/audio button clicks."""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    # Retrieve the stored URL from context.user_data
    url = context.user_data.get("last_url")
    if not url:
        await query.edit_message_text("❌ No link found. Please send a link first.")
        return

    # Force join check again (in case user joined after clicking)
    if not await is_user_member(context, user_id):
        await force_join_required(update, context)
        return

    if query.data == "video":
        await download_video(query.message.chat_id, url, query.message.message_id, context)
    elif query.data == "audio":
        await download_audio(query.message.chat_id, url, query.message.message_id, context)
    elif query.data == "help":
        await help_command(update, context)

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive a link and ask for format."""
    user_id = update.effective_user.id
    add_user(user_id)

    # Force join check
    if not await is_user_member(context, user_id):
        await force_join_required(update, context)
        return

    url = update.message.text.strip()
    if "http" not in url:
        await update.message.reply_text("❌ Please send a valid link.")
        return

    # Store the URL in user_data for later use in button handler
    context.user_data["last_url"] = url

    keyboard = [
        [InlineKeyboardButton("🎬 Video", callback_data="video")],
        [InlineKeyboardButton("🎵 MP3", callback_data="audio")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Select the format you want:", reply_markup=reply_markup)

# -------------------------------
# Admin Commands
# -------------------------------
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show total number of users (admin only)."""
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ You are not authorized to use this command.")
        return
    total = len(user_ids)
    await update.message.reply_text(f"📊 *Total users:* {total}", parse_mode="Markdown")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message to all users (admin only)."""
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ You are not authorized to use this command.")
        return

    # The broadcast message is everything after the command
    message = " ".join(context.args)
    if not message:
        await update.message.reply_text("Usage: /broadcast <message>")
        return

    # Show a progress message
    progress_msg = await update.message.reply_text("📢 Broadcasting... This may take a while.")

    success = 0
    failed = 0
    for uid in user_ids:
        try:
            await context.bot.send_message(chat_id=uid, text=message)
            success += 1
            await asyncio.sleep(0.05)  # small delay to avoid hitting limits
        except Exception as e:
            logger.warning(f"Failed to send broadcast to {uid}: {e}")
            failed += 1

    await progress_msg.edit_text(f"📢 Broadcast finished.\n✅ Sent: {success}\n❌ Failed: {failed}")

# -------------------------------
# Main Application
# -------------------------------
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))

    # Start polling
    app.run_polling()

if __name__ == "__main__":
    main()
