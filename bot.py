from flask import Flask
import os
import threading
import telebot
from telebot.types import Message, ChatMemberUpdated
import requests
import datetime
import pytz
import time
from io import BytesIO
from PIL import Image

# Configuration
BOT_TOKEN = "7799333321:AAFnYX39VqF615G0I19SRxCQqQamV3BwHPM"
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

AUTHORIZED_OWNERS = [7798805438]  # Add all admin IDs
ALLOWED_GROUP_IDS = {-1002255896839, -1002659965676}
REQUIRED_JOIN_GROUP = -1002255896839
DEFAULT_DAILY_LIMIT = 30
remaining_likes = 30  # For global counter

# State
group_limits = {}
verified_users = set()
daily_usage = {}
allowed_users = {}
last_reset = datetime.datetime.now().date()

API_URL = "https://sanatani-ff-api.vercel.app/like?uid={uid}&server_name={region}"
BAN_CHK_URL = "https://sanatani-ff-id-ban-chker.vercel.app/uditanshu-region/ban-info"
INFO_API_URL = "https://infobot-mocha.vercel.app/player"

TIMEZONES = {
    "ind": pytz.timezone("Asia/Kolkata"),
    "eu": pytz.timezone("Europe/Lisbon"),
}

# Helpers
def reset_daily_limits():
    global daily_usage, last_reset
    daily_usage.clear()
    last_reset = datetime.datetime.now().date()

def check_reset():
    if datetime.datetime.now().date() != last_reset:
        reset_daily_limits()

def get_limit(user_id, group_id=None):
    info = allowed_users.get(user_id)
    if info and info["expires"] >= datetime.datetime.now().date():
        return info["limit"]
    return group_limits.get(group_id, DEFAULT_DAILY_LIMIT)

def safe_reply(message, text, **kwargs):
    try:
        return bot.reply_to(message, text, **kwargs)
    except:
        return bot.send_message(message.chat.id, text, **kwargs)

def is_owner(user_id):
    return user_id in AUTHORIZED_OWNERS

def is_group_allowed(chat_id, user_id):
    return chat_id in ALLOWED_GROUP_IDS or chat_id > 0 or is_owner(user_id)

def is_user_joined(user_id):
    try:
        member = bot.get_chat_member(REQUIRED_JOIN_GROUP, user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

def escape_html(text):
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def format_section(title, data_dict):
    """Format any dict into HTML section"""
    lines = [f"<b>{title}</b>"]
    for key, value in data_dict.items():
        lines.append(f"• <b>{escape_html(str(key))}</b>: {escape_html(value)}")
    return "\n".join(lines)

def restricted_group(func):
    def wrapper(msg):
        if not is_group_allowed(msg.chat.id, msg.from_user.id):
            return safe_reply(msg, "❌ This bot is restricted to specific groups only.")
        if not is_user_joined(msg.from_user.id):
            return safe_reply(
                msg,
                "📛 *To use this bot, please join our Main TG Group first:*\n"
                "🔗 [Join](https://t.me/+Dz7qm9CP741kODU1)\n\n"
                "✅ After joining, resend your command.",
                parse_mode="Markdown",
                disable_web_page_preview=True
            )
        return func(msg)
    return wrapper

@bot.message_handler(commands=['player'])
def handle_player(message):
    chat_id = message.chat.id

    if message.chat.type == "private":
        bot.reply_to(message, "❌ This bot cannot be used in private chats.")
        return

    if chat_id not in ALLOWED_GROUP_IDS:
        bot.reply_to(message, "❌ This group is not authorized to use this bot.")
        return

    parts = message.text.strip().split()
    if len(parts) != 3:
        bot.reply_to(message, "Usage: /player <UID> <region>\nExample: /player 1692167462 ind")
        return

    uid, region = parts[1], parts[2].lower()

    status_msg = bot.reply_to(message, "<i>Checking player info…</i>", parse_mode="HTML")            
    try:
        res = requests.get(INFO_API_URL, params={"uid": uid, "region": region})
        data = res.json()

        if res.status_code != 200 or "basicinfo" not in data:
            text = f"<b>Error</b>: {escape_html(data.get('error', 'Unexpected response'))}"
        else:
            lines = []

            if data.get("basicinfo"):
                lines.append(format_section("🚀 Basic Info", data["basicinfo"][0]))
                lines.append("")

            if data.get("claninfo"):
                lines.append(format_section("🏰 Clan Info", data["claninfo"][0]))
                lines.append("")

            if data.get("clanadmin"):
                lines.append(format_section("🛡️ Clan Admin Info", data["clanadmin"][0]))
                lines.append("")

            if data.get("credit"):
                lines.append(f"<i>Credit: {escape_html(data['credit'])}</i>")

            text = "\n".join(lines)

        bot.edit_message_text(
            text,
            chat_id=chat_id,
            message_id=status_msg.message_id,
            parse_mode="HTML"
        )

    except Exception as e:
        bot.edit_message_text(
            f"<b>Failed to fetch data:</b> {escape_html(str(e))}",
            chat_id=chat_id,
            message_id=status_msg.message_id,
            parse_mode="HTML"
        )

@bot.message_handler(commands=['baninfo'])
def handle_baninfo(message):
    chat_id = message.chat.id

    if message.chat.type == "private":
        bot.reply_to(message, "This bot cannot be used in private chats.")
        return

    if chat_id not in ALLOWED_GROUP_IDS:
        bot.reply_to(message, "This group is not authorized to use this bot.")
        return

    parts = message.text.strip().split()
    if len(parts) != 2:
        bot.reply_to(message, "Usage: /baninfo <UID>")
        return

    uid = parts[1]

    # Send "checking..." message and save the sent message to edit later
    status_msg = bot.reply_to(message, "<i>Checking if banned or not...</i>", parse_mode="HTML")

    try:
        res = requests.get(BAN_CHK_URL, params={"uid": uid})
        data = res.json()

        if "error" in data:
            new_text = f"<b>Error</b>: {escape_html(data['error'])}"
        else:
            new_text = (
                f"<b>Nickname</b>: {escape_html(data['nickname'])}\n"
                f"<b>Region</b>: {escape_html(data['region'])}\n"
                f"<b>Ban Status</b>: {escape_html(data['ban_status'])}"
            )
            if data.get("ban_period"):
                new_text += f"\n<b>Ban Period</b>: {escape_html(data['ban_period'])}"

        # Edit the message with final result
        bot.edit_message_text(new_text, chat_id=chat_id, message_id=status_msg.message_id, parse_mode="HTML")

    except Exception as e:
        bot.edit_message_text(
            f"<b>Failed to fetch data:</b> {escape_html(str(e))}",
            chat_id=chat_id,
            message_id=status_msg.message_id,
            parse_mode="HTML"
        )

@bot.message_handler(commands=['spam'])
def handle_spam(message):
    # Check if message is from private chat
    if message.chat.type == "private":
        bot.reply_to(message, "Sorry, this command is not available in private chat.")
        return

    # Check if group is authorized
    if message.chat.id not in ALLOWED_GROUP_IDS:
        bot.reply_to(message, "This group is not authorized to use this bot.")
        return

    # Get UID from command
    try:
        uid = message.text.split()[1]
    except IndexError:
        bot.reply_to(message, "Please provide a UID. Usage: /spam <uid>")
        return

    # Call the API
    url = f"https://sanatani-ff-api.vercel.app/spam?uid={uid}"
    try:
        response = requests.get(url)
        data = response.json()
        msg = (
            f"**SPAM Result**\n"
            f"Credit: {data.get('cradit')}\n"
            f"Success: {data.get('success_count')}\n"
            f"Failed: {data.get('failed_count')}"
        )
        bot.reply_to(message, msg, parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, "API call failed or invalid response.")

def is_authorized(chat_id):
    return chat_id in ALLOWED_GROUP_IDS

@bot.message_handler(commands=['banner'])
def handle_banner(message):
    chat_id = message.chat.id

    if not is_authorized(chat_id):
        bot.reply_to(message, "Sorry, this bot can only be used in authorized groups.")
        return

    try:
        args = message.text.split()
        if len(args) != 3:
            bot.reply_to(message, "Usage: /banner <uid> <region>", reply_to_message_id=message.message_id)
            return

        uid = args[1]
        region = args[2]
        url = f"https://aditya-banner-v6op.onrender.com/banner-image?uid={uid}&region={region}"

        response = requests.get(url)
        if response.status_code == 200:
            img = Image.open(BytesIO(response.content)).convert("RGBA")
            img.thumbnail((512, 512))
            output = BytesIO()
            output.name = "sticker.webp"
            img.save(output, format="WEBP")
            output.seek(0)

            # Send sticker as reply to user's message
            bot.send_sticker(chat_id, output, reply_to_message_id=message.message_id)
        else:
            bot.reply_to(message, "Failed to fetch banner.", reply_to_message_id=message.message_id)
    except Exception as e:
        bot.reply_to(message, f"Error: {str(e)}", reply_to_message_id=message.message_id)

@bot.message_handler(func=lambda m: m.chat.type == 'private')
def block_private(message):
    bot.send_message(message.chat.id, "You can't use this bot in private chat.")

@bot.message_handler(commands=['allowgroup'])
def allow_group(msg):
    if not is_owner(msg.from_user.id):
        return safe_reply(msg, "❌ You do not have permission to use this command.")
    parts = msg.text.strip().split()
    if len(parts) != 3:
        return safe_reply(msg, "❗ Usage: /allowgroup group_id limit\nExample: /allowgroup -1001234567890 10")
    try:
        group_id = int(parts[1])
        limit = int(parts[2])
    except ValueError:
        return safe_reply(msg, "⚠️ Invalid group ID or limit. Both must be numbers.")
    ALLOWED_GROUP_IDS.add(group_id)
    group_limits[group_id] = limit
    safe_reply(msg, f"✅ Group `{group_id}` is now allowed with a daily limit of {limit} likes.", parse_mode="Markdown")

@bot.message_handler(commands=['vip'])
@restricted_group
def add_vip(msg):
    if not is_owner(msg.from_user.id):
        return safe_reply(msg, "❌ You do not have permission to use this command.")
    parts = msg.text.strip().split()
    if len(parts) != 4:
        return safe_reply(msg, "❗ Usage: /vip user_id limit days\nExample: /vip 123456789 10 30")
    try:
        user_id = int(parts[1])
        limit = int(parts[2])
        days = int(parts[3])
    except ValueError:
        return safe_reply(msg, "⚠️ Invalid input. user_id, limit, and days must be numbers.")
    expiry = datetime.datetime.now().date() + datetime.timedelta(days=days)
    allowed_users[user_id] = {"limit": limit, "expires": expiry}
    safe_reply(msg, f"✅ User `{user_id}` is now VIP with limit {limit} for {days} days.", parse_mode="Markdown")

@bot.message_handler(commands=['like'])
@restricted_group
def like_cmd(msg):
    global remaining_likes
    check_reset()
    user_id = msg.from_user.id
    chat_id = msg.chat.id

    parts = msg.text.strip().split()
    if len(parts) != 3:
        return safe_reply(msg, "❗ *Usage:* `/like region uid`\n*Example:* `/like ind 1877437384`", parse_mode="Markdown")

    region, uid = parts[1].lower(), parts[2]

    if not uid.isdigit():
        return safe_reply(msg, "❌ Invalid UID.")

    if daily_usage.get(user_id, 0) >= get_limit(user_id, chat_id):
        return safe_reply(msg,
            "🛑 *Aapka daily like limit khatam ho gaya hai.* \n"
            "💎 VIP access ke liye contact karo [SANATANI_x_ANONYMOUS](https://t.me/sanatani_x_anonymouss)",
            parse_mode="Markdown"
        )

    if remaining_likes <= 0:
        return safe_reply(msg, "❌ No more likes remaining for today.")

    status_msg = safe_reply(msg, "🔄 Sending like request... Please wait...")

    url = API_URL.format(region=region, uid=uid)

    try:
        res = requests.get(url, timeout=10)
        data = res.json()
    except:
        return bot.edit_message_text(
            "❌ THIS BOT IS ONLY WORK FOR INDIAN SERVER 🗿.",
            chat_id,
            status_msg.message_id
        )

    if data.get("status") == 1:
        daily_usage[user_id] = daily_usage.get(user_id, 0) + 1
        remaining_likes -= 1
        reply = (
            f"```\n"
            f"OWNER: {data.get('OWNER', 'NULL')}\n"
            f"Partner: {data.get('Guest Acc. Maintainer', 'NULL')}\n"
            f"UID: {data.get('UID', 'N/A')}\n"
            f"NAME: {data.get('PlayerNickname', 'Unknown')}\n\n"
            f"LIKE DETAILS\n\n"
            f"LIKE AFTER: {data.get('LikesafterCommand', '0')}\n"
            f"LIKE BEFORE: {data.get('LikesbeforeCommand', '0')}\n"
            f"LIKE GIVEN: {data.get('LikesGivenByAPI', '0')}\n"
            f"```\n"
            "Player got daily 100 likes | subs [YOUTUBE](https://youtube.com/@sanatanihackers?si=C2K1nRHZ74tjgjbp) | "
            "More info: [VIP LIKE SxA](https://t.me/sanatani_x_anonymouss) | @sanatani\\_x\\_anonymouss | "
            "Join Our Official Like Group For Daily Likes [LINK](https://t.me/sanatani_ff_like_gc)"
        )
        bot.edit_message_text(reply, chat_id, status_msg.message_id, parse_mode="Markdown")
    else:
        bot.edit_message_text("❌ *Like limit reached for this UID.*", chat_id, status_msg.message_id, parse_mode="Markdown")

@bot.message_handler(commands=['remain'])
@restricted_group
def remain_cmd(msg):
    safe_reply(msg, f"🔢 *Remaining Likes:* `{remaining_likes}`", parse_mode="Markdown")

@bot.message_handler(commands=['setremain'])
@restricted_group
def setremain_cmd(msg):
    global remaining_likes
    if not is_owner(msg.from_user.id):
        return safe_reply(msg, "❌ You are not allowed to use this command.")
    parts = msg.text.strip().split()
    if len(parts) != 2 or not parts[1].isdigit():
        return safe_reply(msg, "❌ Usage: /setremain 30", parse_mode="Markdown")
    remaining_likes = int(parts[1])
    safe_reply(msg, f"✅ *Remaining Likes updated to:* `{remaining_likes}`", parse_mode="Markdown")

@bot.message_handler(commands=['promo'])
@restricted_group
def promo_cmd(msg):
    promo = (
        "Player got daily 100 likes | subs [YOUTUBE](https://youtube.com/@sanatanihackers?si=C2K1nRHZ74tjgjbp) | "
        "More info: [VIP LIKE SxA](https://t.me/sanatani_x_anonymouss) | @sanatani\\_x\\_anonymouss"
    )
    safe_reply(msg, promo, parse_mode="Markdown", disable_web_page_preview=True)

@bot.message_handler(commands=['id'])
@restricted_group
def get_id(msg):
    safe_reply(msg, f"🆔 Chat ID: `{msg.chat.id}`", parse_mode="Markdown")

@bot.message_handler(commands=['help'])
@restricted_group
def help_command(msg):
    help_text = (
        "🤖 *Like Bot Help Menu*\n\n"
        "🔹 `/like region uid`\nSend 100 likes to a UID.\n*Example:* `/like ind 1877437384`\n\n"
        "🔹 `/spam uid`\nSend Friend Request Spam.\n*Example:* `/spam 1877437384`\n\n"
        "🔹 `/banner uid region`\nFetch Banner and Avatar.\n*Example:* `/banner 1877437384 ind`\n\n"
        "🔹 `/player uid region`\nFetch complete player profile info.\n*Example:* `/player 1877437384 ind`\n\n"
        "🔹 `/baninfo uid`\nCheck if a user is banned or not.\n*Example:* `/baninfo 1877437384`\n\n"
        "🔹 `/vip user_id limit days`\nMake user VIP with custom daily like limit.\n\n"
        "🔹 `/allowgroup group_id limit`\nAllow a group to use the bot.\n\n"
        "🔹 `/remain`\nShow remaining global likes for today.\n\n"
        "🔹 `/setremain count`\n(Owners only) Set remaining likes.\n\n"
        "🔹 `/promo`\nShow promo message.\n\n"
        "💎 *For VIP access*, contact [SANATANI_x_ANONYMOUS](https://t.me/sanatani_x_anonymouss)"
    )

    safe_reply(msg, help_text, parse_mode="Markdown")

@bot.message_handler(content_types=['new_chat_members'])
def welcome_new_members(message):
    for new_user in message.new_chat_members:
        name = new_user.first_name
        chat_id = message.chat.id
        help_text = (
        "🤖 *Like Bot Help Menu*\n\n"
        "🔹 `/like region uid`\nSend 100 likes to a UID.\n*Example:* `/like ind 1877437384`\n\n"
        "🔹 `/spam uid`\nSend Friend Request Spam.\n*Example:* `/spam 1877437384`\n\n"
        "🔹 `/banner uid region`\nFetch Banner and Avatar.\n*Example:* `/banner 1877437384 ind`\n\n"
        "🔹 `/player uid region`\nFetch complete player profile info.\n*Example:* `/player 1877437384 ind`\n\n"
        "🔹 `/baninfo uid`\nCheck if a user is banned or not.\n*Example:* `/baninfo 1877437384`\n\n"
        "💎 *For VIP access*, contact [SANATANI_x_ANONYMOUS](https://t.me/sanatani_x_anonymouss)"
    )
        bot.send_message(chat_id, help_text, parse_mode="Markdown")

@bot.message_handler(content_types=['new_chat_members'])
def delete_join_message(message):
    try:
        bot.delete_message(message.chat.id, message.message_id)
    except Exception as e:
        print(f"Failed to delete join message: {e}")

@bot.message_handler(content_types=['left_chat_member'])
def delete_leave_message(message):
    try:
        bot.delete_message(message.chat.id, message.message_id)
    except Exception as e:
        print(f"Failed to delete leave message: {e}")

@app.route('/')
def home():
    return "Bot is running!"

# Thread to keep bot polling
def run_bot():
    print("Bot polling started...")
    bot.polling(non_stop=True)

if __name__ == "__main__":
    threading.Thread(target=run_bot).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
