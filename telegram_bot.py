import os
import time
import logging
import threading
import asyncio
import nest_asyncio  # <--- ADD THIS IMPORT
from flask import Flask
from selenium import webdriver
# ... all other imports are the same ...

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# ... THE REST OF YOUR CODE IS IDENTICAL ...
# ... NO OTHER CHANGES ARE NEEDED UNTIL THE VERY BOTTOM ...


# --- NEW: Main execution logic ---

def run_flask():
    """Runs the Flask web server in a separate thread."""
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

async def main():
    """Sets up and runs the Telegram bot."""
    nest_asyncio.apply()  # <--- ADD THIS LINE TO FIX THE ERROR

    if not TELEGRAM_TOKEN:
        print("Error: TELEGRAM_TOKEN environment variable not set!")
        return

    # Run Flask in a separate thread
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    print(f"Web server started in a background thread.")

    # Set up the bot application
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            GETTING_BILL_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_bill_id)],
            GETTING_CAPTCHA: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_captcha)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(conv_handler)
    
    # Run the bot
    print("Bot is starting polling...")
    await application.run_polling()


if __name__ == "__main__":
    asyncio.run(main())
