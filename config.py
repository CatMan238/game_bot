import os
import logging
from dotenv import load_dotenv

load_dotenv()

# Логирование
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise Exception("❌ BOT_TOKEN не задан!")

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise Exception("❌ DATABASE_URL не задан! Добавьте PostgreSQL в Render.")

OWNER_ID = int(os.environ.get("OWNER_ID", "8210121398"))

BOT_NAME = os.environ.get("BOT_NAME", "Helper")

# Карта для ручных переводов — вынесена в env по соображениям безопасности
CARD_NUMBER = os.environ.get("CARD_NUMBER", "")
if not CARD_NUMBER:
    logger.warning("⚠️ CARD_NUMBER не задан в окружении! Ручная оплата работать не будет.")

# ===== Цены в звёздах =====
PRICE_MONTH = 150
PRICE_6MONTH = 600
PRICE_YEAR = 1000

# ===== Цены в рублях (ручная оплата) =====
PRICE_MONTH_RUB = 200
PRICE_6MONTH_RUB = 700
PRICE_YEAR_RUB = 1200

PRICES = {
    'month': PRICE_MONTH,
    '6month': PRICE_6MONTH,
    'year': PRICE_YEAR,
}
PRICES_RUB = {
    'month': PRICE_MONTH_RUB,
    '6month': PRICE_6MONTH_RUB,
    'year': PRICE_YEAR_RUB,
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

# ===== Flask / Webhook =====
USE_WEBHOOK = os.environ.get("USE_WEBHOOK", "false").lower() == "true"
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")
PORT = int(os.environ.get("PORT", "10000"))

# ===== Часовые пояса =====
TIMEZONES = [
    ('UTC', 'UTC'),
    ('Europe/Moscow', '🇷🇺 Москва (UTC+3)'),
    ('Europe/Kiev', '🇺🇦 Киев (UTC+3)'),
    ('Europe/Minsk', '🇧🇾 Минск (UTC+3)'),
    ('Asia/Tashkent', '🇺🇿 Ташкент (UTC+5)'),
    ('Asia/Almaty', '🇰🇿 Алматы (UTC+6)'),
    ('Asia/Yekaterinburg', '🇷🇺 Екатеринбург (UTC+5)'),
    ('Asia/Vladivostok', '🇷🇺 Владивосток (UTC+10)'),
    ('Europe/Berlin', '🇩🇪 Берлин (UTC+1/+2)'),
    ('Europe/London', '🇬🇧 Лондон (UTC+0/+1)'),
]