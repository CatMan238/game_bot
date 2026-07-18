import os
from dotenv import load_dotenv

load_dotenv()  # загружает переменные из .env (локально)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise Exception("❌ BOT_TOKEN не задан! Добавь переменную окружения BOT_TOKEN на Render или в .env")

# ============================================
#  ОСТАЛЬНЫЕ НАСТРОЙКИ (НЕ СЕКРЕТНЫЕ)
# ============================================
OWNER_ID = 8210121398
CHANNEL_NAME = "🔞GAME CONTENT🔞"
BOT_NAME = "Helper"

PAYMENT_URL_MONTH = "https://pay.cloudtips.ru/p/7eed5968"
PAYMENT_URL_6MONTH = "https://pay.cloudtips.ru/p/0840f5e8"
PAYMENT_URL_YEAR = "https://pay.cloudtips.ru/p/1effa92a"
PAYMENT_URL_TESTER_MONTH = "https://pay.cloudtips.ru/p/dded27d8"
PAYMENT_URL_TESTER_6MONTH = "https://pay.cloudtips.ru/p/65dff92e"
PAYMENT_URL_TESTER_YEAR = "https://pay.cloudtips.ru/p/f3221fd3"

PRICE_MONTH = 100
PRICE_6MONTH = 500
PRICE_YEAR = 900
PRICE_TESTER_MONTH = 200
PRICE_TESTER_6MONTH = 1000
PRICE_TESTER_YEAR = 2000

SUBSCRIPTION_DAYS_MONTH = 30
SUBSCRIPTION_DAYS_6MONTH = 180
SUBSCRIPTION_DAYS_YEAR = 365

DATABASE_PATH = "bot.db"
BOT_VERSION = "beta 0.5.5"
CHANNEL_NEWS_LINK = "https://t.me/HellperBotNews"
CHANNEL_NEWS_NAME = "📢 НАШ КАНАЛ"

# ============================================
#  НИЖЕ НИЧЕГО НЕ МЕНЯЙ!
# ============================================

if BOT_TOKEN == "ЗАМЕНИ_НА_СВОЙ_ТОКЕН":
    raise Exception("❌ ОШИБКА: Не заполнен BOT_TOKEN!")