import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise Exception("❌ BOT_TOKEN не задан!")

OWNER_ID = 8210121398

BOT_NAME = "Helper"
CHANNEL_NAME = "🔞GAME CONTENT🔞"
BOT_VERSION = "1.0.0"
DATABASE_PATH = "bot.db"

# ===== Цены в звёздах (Telegram Stars) =====
PRICE_MONTH = 150
PRICE_6MONTH = 600
PRICE_YEAR = 1000

PRICES = {
    'month': PRICE_MONTH,
    '6month': PRICE_6MONTH,
    'year': PRICE_YEAR,
}
PLAN_NAMES = {
    'month': 'Месяц',
    '6month': '6 месяцев',
    'year': 'Год',
}
SUBSCRIPTION_DAYS = {
    'month': 30,
    '6month': 180,
    'year': 365,
}