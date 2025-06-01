import base64
import requests
from datetime import datetime, timedelta
from telegram.ext import Updater, CommandHandler, ConversationHandler, MessageHandler, Filters

# --- Tokens ---
BOT_TOKEN = "8189332133:AAFMeX5HxkMPqmYDRNOHs8W8JlhzQJRmVhE"
GITHUB_TOKEN = "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"
ADMIN_ID = 6987518006  # Replace with your Telegram ID

# --- GitHub repo config ---
REPO_OWNER = "iuxix"
REPO_NAME = "Paid-file"
FILE_PATH = "users"
BRANCH = "main"

# --- Timezone (IST) ---
IST = timedelta(hours=5, minutes=30)

# --- States ---
CHOOSING, USER_ID, DAYS, TIME, DELETE_ID = range(5)

# --- Operation state ---
operation_mode = {}

# --- GitHub Helpers ---
def get_file_info():
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}?ref={BRANCH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    res = requests.get(url, headers=headers)
    return res.json() if res.status_code == 200 else None

def update_file(new_content, sha, message):
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    data = {
        "message": message,
        "content": base64.b64encode(new_content.encode()).decode(),
        "sha": sha,
        "branch": BRANCH
    }
    res = requests.put(url, json=data, headers=headers)
    return res.status_code in [200, 201]

def generate_expiry_line(user_id, days, time_str):
    try:
        expiry_time = datetime.strptime(time_str, "%H:%M").time()
    except:
        return None
    expiry_date = (datetime.utcnow() + IST + timedelta(days=days)).date()
    expiry_datetime = datetime.combine(expiry_date, expiry_time)
    return f"{user_id} , {expiry_datetime.strftime('%Y-%m-%d : %H:%M')}"

# --- Command handlers ---
def is_admin(update):
    return update.message.from_user.id == ADMIN_ID

def start(update, context):
    if not is_admin(update):
        update.message.reply_text("🚫 Access Denied.")
        return ConversationHandler.END
    update.message.reply_text(
        "✨ Welcome Admin\n\n"
        "/add_user - Add premium user\n"
        "/delete_user - Delete user\n"
        "/list_users - List all users\n"
        "/cancel - Cancel operation"
    )
    return CHOOSING

def add_user(update, context):
    if not is_admin(update): return
    operation_mode[update.effective_chat.id] = "add"
    update.message.reply_text("🆔 Send the user ID to add:")
    return USER_ID

def delete_user(update, context):
    if not is_admin(update): return
    operation_mode[update.effective_chat.id] = "delete"
    update.message.reply_text("🗑️ Send the user ID to delete:")
    return DELETE_ID

def list_users(update, context):
    if not is_admin(update): return
    data = get_file_info()
    if not data:
        update.message.reply_text("❌ Couldn't fetch user list.")
        return

    try:
        lines = base64.b64decode(data["content"]).decode().splitlines()
    except:
        update.message.reply_text("❌ Couldn't decode user file.")
        return

    if not lines:
        update.message.reply_text("📭 No users found.")
        return

    msg = "📄 *User List:*\n"
    count = 0
    for line in lines:
        parts = [x.strip() for x in line.split(",")]
        if len(parts) != 2:
            continue  # skip malformed lines
        uid, exp = parts
        msg += f"• `{uid}` → ⏳ *{exp}*\n"
        count += 1

    if count == 0:
        update.message.reply_text("📭 No valid users found.")
    else:
        update.message.reply_text(msg, parse_mode="Markdown")

def receive_user_id(update, context):
    context.user_data["user_id"] = update.message.text.strip()
    update.message.reply_text("📆 How many days to grant?")
    return DAYS

def receive_days(update, context):
    try:
        context.user_data["days"] = int(update.message.text.strip())
    except:
        update.message.reply_text("❌ Invalid number. Try again:")
        return DAYS
    update.message.reply_text("🕒 Enter expiry time (HH:MM, 24h):")
    return TIME

def receive_time(update, context):
    user_id = context.user_data["user_id"]
    days = context.user_data["days"]
    time_str = update.message.text.strip()
    line = generate_expiry_line(user_id, days, time_str)
    if not line:
        update.message.reply_text("❌ Invalid time format.")
        return TIME
    data = get_file_info()
    if not data:
        update.message.reply_text("❌ GitHub fetch failed.")
        return ConversationHandler.END
    sha = data["sha"]
    lines = base64.b64decode(data["content"]).decode().splitlines()
    updated = False
    for i, l in enumerate(lines):
        if l.startswith(user_id):
            lines[i] = line
            updated = True
            break
    if not updated:
        lines.append(line)
    success = update_file("\n".join(lines) + "\n", sha, f"Add {user_id}")
    if success:
        update.message.reply_text(f"✅ Access {'updated' if updated else 'granted'} for {user_id}")
    else:
        update.message.reply_text("❌ GitHub update failed.")
    return ConversationHandler.END

def receive_delete(update, context):
    user_id = update.message.text.strip()
    data = get_file_info()
    if not data:
        update.message.reply_text("❌ GitHub fetch failed.")
        return ConversationHandler.END
    sha = data["sha"]
    lines = base64.b64decode(data["content"]).decode().splitlines()
    new_lines = [l for l in lines if not l.startswith(user_id)]
    if len(new_lines) == len(lines):
        update.message.reply_text("⚠️ User not found.")
        return ConversationHandler.END
    success = update_file("\n".join(new_lines) + "\n", sha, f"Delete {user_id}")
    update.message.reply_text("🗑️ User deleted." if success else "❌ Deletion failed.")
    return ConversationHandler.END

def cancel(update, context):
    update.message.reply_text("❌ Cancelled.")
    return ConversationHandler.END

# --- Main entry ---
def main():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING: [
                CommandHandler("add_user", add_user),
                CommandHandler("delete_user", delete_user),
                CommandHandler("list_users", list_users)
            ],
            USER_ID: [MessageHandler(Filters.text & ~Filters.command, receive_user_id)],
            DAYS: [MessageHandler(Filters.text & ~Filters.command, receive_days)],
            TIME: [MessageHandler(Filters.text & ~Filters.command, receive_time)],
            DELETE_ID: [MessageHandler(Filters.text & ~Filters.command, receive_delete)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    dp.add_handler(conv)
    dp.add_handler(CommandHandler("list_users", list_users))
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
