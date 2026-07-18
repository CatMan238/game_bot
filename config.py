# ============================================
#  НАСТРОЙКИ БОТА
# ============================================

# 1️⃣ ТОКЕН БОТА
BOT_TOKEN = "8895758637:AAHUeqUdWDyhTkew07aCxlLlbfqgSmuiRKM"

# 2️⃣ ТВОЙ TELEGRAM ID
OWNER_ID = 8210121398

# 3️⃣ НАЗВАНИЕ КАНАЛА
CHANNEL_NAME = "🔞GAME CONTENT🔞"

# 4️⃣ НАЗВАНИЕ БОТА
BOT_NAME = "Helper"

# 5️⃣ ССЫЛКИ ДЛЯ ОПЛАТЫ (ОБЫЧНАЯ ПОДПИСКА)
PAYMENT_URL_MONTH = "https://pay.cloudtips.ru/p/7eed5968"
PAYMENT_URL_6MONTH = "https://pay.cloudtips.ru/p/0840f5e8"
PAYMENT_URL_YEAR = "https://pay.cloudtips.ru/p/1effa92a"

# 6️⃣ ССЫЛКИ ДЛЯ ОПЛАТЫ (ТЕСТЕР-ПОДПИСКА)
PAYMENT_URL_TESTER_MONTH = "https://pay.cloudtips.ru/p/dded27d8"
PAYMENT_URL_TESTER_6MONTH = "https://pay.cloudtips.ru/p/65dff92e"
PAYMENT_URL_TESTER_YEAR = "https://pay.cloudtips.ru/p/f3221fd3"

# 7️⃣ ЦЕНЫ ПОДПИСКИ (рублей)
PRICE_MONTH = 100
PRICE_6MONTH = 500
PRICE_YEAR = 900

PRICE_TESTER_MONTH = 200
PRICE_TESTER_6MONTH = 1000
PRICE_TESTER_YEAR = 2000

# 8️⃣ СРОКИ ПОДПИСКИ (дней)
SUBSCRIPTION_DAYS_MONTH = 30
SUBSCRIPTION_DAYS_6MONTH = 180
SUBSCRIPTION_DAYS_YEAR = 365

# 9️⃣ ПУТЬ К БАЗЕ ДАННЫХ
DATABASE_PATH = "bot.db"

# 🔟 ВЕРСИЯ БОТА
BOT_VERSION = "beta 0.1"

# 1️⃣1️⃣ ССЫЛКА НА КАНАЛ С НОВОСТЯМИ
CHANNEL_NEWS_LINK = "https://t.me/HellperBotNews"
CHANNEL_NEWS_NAME = "📢 НАШ КАНАЛ"

# ============================================
#  НИЖЕ НИЧЕГО НЕ МЕНЯЙ!
# ============================================

if BOT_TOKEN == "ЗАМЕНИ_НА_СВОЙ_ТОКЕН":
    raise Exception("❌ ОШИБКА: Не заполнен BOT_TOKEN!")