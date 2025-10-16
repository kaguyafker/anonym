from telegram import Update, Message, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import logging
import os

# Enable logging
logging.basicConfig(level=logging.INFO)

# Bot token and owner ID
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = 7403104782

# Global storage
dump_channel_id = None
main_channels = set()
pending_messages = {}

# Owner-only decorator
def owner_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id != OWNER_ID:
            await update.message.reply_text("🚫 You are not authorized to use this command.")
            return
        return await func(update, context)
    return wrapper

@owner_only
async def set_dump(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global dump_channel_id
    if context.args:
        dump_channel_id = int(context.args[0])
        await update.message.reply_text(f"✅ Dump channel set to {dump_channel_id}")
    else:
        await update.message.reply_text("❌ Usage: /set <channel_id>")

@owner_only
async def add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        channel_id = int(context.args[0])
        main_channels.add(channel_id)
        await update.message.reply_text(f"✅ Channel {channel_id} added to forward list")
    else:
        await update.message.reply_text("❌ Usage: /add <channel_id>")

@owner_only
async def allow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.reply_to_message:
        original_msg_id = update.message.reply_to_message.message_id
        if original_msg_id in pending_messages:
            msg_text = pending_messages.pop(original_msg_id)
            for channel_id in main_channels:
                try:
                    await context.bot.send_message(chat_id=channel_id, text=msg_text)
                except Exception as e:
                    logging.warning(f"Failed to send to {channel_id}: {e}")
            await update.message.reply_text("✅ Message forwarded to allowed channels.")
        else:
            await update.message.reply_text("❌ No pending message found.")
    else:
        await update.message.reply_text("❌ Reply to a message with /allow to approve it.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global dump_channel_id
    msg: Message = update.message
    if dump_channel_id:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Allow", callback_data=f"allow:{msg.text}"),
             InlineKeyboardButton("❌ Reject", callback_data="reject")]
        ])
        sent = await context.bot.send_message(chat_id=dump_channel_id, text=msg.text, reply_markup=keyboard)
        pending_messages[sent.message_id] = msg.text
    else:
        await msg.reply_text("❌ Dump channel not set. Use /set <channel_id>.")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if user_id != OWNER_ID:
        await query.message.reply_text("🚫 You are not authorized to moderate this message.")
        return

    if data.startswith("allow:"):
        msg_text = data.split("allow:")[1]
        for channel_id in main_channels:
            try:
                await context.bot.send_message(chat_id=channel_id, text=msg_text)
            except Exception as e:
                logging.warning(f"Failed to send to {channel_id}: {e}")
        await query.edit_message_reply_markup(None)
        await query.message.reply_text("✅ Message forwarded.")
    elif data == "reject":
        await query.edit_message_reply_markup(None)
        await query.message.reply_text("❌ Message rejected.")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("set", set_dump))
    app.add_handler(CommandHandler("add", add_channel))
    app.add_handler(CommandHandler("allow", allow))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("🤖 Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
