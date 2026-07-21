import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise Exception("❌ BOT_TOKEN не задан!")

# ============================================
#  ВЛАДЕЛЕЦ
# ============================================
OWNER_ID = 8210121398

# ============================================
#  НАСТРОЙКИ БОТА
# ============================================
BOT_NAME = "Helper"
CHANNEL_NAME = "🔞GAME CONTENT🔞"
BOT_VERSION = "1.0.0"
DATABASE_PATH = "bot.db"

# ============================================
#  ПЛАТЁЖНЫЙ ПРОВАЙДЕР (YooKassa)
# ============================================
YOOKASSA_SHOP_ID = os.environ.get("YOOKASSA_SHOP_ID", "")
YOOKASSA_SECRET_KEY = os.environ.get("YOOKASSA_SECRET_KEY", "")
PROVIDER_TOKEN = os.environ.get("PROVIDER_TOKEN", "")

# ============================================
#  ЦЕНЫ (РУБЛИ)
# ============================================
PRICE_MONTH = 119
PRICE_6MONTH = 643    # 6 * 119 * 0.9
PRICE_YEAR = 1071     # 12 * 119 * 0.75

# ============================================
#  КАНАЛЫ
# ============================================
CHANNEL_NEWS_LINK = "https://t.me/HellperBotNews"
CHANNEL_NEWS_NAME = "📢 НАШ КАНАЛ"

if BOT_TOKEN == "ЗАМЕНИ_НА_СВОЙ_ТОКЕН":
    raise Exception("❌ ОШИБКА: Не заполнен BOT_TOKEN!")