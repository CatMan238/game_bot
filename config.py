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