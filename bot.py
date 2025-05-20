from flask import Flask
import os
import threading
import telebot
import requests
import datetime
import pytz
import time

# Configuration
BOT_TOKEN = "7799333321:AAFnYX39VqF615G0I19SRxCQqQamV3BwHPM"
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

AUTHORIZED_OWNERS = [7798805438]  # Add all admin IDs
ALLOWED_GROUP_IDS = {-1002255896839}
REQUIRED_JOIN_GROUP = -1002255896839
DEFAULT_DAILY_LIMIT = 1
remaining_likes = 30  # For global counter

# State
group_limits = {}
verified_users = set()
daily_usage = {}
allowed_users = {}
last_reset = datetime.datetime.now().date()

API_URL = "https://sanatani-ff-api.vercel.app//like?uid={uid}&server_name={region}"

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

def restricted_group(func):
    def wrapper(msg):
        if not is_group_allowed(msg.chat.id, msg.from_user.id):
            return safe_reply(msg, "❌ This bot is restricted to specific groups only.")
        if not is_user_joined(msg.from_user.id):
            return safe_reply(
                msg,
                "📛 *To use this bot, please join our Youtube Channel first:*\n"
                "🔗 [Join](https://youtube.com/@sanatanihackers?si=C2K1nRHZ74tjgjbp)\n\n"
                "✅ After joining, resend your command.",
                parse_mode="Markdown",
                disable_web_page_preview=True
            )
        return func(msg)
    return wrapper

# Commands

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
            f"UID: {data.get('UID', 'N/A')}\n"
            f"NAME: {data.get('PlayerNickname', 'Unknown')}\n\n"
            f"LIKE DETAILS\n\n"
            f"LIKE AFTER: {data.get('LikesafterCommand', '0')}\n"
            f"LIKE BEFORE: {data.get('LikesbeforeCommand', '0')}\n"
            f"LIKE GIVEN: {data.get('LikesGivenByAPI', '0')}\n"
            f"```\n"
            "Player got daily 100 likes | subs [YOUTUBE](https://youtube.com/@sanatanihackers?si=C2K1nRHZ74tjgjbp) | "
            "More info: [VIP LIKE SxA](https://t.me/sanatani_x_anonymouss) | @sanatani\\_x\\_anonymouss"
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
        "🔹 `/like region uid`\nSend 100 likes to a UID.\n*Example:* `/like bd 123456789`\n\n"
        "🔹 `/vip user_id limit days`\nMake user VIP with custom daily like limit.\n\n"
        "🔹 `/allowgroup group_id limit`\nAllow a group to use the bot.\n\n"
        "🔹 `/remain`\nShow remaining global likes for today.\n\n"
        "🔹 `/setremain count`\n(Owners only) Set remaining likes.\n\n"
        "🔹 `/promo`\nShow promo message.\n\n"
        "💎 *For VIP access*, contact [SANATANI_x_ANONYMOUS](https://t.me/sanatani_x_anonymouss)"
    )
    safe_reply(msg, help_text, parse_mode="Markdown")



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
