import os
import logging
import traceback
from collections import defaultdict
from typing import DefaultDict, Dict
from dotenv import load_dotenv
from telegram import Update, LabeledPrice, InlineKeyboardButton, InlineKeyboardMarkup, Message
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    PreCheckoutQueryHandler,
    CallbackContext
)

from config import ITEMS, MESSAGES

load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

STATS: Dict[str, DefaultDict[str, int]] = {
    'purchases': defaultdict(int),
    'refunds': defaultdict(int)
}


async def start(update: Update, context: CallbackContext) -> None:
    keyboard = [
        [InlineKeyboardButton(f"{item['name']} - {item['price']} ⭐", callback_data=item_id)]
        for item_id, item in ITEMS.items()
    ]
    await update.message.reply_text(MESSAGES['welcome'], reply_markup=InlineKeyboardMarkup(keyboard))


async def help_command(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text(MESSAGES['help'], parse_mode='Markdown')


async def refund_command(update: Update, context: CallbackContext) -> None:
    if not context.args:
        await update.message.reply_text(MESSAGES['refund_usage'])
        return

    try:
        charge_id = context.args[0]
        user_id = update.effective_user.id

        success = await context.bot.refund_star_payment(
            user_id=user_id,
            telegram_payment_charge_id=charge_id
        )

        if success:
            STATS['refunds'][str(user_id)] += 1
            await update.message.reply_text(MESSAGES['refund_success'])
        else:
            await update.message.reply_text(MESSAGES['refund_failed'])

    except Exception as e:
        logger.error(traceback.format_exc())
        await update.message.reply_text(f"❌ Error: {e}")


async def button_handler(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()

    item_id = query.data
    item = ITEMS.get(item_id)
    if not item:
        return

    await context.bot.send_invoice(
        chat_id=query.message.chat_id,
        title=item['name'],
        description=item['description'],
        payload=item_id,
        provider_token="",  # Leave empty for Telegram Stars
        currency="XTR",
        prices=[LabeledPrice(item['name'], int(item['price']))],
        start_parameter="start"
    )


async def precheckout_callback(update: Update, context: CallbackContext) -> None:
    query = update.pre_checkout_query
    if query.invoice_payload in ITEMS:
        await query.answer(ok=True)
    else:
        await query.answer(ok=False, error_message="Invalid item.")


async def successful_payment_callback(update: Update, context: CallbackContext) -> None:
    payment = update.message.successful_payment
    item = ITEMS[payment.invoice_payload]
    user_id = update.effective_user.id
    STATS['purchases'][str(user_id)] += 1

    await update.message.reply_text(
        f"🎉 Payment successful!\n\n"
        f"`{item['secret']}` is your secret code for {item['name']}.\n"
        f"Use /refund {payment.telegram_payment_charge_id} if you need a refund.",
        parse_mode='Markdown'
    )


async def error_handler(update: object, context: CallbackContext) -> None:
    logger.error(f"Update caused error: {context.error}")


def main():
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("refund", refund_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))

    application.add_error_handler(error_handler)

    logger.info("Bot is running")
    application.run_polling()


if __name__ == "__main__":
    main()
