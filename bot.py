import yt_dlp
import threading
import time
import os
import json
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, MessageHandler, CommandHandler,
    CallbackQueryHandler, filters, ContextTypes
)

# ============================================================
#  CONFIG — set these as environment variables
# ============================================================
TOKEN       = os.getenv("BOT_TOKEN")
ADMIN_ID    = int(os.getenv("ADMIN_ID", "0"))        # your Telegram user ID
CHANNEL_ID  = os.getenv("CHANNEL_ID", "")            # e.g. @yourchannel  (leave "" to disable)

USERS_FILE  = "users.json"

# ============================================================
#  USERS DB  (simple JSON file)
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

    def log_message(self, *args):   # silence access logs
        pass

threading.Thread(target=lambda: HTTPServer(("0.0.0.0", 10000), Handler).serve_forever(),
                 daemon=True).start()

# ============================================================
#  FORCE-JOIN HELPER
# ============================================================
async def is_subscribed(bot, user_id: int) -> bool:
    """Return True if CHANNEL_ID is not set OR user has joined."""
    if not CHANNEL_ID:
        return True
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status not in ("left", "kicked")
    except Exception:
        return True   # if check fails, let the user through

def join_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{CHANNEL_ID.lstrip('@')}")],
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

    # ── Force-join check ──
    if query.data == "check_join":
        if await is_subscribed(context.bot, user_id):
            await query.edit_message_text(
                "✅ *Access granted!*\n\nNow send me any Instagram / Facebook / Pinterest link.",
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
#  VIDEO DOWNLOAD
# ============================================================
async def download_video(query, url: str):
    filename = f"video_{int(time.time())}.mp4"

    steps = ["⏳ Starting download...", "⬇️ Downloading video  [▓░░░░░░░░░] 10%",
             "⬇️ Downloading video  [▓▓▓▓░░░░░░] 40%",
             "⬇️ Downloading video  [▓▓▓▓▓▓▓░░░] 70%",
             "⬇️ Downloading video  [▓▓▓▓▓▓▓▓▓░] 90%"]

    anim_task = threading.Thread(target=lambda: None, daemon=True)  # placeholder

    await query.edit_message_text(steps[0])

    try:
        ydl_opts = {
            "format": "best[ext=mp4]/best",
            "outtmpl": filename,
            "quiet": True,
            "no_warnings": True,
        }

        # Animate while downloading (simple sequential messages)
        for step in steps[1:]:
            await query.edit_message_text(step)
            time.sleep(0.4)

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        await query.edit_message_text("📤 Uploading to Telegram...")

        with open(filename, "rb") as f:
            await query.message.reply_video(
                video=f,
                caption=(
                    "🎬 *Your video is ready!*\n"
                    "━━━━━━━━━━━━━━━━\n"
                    "📥 Downloaded via *AMM Reels Bot*"
                ),
                parse_mode="Markdown"
            )

        await query.edit_message_text("✅ *Done! Enjoy your video.* 🎉", parse_mode="Markdown")

    except Exception as e:
        await query.edit_message_text(
            "❌ *Download failed!*\n\n"
            "Possible reasons:\n"
            "• Private / expired link\n"
            "• Platform blocked the request\n\n"
            "_Please try again with a different link._",
            parse_mode="Markdown"
        )
        print(f"[VIDEO ERROR] {e}")
    finally:
        if os.path.exists(filename):
            os.remove(filename)

# ============================================================
#  AUDIO DOWNLOAD
# ============================================================
async def download_audio(query, url: str):
    base_name = f"audio_{int(time.time())}"
    out_path  = f"{base_name}.mp3"

    await query.edit_message_text("🎵 Extracting audio... [▓░░░░░░░░░] 10%")

    try:
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": f"{base_name}.%(ext)s",
            "quiet": True,
            "no_warnings": True,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        }

        await query.edit_message_text("🎵 Extracting audio... [▓▓▓▓▓░░░░░] 50%")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        await query.edit_message_text("🎵 Extracting audio... [▓▓▓▓▓▓▓▓▓▓] 100%")
        await query.edit_message_text("📤 Uploading audio...")

        with open(out_path, "rb") as f:
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

    except Exception as e:
        await query.edit_message_text(
            "❌ *Audio extraction failed!*\n\n"
            "_Make sure FFmpeg is installed and the link is valid._",
            parse_mode="Markdown"
        )
        print(f"[AUDIO ERROR] {e}")
    finally:
        for ext in ["mp3", "m4a", "webm", "opus"]:
            f = f"{base_name}.{ext}"
            if os.path.exists(f):
                os.remove(f)

# ============================================================
#  ADMIN COMMANDS
# ============================================================
def admin_only(func):
    """Decorator — only ADMIN_ID can run this command."""
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
        time.sleep(0.05)   # respect rate limits

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

app.add_handler(CommandHandler("start",       start))
app.add_handler(CommandHandler("stats",       stats))
app.add_handler(CommandHandler("broadcast",   broadcast))
app.add_handler(CommandHandler("adminhelp",   admin_help))
app.add_handler(CallbackQueryHandler(button))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, downloader))

print("🚀 AMM Reels Bot started!")
app.run_polling()
