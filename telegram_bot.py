import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
# New imports for Render/Docker
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# --- Bot and Web Scraping Configuration ---
# Read the secure token from an environment variable
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

# Website URL
URL = "https://modiriattolid.goped.ir/"

# Define XPath locators
BILL_ID_XPATH = "/html/body/div[2]/form/div/div[2]/input"
CAPTCHA_FIELD_XPATH = "/html/body/div[2]/form/div/div[3]/div/div/input"
CAPTCHA_IMAGE_XPATH = "/html/body/div[2]/form/div/div[3]/div/img"
SEARCH_BUTTON_XPATH = "/html/body/div[2]/form/div/div[4]/a"
RESULTS_TABLE_XPATH = "/html/body/div[3]/div/div/div[2]/div[2]/table"

# --- Conversation States ---
GETTING_BILL_ID, GETTING_CAPTCHA = range(2)

# --- Bot Functions ---

def get_driver():
    """Sets up the Chrome driver for a Linux environment on Render."""
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--headless")  # Run Chrome without a GUI
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=chrome_options)
    return driver

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the conversation and asks for the Bill ID."""
    await update.message.reply_text(
        "سلام! لطفاً شناسه قبض ۱۳ رقمی خود را وارد کنید."
    )
    return GETTING_BILL_ID

async def get_bill_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Validates the Bill ID and fetches the CAPTCHA image."""
    bill_id = update.message.text
    
    if not bill_id.isdigit() or len(bill_id) != 13:
        await update.message.reply_text(
            "خطا: شناسه قبض باید یک عدد ۱۳ رقمی باشد. لطفاً دوباره تلاش کنید."
        )
        return GETTING_BILL_ID

    context.user_data['bill_id'] = bill_id
    chat_id = update.message.chat_id

    await update.message.reply_text("شناسه قبض معتبر است. در حال دریافت کد امنیتی از سایت... لطفاً صبر کنید.")
    
    driver = get_driver()
    try:
        driver.get(URL)
        wait = WebDriverWait(driver, 15)

        captcha_image_element = wait.until(EC.visibility_of_element_located((By.XPATH, CAPTCHA_IMAGE_XPATH)))
        captcha_screenshot_path = f"captcha_{chat_id}.png"
        captcha_image_element.screenshot(captcha_screenshot_path)
        
        await context.bot.send_photo(
            chat_id=chat_id,
            photo=open(captcha_screenshot_path, 'rb'),
            caption="لطفاً کد امنیتی ۵ رقمی را از تصویر بالا وارد کنید."
        )
        
        context.user_data['driver'] = driver
        os.remove(captcha_screenshot_path)
        
        return GETTING_CAPTCHA

    except Exception as e:
        await update.message.reply_text(f"خطایی در ارتباط با سایت رخ داد: {e}")
        if 'driver' in locals() and driver:
            driver.quit()
        return ConversationHandler.END

async def get_captcha(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Validates CAPTCHA, completes the process, and sends the final screenshot."""
    captcha_code = update.message.text
    
    if not captcha_code.isdigit() or len(captcha_code) != 5:
        await update.message.reply_text(
            "خطا: کد امنیتی باید یک عدد ۵ رقمی باشد. لطفاً دوباره تلاش کنید."
        )
        return GETTING_CAPTCHA

    bill_id = context.user_data.get('bill_id')
    driver = context.user_data.get('driver')
    chat_id = update.message.chat_id

    if not all([bill_id, driver]):
        await update.message.reply_text("مشکلی پیش آمده. لطفاً با /start مجدداً شروع کنید.")
        return ConversationHandler.END

    await update.message.reply_text("کد امنیتی معتبر است. در حال ورود اطلاعات و دریافت جدول... لطفاً صبر کنید.")

    try:
        wait = WebDriverWait(driver, 15)
        
        bill_id_field = wait.until(EC.element_to_be_clickable((By.XPATH, BILL_ID_XPATH)))
        bill_id_field.send_keys(bill_id)

        captcha_field = wait.until(EC.element_to_be_clickable((By.XPATH, CAPTCHA_FIELD_XPATH)))
        captcha_field.send_keys(captcha_code)

        search_button = wait.until(EC.element_to_be_clickable((By.XPATH, SEARCH_BUTTON_XPATH)))
        search_button.click()

        results_table = wait.until(EC.visibility_of_element_located((By.XPATH, RESULTS_TABLE_XPATH)))
        results_screenshot_path = f"results_{chat_id}.png"
        results_table.screenshot(results_screenshot_path)

        await context.bot.send_document(
            chat_id=chat_id,
            document=open(results_screenshot_path, 'rb'),
            caption="جدول زمان‌بندی خاموشی:"
        )

        os.remove(results_screenshot_path)

    except TimeoutException:
        await update.message.reply_text("خطا: کد امنیتی اشتباه است یا صفحه بارگذاری نشد. لطفاً با /start مجدداً تلاش کنید.")
    except Exception as e:
        await update.message.reply_text(f"خطایی در پردازش رخ داد: {e}")
    finally:
        driver.quit()

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation."""
    await update.message.reply_text("عملیات لغو شد.")
    if 'driver' in context.user_data:
        context.user_data['driver'].quit()
    return ConversationHandler.END


def main() -> None:
    """Run the bot."""
    if not TELEGRAM_TOKEN:
        print("Error: TELEGRAM_TOKEN environment variable not set!")
        return
        
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

    print("Bot is running...")
    application.run_polling()


if __name__ == "__main__":
    main()