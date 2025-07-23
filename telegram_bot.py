import os
import time
import logging
import threading
import asyncio
import nest_asyncio
from flask import Flask
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.service import Service as ChromeService

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# --- Flask Web Server Setup ---
app = Flask(__name__)
@app.route('/')
def health_check():
    return "Bot is running and web server is healthy.", 200

# --- Bot Configuration ---
URL = "https://modiriattolid.goped.ir/"

# XPath locators
BILL_ID_XPATH = "/html/body/div[2]/form/div/div[2]/input"
CAPTCHA_FIELD_XPATH = "/html/body/div[2]/form/div/div[3]/div/div/input"
CAPTCHA_IMAGE_XPATH = "/html/body/div[2]/form/div/div[3]/div/img"
SEARCH_BUTTON_XPATH = "/html/body/div[2]/form/div/div[4]/a"
RESULTS_TABLE_XPATH = "/html/body/div[3]/div/div/div[2]/div[2]/table"

# Conversation states
GETTING_BILL_ID, GETTING_CAPTCHA = range(2)

# --- Selenium Setup ---
def get_driver():
    """Sets up the Chrome driver for the Docker environment."""
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    # The Dockerfile now installs chromedriver, so we don't need webdriver-manager
    return webdriver.Chrome(service=ChromeService(), options=chrome_options)

# --- Bot Functions ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("سلام! لطفاً شناسه قبض ۱۳ رقمی خود را وارد کنید.")
    return GETTING_BILL_ID

async def get_bill_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    bill_id = update.message.text
    if not bill_id.isdigit() or len(bill_id) != 13:
        await update.message.reply_text("خطا: شناسه قبض باید یک عدد ۱۳ رقمی باشد. لطفاً دوباره تلاش کنید.")
        return GETTING_BILL_ID
    context.user_data['bill_id'] = bill_id
    await update.message.reply_text("شناسه قبض معتبر است. در حال دریافت کد امنیتی...")
    driver = get_driver()
    try:
        driver.get(URL)
        wait = WebDriverWait(driver, 15)
        captcha_image_element = wait.until(EC.visibility_of_element_located((By.XPATH, CAPTCHA_IMAGE_XPATH)))
        captcha_screenshot_path = f"captcha_{update.message.chat_id}.png"
        captcha_image_element.screenshot(captcha_screenshot_path)
        await context.bot.send_photo(chat_id=update.message.chat_id, photo=open(captcha_screenshot_path, 'rb'), caption="لطفاً کد امنیتی ۵ رقمی را از تصویر بالا وارد کنید.")
        context.user_data['driver'] = driver
        os.remove(captcha_screenshot_path)
        return GETTING_CAPTCHA
    except Exception as e:
        await update.message.reply_text(f"خطایی در ارتباط با سایت رخ داد: {e}")
        if 'driver' in locals() and driver: driver.quit()
        return ConversationHandler.END

async def get_captcha(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    captcha_code = update.message.text
    if not captcha_code.isdigit() or len(captcha_code) != 5:
        await update.message.reply_text("خطا: کد امنیتی باید یک عدد ۵ رقمی باشد. لطفاً دوباره تلاش کنید.")
        return GETTING_CAPTCHA
    bill_id = context.user_data.get('bill_id')
    driver = context.user_data.get('driver')
    await update.message.reply_text("در حال پردازش...")
    try:
        wait = WebDriverWait(driver, 15)
        bill_id_field = wait.until(EC.element_to_be_clickable((By.XPATH, BILL_ID_XPATH)))
        bill_id_field.send_keys(bill_id)
        captcha_field = wait.until(EC.element_to_be_clickable((By.XPATH, CAPTCHA_FIELD_XPATH)))
        captcha_field.send_keys(captcha_code)
        search_button = wait.until(EC.element_to_be_clickable((By.XPATH, SEARCH_BUTTON_XPATH)))
        search_button.click()
        results_table = wait.until(EC.visibility_of_element_located((By.XPATH, RESULTS_TABLE_XPATH)))
        results_screenshot_path = f"results_{update.message.chat_id}.png"
        results_table.screenshot(results_screenshot_path)
        await context.bot.send_document(chat_id=update.message.chat_id, document=open(results_screenshot_path, 'rb'), caption="جدول زمان‌بندی خاموشی:")
        os.remove(results_screenshot_path)
    except TimeoutException:
        await update.message.reply_text("خطا: کد امنیتی اشتباه است. لطفاً با /start مجدداً تلاش کنید.")
    except Exception as e:
        await update.message.reply_text(f"خطایی در پردازش رخ داد: {e}")
    finally:
        driver.quit()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("عملیات لغو شد.")
    if 'driver' in context.user_data: context.user_data['driver'].quit()
    return ConversationHandler.END

# --- Main execution logic ---
def run_flask():
    """Runs the Flask web server in a separate thread."""
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

async def main():
    """Sets up and runs the Telegram bot."""
    nest_asyncio.apply()

    TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
    if not TELEGRAM_TOKEN:
        print("Error: TELEGRAM_TOKEN environment variable not set!")
        return

    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    print(f"Web server started in a background thread.")

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
    
    print("Bot is starting polling...")
    await application.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
