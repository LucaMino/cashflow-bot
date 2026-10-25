import asyncio
import logging

from telegram import Update
from telegram.ext import ContextTypes

from config import settings
from llm import run

log = logging.getLogger(__name__)

HELP = (
    "Tell me about your expenses and income in plain language.\n\n"
    "Record:\n"
    "• coffee 1.20 and fuel 40\n"
    "• yesterday pizza 12.50\n"
    "• salary 1800\n\n"
    "Ask:\n"
    "• how much did I spend this month?\n"
    "• how much on food in September?\n"
    "• show me last week's expenses\n\n"
)


async def on_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(HELP)


async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if msg is None or msg.text is None:
        return
    # get the tools from the bot_data
    tools = ctx.application.bot_data["tools"]
    # show typing action while processing the request
    await msg.chat.send_action("typing")
    try:
        # run the LLM in a separate thread to avoid blocking the event loop
        reply = await asyncio.to_thread(run, msg.text, tools, settings.llm_model, settings.tz)
    except Exception:
        log.exception("run failed")
        reply = "Sorry, something went wrong. Try again later."
    await msg.reply_text(reply or "Done.")
