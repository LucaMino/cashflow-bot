from dotenv import load_dotenv

# first of all: litellm reads API keys from os.environ
load_dotenv()

import logging
import sys

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from config import Settings
from handlers import on_start, on_text
from sheet import open_sheet
from tools import build_tools

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
# set to WARNING to prevent httpx from logging URLs containing tokens
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("LiteLLM").setLevel(logging.WARNING)


def main() -> None:
    settings = Settings()  # type: ignore[call-arg]
    sheet = open_sheet(settings.google_sa_json, settings.sheet_id, settings.sheet_tab)
    app = Application.builder().token(settings.tg_token).build()
    app.bot_data["settings"] = settings
    app.bot_data["tools"] = build_tools(sheet, settings.category_list, settings.payment_method_list)

    # only allow the bot to be used in private chat by the allowed users
    only_me = filters.User(user_id=settings.allowed_ids) & filters.ChatType.PRIVATE
    # add handlers for /start and text messages
    app.add_handler(CommandHandler("start", on_start, filters=only_me))
    app.add_handler(MessageHandler(only_me & filters.TEXT & ~filters.COMMAND, on_text))

    # run the bot in polling mode if "poll" is in the command line arguments, otherwise use webhook mode
    if "poll" in sys.argv:
        app.run_polling(allowed_updates=Update.ALL_TYPES)
        return

    app.run_webhook(
        listen="0.0.0.0",  # all interfaces: the reverse proxy reaches the app from outside the container
        port=settings.port,
        url_path="webhook",
        webhook_url=f"{settings.webhook_url.rstrip('/')}/webhook",
        secret_token=settings.tg_webhook_secret,
        allowed_updates=["message"],  # only receive messages, not other updates
    )


if __name__ == "__main__":
    main()
