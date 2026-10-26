import os
import random
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Dice
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Environment Variables
TOKEN = os.getenv("BOT_TOKEN")
# Optional: Require users to join a channel to get daily rewards / play
REQUIRED_CHANNEL_ID = os.getenv("REQUIRED_CHANNEL_ID")  # e.g., "@yourchannel" or "-100123456789"
CHANNEL_LINK = os.getenv("CHANNEL_LINK", "https://t.me/yourchannel")

# In-memory database (For production, consider SQLite, PostgreSQL, or Redis)
user_balances = {}
daily_claimed = {}

def get_balance(user_id: int) -> int:
    return user_balances.get(user_id, 100)  # Default starting bonus: 100 coins

def update_balance(user_id: int, amount: int):
    user_balances[user_id] = get_balance(user_id) + amount

async def check_membership(bot, user_id: int) -> bool:
    """Checks if the user is a member of the required channel."""
    if not REQUIRED_CHANNEL_ID:
        return True
    try:
        member = await bot.get_chat_member(chat_id=REQUIRED_CHANNEL_ID, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        logger.error(f"Error checking channel membership: {e}")
        return True

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command and main menu."""
    user = update.effective_user
    balance = get_balance(user.id)
    
    keyboard = [
        [InlineKeyboardButton("🎰 Spin Slots (Bet 10)", callback_data="play_slots")],
        [InlineKeyboardButton("🎲 Roll Dice (Bet 10)", callback_data="play_dice")],
        [InlineKeyboardButton("🎁 Claim Daily Bonus", callback_data="claim_daily")],
        [InlineKeyboardButton("💰 Check Balance", callback_data="check_balance")],
        [InlineKeyboardButton("📢 Join Channel for Updates", url=CHANNEL_LINK)],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    welcome_text = (
        f"👋 Welcome to the Lucky Casino Bot, {user.first_name}!\n\n"
        f"💳 Your Balance: **{balance} coins**\n\n"
        "Play games, boost your points, and claim your daily rewards!"
    )

    if update.message:
        await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.message.edit_text(welcome_text, parse_mode="Markdown", reply_markup=reply_markup)

async def check_balance_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    balance = get_balance(query.from_user.id)
    await query.message.reply_text(f"💰 Current balance: **{balance} coins**", parse_mode="Markdown")

async def claim_daily_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    # Check Channel Subscription
    if REQUIRED_CHANNEL_ID and not await check_membership(context.bot, user_id):
        keyboard = [[InlineKeyboardButton("📢 Join Channel", url=CHANNEL_LINK)]]
        await query.message.reply_text(
            "🔒 You must join our official channel to claim your daily bonus!",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    # Check daily cooldown (simplified for session; key by date/day in real app)
    if daily_claimed.get(user_id):
        await query.message.reply_text("⏳ You have already claimed your daily bonus today! Come back tomorrow.")
        return

    bonus = 50
    update_balance(user_id, bonus)
    daily_claimed[user_id] = True
    await query.message.reply_text(f"🎁 Success! You received **+{bonus} coins** as a daily bonus!", parse_mode="Markdown")

async def play_slots_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    bet_amount = 10

    if get_balance(user_id) < bet_amount:
        await query.message.reply_text("❌ You don't have enough coins to place this bet. Claim your daily bonus!")
        return

    # Deduct bet
    update_balance(user_id, -bet_amount)

    # Send Telegram native slot machine animation
    msg = await query.message.reply_dice(emoji="🎰")
    val = msg.dice.value

    # Telegram Slot values: 1 (BAR BAR BAR), 64 (7 7 7), etc.
    # Jackpot combinations: 1 (Bar), 22 (Grapes), 43 (Lemon), 64 (777)
    if val == 64:  # Triple 777 Jackpot
        win = 100
        update_balance(user_id, win)
        result_text = f"🎉 **JACKPOT (777)!** You won **+{win} coins**!"
    elif val in [1, 22, 43]:  # Match 3 non-7s
        win = 40
        update_balance(user_id, win)
        result_text = f"🥳 **GREAT WIN!** You won **+{win} coins**!"
    elif val in [16, 32, 48]:  # Two matching symbols
        win = 15
        update_balance(user_id, win)
        result_text = f"✨ **MINI WIN!** You won **+{win} coins**!"
    else:
        result_text = f"💔 No match. You lost {bet_amount} coins. Try again!"

    await query.message.reply_text(result_text, parse_mode="Markdown")

async def play_dice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    bet_amount = 10

    if get_balance(user_id) < bet_amount:
        await query.message.reply_text("❌ Insufficient balance to play.")
        return

    update_balance(user_id, -bet_amount)
    msg = await query.message.reply_dice(emoji="🎲")
    val = msg.dice.value

    if val >= 4:
        win = 20
        update_balance(user_id, win)
        result_text = f"🎲 You rolled a **{val}**! You won **+{win} coins**!"
    else:
        result_text = f"🎲 You rolled a **{val}**. Better luck next time!"

    await query.message.reply_text(result_text, parse_mode="Markdown")

def main():
    if not TOKEN:
        raise ValueError("BOT_TOKEN environment variable is missing!")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(start, pattern="^main_menu$"))
    app.add_handler(CallbackQueryHandler(check_balance_handler, pattern="^check_balance$"))
    app.add_handler(CallbackQueryHandler(claim_daily_handler, pattern="^claim_daily$"))
    app.add_handler(CallbackQueryHandler(play_slots_handler, pattern="^play_slots$"))
    app.add_handler(CallbackQueryHandler(play_dice_handler, pattern="^play_dice$"))

    logger.info("Bot started successfully...")
    app.run_polling()

if __name__ == "__main__":
    main()
