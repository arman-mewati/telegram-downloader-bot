import yt_dlp
import threading
import time
import os
import json
import subprocess
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, MessageHandler, CommandHandler,
    CallbackQueryHandler, filters, ContextTypes
)

# ============================================================
#  CONFIG
# ============================================================
TOKEN      = os.getenv("BOT_TOKEN")
ADMIN_ID   = int(os.getenv("ADMIN_ID", "0"))
CHANNEL_ID = os.getenv("CHANNEL_ID", "")

USERS_FILE = "users.json"

# ============================================================
#  AUTO INSTALL FFMPEG (Render fix)
# ============================================================
def install_ffmpeg():
    if os.path.exists("/usr/bin/ffmpeg"):
        print("✅ FFmpeg already installed")
        return
    print("📦 Installing FFmpeg...")
    try:
        subprocess.run(["apt-get", "update", "-y"],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["apt-get", "install", "-y", "ffmpeg"],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("✅ FFmpeg installed successfully")
    except Exception as e:
        print(f"❌ FFmpeg install failed: {e}")

install_ffmpeg()

# ============================================================
#  USERS DB
# ============================================================
def load_users() -> set:
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_users(users: set):
    with open(USERS_FILE, "w") as f:
        json.dump(list(users), f)

def add_user(uid: int):
    users = load_users()
    users.add(uid)
    save_users(users)

# ============================================================
#  IN-MEMORY STORE
# ============================================================
user_links: dict[int, str] = {}

# ============================================================
#  ANTI-SLEEP WEB SERVER
# ============================================================
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"AMM Reels Bot is alive!")
    def log_message(self, *args):
        pass

threading.Thread(
    target=lambda: HTTPServer(("0.0.0.0", 10000), Handler).serve_forever(),
    daemon=True
).start()

# ============================================================
#  YT-DLP OPTIONS
# ============================================================
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

COMMON = {
    "quiet": True,
    "no_warnings": True,
    "http_headers": HEADERS,
    "socket_timeout": 30,
    "retries": 5,
    "extractor_retries": 5,
    "nocheckcertificate": True,
}

def video_opts(filename: str) -> dict:
    return {
        **COMMON,
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "outtmpl": filename,
        "merge_output_format": "mp4",
        "ffmpeg_location": "/usr/bin/ffmpeg",
    }

def audio_opts(base_name: str) -> dict:
    return {
        **COMMON,
        "format": "bestaudio/best",
        "outtmpl": f"{base_name}.%(ext)s",
        "ffmpeg_location": "/usr/bin/ffmpeg",
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
    }

# ============================================================
#  FORCE-JOIN HELPER
# ============================================================
async def is_subscribed(bot, user_id: int) -> bool:
    if not CHANNEL_ID:
        return True
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status not in ("left", "kicked")
    except Exception:
        return True

def join_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Join Channel",
                              url=f"https://t.me/{CHANNEL_ID.lstrip('@')}")],
        [InlineKeyboardButton("✅ I Joined", callback_data="check_join")]
    ])

# ============================================================
#  /start
# ============================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    add_user(user.id)

    if not await is_subscribed(context.bot, user.id):
        await update.message.reply_text(
            "🔒 *Access Restricted!*\n\n"
            "You must join our channel first to use this bot.\n"
            "👇 Click below to join:",
            parse_mode="Markdown",
            reply_markup=join_keyboard()
        )
        return

    await update.message.reply_text(
        f"╔══════════════════════╗\n"
        f"║   🎬 *AMM Reels Bot*   ║\n"
        f"╚══════════════════════╝\n\n"
        f"👋 Welcome, *{user.first_name}*!\n\n"
        f"📥 *Supported Platforms:*\n"
        f"  • Instagram Reels & Posts\n"
        f"  • Facebook Videos\n"
        f"  • Pinterest Videos\n\n"
        f"🚀 *How to use:*\n"
        f"  Simply paste any link and choose\n"
        f"  🎬 Video  or  🎵 MP3\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━",
        parse_mode="Markdown"
    )

# ============================================================
#  LINK RECEIVER
# ============================================================
async def downloader(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    add_user(user.id)

    if not await is_subscribed(context.bot, user.id):
        await update.message.reply_text(
            "🔒 Join our channel first!",
            reply_markup=join_keyboard()
        )
        return

    url = update.message.text.strip()

    if "http" not in url:
        await update.message.reply_text(
            "❌ *Invalid link!*\n\nPlease send a valid Instagram / Facebook / Pinterest URL.",
            parse_mode="Markdown"
        )
        return

    user_links[user.id] = url

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎬 Download Video", callback_data="video"),
            InlineKeyboardButton("🎵 Download MP3",   callback_data="audio")
        ],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
    ])

    await update.message.reply_text(
        "🔗 *Link received!*\n\nChoose download format:",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

# ============================================================
#  BUTTON HANDLER
# ============================================================
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "check_join":
        if await is_subscribed(context.bot, user_id):
            await query.edit_message_text(
                "✅ *Access granted!*\n\nNow send me any link.",
                parse_mode="Markdown"
            )
        else:
            await query.answer("❌ You haven't joined yet!", show_alert=True)
        return

    if query.data == "cancel":
        await query.edit_message_text("🚫 Cancelled.")
        return

    url = user_links.get(user_id)
    if not url:
        await query.edit_message_text("⚠️ Session expired. Please send the link again.")
        return

    if query.data == "video":
        await download_video(query, url)
    elif query.data == "audio":
        await download_audio(query, url)

# ============================================================
#  ERROR MESSAGE HELPER
# ============================================================
def parse_error(err: str) -> str:
    e = err.lower()
    if "login" in e or "private" in e or "authentication" in e:
        return "🔒 *Private content!*\n\nThis post is private or requires login."
    if "ffmpeg" in e:
        return "⚙️ *FFmpeg error!*\n\nPlease wait 30 seconds and try again."
    if "404" in e or "not found" in e:
        return "🔗 *Link expired!*\n\nThis link is no longer available."
    if "rate" in e or "429" in e:
        return "⏳ *Rate limited!*\n\nToo many requests. Please wait a few minutes."
    if "unsupported url" in e:
        return "❌ *Unsupported link!*\n\nOnly Instagram, Facebook, Pinterest links are supported."
    return f"❌ *Download failed!*\n\n`{err[:250]}`"

# ============================================================
#  VIDEO DOWNLOAD
# ============================================================
async def download_video(query, url: str):
    ts       = int(time.time())
    filename = f"video_{ts}.mp4"

    try:
        await query.edit_message_text("⬇️ Downloading video `[▓░░░░░░░░░]` 10%",
                                      parse_mode="Markdown")

        with yt_dlp.YoutubeDL(video_opts(filename)) as ydl:
            await query.edit_message_text("⬇️ Downloading video `[▓▓▓▓░░░░░░]` 40%",
                                          parse_mode="Markdown")
            ydl.download([url])

        await query.edit_message_text("⬇️ Downloading video `[▓▓▓▓▓▓▓▓▓░]` 90%",
                                      parse_mode="Markdown")

        # Find the file (extension may vary)
        actual = filename
        if not os.path.exists(actual):
            for f in os.listdir("."):
                if f.startswith(f"video_{ts}"):
                    actual = f
                    break

        await query.edit_message_text("📤 Uploading to Telegram...", parse_mode="Markdown")

        with open(actual, "rb") as f:
            await query.message.reply_video(
                video=f,
                caption=(
                    "🎬 *Your video is ready!*\n"
                    "━━━━━━━━━━━━━━━━\n"
                    "📥 Downloaded via *AMM Reels Bot*"
                ),
                parse_mode="Markdown",
                supports_streaming=True
            )

        await query.edit_message_text("✅ *Done! Enjoy your video.* 🎉", parse_mode="Markdown")

    except yt_dlp.utils.DownloadError as e:
        print(f"[VIDEO DownloadError] {e}")
        await query.edit_message_text(parse_error(str(e)), parse_mode="Markdown")

    except Exception as e:
        print(f"[VIDEO Exception] {e}")
        await query.edit_message_text(
            f"❌ *Unexpected error!*\n\n`{str(e)[:250]}`",
            parse_mode="Markdown"
        )
    finally:
        for f in os.listdir("."):
            if f.startswith(f"video_{ts}"):
                try:
                    os.remove(f)
                except Exception:
                    pass

# ============================================================
#  AUDIO DOWNLOAD
# ============================================================
async def download_audio(query, url: str):
    ts        = int(time.time())
    base_name = f"audio_{ts}"

    try:
        await query.edit_message_text("🎵 Extracting audio `[▓░░░░░░░░░]` 10%",
                                      parse_mode="Markdown")

        with yt_dlp.YoutubeDL(audio_opts(base_name)) as ydl:
            await query.edit_message_text("🎵 Extracting audio `[▓▓▓▓▓░░░░░]` 50%",
                                          parse_mode="Markdown")
            ydl.download([url])

        await query.edit_message_text("🎵 Extracting audio `[▓▓▓▓▓▓▓▓▓▓]` 100%",
                                      parse_mode="Markdown")

        # Find output file
        out_file = f"{base_name}.mp3"
        if not os.path.exists(out_file):
            for f in os.listdir("."):
                if f.startswith(base_name):
                    out_file = f
                    break

        await query.edit_message_text("📤 Uploading audio...", parse_mode="Markdown")

        with open(out_file, "rb") as f:
            await query.message.reply_audio(
                audio=f,
                title="AMM Reels",
                performer="AMM Reels Bot",
                caption=(
                    "🎵 *Your audio is ready!*\n"
                    "━━━━━━━━━━━━━━━━\n"
                    "🎧 Downloaded via *AMM Reels Bot*"
                ),
                parse_mode="Markdown"
            )

        await query.edit_message_text("✅ *Done! Enjoy the music.* 🎶", parse_mode="Markdown")

    except yt_dlp.utils.DownloadError as e:
        print(f"[AUDIO DownloadError] {e}")
        await query.edit_message_text(parse_error(str(e)), parse_mode="Markdown")

    except Exception as e:
        print(f"[AUDIO Exception] {e}")
        await query.edit_message_text(
            f"❌ *Unexpected error!*\n\n`{str(e)[:250]}`",
            parse_mode="Markdown"
        )
    finally:
        for ext in ["mp3", "m4a", "webm", "opus", "ogg"]:
            f = f"{base_name}.{ext}"
            if os.path.exists(f):
                try:
                    os.remove(f)
                except Exception:
                    pass

# ============================================================
#  ADMIN COMMANDS
# ============================================================
def admin_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_ID:
            await update.message.reply_text("🚫 Admin only command!")
            return
        await func(update, context)
    return wrapper

@admin_only
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = load_users()
    await update.message.reply_text(
        f"📊 *Bot Statistics*\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"👥 Total Users : *{len(users)}*\n"
        f"🕐 Checked at  : `{datetime.now().strftime('%Y-%m-%d %H:%M')}`",
        parse_mode="Markdown"
    )

@admin_only
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Usage: `/broadcast Your message here`",
            parse_mode="Markdown"
        )
        return

    message = " ".join(context.args)
    users   = load_users()
    sent    = 0
    failed  = 0

    status_msg = await update.message.reply_text(f"📢 Broadcasting to {len(users)} users...")

    for uid in users:
        try:
            await context.bot.send_message(
                chat_id=uid,
                text=(
                    f"📢 *Announcement from AMM Reels Bot*\n"
                    f"━━━━━━━━━━━━━━━━\n"
                    f"{message}"
                ),
                parse_mode="Markdown"
            )
            sent += 1
        except Exception:
            failed += 1
        time.sleep(0.05)

    await status_msg.edit_text(
        f"✅ *Broadcast complete!*\n\n"
        f"📨 Sent   : *{sent}*\n"
        f"❌ Failed : *{failed}*",
        parse_mode="Markdown"
    )

@admin_only
async def admin_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🛠 *Admin Commands*\n"
        "━━━━━━━━━━━━━━━━\n"
        "`/stats`          — Total user count\n"
        "`/broadcast msg`  — Send msg to all users\n"
        "`/adminhelp`      — Show this menu",
        parse_mode="Markdown"
    )

# ============================================================
#  MAIN
# ============================================================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start",      start))
app.add_handler(CommandHandler("stats",      stats))
app.add_handler(CommandHandler("broadcast",  broadcast))
app.add_handler(CommandHandler("adminhelp",  admin_help))
app.add_handler(CallbackQueryHandler(button))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, downloader))

print("🚀 AMM Reels Bot started!")
app.run_polling()
