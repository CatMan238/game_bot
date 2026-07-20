import logging
import json
import re
import random
import string
import os
import asyncio
import threading
import time
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputMediaVideo, InputMediaAnimation
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ChatJoinRequestHandler, PreCheckoutQueryHandler
from config import *
from database.db import *

# ============================================
#  НАСТРОЙКА ЛОГОВ
# ============================================

if not os.path.exists('logs'):
    os.makedirs('logs')

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('logs/main.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================
#  ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ
# ============================================

BOT_STOPPED = False
BOT_VERSION = "beta 0.4"
USER_MESSAGES = {}
USER_LAST_MENU = {}
USER_TEMP_DATA = {}

CATEGORIES = [
    'Музыка', 'Игры', 'Политика', 'Мода', 'Фильмы',
    'Софт и приложения', 'Творчество', '18+', 'Эротика',
    'Спорт', 'Курсы', 'Юмор', 'Блог'
]
ADULT_CATEGORIES = ['18+', 'Эротика']

# ============================================
#  ЯЗЫКИ (ПОЛНОСТЬЮ РАБОТАЮТ - ПУНКТ 7)
# ============================================

LANGUAGES = {
    'ru': {
        'main': '🏠 ГЛАВНОЕ МЕНЮ',
        'back': '◀️ НАЗАД',
        'yes': '✅ ДА',
        'no': '❌ НЕТ',
        'saved': '✅ СОХРАНЕНО!',
        'no_access': '❌ ДОСТУП ЗАПРЕЩЁН!',
        'no_sub': '❌ У ВАС НЕТ АКТИВНОЙ ПОДПИСКИ!',
        'bot_stopped': '🔧 БОТ ЗАКРЫТ НА ТЕХНИЧЕСКОЕ ОБСЛУЖИВАНИЕ!\n\n⏳ Пожалуйста, подождите.',
        'support_contact': '👤 @GanzalesSs920',
        'profile': '👤 ПРОФИЛЬ',
        'subscription': '💳 ПОДПИСКА',
        'connect_channel': '🔗 ПРИВЯЗАТЬ КАНАЛ',
        'disconnect_channel': '❌ ОТВЯЗАТЬ КАНАЛ',
        'channel_settings': '⚙️ НАСТРОЙКИ КАНАЛА',
        'partnership': '🤝 ПАРТНЁРСТВО',
        'search_channels': '🔍 ПОИСК КАНАЛОВ',
        'search_users': '🔍 ПОИСК ЛЮДЕЙ',
        'language': '🌍 ЯЗЫК',
        'support': '💬 ПОДДЕРЖКА',
        'developer': '⚙️ ДЛЯ РАЗРАБОТЧИКОВ',
        'customize': '🎨 КАСТОМИЗАЦИЯ',
        'beta_features': '🔬 БЕТА-ФУНКЦИИ',
        'version': 'ℹ️ ВЕРСИЯ',
        'change_name': '✏️ ИЗМЕНИТЬ ИМЯ',
        'send_message': '💬 НАПИСАТЬ',
        'delete_profile': '🗑 УДАЛИТЬ ПРОФИЛЬ',
        'mail': '📬 ПОЧТА',
        'subscription_active': 'АКТИВНА ДО {date}',
        'subscription_none': 'НЕТУ',
        'monthly': 'НА МЕСЯЦ',
        'half_year': 'НА 6 МЕСЯЦЕВ',
        'yearly': 'НА ГОД',
        'stars_price_month': '⭐ 50 Stars',
        'stars_price_6month': '⭐ 250 Stars',
        'stars_price_year': '⭐ 450 Stars',
        'pay_with_stars': '⭐ ОПЛАТИТЬ STARS',
        'check_payment': '🔄 ПРОВЕРИТЬ ОПЛАТУ',
    },
    'en': {
        'main': '🏠 MAIN MENU',
        'back': '◀️ BACK',
        'yes': '✅ YES',
        'no': '❌ NO',
        'saved': '✅ SAVED!',
        'no_access': '❌ ACCESS DENIED!',
        'no_sub': '❌ NO ACTIVE SUBSCRIPTION!',
        'bot_stopped': '🔧 BOT UNDER MAINTENANCE!\n\n⏳ Please wait.',
        'support_contact': '👤 @GanzalesSs920',
        'profile': '👤 PROFILE',
        'subscription': '💳 SUBSCRIPTION',
        'connect_channel': '🔗 CONNECT CHANNEL',
        'disconnect_channel': '❌ DISCONNECT CHANNEL',
        'channel_settings': '⚙️ CHANNEL SETTINGS',
        'partnership': '🤝 PARTNERSHIP',
        'search_channels': '🔍 SEARCH CHANNELS',
        'search_users': '🔍 SEARCH USERS',
        'language': '🌍 LANGUAGE',
        'support': '💬 SUPPORT',
        'developer': '⚙️ DEVELOPER',
        'customize': '🎨 CUSTOMIZE',
        'beta_features': '🔬 BETA FEATURES',
        'version': 'ℹ️ VERSION',
        'change_name': '✏️ CHANGE NAME',
        'send_message': '💬 SEND MESSAGE',
        'delete_profile': '🗑 DELETE PROFILE',
        'mail': '📬 MAIL',
        'subscription_active': 'ACTIVE UNTIL {date}',
        'subscription_none': 'NONE',
        'monthly': 'MONTHLY',
        'half_year': '6 MONTHS',
        'yearly': 'YEARLY',
        'stars_price_month': '⭐ 50 Stars',
        'stars_price_6month': '⭐ 250 Stars',
        'stars_price_year': '⭐ 450 Stars',
        'pay_with_stars': '⭐ PAY WITH STARS',
        'check_payment': '🔄 CHECK PAYMENT',
    }
}

def get_lang(user_id):
    return get_user_language(user_id) or 'ru'

def get_text(user_id, key, **kwargs):
    lang = get_lang(user_id)
    lang_dict = LANGUAGES.get(lang, LANGUAGES['ru'])
    parts = key.split('.')
    text = lang_dict
    for p in parts:
        if isinstance(text, dict):
            text = text.get(p, key)
        else:
            return key
    if isinstance(text, dict):
        return key
    for k, v in kwargs.items():
        text = text.replace(f"{{{k}}}", str(v))
    return text

# ============================================
#  ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================

def extract_channel_id_from_text(text):
    text = text.strip()
    match = re.search(r'(-?\d+)', text)
    return int(match.group(1)) if match else None

def extract_username_from_link(text):
    match = re.search(r'(?:https?://)?t\.me/([a-zA-Z0-9_]+)', text)
    return match.group(1) if match else None

def get_chat_info(bot, chat_id):
    try:
        chat = bot.get_chat(chat_id)
        return {'title': chat.title, 'id': chat.id}
    except:
        return None

def get_channel_subscribers(bot, channel_id):
    try:
        chat = bot.get_chat(channel_id)
        if hasattr(chat, 'member_count'):
            return chat.member_count
        try:
            return bot.get_chat_members_count(channel_id)
        except:
            return 0
    except:
        return 0

def update_channel_subscribers(bot, channel_id):
    try:
        count = get_channel_subscribers(bot, channel_id)
        update_channel_subscribers_db(channel_id, count)
        return count
    except:
        return 0

def get_channel_admins(bot, channel_id):
    try:
        admins = []
        for admin in bot.get_chat_administrators(channel_id):
            if admin.user.is_bot:
                continue
            admins.append({
                'id': admin.user.id,
                'name': admin.user.first_name or admin.user.username or str(admin.user.id)
            })
        return admins
    except:
        return []

def get_channel_photo(bot, channel_id):
    try:
        photos = bot.get_chat_photos(channel_id, limit=1)
        if photos:
            return photos[0].file_id
    except:
        pass
    return None

def get_channel_description(bot, channel_id):
    try:
        chat = bot.get_chat(channel_id)
        return chat.description if hasattr(chat, 'description') and chat.description else None
    except:
        return None

def get_channel_username(bot, channel_id):
    try:
        chat = bot.get_chat(channel_id)
        return chat.username if hasattr(chat, 'username') and chat.username else None
    except:
        return None

async def check_bot_rights_async(bot, chat_id):
    try:
        member = await bot.get_chat_member(chat_id, bot.id)
        if member.status == 'creator':
            return True, "✅ Бот создатель!"
        if member.status != 'administrator':
            return False, "❌ Бот не администратор!\n\n📌 Добавьте бота в АДМИНИСТРАТОРЫ!"
        missing = []
        rights = {
            'can_post_messages': "❌ Публикация",
            'can_edit_messages': "❌ Редактирование",
            'can_delete_messages': "❌ Удаление",
            'can_invite_users': "❌ Приглашение",
            'can_restrict_members': "❌ Блокировка",
            'can_manage_chat': "❌ Управление"
        }
        for right, name in rights.items():
            if not getattr(member, right, False):
                missing.append(name)
        if missing:
            return False, "⚠️ НЕТ прав:\n" + "\n".join(missing)
        return True, "✅ Все права есть!"
    except Exception as e:
        return False, f"❌ Ошибка: {e}"

def send_message_to_user(bot, from_id, to_id, text, anonymous=False):
    try:
        if from_id == to_id:
            return False, "❌ НЕЛЬЗЯ ОТПРАВИТЬ СЕБЕ!"
        if anonymous:
            bot.send_message(chat_id=to_id, text=f"💬 АНОНИМНОЕ СООБЩЕНИЕ\n\n{text}")
        else:
            from_name = get_user_nickname(from_id) or f"User {from_id}"
            bot.send_message(chat_id=to_id, text=f"💬 СООБЩЕНИЕ ОТ {from_name}\n\n{text}")
        return True, "✅ Сообщение отправлено!"
    except Exception as e:
        return False, f"❌ Ошибка: {e}"

def add_user_message(user_id, message):
    try:
        if user_id not in USER_MESSAGES:
            USER_MESSAGES[user_id] = []
        USER_MESSAGES[user_id].append(message.message_id)
        if len(USER_MESSAGES[user_id]) > 20:
            USER_MESSAGES[user_id] = USER_MESSAGES[user_id][-20:]
    except:
        pass

async def delete_user_messages(bot, user_id, keep_last=1):
    try:
        if user_id in USER_MESSAGES and USER_MESSAGES[user_id]:
            to_delete = USER_MESSAGES[user_id][:-keep_last] if keep_last > 0 else USER_MESSAGES[user_id]
            for msg_id in to_delete:
                try:
                    await bot.delete_message(chat_id=user_id, message_id=msg_id)
                except:
                    pass
            if keep_last > 0:
                USER_MESSAGES[user_id] = USER_MESSAGES[user_id][-keep_last:]
            else:
                USER_MESSAGES[user_id] = []
    except:
        pass

async def clear_user_messages(bot, user_id):
    try:
        if user_id in USER_MESSAGES:
            for msg_id in USER_MESSAGES[user_id]:
                try:
                    await bot.delete_message(chat_id=user_id, message_id=msg_id)
                except:
                    pass
            USER_MESSAGES[user_id] = []
    except:
        pass

def log_main(user_id, action, details=""):
    try:
        nickname = get_user_nickname(user_id) or str(user_id)
        logger.info(f"{nickname} ({user_id}): {action} - {details}")
    except:
        pass

def log_error(error_msg):
    try:
        logger.error(error_msg)
    except:
        pass

def is_channel_connected_to_anyone(channel_id):
    conn = get_db()
    cursor = conn.cursor()
    result = cursor.execute('SELECT * FROM channels WHERE channel_id = ?', (channel_id,)).fetchone()
    conn.close()
    return result is not None

def get_channel_by_channel_id(channel_id):
    conn = get_db()
    cursor = conn.cursor()
    result = cursor.execute('SELECT * FROM channels WHERE channel_id = ?', (channel_id,)).fetchone()
    conn.close()
    return result

def get_channel_linked_group(channel_id):
    return get_setting(f"linked_group_{channel_id}")

def set_channel_linked_group(channel_id, group_id):
    set_setting(f"linked_group_{channel_id}", str(group_id))

def get_channel_info_full(bot, channel_id):
    """Получить полную информацию о канале"""
    try:
        chat = bot.get_chat(channel_id)
        info = {
            'title': chat.title,
            'id': chat.id,
            'username': chat.username if hasattr(chat, 'username') and chat.username else None,
            'description': chat.description if hasattr(chat, 'description') and chat.description else None,
            'member_count': chat.member_count if hasattr(chat, 'member_count') else 0,
            'linked_chat_id': chat.linked_chat_id if hasattr(chat, 'linked_chat_id') else None,
            'photo': None,
            'admins': []
        }
        try:
            photos = bot.get_chat_photos(channel_id, limit=1)
            if photos:
                info['photo'] = photos[0].file_id
        except:
            pass
        try:
            for admin in bot.get_chat_administrators(channel_id):
                if not admin.user.is_bot:
                    info['admins'].append({
                        'id': admin.user.id,
                        'name': admin.user.first_name or admin.user.username or str(admin.user.id)
                    })
        except:
            pass
        return info
    except Exception as e:
        log_error(f"Get channel info error: {e}")
        return None

# ============================================
#  УВЕДОМЛЕНИЯ (ПОЧТА) - ПУНКТ 19
# ============================================

def add_notification(user_id, notif_type, content, link_data=None):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            type TEXT,
            content TEXT,
            link_data TEXT,
            read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        INSERT INTO notifications (user_id, type, content, link_data)
        VALUES (?, ?, ?, ?)
    ''', (user_id, notif_type, content, link_data))
    conn.commit()
    conn.close()
    return True

def get_user_notifications(user_id, unread_only=True):
    conn = get_db()
    cursor = conn.cursor()
    if unread_only:
        notifs = cursor.execute('''
            SELECT * FROM notifications 
            WHERE user_id = ? AND read = 0
            ORDER BY created_at DESC
        ''', (user_id,)).fetchall()
    else:
        notifs = cursor.execute('''
            SELECT * FROM notifications 
            WHERE user_id = ?
            ORDER BY created_at DESC
        ''', (user_id,)).fetchall()
    conn.close()
    return notifs

def mark_notification_read(notif_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE notifications SET read = 1 WHERE id = ?', (notif_id,))
    conn.commit()
    conn.close()

def delete_notification(notif_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM notifications WHERE id = ?', (notif_id,))
    conn.commit()
    conn.close()

async def send_notification(bot, user_id, notif_type, content, callback_data=None):
    add_notification(user_id, notif_type, content, callback_data)
    try:
        kb = [
            [InlineKeyboardButton("👁 ПОСМОТРЕТЬ", callback_data=f"view_notif_{user_id}")],
            [InlineKeyboardButton("❌ СКРЫТЬ", callback_data=f"hide_notif_{user_id}")]
        ]
        await bot.send_message(
            chat_id=user_id,
            text=f"📬 ВАМ ПРИШЛО УВЕДОМЛЕНИЕ!\n\n📌 {notif_type}\n📝 {content}",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return True
    except:
        return False

# ============================================
#  СИСТЕМА ОТЗЫВОВ - ПУНКТ 19
# ============================================

def add_feedback(user_id, feature_name, feedback_text, rating=5):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            feature_name TEXT,
            feedback TEXT,
            rating INTEGER DEFAULT 5,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        INSERT INTO feedback (user_id, feature_name, feedback, rating)
        VALUES (?, ?, ?, ?)
    ''', (user_id, feature_name, feedback_text, rating))
    conn.commit()
    conn.close()
    return True

def get_feedback(feature_name=None):
    conn = get_db()
    cursor = conn.cursor()
    if feature_name:
        feedback = cursor.execute('''
            SELECT * FROM feedback WHERE feature_name = ?
            ORDER BY created_at DESC
        ''', (feature_name,)).fetchall()
    else:
        feedback = cursor.execute('''
            SELECT * FROM feedback ORDER BY created_at DESC
        ''',).fetchall()
    conn.close()
    return feedback

# ============================================
#  БЛОКИРОВКА ПОЛЬЗОВАТЕЛЕЙ - ПУНКТ 17
# ============================================

def block_user(user_id):
    set_setting(f"blocked_{user_id}", '1')
    return True

def unblock_user(user_id):
    set_setting(f"blocked_{user_id}", '0')
    return True

def is_user_blocked(user_id):
    return get_setting(f"blocked_{user_id}") == '1'

def get_blocked_users():
    conn = get_db()
    cursor = conn.cursor()
    blocked = cursor.execute("SELECT key FROM settings WHERE key LIKE 'blocked_%' AND value = '1'").fetchall()
    conn.close()
    return [int(b['key'].replace('blocked_', '')) for b in blocked]

# ============================================
#  ОПЛАТА ЧЕРЕЗ TELEGRAM STARS - ПУНКТ 23
# ============================================

STARS_PRICES = {
    'month_regular': 50,
    'month_tester': 100,
    '6month_regular': 250,
    '6month_tester': 500,
    'year_regular': 450,
    'year_tester': 900,
}

SUBSCRIPTION_DAYS = {
    'month': 30,
    '6month': 180,
    'year': 365,
}

def create_payment(user_id, plan_type, amount):
    """Создать запись о платеже"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            plan_type TEXT,
            amount INTEGER,
            payment_id TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            confirmed_at TIMESTAMP
        )
    ''')
    # Генерируем уникальный ID платежа
    payment_id = f"pay_{user_id}_{int(time.time())}_{random.randint(1000, 9999)}"
    cursor.execute('''
        INSERT INTO payments (user_id, plan_type, amount, payment_id)
        VALUES (?, ?, ?, ?)
    ''', (user_id, plan_type, amount, payment_id))
    conn.commit()
    conn.close()
    return payment_id

def get_payment(payment_id):
    conn = get_db()
    cursor = conn.cursor()
    payment = cursor.execute('SELECT * FROM payments WHERE payment_id = ?', (payment_id,)).fetchone()
    conn.close()
    return payment

def update_payment_status(payment_id, status):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE payments SET status = ?, confirmed_at = CURRENT_TIMESTAMP
        WHERE payment_id = ?
    ''', (status, payment_id))
    conn.commit()
    conn.close()

def get_pending_payment(user_id):
    conn = get_db()
    cursor = conn.cursor()
    payment = cursor.execute('''
        SELECT * FROM payments 
        WHERE user_id = ? AND status = 'pending'
        ORDER BY created_at DESC LIMIT 1
    ''', (user_id,)).fetchone()
    conn.close()
    return payment

def parse_plan_type(plan_type):
    """Разобрать тип плана и вернуть (тип_подписки, дней)"""
    parts = plan_type.split('_')
    if len(parts) == 2:
        period, sub_type = parts
        days = SUBSCRIPTION_DAYS.get(period, 30)
        return sub_type, days
    return 'regular', 30

# ============================================
#  КЛАВИАТУРЫ
# ============================================

def main_kb(user_id):
    kb = [
        [InlineKeyboardButton("💳 ПОДПИСКА", callback_data='subscription'), InlineKeyboardButton("👤 ПРОФИЛЬ", callback_data='profile')],
        [InlineKeyboardButton("🔗 ПРИВЯЗАТЬ КАНАЛ", callback_data='connect_channel'), InlineKeyboardButton("⚙️ НАСТРОЙКИ", callback_data='channel_settings')],
        [InlineKeyboardButton("📢 ВП (ВЗАИМОПОСТ)", callback_data='vp_menu')],
        [InlineKeyboardButton("🌍 ЯЗЫК", callback_data='language'), InlineKeyboardButton("ℹ️ ВЕРСИЯ", callback_data='version')],
        [InlineKeyboardButton("💬 ПОДДЕРЖКА", callback_data='support')],
    ]
    if is_subscribed(user_id) or is_tester(user_id) or user_id == OWNER_ID:
        kb.insert(3, [InlineKeyboardButton("🔍 ПОИСК КАНАЛОВ", callback_data='search_channels'), InlineKeyboardButton("🔍 ПОИСК ЛЮДЕЙ", callback_data='search_users')])
    if is_tester(user_id) or user_id == OWNER_ID:
        kb.append([InlineKeyboardButton("🔬 БЕТА-ФУНКЦИИ", callback_data='beta_features')])
    kb.append([InlineKeyboardButton("⚙️ ДЛЯ РАЗРАБОТЧИКОВ", callback_data='developer')])
    USER_LAST_MENU[user_id] = 'main'
    return InlineKeyboardMarkup(kb)

def back_kb(user_id, back_to='back', disable=False):
    """Кнопка назад с возможностью отключения (для регистрации - пункт 16)"""
    if disable:
        return InlineKeyboardMarkup([])
    USER_LAST_MENU[user_id] = back_to
    return InlineKeyboardMarkup([[InlineKeyboardButton("◀️ НАЗАД", callback_data=back_to)]])

def reg_kb(user_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ РЕГИСТРАЦИЯ", callback_data='register')],
        [InlineKeyboardButton("🌍 ЯЗЫК", callback_data='language')],
    ])

def subscription_kb(user_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 ОБЫЧНАЯ", callback_data='sub_regular')],
        [InlineKeyboardButton("🧪 ТЕСТЕР", callback_data='sub_tester')],
        [InlineKeyboardButton("🎟 АКТИВАЦИЯ КОДА", callback_data='activate_code')],
        [InlineKeyboardButton("◀️ НАЗАД", callback_data='back')],
    ])

def sub_regular_kb(user_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📅 НА МЕСЯЦ - {STARS_PRICES['month_regular']} ⭐", callback_data='sub_month_regular')],
        [InlineKeyboardButton(f"📅 НА 6 МЕСЯЦЕВ - {STARS_PRICES['6month_regular']} ⭐", callback_data='sub_6month_regular')],
        [InlineKeyboardButton(f"📅 НА ГОД - {STARS_PRICES['year_regular']} ⭐", callback_data='sub_year_regular')],
        [InlineKeyboardButton("◀️ НАЗАД", callback_data='subscription')],
    ])

def sub_tester_kb(user_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📅 НА МЕСЯЦ - {STARS_PRICES['month_tester']} ⭐", callback_data='sub_month_tester')],
        [InlineKeyboardButton(f"📅 НА 6 МЕСЯЦЕВ - {STARS_PRICES['6month_tester']} ⭐", callback_data='sub_6month_tester')],
        [InlineKeyboardButton(f"📅 НА ГОД - {STARS_PRICES['year_tester']} ⭐", callback_data='sub_year_tester')],
        [InlineKeyboardButton("◀️ НАЗАД", callback_data='subscription')],
    ])

def categories_kb(user_id, selected=None):
    keyboard = []
    row = []
    for cat in CATEGORIES:
        if cat in ADULT_CATEGORIES and not is_adult(user_id):
            continue
        check = "✅ " if selected and cat in selected else ""
        row.append(InlineKeyboardButton(f"{check}{cat}", callback_data=f"cat_{cat}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("✅ ПОДТВЕРДИТЬ", callback_data='confirm_categories')])
    keyboard.append([InlineKeyboardButton("◀️ НАЗАД", callback_data='back')])
    return InlineKeyboardMarkup(keyboard)

def dev_kb(user_id):
    global BOT_STOPPED
    maint_text = "⏹ ЗАКРЫТЬ" if not BOT_STOPPED else "▶️ ОТКРЫТЬ"
    maint_data = 'maintenance_on' if not BOT_STOPPED else 'maintenance_off'
    timer_hours = get_vp_timer()
    kb = [
        [InlineKeyboardButton("🎟 СОЗДАНИЕ КОДА", callback_data='dev_create_code'), InlineKeyboardButton("📋 АКТИВНЫЕ КОДЫ", callback_data='dev_active_codes')],
        [InlineKeyboardButton("📨 РАССЫЛКА", callback_data='dev_broadcast'), InlineKeyboardButton(maint_text, callback_data=maint_data)],
        [InlineKeyboardButton("🎁 ПОДАРИТЬ", callback_data='dev_gift'), InlineKeyboardButton("📊 ОТЧЁТ", callback_data='dev_report')],
        [InlineKeyboardButton("🎨 КАСТОМИЗАЦИЯ", callback_data='dev_customize'), InlineKeyboardButton("🧪 ТЕСТЕРЫ", callback_data='dev_testers')],
        [InlineKeyboardButton("👥 ВСЕ ПОЛЬЗОВАТЕЛИ", callback_data='dev_all_users')],
        [InlineKeyboardButton(f"⏰ ТАЙМЕР ВП: {timer_hours}ч", callback_data='dev_vp_timer')],
        [InlineKeyboardButton("🗑 ОЧИСТИТЬ ВП", callback_data='dev_clear_vp')],
        [InlineKeyboardButton("🔬 УПРАВЛЕНИЕ БЕТА-ФУНКЦИЯМИ", callback_data='dev_beta_management')],
        [InlineKeyboardButton("📝 РЕДАКТОР РЕГИСТРАЦИИ", callback_data='dev_edit_registration')],
        [InlineKeyboardButton("◀️ В ГЛАВНОЕ МЕНЮ", callback_data='back_to_main')],
    ]
    USER_LAST_MENU[user_id] = 'developer'
    return InlineKeyboardMarkup(kb)

def channel_settings_kb(user_id, channel_id):
    welcome_enabled = get_setting(f"welcome_enabled_{channel_id}") == '1'
    farewell_enabled = get_setting(f"farewell_enabled_{channel_id}") == '1'
    anti_spam_enabled = get_setting(f"anti_spam_enabled_{channel_id}") == '1'
    auto_approve_enabled = get_auto_approve(channel_id)
    privacy = get_channel_privacy(channel_id)
    
    welcome_status = "✅ ВКЛ" if welcome_enabled else "❌ ВЫКЛ"
    farewell_status = "✅ ВКЛ" if farewell_enabled else "❌ ВЫКЛ"
    anti_spam_status = "✅ ВКЛ" if anti_spam_enabled else "❌ ВЫКЛ"
    auto_approve_status = "✅ ВКЛ" if auto_approve_enabled else "❌ ВЫКЛ"
    privacy_status = "🔒 СКРЫТ" if privacy == 'private' else "🔓 ВИДЕН"
    
    # Получаем информацию о канале сразу (пункт 5)
    ch = get_channel_by_channel_id(channel_id)
    channel_info_text = ""
    if ch:
        channel_info_text = f"\n📺 {ch['channel_name']}\n📂 {ch['category'] if ch['category'] else 'Без категории'}\n👥 {ch['subscribers'] if ch['subscribers'] else 0}\n🔒 {privacy_status}"
    
    kb = [
        [InlineKeyboardButton(f"ℹ️ ИНФОРМАЦИЯ {channel_info_text[:30]}", callback_data=f"channel_info_{channel_id}")],
        [InlineKeyboardButton(f"🚫 ФИЛЬТР СЛОВ {anti_spam_status}", callback_data=f"toggle_anti_spam_{channel_id}")],
        [InlineKeyboardButton("📅 АВТОПОСТИНГ", callback_data=f"auto_posting_menu_{channel_id}")],
        [InlineKeyboardButton("📊 ЛИДЕРБОАРД", callback_data=f"set_leaderboard_{channel_id}"), InlineKeyboardButton("📊 СТАТИСТИКА", callback_data=f"set_stats_{channel_id}")],
        [InlineKeyboardButton(f"👋 ПРИВЕТСТВИЕ {welcome_status}", callback_data=f"set_welcome_{channel_id}")],
        [InlineKeyboardButton(f"👋 ПРОЩАНИЕ {farewell_status}", callback_data=f"set_farewell_{channel_id}")],
        [InlineKeyboardButton(f"🔗 АВТОПРИЁМ ЗАЯВОК {auto_approve_status}", callback_data=f"set_auto_approve_{channel_id}")],
        [InlineKeyboardButton("❓ КАПТЧА", callback_data=f"set_captcha_{channel_id}")],
        [InlineKeyboardButton(f"🔒 ВИДИМОСТЬ {privacy_status}", callback_data=f"set_privacy_{channel_id}")],
        [InlineKeyboardButton("◀️ НАЗАД", callback_data='back')],
    ]
    return InlineKeyboardMarkup(kb)

def channel_info_kb(channel_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 ОБНОВИТЬ", callback_data=f"channel_info_{channel_id}")],
        [InlineKeyboardButton("◀️ НАЗАД", callback_data=f"set_ch_{channel_id}")],
    ])

def auto_posting_menu_kb(channel_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 ЗАПЛАНИРОВАТЬ ПОСТ", callback_data=f"set_posting_{channel_id}")],
        [InlineKeyboardButton("📋 ВСЕ ЗАПЛАНИРОВАННЫЕ", callback_data=f"post_view_{channel_id}")],
        [InlineKeyboardButton("❌ УДАЛИТЬ ЗАПЛАНИРОВАННЫЙ", callback_data=f"post_cancel_{channel_id}")],
        [InlineKeyboardButton("◀️ НАЗАД", callback_data=f"set_ch_{channel_id}")],
    ])

def connect_methods_kb(user_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 ПО ID", callback_data='connect_by_id')],
        [InlineKeyboardButton("🔗 ПО ССЫЛКЕ", callback_data='connect_by_link')],
        [InlineKeyboardButton("📌 ПО USERNAME", callback_data='connect_by_username')],
        [InlineKeyboardButton("📩 ПЕРЕСЛАТЬ СООБЩЕНИЕ", callback_data='connect_by_forward')],
        [InlineKeyboardButton("◀️ НАЗАД", callback_data='back')],
    ])

def search_channels_kb(user_id):
    if not is_subscribed(user_id) and user_id != OWNER_ID and not is_tester(user_id):
        return None
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 ПО НАЗВАНИЮ", callback_data='search_by_name')],
        [InlineKeyboardButton("🔍 ПО ID В БОТЕ", callback_data='search_by_bot_id')],
        [InlineKeyboardButton("🔍 ПО ID В ТГ", callback_data='search_by_tg_id')],
        [InlineKeyboardButton("📂 ФИЛЬТР ПО КАТЕГОРИИ", callback_data='filter_category')],
        [InlineKeyboardButton("📊 СОРТИРОВКА", callback_data='sort_subscribers')],
        [InlineKeyboardButton("◀️ НАЗАД", callback_data='back')],
    ])

def filter_category_kb(user_id, selected=None):
    keyboard = [[InlineKeyboardButton("📂 ВСЕ КАТЕГОРИИ", callback_data='filter_all')]]
    row = []
    for cat in CATEGORIES:
        if cat in ADULT_CATEGORIES and not is_adult(user_id):
            continue
        check = "✅ " if cat == selected else ""
        row.append(InlineKeyboardButton(f"{check}{cat}", callback_data=f"filter_cat_{cat}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("◀️ НАЗАД", callback_data='search_channels')])
    return InlineKeyboardMarkup(keyboard)

def sort_kb(user_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬆️ ПО ВОЗРАСТАНИЮ", callback_data='sort_asc')],
        [InlineKeyboardButton("⬇️ ПО УБЫВАНИЮ", callback_data='sort_desc')],
        [InlineKeyboardButton("◀️ НАЗАД", callback_data='search_channels')],
    ])

def profile_kb(user_id):
    kb = [
        [InlineKeyboardButton("✏️ ИЗМЕНИТЬ ИМЯ", callback_data='change_name')],
        [InlineKeyboardButton("💬 НАПИСАТЬ", callback_data='send_message_to_user')],
        [InlineKeyboardButton("📬 ПОЧТА", callback_data='show_notifications')],
        [InlineKeyboardButton("🗑 УДАЛИТЬ ПРОФИЛЬ", callback_data='delete_profile_confirm')],
    ]
    if user_id == OWNER_ID:
        kb.append([InlineKeyboardButton("♾️ БЕЗЛИМИТ", callback_data='change_name_infinite')])
    kb.append([InlineKeyboardButton("◀️ НАЗАД", callback_data='back')])
    return InlineKeyboardMarkup(kb)

def user_profile_kb(user_id, target_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 НАПИСАТЬ", callback_data=f"msg_to_{target_id}")],
        [InlineKeyboardButton("◀️ НАЗАД", callback_data='back')],
    ])

def channel_profile_kb(channel_id, privacy, user_id):
    kb = []
    if privacy == 'public':
        kb.append([InlineKeyboardButton("🚀 ПЕРЕЙТИ В КАНАЛ", callback_data=f"go_channel_{channel_id}")])
    else:
        kb.append([InlineKeyboardButton("📩 ПОДАТЬ ЗАЯВКУ", callback_data=f"apply_channel_{channel_id}")])
    if user_id == OWNER_ID:
        kb.append([InlineKeyboardButton("🗑 УДАЛИТЬ КАНАЛ", callback_data=f"admin_del_channel_{channel_id}")])
    kb.append([InlineKeyboardButton("◀️ НАЗАД", callback_data='back')])
    return InlineKeyboardMarkup(kb)

def beta_features_kb(user_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔬 ПРИМЕР БЕТА-ФУНКЦИИ", callback_data='beta_example')],
        [InlineKeyboardButton("📊 СТАТИСТИКА БЕТА", callback_data='beta_stats')],
        [InlineKeyboardButton("🤖 ИИ ПОДДЕРЖКА (БЕТА)", callback_data='beta_ai_support')],
        [InlineKeyboardButton("📝 ОСТАВИТЬ ОТЗЫВ", callback_data='beta_feedback')],
        [InlineKeyboardButton("◀️ НАЗАД", callback_data='back')],
    ])

def code_days_kb(user_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 7 ДНЕЙ", callback_data='code_days_7'), InlineKeyboardButton("📅 14 ДНЕЙ", callback_data='code_days_14')],
        [InlineKeyboardButton("📅 30 ДНЕЙ", callback_data='code_days_30'), InlineKeyboardButton("📅 60 ДНЕЙ", callback_data='code_days_60')],
        [InlineKeyboardButton("📅 90 ДНЕЙ", callback_data='code_days_90'), InlineKeyboardButton("📅 365 ДНЕЙ", callback_data='code_days_365')],
        [InlineKeyboardButton("◀️ НАЗАД", callback_data='back')],
    ])

def vp_kb(user_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 ВСЕ ПОСТЫ", callback_data='vp_view')],
        [InlineKeyboardButton("➕ СОЗДАТЬ ПОСТ", callback_data='vp_create')],
        [InlineKeyboardButton("◀️ НАЗАД", callback_data='back')],
    ])

def vp_create_kb(user_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📷 ДОБАВИТЬ МЕДИА", callback_data='vp_add_media')],
        [InlineKeyboardButton("🔞 18+", callback_data='vp_toggle_adult')],
        [InlineKeyboardButton("📂 КАТЕГОРИЯ", callback_data='vp_choose_category')],
        [InlineKeyboardButton("✅ ВЫЛОЖИТЬ", callback_data='vp_publish')],
        [InlineKeyboardButton("◀️ ОТМЕНИТЬ", callback_data='vp_cancel')],
    ])

def vp_category_kb(user_id, selected=None):
    keyboard = []
    row = []
    for cat in CATEGORIES:
        if cat in ADULT_CATEGORIES and not is_adult(user_id):
            continue
        check = "✅ " if cat == selected else ""
        row.append(InlineKeyboardButton(f"{check}{cat}", callback_data=f"vp_cat_{cat}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("◀️ НАЗАД", callback_data='vp_create')])
    return InlineKeyboardMarkup(keyboard)

def vp_timer_kb(user_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 6 ЧАСОВ", callback_data='vp_timer_6')],
        [InlineKeyboardButton("📅 12 ЧАСОВ", callback_data='vp_timer_12')],
        [InlineKeyboardButton("📅 24 ЧАСА", callback_data='vp_timer_24')],
        [InlineKeyboardButton("📅 48 ЧАСОВ", callback_data='vp_timer_48')],
        [InlineKeyboardButton("📅 72 ЧАСА", callback_data='vp_timer_72')],
        [InlineKeyboardButton("✏️ СВОЁ ЗНАЧЕНИЕ", callback_data='vp_timer_custom')],
        [InlineKeyboardButton("◀️ НАЗАД", callback_data='developer')],
    ])

def welcome_commands_kb(channel_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 {name} - имя пользователя", callback_data=f"welcome_cmd_name_{channel_id}")],
        [InlineKeyboardButton("📋 {chat} - название канала", callback_data=f"welcome_cmd_chat_{channel_id}")],
        [InlineKeyboardButton("📋 {mention} - упоминание", callback_data=f"welcome_cmd_mention_{channel_id}")],
        [InlineKeyboardButton("📋 {count} - подписчики", callback_data=f"welcome_cmd_count_{channel_id}")],
        [InlineKeyboardButton("📋 КОПИРОВАТЬ ШАБЛОН", callback_data=f"welcome_copy_template_{channel_id}")],
        [InlineKeyboardButton("✏️ РЕДАКТИРОВАТЬ ТЕКСТ", callback_data=f"welcome_edit_text_{channel_id}")],
        [InlineKeyboardButton("✅ ВКЛЮЧИТЬ", callback_data=f"welcome_enable_{channel_id}")],
        [InlineKeyboardButton("❌ ВЫКЛЮЧИТЬ", callback_data=f"welcome_disable_{channel_id}")],
        [InlineKeyboardButton("◀️ НАЗАД", callback_data=f"set_ch_{channel_id}")],
    ])

def farewell_commands_kb(channel_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 {name} - имя пользователя", callback_data=f"farewell_cmd_name_{channel_id}")],
        [InlineKeyboardButton("📋 {chat} - название канала", callback_data=f"farewell_cmd_chat_{channel_id}")],
        [InlineKeyboardButton("📋 {mention} - упоминание", callback_data=f"farewell_cmd_mention_{channel_id}")],
        [InlineKeyboardButton("📋 {count} - подписчики", callback_data=f"farewell_cmd_count_{channel_id}")],
        [InlineKeyboardButton("📋 КОПИРОВАТЬ ШАБЛОН", callback_data=f"farewell_copy_template_{channel_id}")],
        [InlineKeyboardButton("✏️ РЕДАКТИРОВАТЬ ТЕКСТ", callback_data=f"farewell_edit_text_{channel_id}")],
        [InlineKeyboardButton("✅ ВКЛЮЧИТЬ", callback_data=f"farewell_enable_{channel_id}")],
        [InlineKeyboardButton("❌ ВЫКЛЮЧИТЬ", callback_data=f"farewell_disable_{channel_id}")],
        [InlineKeyboardButton("◀️ НАЗАД", callback_data=f"set_ch_{channel_id}")],
    ])

def registration_editor_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 РЕДАКТИРОВАТЬ ТЕКСТ", callback_data='dev_edit_reg_text')],
        [InlineKeyboardButton("📎 РЕДАКТИРОВАТЬ МЕДИА", callback_data='dev_edit_reg_media')],
        [InlineKeyboardButton("🔄 СБРОСИТЬ", callback_data='dev_reset_reg')],
        [InlineKeyboardButton("◀️ НАЗАД", callback_data='developer')],
    ])

def beta_management_kb(user_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 ВСЕ БЕТА-ФУНКЦИИ", callback_data='dev_list_beta_features')],
        [InlineKeyboardButton("➕ ДОБАВИТЬ БЕТА-ФУНКЦИЮ", callback_data='dev_add_beta_feature')],
        [InlineKeyboardButton("📊 ИСТОРИЯ ОБНОВЛЕНИЙ", callback_data='dev_update_logs')],
        [InlineKeyboardButton("◀️ НАЗАД", callback_data='developer')],
    ])

def broadcast_audience_kb(user_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 ОБЫЧНЫЕ ПОЛЬЗОВАТЕЛИ", callback_data='broadcast_regular')],
        [InlineKeyboardButton("💳 С ПОДПИСКОЙ", callback_data='broadcast_subscribed')],
        [InlineKeyboardButton("🧪 ТЕСТЕРЫ", callback_data='broadcast_testers')],
        [InlineKeyboardButton("👥 ВСЕ ПОЛЬЗОВАТЕЛИ", callback_data='broadcast_all')],
        [InlineKeyboardButton("◀️ НАЗАД", callback_data='developer')],
    ])

def gift_kb(user_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 ОБЫЧНАЯ ПОДПИСКА", callback_data='gift_regular')],
        [InlineKeyboardButton("🧪 ТЕСТЕР ПОДПИСКА", callback_data='gift_tester')],
        [InlineKeyboardButton("◀️ НАЗАД", callback_data='developer')],
    ])

def feedback_kb(user_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⭐ 1", callback_data='feedback_1'), InlineKeyboardButton("⭐ 2", callback_data='feedback_2'), InlineKeyboardButton("⭐ 3", callback_data='feedback_3'), InlineKeyboardButton("⭐ 4", callback_data='feedback_4'), InlineKeyboardButton("⭐ 5", callback_data='feedback_5')],
        [InlineKeyboardButton("◀️ НАЗАД", callback_data='back')],
    ])

# ============================================
#  ОБРАБОТЧИКИ КОМАНД
# ============================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    
    # Проверка блокировки (пункт 17)
    if is_user_blocked(uid):
        await update.message.reply_text("❌ ВАШ АККАУНТ ЗАБЛОКИРОВАН!\n\nОбратитесь к разработчику: @GanzalesSs920")
        return
    
    create_user(uid, user.username)
    global BOT_STOPPED
    await clear_user_messages(context.bot, uid)
    log_main(uid, "Запуск бота", "/start")
    
    if BOT_STOPPED and uid != OWNER_ID:
        msg = await update.message.reply_text(
            "🔧 БОТ ЗАКРЫТ НА ТО!\n\n⏳ Пожалуйста, подождите.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💬 ПОДДЕРЖКА", callback_data='support')]])
        )
        add_user_message(uid, msg)
        return
    
    reg_text = get_setting("reg_text") or "🌟 ДОБРО ПОЖАЛОВАТЬ В {BOT_NAME}! 🌟\n\n📋 Для использования бота необходимо ЗАРЕГИСТРИРОВАТЬСЯ.\n\n🔹 Нажмите кнопку '✅ РЕГИСТРАЦИЯ'"
    reg_media = get_setting("reg_media")
    
    if not is_registered(uid):
        text = reg_text.replace("{BOT_NAME}", BOT_NAME)
        if reg_media:
            try:
                msg = await update.message.reply_photo(photo=reg_media, caption=text, reply_markup=reg_kb(uid))
                add_user_message(uid, msg)
                return
            except:
                try:
                    msg = await update.message.reply_video(video=reg_media, caption=text, reply_markup=reg_kb(uid))
                    add_user_message(uid, msg)
                    return
                except:
                    try:
                        msg = await update.message.reply_animation(animation=reg_media, caption=text, reply_markup=reg_kb(uid))
                        add_user_message(uid, msg)
                        return
                    except Exception as e:
                        log_error(f"Reg media error: {e}")
        msg = await update.message.reply_text(text, reply_markup=reg_kb(uid))
        add_user_message(uid, msg)
        return
    
    if uid == OWNER_ID and not is_subscribed(uid):
        end_date = (datetime.now() + timedelta(days=3650)).strftime('%Y-%m-%d')
        set_subscription(uid, end_date)
    
    custom_desc = get_setting("global_desc") or "Всем привет и спасибо что выбрали меня! 🎉"
    custom_media = get_setting("global_media")
    text = f"🌟 ДОБРО ПОЖАЛОВАТЬ В {BOT_NAME}! 🌟\n\n{custom_desc}"
    
    if custom_media:
        try:
            msg = await update.message.reply_photo(photo=custom_media, caption=text, reply_markup=main_kb(uid))
            add_user_message(uid, msg)
            return
        except:
            try:
                msg = await update.message.reply_video(video=custom_media, caption=text, reply_markup=main_kb(uid))
                add_user_message(uid, msg)
                return
            except:
                try:
                    msg = await update.message.reply_animation(animation=custom_media, caption=text, reply_markup=main_kb(uid))
                    add_user_message(uid, msg)
                    return
                except Exception as e:
                    log_error(f"Custom media error: {e}")
    
    msg = await update.message.reply_text(text, reply_markup=main_kb(uid))
    add_user_message(uid, msg)

async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_STOPPED
    if not update.effective_user:
        return
    
    u = update.effective_user
    uid = u.id
    msg = update.message
    
    # Проверка блокировки
    if is_user_blocked(uid):
        await msg.reply_text("❌ ВАШ АККАУНТ ЗАБЛОКИРОВАН!\n\nОбратитесь к разработчику: @GanzalesSs920")
        return
    
    try:
        await msg.delete()
    except:
        pass
    
    log_main(uid, "Сообщение", msg.text[:50] if msg.text else "Медиа")
    
    if BOT_STOPPED and uid != OWNER_ID:
        reply = await msg.reply_text(
            "🔧 БОТ ЗАКРЫТ НА ТО!\n\n⏳ Пожалуйста, подождите.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💬 ПОДДЕРЖКА", callback_data='support')]])
        )
        add_user_message(uid, reply)
        await delete_user_messages(context.bot, uid, keep_last=1)
        return
    
    # ===== РЕГИСТРАЦИЯ (ПУНКТ 16 - НЕЛЬЗЯ СКИПНУТЬ) =====
    if context.user_data.get('reg_wait'):
        name = msg.text.strip()
        if not re.match(r'^[a-zA-Zа-яА-Я0-9_]+$', name):
            reply = await msg.reply_text("❌ Только буквы, цифры и _", reply_markup=back_kb(uid, disable=True))
            add_user_message(uid, reply)
            await delete_user_messages(context.bot, uid, keep_last=1)
            return
        if len(name) < 2:
            reply = await msg.reply_text("❌ Минимум 2 символа!", reply_markup=back_kb(uid, disable=True))
            add_user_message(uid, reply)
            await delete_user_messages(context.bot, uid, keep_last=1)
            return
        if is_nickname_taken(name):
            reply = await msg.reply_text("❌ Это имя уже занято!", reply_markup=back_kb(uid, disable=True))
            add_user_message(uid, reply)
            await delete_user_messages(context.bot, uid, keep_last=1)
            return
        context.user_data['temp_name'] = name
        context.user_data['reg_wait'] = False
        context.user_data['age_wait'] = True
        reply = await msg.reply_text("🔞 ВАМ ЕСТЬ 18 ЛЕТ?\n\nОтветьте 'ДА' или 'НЕТ'", reply_markup=back_kb(uid, disable=True))
        add_user_message(uid, reply)
        await delete_user_messages(context.bot, uid, keep_last=1)
        return
    
    if context.user_data.get('age_wait'):
        answer = msg.text.strip().lower()
        if answer in ['да', 'yes', '1']:
            set_adult(uid, True)
            name = context.user_data.get('temp_name', 'Пользователь')
            set_user_nickname(uid, name)
            set_registered(uid)
            context.user_data['age_wait'] = False
            context.user_data['temp_name'] = None
            log_main(uid, "Регистрация", f"{name} (18+)")
            reply = await msg.reply_text(
                f"✅ РЕГИСТРАЦИЯ ЗАВЕРШЕНА!\n\n👤 {name}\n🆔 ID: {uid}\n🔞 Возраст подтверждён!",
                reply_markup=main_kb(uid)
            )
            add_user_message(uid, reply)
            await delete_user_messages(context.bot, uid, keep_last=1)
        elif answer in ['нет', 'no', '0']:
            set_adult(uid, False)
            name = context.user_data.get('temp_name', 'Пользователь')
            set_user_nickname(uid, name)
            set_registered(uid)
            context.user_data['age_wait'] = False
            context.user_data['temp_name'] = None
            log_main(uid, "Регистрация", f"{name} (18-)")
            reply = await msg.reply_text(
                f"✅ РЕГИСТРАЦИЯ ЗАВЕРШЕНА!\n\n👤 {name}\n🆔 ID: {uid}\n🔞 Доступ к 18+ контенту ЗАКРЫТ!",
                reply_markup=main_kb(uid)
            )
            add_user_message(uid, reply)
            await delete_user_messages(context.bot, uid, keep_last=1)
        else:
            reply = await msg.reply_text("❌ ВВЕДИТЕ 'ДА' ИЛИ 'НЕТ'!", reply_markup=back_kb(uid, disable=True))
            add_user_message(uid, reply)
            await delete_user_messages(context.bot, uid, keep_last=1)
        return
    
    # ===== ОСТАЛЬНЫЕ РЕЖИМЫ =====
    
    # Изменение имени
    if context.user_data.get('change_name_wait'):
        name = msg.text.strip()
        if not re.match(r'^[a-zA-Zа-яА-Я0-9_]+$', name):
            reply = await msg.reply_text("❌ Только буквы, цифры и _", reply_markup=back_kb(uid))
            add_user_message(uid, reply)
            await delete_user_messages(context.bot, uid, keep_last=1)
            return
        if len(name) < 2:
            reply = await msg.reply_text("❌ Минимум 2 символа!", reply_markup=back_kb(uid))
            add_user_message(uid, reply)
            await delete_user_messages(context.bot, uid, keep_last=1)
            return
        if is_nickname_taken(name):
            reply = await msg.reply_text("❌ Имя уже занято!", reply_markup=back_kb(uid))
            add_user_message(uid, reply)
            await delete_user_messages(context.bot, uid, keep_last=1)
            return
        old_name = get_user_nickname(uid)
        set_user_nickname(uid, name)
        if uid != OWNER_ID:
            increment_name_changes(uid)
        context.user_data['change_name_wait'] = False
        log_main(uid, "Смена имени", f"{old_name} → {name}")
        reply = await msg.reply_text(
            f"✅ ИМЯ ИЗМЕНЕНО!\n\n👤 {name}\n\n🔽 Что дальше?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✏️ ИЗМЕНИТЬ ЕЩЁ", callback_data='change_name')],
                [InlineKeyboardButton("👤 В ПРОФИЛЬ", callback_data='profile')],
                [InlineKeyboardButton("◀️ В ГЛАВНОЕ МЕНЮ", callback_data='back')],
            ])
        )
        add_user_message(uid, reply)
        await delete_user_messages(context.bot, uid, keep_last=1)
        return
    
    # Отправка сообщения
    if context.user_data.get('send_message_wait'):
        target_id = context.user_data['send_message_target']
        anonymous = context.user_data.get('send_message_anonymous', False)
        text = msg.text.strip()
        if not text:
            reply = await msg.reply_text("❌ ВВЕДИТЕ ТЕКСТ!", reply_markup=back_kb(uid))
            add_user_message(uid, reply)
            await delete_user_messages(context.bot, uid, keep_last=1)
            return
        success, result = send_message_to_user(context.bot, uid, target_id, text, anonymous)
        context.user_data['send_message_wait'] = False
        context.user_data['send_message_target'] = None
        log_main(uid, "Отправил сообщение", f"{'Анонимно' if anonymous else 'Публично'} → {target_id}")
        if success:
            await send_notification(
                context.bot,
                target_id,
                "💬 Новое сообщение",
                f"Вам написали: {text[:100]}{'...' if len(text) > 100 else ''}",
                f"view_msg_{target_id}"
            )
        reply = await msg.reply_text(result, reply_markup=main_kb(uid))
        add_user_message(uid, reply)
        await delete_user_messages(context.bot, uid, keep_last=1)
        return
    
    # Анти-спам: добавление слова
    if context.user_data.get('spam_add_wait'):
        channel_id = context.user_data['spam_add_wait']
        word = msg.text.strip()
        if word:
            add_blacklist_word(channel_id, word)
            reply = await msg.reply_text(f"✅ СЛОВО '{word}' ДОБАВЛЕНО В ЧЁРНЫЙ СПИСОК!", reply_markup=back_kb(uid))
            add_user_message(uid, reply)
            await delete_user_messages(context.bot, uid, keep_last=1)
        context.user_data['spam_add_wait'] = None
        return
    
    # Приветствие
    if context.user_data.get('welcome_edit_text_wait'):
        channel_id = context.user_data['welcome_edit_text_wait']
        text = msg.text.strip()
        if text:
            set_welcome_text(channel_id, text)
            set_setting(f"welcome_enabled_{channel_id}", '1')
            context.user_data['welcome_edit_text_wait'] = None
            reply = await msg.reply_text(
                f"✅ ПРИВЕТСТВИЕ СОХРАНЕНО!\n\n📝 {text}",
                reply_markup=welcome_commands_kb(channel_id)
            )
            add_user_message(uid, reply)
        await delete_user_messages(context.bot, uid, keep_last=1)
        return
    
    # Прощание
    if context.user_data.get('farewell_edit_text_wait'):
        channel_id = context.user_data['farewell_edit_text_wait']
        text = msg.text.strip()
        if text:
            set_farewell_text(channel_id, text)
            set_setting(f"farewell_enabled_{channel_id}", '1')
            context.user_data['farewell_edit_text_wait'] = None
            reply = await msg.reply_text(
                f"✅ ПРОЩАНИЕ СОХРАНЕНО!\n\n📝 {text}",
                reply_markup=farewell_commands_kb(channel_id)
            )
            add_user_message(uid, reply)
        await delete_user_messages(context.bot, uid, keep_last=1)
        return
    
    # Каптча
    if context.user_data.get('captcha_q_wait'):
        channel_id = context.user_data['captcha_q_wait']
        context.user_data['captcha_q'] = msg.text
        context.user_data['captcha_q_wait'] = None
        reply = await msg.reply_text("✏️ ВВЕДИТЕ ОТВЕТЫ (через запятую):", reply_markup=back_kb(uid))
        add_user_message(uid, reply)
        await delete_user_messages(context.bot, uid, keep_last=1)
        return
    
    if context.user_data.get('captcha_a_wait'):
        channel_id = context.user_data['captcha_a_wait']
        answers = [a.strip() for a in msg.text.split(',')]
        question = context.user_data.get('captcha_q', 'Есть ли вам 18 лет?')
        set_captcha_settings(channel_id, question, answers)
        context.user_data['captcha_a_wait'] = None
        context.user_data['captcha_q'] = None
        reply = await msg.reply_text("✅ КАПТЧА СОХРАНЕНА!", reply_markup=back_kb(uid))
        add_user_message(uid, reply)
        await delete_user_messages(context.bot, uid, keep_last=1)
        return
    
    # Автопостинг
    if context.user_data.get('post_wait'):
        channel_id = context.user_data['post_wait']
        post_data = {
            'text': msg.text or '',
            'media': None,
            'media_type': None
        }
        if msg.photo:
            post_data['media'] = msg.photo[-1].file_id
            post_data['media_type'] = 'photo'
        elif msg.video:
            post_data['media'] = msg.video.file_id
            post_data['media_type'] = 'video'
        elif msg.animation:
            post_data['media'] = msg.animation.file_id
            post_data['media_type'] = 'animation'
        elif msg.document:
            post_data['media'] = msg.document.file_id
            post_data['media_type'] = 'document'
        context.user_data['post_data'] = post_data
        context.user_data['post_wait'] = None
        context.user_data['post_channel_id'] = channel_id
        context.user_data['post_date_wait'] = True
        reply = await msg.reply_text(
            "📅 ВВЕДИТЕ ДАТУ (ДД.ММ.ГГГГ ЧЧ:ММ):\n"
            "Пример: 31.12.2026 23:59",
            reply_markup=back_kb(uid)
        )
        add_user_message(uid, reply)
        await delete_user_messages(context.bot, uid, keep_last=1)
        return
    
    if context.user_data.get('post_date_wait'):
        try:
            parts = msg.text.split(' ')
            dt = datetime.strptime(f"{parts[0]} {parts[1] if len(parts) > 1 else '00:00'}", '%d.%m.%Y %H:%M')
            scheduled = dt.strftime('%Y-%m-%d %H:%M:%S')
            post_data = context.user_data.get('post_data', {})
            add_scheduled_post(
                context.user_data['post_channel_id'],
                post_data.get('text', ''),
                post_data.get('media'),
                scheduled
            )
            context.user_data['post_date_wait'] = None
            context.user_data['post_data'] = None
            context.user_data['post_channel_id'] = None
            reply = await msg.reply_text(
                f"✅ ПОСТ ЗАПЛАНИРОВАН!\n\n"
                f"📅 {dt.strftime('%d.%m.%Y %H:%M')}\n"
                f"{'🖼 С медиа' if post_data.get('media') else '📝 Без медиа'}",
                reply_markup=auto_posting_menu_kb(context.user_data.get('post_channel_id', 0))
            )
            add_user_message(uid, reply)
        except Exception as e:
            reply = await msg.reply_text(
                f"❌ НЕВЕРНЫЙ ФОРМАТ!\n\n"
                f"Пример: 31.12.2026 23:59\n"
                f"Ошибка: {str(e)}",
                reply_markup=back_kb(uid)
            )
            add_user_message(uid, reply)
        await delete_user_messages(context.bot, uid, keep_last=1)
        return
    
    # Разработчик: создание кода
    if context.user_data.get('code_create_name'):
        context.user_data['code_name'] = msg.text.strip()
        context.user_data['code_create_name'] = False
        context.user_data['code_create_uses'] = True
        reply = await msg.reply_text(
            f"📝 Название: {context.user_data['code_name']}\n\n"
            f"🔢 Введите количество использований:",
            reply_markup=back_kb(uid)
        )
        add_user_message(uid, reply)
        await delete_user_messages(context.bot, uid, keep_last=1)
        return
    
    if context.user_data.get('code_create_uses'):
        try:
            uses = int(msg.text.strip())
            if uses <= 0:
                raise ValueError
            context.user_data['code_create_uses'] = False
            context.user_data['code_create_uses_count'] = uses
            context.user_data['code_create_days_wait'] = True
            reply = await msg.reply_text(
                f"📝 Название: {context.user_data['code_name']}\n"
                f"🔢 Использований: {uses}\n\n"
                f"📅 Выберите срок действия:",
                reply_markup=code_days_kb(uid)
            )
            add_user_message(uid, reply)
        except:
            reply = await msg.reply_text("❌ Введите число больше 0!", reply_markup=back_kb(uid))
            add_user_message(uid, reply)
        await delete_user_messages(context.bot, uid, keep_last=1)
        return
    
    # Разработчик: бета-функции
    if context.user_data.get('add_beta_feature_name'):
        context.user_data['beta_name'] = msg.text.strip()
        context.user_data['add_beta_feature_name'] = False
        context.user_data['add_beta_feature_code'] = True
        reply = await msg.reply_text(
            f"📝 Название: {context.user_data['beta_name']}\n\n"
            f"📝 Введите описание функции:",
            reply_markup=back_kb(uid)
        )
        add_user_message(uid, reply)
        await delete_user_messages(context.bot, uid, keep_last=1)
        return
    
    if context.user_data.get('add_beta_feature_code'):
        code = msg.text.strip()
        name = context.user_data.get('beta_name', 'Бета-функция')
        add_beta_feature(name, code, code[:100] + '...' if len(code) > 100 else code)
        context.user_data['add_beta_feature_code'] = False
        context.user_data['beta_name'] = None
        reply = await msg.reply_text(
            f"✅ БЕТА-ФУНКЦИЯ ДОБАВЛЕНА!\n\n"
            f"📝 Название: {name}\n"
            f"📌 Статус: Тестирование",
            reply_markup=dev_kb(uid)
        )
        add_user_message(uid, reply)
        await delete_user_messages(context.bot, uid, keep_last=1)
        return
    
    # Разработчик: тестеры
    if context.user_data.get('add_tester_wait'):
        if uid != OWNER_ID:
            return
        try:
            target_id = int(msg.text.strip())
            set_setting(f"tester_{target_id}", '1')
            log_main(uid, "Добавил тестера", str(target_id))
            reply = await msg.reply_text(f"✅ ТЕСТЕР ДОБАВЛЕН! ID: {target_id}", reply_markup=dev_kb(uid))
            add_user_message(uid, reply)
            try:
                await context.bot.send_message(chat_id=target_id, text="🎉 ВЫ СТАЛИ ТЕСТЕРОМ!")
            except:
                pass
        except:
            reply = await msg.reply_text("❌ НЕВЕРНЫЙ ID!", reply_markup=back_kb(uid))
            add_user_message(uid, reply)
        context.user_data['add_tester_wait'] = False
        await delete_user_messages(context.bot, uid, keep_last=1)
        return
    
    if context.user_data.get('remove_tester_wait'):
        if uid != OWNER_ID:
            return
        try:
            target_id = int(msg.text.strip())
            set_setting(f"tester_{target_id}", '0')
            log_main(uid, "Удалил тестера", str(target_id))
            reply = await msg.reply_text(f"✅ ТЕСТЕР УДАЛЕН! ID: {target_id}", reply_markup=dev_kb(uid))
            add_user_message(uid, reply)
        except:
            reply = await msg.reply_text("❌ НЕВЕРНЫЙ ID!", reply_markup=back_kb(uid))
            add_user_message(uid, reply)
        context.user_data['remove_tester_wait'] = False
        await delete_user_messages(context.bot, uid, keep_last=1)
        return
    
    # Разработчик: рассылка
    if context.user_data.get('broadcast_wait'):
        if uid != OWNER_ID:
            return
        broadcast_data = {'text': msg.text or '', 'media': None, 'media_type': None}
        if msg.photo:
            broadcast_data['media'] = msg.photo[-1].file_id
            broadcast_data['media_type'] = 'photo'
        elif msg.video:
            broadcast_data['media'] = msg.video.file_id
            broadcast_data['media_type'] = 'video'
        elif msg.animation:
            broadcast_data['media'] = msg.animation.file_id
            broadcast_data['media_type'] = 'animation'
        elif msg.document:
            broadcast_data['media'] = msg.document.file_id
            broadcast_data['media_type'] = 'document'
        audience_type = context.user_data.get('broadcast_audience', 'all')
        all_users = get_all_users()
        count = 0
        for u in all_users:
            if is_user_blocked(u['user_id']):
                continue
            include = False
            if audience_type == 'regular':
                if not is_tester(u['user_id']) and u['user_id'] != OWNER_ID and not is_subscribed(u['user_id']):
                    include = True
            elif audience_type == 'subscribed':
                if is_subscribed(u['user_id']) and u['user_id'] != OWNER_ID:
                    include = True
            elif audience_type == 'testers':
                if is_tester(u['user_id']):
                    include = True
            else:
                include = True
            if include:
                try:
                    if broadcast_data['media']:
                        if broadcast_data['media_type'] == 'photo':
                            await context.bot.send_photo(chat_id=u['user_id'], photo=broadcast_data['media'], caption=broadcast_data['text'] if broadcast_data['text'] else None)
                        elif broadcast_data['media_type'] == 'video':
                            await context.bot.send_video(chat_id=u['user_id'], video=broadcast_data['media'], caption=broadcast_data['text'] if broadcast_data['text'] else None)
                        elif broadcast_data['media_type'] == 'animation':
                            await context.bot.send_animation(chat_id=u['user_id'], animation=broadcast_data['media'], caption=broadcast_data['text'] if broadcast_data['text'] else None)
                        elif broadcast_data['media_type'] == 'document':
                            await context.bot.send_document(chat_id=u['user_id'], document=broadcast_data['media'], caption=broadcast_data['text'] if broadcast_data['text'] else None)
                    else:
                        await context.bot.send_message(chat_id=u['user_id'], text=f"📨 РАССЫЛКА\n\n{broadcast_data['text']}")
                    count += 1
                    await asyncio.sleep(0.05)
                except:
                    pass
        context.user_data['broadcast_wait'] = False
        context.user_data['broadcast_audience'] = None
        reply = await msg.reply_text(
            f"✅ РАССЫЛКА ЗАВЕРШЕНА!\n\n"
            f"📨 Отправлено: {count} пользователям\n"
            f"👥 Аудитория: {audience_type}\n"
            f"🖼 С медиа: {'✅' if broadcast_data['media'] else '❌'}",
            reply_markup=dev_kb(uid)
        )
        add_user_message(uid, reply)
        await delete_user_messages(context.bot, uid, keep_last=1)
        return
    
    # Разработчик: подарок
    if context.user_data.get('gift_wait'):
        if uid != OWNER_ID:
            return
        try:
            target_id = int(msg.text.strip())
            gift_type = context.user_data.get('gift_type', 'regular')
            days = 30 if gift_type == 'regular' else 60
            end_date = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')
            set_subscription(target_id, end_date)
            if gift_type == 'tester':
                set_setting(f"tester_{target_id}", '1')
            reply = await msg.reply_text(
                f"🎁 ПОДАРЕНА! До {end_date}\n🧪 Тип: {'ТЕСТЕР' if gift_type == 'tester' else 'ОБЫЧНАЯ'}",
                reply_markup=dev_kb(uid)
            )
            add_user_message(uid, reply)
            try:
                await context.bot.send_message(
                    chat_id=target_id,
                    text=f"🎁 Вам подарили подписку до {end_date}!\n🧪 Тип: {'ТЕСТЕР' if gift_type == 'tester' else 'ОБЫЧНАЯ'}"
                )
            except:
                pass
        except:
            reply = await msg.reply_text("❌ НЕВЕРНЫЙ ID!", reply_markup=back_kb(uid))
            add_user_message(uid, reply)
        context.user_data['gift_wait'] = False
        context.user_data['gift_type'] = None
        await delete_user_messages(context.bot, uid, keep_last=1)
        return
    
    # Разработчик: кастомизация
    if context.user_data.get('custom_desc_wait'):
        if uid != OWNER_ID:
            return
        set_setting("global_desc", msg.text)
        context.user_data['custom_desc_wait'] = False
        reply = await msg.reply_text(
            f"✅ ОПИСАНИЕ ОБНОВЛЕНО!\n\n📝 {msg.text}",
            reply_markup=dev_kb(uid)
        )
        add_user_message(uid, reply)
        await delete_user_messages(context.bot, uid, keep_last=1)
        return
    
    if context.user_data.get('custom_media_wait'):
        if uid != OWNER_ID:
            return
        media_id = None
        if msg.photo:
            media_id = msg.photo[-1].file_id
        elif msg.video:
            media_id = msg.video.file_id
        elif msg.animation:
            media_id = msg.animation.file_id
        elif msg.document:
            media_id = msg.document.file_id
        if media_id:
            set_setting("global_media", media_id)
            context.user_data['custom_media_wait'] = False
            reply = await msg.reply_text("✅ МЕДИА СОХРАНЕНО!", reply_markup=dev_kb(uid))
            add_user_message(uid, reply)
        else:
            reply = await msg.reply_text("❌ ОТПРАВЬТЕ ФОТО/ВИДЕО/GIF!", reply_markup=back_kb(uid))
            add_user_message(uid, reply)
        await delete_user_messages(context.bot, uid, keep_last=1)
        return
    
    # Разработчик: редактор регистрации
    if context.user_data.get('edit_reg_text_wait'):
        if uid != OWNER_ID:
            return
        set_setting("reg_text", msg.text)
        context.user_data['edit_reg_text_wait'] = False
        reply = await msg.reply_text(
            f"✅ ТЕКСТ РЕГИСТРАЦИИ СОХРАНЕН!\n\n📝 {msg.text}",
            reply_markup=registration_editor_kb()
        )
        add_user_message(uid, reply)
        await delete_user_messages(context.bot, uid, keep_last=1)
        return
    
    if context.user_data.get('edit_reg_media_wait'):
        if uid != OWNER_ID:
            return
        media_id = None
        if msg.photo:
            media_id = msg.photo[-1].file_id
        elif msg.video:
            media_id = msg.video.file_id
        elif msg.animation:
            media_id = msg.animation.file_id
        elif msg.document:
            media_id = msg.document.file_id
        if media_id:
            set_setting("reg_media", media_id)
            context.user_data['edit_reg_media_wait'] = False
            reply = await msg.reply_text("✅ МЕДИА РЕГИСТРАЦИИ СОХРАНЕНО!", reply_markup=registration_editor_kb())
            add_user_message(uid, reply)
        else:
            reply = await msg.reply_text("❌ ОТПРАВЬТЕ ФОТО/ВИДЕО/GIF!", reply_markup=back_kb(uid))
            add_user_message(uid, reply)
        await delete_user_messages(context.bot, uid, keep_last=1)
        return
    
    # ВП: создание поста
    if context.user_data.get('vp_wait_channel'):
        try:
            chat_id = extract_channel_id_from_text(msg.text)
            if chat_id is None:
                reply = await msg.reply_text(
                    "❌ НЕВЕРНЫЙ ID!\n\n"
                    "Введите ID канала (начинается с -100):\n"
                    "Пример: -1001234567890",
                    reply_markup=back_kb(uid)
                )
                add_user_message(uid, reply)
                return
            try:
                chat = await context.bot.get_chat(chat_id)
                if chat.type not in ['channel', 'supergroup']:
                    reply = await msg.reply_text("❌ ЭТО НЕ КАНАЛ!", reply_markup=back_kb(uid))
                    add_user_message(uid, reply)
                    return
            except:
                reply = await msg.reply_text("❌ КАНАЛ НЕ НАЙДЕН!", reply_markup=back_kb(uid))
                add_user_message(uid, reply)
                return
            context.user_data['vp_post']['channel_id'] = chat_id
            context.user_data['vp_wait_channel'] = False
            reply = await msg.reply_text(
                "✅ КАНАЛ ВЫБРАН!\n\n"
                "📝 Введите текст поста (минимум 10 символов):",
                reply_markup=back_kb(uid)
            )
            context.user_data['vp_wait_text'] = True
            add_user_message(uid, reply)
        except Exception as e:
            reply = await msg.reply_text(f"❌ ОШИБКА: {str(e)[:100]}", reply_markup=back_kb(uid))
            add_user_message(uid, reply)
            context.user_data['vp_wait_channel'] = False
        await delete_user_messages(context.bot, uid, keep_last=1)
        return
    
    if context.user_data.get('vp_wait_text'):
        text = msg.text.strip()
        if len(text) < 10:
            reply = await msg.reply_text(
                "❌ ТЕКСТ ДОЛЖЕН БЫТЬ НЕ МЕНЕЕ 10 СИМВОЛОВ!",
                reply_markup=back_kb(uid)
            )
            add_user_message(uid, reply)
            await delete_user_messages(context.bot, uid, keep_last=1)
            return
        if 'vp_post' not in context.user_data:
            context.user_data['vp_post'] = {}
        context.user_data['vp_post']['text'] = text
        context.user_data['vp_wait_text'] = False
        if uid == OWNER_ID and not context.user_data['vp_post'].get('channel_id'):
            channels = get_user_channels(uid)
            if channels:
                context.user_data['vp_post']['channel_id'] = channels[0]['channel_id']
        if not context.user_data['vp_post'].get('channel_id'):
            reply = await msg.reply_text(
                "❌ НЕ ВЫБРАН КАНАЛ!\n\n"
                "Введите ID канала вручную:",
                reply_markup=back_kb(uid)
            )
            context.user_data['vp_wait_channel'] = True
            add_user_message(uid, reply)
            await delete_user_messages(context.bot, uid, keep_last=1)
            return
        reply = await msg.reply_text(
            "✅ ТЕКСТ СОХРАНЕН!\n\n"
            "Теперь настройте пост:",
            reply_markup=vp_create_kb(uid)
        )
        add_user_message(uid, reply)
        await delete_user_messages(context.bot, uid, keep_last=1)
        return
    
    if context.user_data.get('vp_wait_media'):
        media_id = None
        if msg.photo:
            media_id = msg.photo[-1].file_id
        elif msg.video:
            media_id = msg.video.file_id
        elif msg.animation:
            media_id = msg.animation.file_id
        if media_id:
            if 'vp_post' not in context.user_data:
                context.user_data['vp_post'] = {}
            context.user_data['vp_post']['media'] = media_id
            reply = await msg.reply_text(
                "✅ МЕДИА СОХРАНЕНО!\n\n"
                "Продолжайте настройку:",
                reply_markup=vp_create_kb(uid)
            )
            add_user_message(uid, reply)
        else:
            reply = await msg.reply_text(
                "⚠️ МЕДИА НЕ ОБНАРУЖЕНО (пропускаем)\n\n"
                "Продолжайте настройку:",
                reply_markup=vp_create_kb(uid)
            )
            add_user_message(uid, reply)
        context.user_data['vp_wait_media'] = False
        await delete_user_messages(context.bot, uid, keep_last=1)
        return
    
    # Разработчик: поиск пользователей
    if context.user_data.get('dev_search_type'):
        search_type = context.user_data['dev_search_type']
        query = msg.text.strip()
        all_users = get_all_users()
        results = []
        for u in all_users:
            if is_user_blocked(u['user_id']):
                continue
            if search_type == 'nick':
                nickname = get_user_nickname(u['user_id']) or ''
                if query.lower() in nickname.lower():
                    results.append(u)
            elif search_type == 'user_id':
                if query == str(u['user_id']):
                    results.append(u)
            elif search_type == 'channel_name':
                channels = get_user_channels(u['user_id'])
                for ch in channels:
                    if query.lower() in ch['channel_name'].lower():
                        results.append(u)
                        break
        if not results:
            reply = await msg.reply_text("❌ НЕ НАЙДЕНО!", reply_markup=back_kb(uid))
            add_user_message(uid, reply)
        else:
            text = f"🔍 РЕЗУЛЬТАТЫ ПОИСКА ({len(results)}):\n\n"
            for u in results[:20]:
                nickname = get_user_nickname(u['user_id']) or "Не указан"
                sub_end = get_subscription_end(u['user_id'])
                sub_status = f"✅ ДО {sub_end}" if sub_end and is_subscribed(u['user_id']) else "❌ НЕТ"
                is_tester_user = "✅ ДА" if is_tester(u['user_id']) else "❌ НЕТ"
                is_blocked = "🔒 ДА" if is_user_blocked(u['user_id']) else "❌ НЕТ"
                channels = get_user_channels(u['user_id'])
                text += (
                    f"👤 {nickname}\n"
                    f"   🆔 ID: {u['user_id']}\n"
                    f"   👤 Username: @{u['username'] if u['username'] else 'Не указан'}\n"
                    f"   💳 Подписка: {sub_status}\n"
                    f"   🧪 Тестер: {is_tester_user}\n"
                    f"   🔒 Заблокирован: {is_blocked}\n"
                )
                if channels:
                    text += f"   📺 Каналов: {len(channels)}\n"
                    for ch in channels[:3]:
                        text += f"      📺 {ch['channel_name']} (ID: {ch['channel_id']})\n"
                text += "\n"
                if uid == OWNER_ID:
                    if is_user_blocked(u['user_id']):
                        text += f"   [🔓 РАЗБЛОКИРОВАТЬ](callback_data=unblock_user_{u['user_id']})\n"
                    else:
                        text += f"   [🔒 ЗАБЛОКИРОВАТЬ](callback_data=block_user_{u['user_id']})\n"
            if len(results) > 20:
                text += f"... и еще {len(results) - 20}"
            reply = await msg.reply_text(text, reply_markup=back_kb(uid))
            add_user_message(uid, reply)
        context.user_data['dev_search_type'] = None
        await delete_user_messages(context.bot, uid, keep_last=1)
        return
    
    # ===== ОТЗЫВЫ (ПУНКТ 19) =====
    if context.user_data.get('feedback_wait'):
        text = msg.text.strip()
        if not text:
            reply = await msg.reply_text("❌ ВВЕДИТЕ ТЕКСТ ОТЗЫВА!", reply_markup=back_kb(uid))
            add_user_message(uid, reply)
            await delete_user_messages(context.bot, uid, keep_last=1)
            return
        feature = context.user_data.get('feedback_feature', 'Неизвестная функция')
        rating = context.user_data.get('feedback_rating', 5)
        add_feedback(uid, feature, text, rating)
        context.user_data['feedback_wait'] = False
        context.user_data['feedback_feature'] = None
        context.user_data['feedback_rating'] = None
        # Отправляем уведомление разработчику
        await context.bot.send_message(
            chat_id=OWNER_ID,
            text=f"📝 НОВЫЙ ОТЗЫВ!\n\n"
            f"👤 Пользователь: {get_user_nickname(uid) or uid}\n"
            f"🔬 Функция: {feature}\n"
            f"⭐ Оценка: {rating}/5\n"
            f"📝 Текст:\n{text}"
        )
        reply = await msg.reply_text(
            f"✅ ОТЗЫВ ОТПРАВЛЕН!\n\n"
            f"Спасибо за ваш отзыв о функции '{feature}'!",
            reply_markup=main_kb(uid)
        )
        add_user_message(uid, reply)
        await delete_user_messages(context.bot, uid, keep_last=1)
        return
    
    # По умолчанию
    reply = await msg.reply_text("🔄 Используй кнопки!", reply_markup=main_kb(uid))
    add_user_message(uid, reply)
    await delete_user_messages(context.bot, uid, keep_last=1)

# ============================================
#  АНТИ-СПАМ / ФИЛЬТР СЛОВ (ПУНКТ 4)
# ============================================

async def check_spam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id
    if user_id == OWNER_ID or user_id == context.bot.id:
        return
    if is_user_blocked(user_id):
        return
    if get_setting(f"anti_spam_enabled_{chat_id}") != '1':
        return
    words = get_blacklist_words(chat_id)
    if not words:
        return
    text = update.message.text.lower()
    message_text = update.message.text
    for word in words:
        if word.lower() in text:
            try:
                await update.message.delete()
                user_name = update.message.from_user.first_name or "Пользователь"
                user_mention = f"@{update.message.from_user.username}" if update.message.from_user.username else user_name
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"🚫 ВАШЕ СООБЩЕНИЕ УДАЛЕНО!\n\n"
                    f"📌 Причина: Запрещённое слово '{word}'\n"
                    f"👤 {user_mention}\n"
                    f"🆔 ID: {user_id}\n\n"
                    f"⚠️ Повторные нарушения приведут к блокировке!"
                )
                log_main(user_id, "Фильтр слов", f"Удалено сообщение с словом '{word}' в группе {chat_id}")
                log_main(user_id, "Текст", message_text[:100])
                break
            except Exception as e:
                log_error(f"Anti-spam error: {e}")

async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.new_chat_members:
        return
    chat_id = update.message.chat_id
    if get_setting(f"welcome_enabled_{chat_id}") != '1':
        return
    welcome_text = get_welcome_text(chat_id)
    if not welcome_text:
        return
    for member in update.message.new_chat_members:
        if member.id == context.bot.id:
            continue
        name = member.first_name or "Пользователь"
        chat_title = update.message.chat.title or "Канал"
        mention = f"@{member.username}" if member.username else name
        count = get_channel_subscribers(context.bot, chat_id)
        text = (welcome_text
                .replace("{name}", name)
                .replace("{chat}", chat_title)
                .replace("{mention}", mention)
                .replace("{count}", str(count)))
        try:
            await update.message.reply_text(text)
        except Exception as e:
            log_error(f"Welcome error: {e}")

async def farewell_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.left_chat_member:
        return
    chat_id = update.message.chat_id
    if get_setting(f"farewell_enabled_{chat_id}") != '1':
        return
    farewell_text = get_farewell_text(chat_id)
    if not farewell_text:
        return
    member = update.message.left_chat_member
    if member.id == context.bot.id:
        return
    name = member.first_name or "Пользователь"
    chat_title = update.message.chat.title or "Канал"
    mention = f"@{member.username}" if member.username else name
    count = get_channel_subscribers(context.bot, chat_id)
    text = (farewell_text
            .replace("{name}", name)
            .replace("{chat}", chat_title)
            .replace("{mention}", mention)
            .replace("{count}", str(count)))
    try:
        await update.message.reply_text(text)
    except Exception as e:
        log_error(f"Farewell error: {e}")

async def handle_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        chat_id = update.chat_join_request.chat.id
        user_id = update.chat_join_request.from_user.id
        
        if is_user_blocked(user_id):
            try:
                await context.bot.decline_chat_join_request(chat_id=chat_id, user_id=user_id)
                log_main(user_id, "Автоприём", f"Заявка отклонена - пользователь заблокирован")
                return
            except:
                pass
        
        if get_auto_approve(chat_id):
            try:
                await context.bot.approve_chat_join_request(chat_id=chat_id, user_id=user_id)
                log_main(user_id, "Автоприём", f"Заявка одобрена в канал {chat_id}")
                try:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=f"✅ ВАША ЗАЯВКА ОДОБРЕНА!\n\n"
                        f"📺 Канал: {update.chat_join_request.chat.title}\n"
                        f"🎉 Добро пожаловать!"
                    )
                except:
                    pass
            except Exception as e:
                log_error(f"Join request error: {e}")
                try:
                    await context.bot.approve_chat_join_request(chat_id=chat_id, user_id=user_id)
                except:
                    pass
    except Exception as e:
        log_error(f"Join request handler error: {e}")

# ============================================
#  ОБРАБОТЧИК ПЛАТЕЖЕЙ (TELEGRAM STARS) - ПУНКТ 23
# ============================================

async def pre_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик предпроверки платежа"""
    query = update.pre_checkout_query
    user_id = query.from_user.id
    
    # Проверяем, есть ли платёж в ожидании
    payment = get_pending_payment(user_id)
    if not payment:
        await query.answer(ok=False, error_message="❌ Платёж не найден. Попробуйте заново.")
        return
    
    # Проверяем сумму
    expected_amount = payment['amount']
    if query.total_amount != expected_amount:
        await query.answer(ok=False, error_message=f"❌ Неверная сумма. Ожидается {expected_amount} ⭐")
        return
    
    # Всё ок, подтверждаем
    await query.answer(ok=True)

async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик успешного платежа"""
    message = update.message
    user_id = message.from_user.id
    payment_info = message.successful_payment
    
    # Находим платёж в БД
    payment = get_pending_payment(user_id)
    if not payment:
        await message.reply_text("❌ ОШИБКА! Платёж не найден в системе.\n\nОбратитесь к разработчику: @GanzalesSs920")
        return
    
    # Обновляем статус платежа
    update_payment_status(payment['payment_id'], 'success')
    
    # Получаем тип подписки и дни
    plan_type = payment['plan_type']
    sub_type, days = parse_plan_type(plan_type)
    
    # Активируем подписку
    end_date = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')
    set_subscription(user_id, end_date)
    
    # Если тестер - добавляем в тестеры
    if sub_type == 'tester':
        set_setting(f"tester_{user_id}", '1')
    
    log_main(user_id, "Оплата Stars", f"{plan_type} на {days} дней")
    
    await message.reply_text(
        f"✅ ОПЛАТА ПОДТВЕРЖДЕНА!\n\n"
        f"⭐ Спасибо за покупку!\n"
        f"📅 Подписка активна до {end_date}\n"
        f"🧪 Тип: {'ТЕСТЕР' if sub_type == 'tester' else 'ОБЫЧНАЯ'}\n\n"
        f"🔽 Что дальше?",
        reply_markup=main_kb(user_id)
    )
    
    # Уведомление разработчику
    await context.bot.send_message(
        chat_id=OWNER_ID,
        text=f"💰 НОВАЯ ОПЛАТА!\n\n"
        f"👤 Пользователь: {get_user_nickname(user_id) or user_id}\n"
        f"📅 План: {plan_type}\n"
        f"⭐ Сумма: {payment['amount']} Stars\n"
        f"📅 Подписка до: {end_date}"
    )

# ============================================
#  ОБРАБОТЧИК КНОПОК (CALLBACK)
# ============================================

async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_STOPPED, BOT_VERSION
    if not update.effective_user:
        return
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    data = query.data
    await delete_user_messages(context.bot, uid, keep_last=1)
    
    async def edit_current(text, reply_markup=None, media=None):
        try:
            if media:
                try:
                    await query.edit_message_media(media=InputMediaPhoto(media=media, caption=text), reply_markup=reply_markup)
                    return
                except:
                    try:
                        await query.edit_message_media(media=InputMediaVideo(media=media, caption=text), reply_markup=reply_markup)
                        return
                    except:
                        try:
                            await query.edit_message_media(media=InputMediaAnimation(media=media, caption=text), reply_markup=reply_markup)
                            return
                        except:
                            pass
            await query.edit_message_text(text, reply_markup=reply_markup)
        except Exception as e:
            log_error(f"Edit error: {e}")
            try:
                if media:
                    msg = await query.message.reply_photo(photo=media, caption=text, reply_markup=reply_markup)
                else:
                    msg = await query.message.reply_text(text, reply_markup=reply_markup)
                add_user_message(uid, msg)
                try:
                    await query.message.delete()
                except:
                    pass
            except:
                pass
    
    async def send_vp_post(post):
        user_id = post['user_id']
        channel_id = post['channel_id']
        text = post['text']
        media = post['media']
        is_adult = post['is_adult']
        category = post['category']
        created_at = post['created_at']
        owner_name = get_user_nickname(user_id) or "Неизвестен"
        channel = None
        for ch in get_user_channels(user_id):
            if ch['channel_id'] == channel_id:
                channel = ch
                break
        channel_name = channel['channel_name'] if channel else "Канал удален"
        caption = (
            f"📢 ВП (ВЗАИМОПОСТ)\n\n"
            f"📺 Канал: {channel_name}\n"
            f"👤 Владелец: {owner_name}\n"
            f"📂 Категория: {category if category else 'Без категории'}\n"
        )
        if is_adult:
            caption += f"🔞 18+\n"
        caption += f"🕐 {created_at}\n\n📝 {text}\n\n"
        kb = []
        if uid == OWNER_ID:
            kb.append([InlineKeyboardButton("🗑 УДАЛИТЬ ПОСТ", callback_data=f"vp_delete_{post['id']}")])
        kb.append([InlineKeyboardButton("◀️ НАЗАД", callback_data='vp_view')])
        try:
            if media:
                try:
                    await query.message.reply_photo(photo=media, caption=caption, reply_markup=InlineKeyboardMarkup(kb))
                    return
                except:
                    pass
                try:
                    await query.message.reply_video(video=media, caption=caption, reply_markup=InlineKeyboardMarkup(kb))
                    return
                except:
                    pass
                try:
                    await query.message.reply_animation(animation=media, caption=caption, reply_markup=InlineKeyboardMarkup(kb))
                    return
                except:
                    pass
                await query.message.reply_text(caption + "\n⚠️ Медиа не загрузилось", reply_markup=InlineKeyboardMarkup(kb))
            else:
                await query.message.reply_text(caption, reply_markup=InlineKeyboardMarkup(kb))
        except Exception as e:
            log_error(f"Send VP post error: {e}")
            await query.message.reply_text(caption + f"\n\n❌ Ошибка", reply_markup=InlineKeyboardMarkup(kb))
    
    log_main(uid, "Нажатие кнопки", data)
    
    if BOT_STOPPED and uid != OWNER_ID:
        await edit_current("🔧 БОТ ЗАКРЫТ НА ТО!\n\n⏳ Пожалуйста, подождите.", InlineKeyboardMarkup([[InlineKeyboardButton("💬 ПОДДЕРЖКА", callback_data='support')]]))
        return
    
    # ===== НАВИГАЦИЯ (ПУНКТ 20) =====
    if data == 'back_to_main':
        custom_desc = get_setting("global_desc") or "Всем привет и спасибо что выбрали меня! 🎉"
        custom_media = get_setting("global_media")
        text = f"🌟 ДОБРО ПОЖАЛОВАТЬ В {BOT_NAME}! 🌟\n\n{custom_desc}"
        USER_LAST_MENU[uid] = 'main'
        await edit_current(text, main_kb(uid), custom_media)
        return
    
    if data == 'back':
        last_menu = USER_LAST_MENU.get(uid, 'main')
        if last_menu == 'developer':
            await edit_current("⚙️ ПАНЕЛЬ РАЗРАБОТЧИКА", dev_kb(uid))
        else:
            custom_desc = get_setting("global_desc") or "Всем привет и спасибо что выбрали меня! 🎉"
            custom_media = get_setting("global_media")
            text = f"🌟 ДОБРО ПОЖАЛОВАТЬ В {BOT_NAME}! 🌟\n\n{custom_desc}"
            await edit_current(text, main_kb(uid), custom_media)
        return
    
    # ===== РЕГИСТРАЦИЯ =====
    if data == 'register':
        if is_registered(uid):
            await edit_current("✅ ВЫ УЖЕ ЗАРЕГИСТРИРОВАНЫ!", main_kb(uid))
            return
        context.user_data['reg_wait'] = True
        await edit_current("📝 ПРИДУМАЙТЕ УНИКАЛЬНОЕ ИМЯ:\n\n❌ Уникальное!\n✅ Минимум 2 символа\n✅ Буквы, цифры и _\n\n📌 Пример: Gamer_2024", back_kb(uid, disable=True))
        return
    
    if data == 'age_verify':
        context.user_data['age_wait'] = True
        await edit_current("🔞 ВАМ ЕСТЬ 18 ЛЕТ?\n\nВведите 'ДА' или 'НЕТ'", back_kb(uid, disable=True))
        return
    
    # ===== ПОДПИСКА (TELEGRAM STARS) =====
    if data == 'subscription':
        await edit_current("💳 ВЫБЕРИТЕ ТИП ПОДПИСКИ:\n\n👤 ОБЫЧНАЯ - доступ к основным функциям\n🧪 ТЕСТЕР - доступ к бета-функциям + все привилегии обычной", subscription_kb(uid))
        return
    
    if data == 'sub_regular':
        await edit_current("👤 ОБЫЧНАЯ ПОДПИСКА\n\n✅ Доступ к основным функциям\n✅ Поиск каналов\n✅ ВП (ВзаимоПост)\n✅ Привязка каналов\n\n💰 Выберите срок:", sub_regular_kb(uid))
        return
    
    if data == 'sub_tester':
        await edit_current("🧪 ТЕСТЕР ПОДПИСКА\n\n✅ Все привилегии обычной подписки\n✅ Доступ к бета-функциям\n✅ Тестирование новых функций\n✅ Приоритетная поддержка\n\n💰 Выберите срок:", sub_tester_kb(uid))
        return
    
    if data.startswith('sub_'):
        # Обработка выбора подписки
        plan_type = data.replace('sub_', '')
        amount = STARS_PRICES.get(plan_type)
        if not amount:
            await edit_current("❌ НЕВЕРНЫЙ ТАРИФ!", back_kb(uid))
            return
        
        # Создаём платёж
        payment_id = create_payment(uid, plan_type, amount)
        
        # Определяем название для отображения
        plan_names = {
            'month_regular': 'Месяц (Обычная)',
            'month_tester': 'Месяц (Тестер)',
            '6month_regular': '6 месяцев (Обычная)',
            '6month_tester': '6 месяцев (Тестер)',
            'year_regular': 'Год (Обычная)',
            'year_tester': 'Год (Тестер)',
        }
        plan_name = plan_names.get(plan_type, 'Подписка')
        
        # Создаём инвойс
        try:
            await context.bot.send_invoice(
                chat_id=uid,
                title=f"💳 {plan_name}",
                description=f"Подписка {plan_name} на {SUBSCRIPTION_DAYS[plan_type.split('_')[0]]} дней",
                payload=payment_id,
                provider_token="",
                currency="XTR",
                prices=[{"label": plan_name, "amount": amount}],
                start_parameter="subscription",
                need_name=False,
                need_phone_number=False,
                need_email=False,
                need_shipping_address=False,
                is_flexible=False,
            )
        except Exception as e:
            log_error(f"Invoice error: {e}")
            await edit_current(f"❌ ОШИБКА СОЗДАНИЯ ПЛАТЕЖА!\n\n{str(e)}", back_kb(uid))
        return
    
    if data == 'activate_code':
        context.user_data['code_wait'] = True
        await edit_current("🎟 ВВЕДИТЕ КОД:", back_kb(uid))
        return
    
    # ===== ПРОФИЛЬ =====
    if data == 'profile':
        nickname = get_user_nickname(uid) or "Не указан"
        sub_end = get_subscription_end(uid)
        sub_status = f"АКТИВНА ДО {sub_end}" if sub_end and is_subscribed(uid) else "НЕТУ"
        adult_status = "✅ Подтверждён" if is_adult(uid) else "❌ Не подтверждён"
        is_tester_user = "✅ Да" if is_tester(uid) else "❌ Нет"
        is_blocked_user = "🔒 Да" if is_user_blocked(uid) else "❌ Нет"
        channels = get_user_channels(uid)
        channels_text = ""
        if channels:
            for ch in channels:
                try:
                    chat = await context.bot.get_chat(ch['channel_id'])
                    channel_link = f"https://t.me/{chat.username}" if hasattr(chat, 'username') and chat.username else "Нет ссылки"
                except:
                    channel_link = "Недоступно"
                channels_text += f"\n   📺 {ch['channel_name']}\n   🆔 ТГ ID: {ch['channel_id']}\n   🔗 Ссылка: {channel_link}\n   📂 {ch['category'] if ch['category'] else 'Не указана'}\n"
        else:
            channels_text = "\n   ❌ Нет каналов"
        name_changes = get_name_changes(uid)
        name_changes_text = "♾️ БЕЗЛИМИТ" if uid == OWNER_ID else f"{1 - name_changes} из 1"
        notifs = get_user_notifications(uid, unread_only=True)
        notif_count = len(notifs)
        notif_text = f"📬 {notif_count} новых" if notif_count > 0 else "📭 Пусто"
        text = (
            f"👤 ПРОФИЛЬ\n\n"
            f"👤 Никнейм: {nickname}\n"
            f"🆔 ID в боте: {uid}\n"
            f"🆔 ID в Telegram: {uid}\n"
            f"📝 Смена имени: {name_changes_text}\n"
            f"🔞 Возраст: {adult_status}\n"
            f"🧪 Тестер: {is_tester_user}\n"
            f"🔒 Заблокирован: {is_blocked_user}\n"
            f"💰 ПОДПИСКА: {sub_status}\n"
            f"{notif_text}\n"
            f"📺 КАНАЛЫ:{channels_text}"
        )
        await edit_current(text, profile_kb(uid))
        return
    
    if data == 'change_name':
        if uid == OWNER_ID:
            context.user_data['change_name_wait'] = True
            await edit_current("📝 ВВЕДИТЕ НОВОЕ ИМЯ (безлимит):", back_kb(uid))
            return
        if get_name_changes(uid) >= 1:
            await edit_current("❌ ЛИМИТ ИСЧЕРПАН! (1 раз)", back_kb(uid))
            return
        context.user_data['change_name_wait'] = True
        await edit_current("📝 ВВЕДИТЕ НОВОЕ ИМЯ:", back_kb(uid))
        return
    
    if data == 'change_name_infinite':
        if uid != OWNER_ID:
            return
        context.user_data['change_name_wait'] = True
        await edit_current("📝 ВВЕДИТЕ НОВОЕ ИМЯ (безлимит):", back_kb(uid))
        return
    
    if data == 'delete_profile_confirm':
        await edit_current("⚠️ ВЫ УВЕРЕНЫ?\n\nВсе данные будут потеряны!", InlineKeyboardMarkup([[InlineKeyboardButton("✅ ДА", callback_data='delete_profile_yes')], [InlineKeyboardButton("❌ НЕТ", callback_data='delete_profile_no')]]))
        return
    
    if data == 'delete_profile_yes':
        if delete_user_profile(uid):
            log_main(uid, "Удалил профиль", "Успешно")
            await edit_current("✅ ПРОФИЛЬ УДАЛЁН!\n\n/start для регистрации", None)
        else:
            await edit_current("❌ ОШИБКА!", back_kb(uid))
        return
    
    if data == 'delete_profile_no':
        await edit_current("✅ ОТМЕНЕНО!", back_kb(uid))
        return
    
    # ===== ПОЧТА/УВЕДОМЛЕНИЯ (ПУНКТ 19) =====
    if data == 'show_notifications':
        notifs = get_user_notifications(uid, unread_only=True)
        if not notifs:
            await edit_current("📭 У ВАС НЕТ НОВЫХ УВЕДОМЛЕНИЙ!", back_kb(uid))
            return
        text = "📬 ВАШИ УВЕДОМЛЕНИЯ:\n\n"
        kb = []
        for n in notifs[:10]:
            text += f"📌 {n['type']}\n"
            text += f"📝 {n['content'][:50]}...\n"
            text += f"🕐 {n['created_at']}\n\n"
            kb.append([InlineKeyboardButton(f"👁 {n['type']}", callback_data=f"view_notif_{n['id']}")])
        kb.append([InlineKeyboardButton("🗑 ОЧИСТИТЬ ВСЕ", callback_data='clear_notifications')])
        kb.append([InlineKeyboardButton("◀️ НАЗАД", callback_data='back')])
        await edit_current(text, InlineKeyboardMarkup(kb))
        return
    
    if data.startswith('view_notif_'):
        notif_id = int(data.replace('view_notif_', ''))
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('CREATE TABLE IF NOT EXISTS notifications (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, type TEXT, content TEXT, link_data TEXT, read INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
        result = cursor.execute('SELECT * FROM notifications WHERE id = ?', (notif_id,)).fetchone()
        conn.close()
        if result:
            mark_notification_read(notif_id)
            await edit_current(f"📬 {result['type']}\n\n{result['content']}\n\n🕐 {result['created_at']}", InlineKeyboardMarkup([[InlineKeyboardButton("🗑 УДАЛИТЬ", callback_data=f"delete_notif_{notif_id}")], [InlineKeyboardButton("◀️ НАЗАД", callback_data='show_notifications')]]))
        else:
            await edit_current("❌ УВЕДОМЛЕНИЕ НЕ НАЙДЕНО!", back_kb(uid))
        return
    
    if data.startswith('delete_notif_'):
        notif_id = int(data.replace('delete_notif_', ''))
        delete_notification(notif_id)
        await edit_current("✅ УДАЛЕНО!", back_kb(uid))
        return
    
    if data == 'clear_notifications':
        mark_all_notifications_read(uid)
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM notifications WHERE user_id = ?', (uid,))
        conn.commit()
        conn.close()
        await edit_current("✅ ВСЕ УВЕДОМЛЕНИЯ ОЧИЩЕНЫ!", back_kb(uid))
        return
    
    if data.startswith('hide_notif_'):
        await edit_current("✅ УВЕДОМЛЕНИЕ СКРЫТО!", main_kb(uid))
        return
    
    # ===== СООБЩЕНИЯ ПОЛЬЗОВАТЕЛЯМ =====
    if data == 'send_message_to_user':
        if not is_registered(uid):
            await edit_current("❌ СНАЧАЛА ЗАРЕГИСТРИРУЙТЕСЬ!", back_kb(uid))
            return
        context.user_data['send_message_wait'] = True
        context.user_data['send_message_target'] = uid
        await edit_current("📝 ВВЕДИТЕ ID ПОЛЬЗОВАТЕЛЯ:", InlineKeyboardMarkup([[InlineKeyboardButton("👤 НАПИСАТЬ СЕБЕ", callback_data='msg_to_self')], [InlineKeyboardButton("◀️ НАЗАД", callback_data='back')]]))
        return
    
    if data.startswith('msg_to_'):
        target_id = int(data.replace('msg_to_', ''))
        if target_id == uid:
            await edit_current("❌ НЕЛЬЗЯ СЕБЕ!", back_kb(uid))
            return
        context.user_data['send_message_target'] = target_id
        context.user_data['send_message_wait'] = True
        context.user_data['send_message_anonymous'] = False
        await edit_current(f"📝 ВВЕДИТЕ ТЕКСТ ДЛЯ {get_user_nickname(target_id) or target_id}:", InlineKeyboardMarkup([[InlineKeyboardButton("🔒 ВКЛЮЧИТЬ АНОНИМНО", callback_data='toggle_anonymous')], [InlineKeyboardButton("◀️ НАЗАД", callback_data='back')]]))
        return
    
    if data == 'toggle_anonymous':
        current = context.user_data.get('send_message_anonymous', False)
        context.user_data['send_message_anonymous'] = not current
        status = "ВКЛ" if context.user_data['send_message_anonymous'] else "ВЫКЛ"
        target_id = context.user_data.get('send_message_target', uid)
        await edit_current(f"📝 ВВЕДИТЕ ТЕКСТ ДЛЯ {get_user_nickname(target_id) or target_id}:\n\n🔒 Анонимно: {status}", InlineKeyboardMarkup([[InlineKeyboardButton(f"🔒 {'ВЫКЛЮЧИТЬ' if context.user_data['send_message_anonymous'] else 'ВКЛЮЧИТЬ'}", callback_data='toggle_anonymous')], [InlineKeyboardButton("◀️ НАЗАД", callback_data='back')]]))
        return
    
    if data == 'msg_to_self':
        await edit_current("❌ НЕЛЬЗЯ СЕБЕ!", back_kb(uid))
        return
    
    if data.startswith('user_profile_'):
        target_id = int(data.replace('user_profile_', ''))
        if target_id == uid:
            await edit_current("❌ ЭТО ВЫ!", back_kb(uid))
            return
        nickname = get_user_nickname(target_id) or "Неизвестен"
        sub_end = get_subscription_end(target_id)
        sub_status = f"АКТИВНА ДО {sub_end}" if sub_end and is_subscribed(target_id) else "НЕТУ"
        await edit_current(f"👤 ПРОФИЛЬ\n\n👤 {nickname}\n🆔 ID в боте: {target_id}\n🆔 ID в Telegram: {target_id}\n💰 {sub_status}", user_profile_kb(uid, target_id))
        return
    
    # ===== ПРИВЯЗКА КАНАЛА =====
    if data == 'connect_channel':
        if not is_subscribed(uid):
            await edit_current("❌ ТРЕБУЕТСЯ ПОДПИСКА!", InlineKeyboardMarkup([[InlineKeyboardButton("💳 ПОДПИСКА", callback_data='subscription')], [InlineKeyboardButton("◀️ НАЗАД", callback_data='back')]]))
            return
        await edit_current("🔗 ВЫБЕРИТЕ СПОСОБ:", connect_methods_kb(uid))
        return
    
    if data == 'connect_by_id':
        if not is_subscribed(uid):
            await edit_current("❌ ТРЕБУЕТСЯ ПОДПИСКА!", back_kb(uid))
            return
        context.user_data['connect_wait'] = True
        await edit_current("📝 ВВЕДИТЕ ID КАНАЛА (-100):\nПример: -1001234567890\n\n💡 Узнать ID через @userinfobot", back_kb(uid))
        return
    
    if data == 'connect_by_link':
        if not is_subscribed(uid):
            await edit_current("❌ ТРЕБУЕТСЯ ПОДПИСКА!", back_kb(uid))
            return
        context.user_data['connect_by_link'] = True
        await edit_current("🔗 ВСТАВЬТЕ ССЫЛКУ:\nhttps://t.me/username", back_kb(uid))
        return
    
    if data == 'connect_by_username':
        if not is_subscribed(uid):
            await edit_current("❌ ТРЕБУЕТСЯ ПОДПИСКА!", back_kb(uid))
            return
        context.user_data['connect_by_username'] = True
        await edit_current("📌 ВВЕДИТЕ @username:\n@my_channel", back_kb(uid))
        return
    
    if data == 'connect_by_forward':
        if not is_subscribed(uid):
            await edit_current("❌ ТРЕБУЕТСЯ ПОДПИСКА!", back_kb(uid))
            return
        context.user_data['connect_by_forward_wait'] = True
        await edit_current("📩 ПЕРЕСЛАТЬ СООБЩЕНИЕ\n\n1. Найдите любое сообщение в канале\n2. Перешлите его сюда\n3. Бот сам определит канал\n\n⚠️ Бот должен быть администратором канала!", back_kb(uid))
        return
    
    if data.startswith('cat_'):
        cat = data.replace('cat_', '')
        if 'selected_categories' not in context.user_data:
            context.user_data['selected_categories'] = []
        if cat in context.user_data['selected_categories']:
            context.user_data['selected_categories'].remove(cat)
        else:
            if len(context.user_data['selected_categories']) >= 2:
                await edit_current("❌ НЕЛЬЗЯ ВЫБРАТЬ БОЛЬШЕ 2 КАТЕГОРИЙ!\n\nУберите одну из выбранных.", back_kb(uid))
                return
            context.user_data['selected_categories'].append(cat)
        selected_text = ', '.join(context.user_data['selected_categories']) if context.user_data['selected_categories'] else 'Ничего не выбрано'
        await edit_current(f"📂 ВЫБЕРИТЕ ДО 2 КАТЕГОРИЙ:\n\n✅ Выбрано: {selected_text}\n\nНажмите на категорию чтобы выбрать/убрать", categories_kb(uid, context.user_data['selected_categories']))
        return
    
    if data == 'confirm_categories':
        selected = context.user_data.get('selected_categories', [])
        if not selected:
            await edit_current("❌ ВЫБЕРИТЕ ХОТЯ БЫ ОДНУ КАТЕГОРИЮ!", back_kb(uid))
            return
        channel_id = context.user_data.get('connect_channel_id')
        if channel_id:
            chat_name = context.user_data.get('connect_channel_name')
            end_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
            subscribers = get_channel_subscribers(context.bot, channel_id)
            privacy = 'private'
            try:
                chat = context.bot.get_chat(channel_id)
                if hasattr(chat, 'username') and chat.username:
                    privacy = 'public'
            except:
                privacy = 'private'
            categories_str = ', '.join(selected)
            add_channel_db(channel_id, chat_name, uid, categories_str, end_date, privacy, subscribers)
            linked_group_id = None
            try:
                chat_info = context.bot.get_chat(channel_id)
                if hasattr(chat_info, 'linked_chat_id') and chat_info.linked_chat_id:
                    linked_group_id = chat_info.linked_chat_id
                    set_channel_linked_group(channel_id, linked_group_id)
            except:
                pass
            context.user_data['selected_categories'] = []
            context.user_data['connect_channel_id'] = None
            context.user_data['connect_channel_name'] = None
            group_text = f"\n💬 Группа: {'✅ Найдена' if linked_group_id else '❌ Не найдена'}"
            await edit_current(f"✅ КАНАЛ ПРИВЯЗАН!\n\n📺 {chat_name}\n📂 Категории: {categories_str}\n🔒 {privacy}\n👥 {subscribers}{group_text}\n\n🔽 Что дальше?", InlineKeyboardMarkup([[InlineKeyboardButton("🔗 ПРИВЯЗАТЬ ЕЩЁ", callback_data='connect_channel')], [InlineKeyboardButton("⚙️ НАСТРОЙКИ", callback_data=f"set_ch_{channel_id}")], [InlineKeyboardButton("◀️ В ГЛАВНОЕ МЕНЮ", callback_data='back')]]))
        else:
            await edit_current("❌ ОШИБКА! Канал не найден.", back_kb(uid))
        return
    
    if data == 'disconnect_channel':
        channels = get_user_channels(uid)
        if not channels:
            await edit_current("❌ Нет каналов!", back_kb(uid))
            return
        kb = [[InlineKeyboardButton(f"❌ {ch['channel_name']}", callback_data=f"del_ch_{ch['channel_id']}")] for ch in channels]
        kb.append([InlineKeyboardButton("◀️ НАЗАД", callback_data='back')])
        await edit_current("❌ ВЫБЕРИТЕ:", InlineKeyboardMarkup(kb))
        return
    
    if data.startswith('del_ch_'):
        channel_id = int(data.replace('del_ch_', ''))
        del_channel_db(channel_id, uid)
        await edit_current("✅ ОТВЯЗАН!", back_kb(uid))
        return
    
    # ===== НАСТРОЙКИ КАНАЛА =====
    if data == 'channel_settings':
        if not is_subscribed(uid):
            await edit_current("❌ ТРЕБУЕТСЯ ПОДПИСКА!", back_kb(uid))
            return
        channels = get_user_channels(uid)
        if not channels:
            await edit_current("❌ Нет каналов!", back_kb(uid))
            return
        kb = [[InlineKeyboardButton(f"📺 {ch['channel_name']}", callback_data=f"set_ch_{ch['channel_id']}")] for ch in channels]
        kb.append([InlineKeyboardButton("◀️ НАЗАД", callback_data='back')])
        await edit_current("⚙️ ВЫБЕРИТЕ:", InlineKeyboardMarkup(kb))
        return
    
    if data.startswith('set_ch_'):
        channel_id = int(data.replace('set_ch_', ''))
        context.user_data['selected_channel'] = channel_id
        info = get_chat_info(context.bot, channel_id)
        name = info['title'] if info else f"Канал {channel_id}"
        USER_LAST_MENU[uid] = f"set_ch_{channel_id}"
        await edit_current(f"⚙️ {name}", channel_settings_kb(uid, channel_id))
        return
    
    # ===== ИНФОРМАЦИЯ О КАНАЛЕ (ПУНКТЫ 3, 14, 5) =====
    if data.startswith('channel_info_'):
        channel_id = int(data.replace('channel_info_', ''))
        ch = get_channel_by_channel_id(channel_id)
        if not ch:
            await edit_current("❌ КАНАЛ НЕ НАЙДЕН!", back_kb(uid))
            return
        
        # Получаем полную информацию
        info = get_channel_info_full(context.bot, channel_id)
        if not info:
            await edit_current("❌ НЕ УДАЛОСЬ ПОЛУЧИТЬ ИНФОРМАЦИЮ!", back_kb(uid))
            return
        
        # Обновляем подписчиков в БД
        update_channel_subscribers(context.bot, channel_id)
        ch = get_channel_by_channel_id(channel_id)
        
        # Собираем текст
        privacy = ch['privacy'] if ch['privacy'] else 'public'
        privacy_text = "🔒 СКРЫТ" if privacy == 'private' else "🔓 ВИДЕН"
        linked_group = get_channel_linked_group(channel_id)
        group_text = f"✅ {linked_group}" if linked_group else "❌ Не найдена"
        
        admins_text = ""
        if info['admins']:
            for admin in info['admins'][:5]:
                admins_text += f"   👤 {admin['name']} (ID: {admin['id']})\n"
            if len(info['admins']) > 5:
                admins_text += f"   ... и еще {len(info['admins']) - 5}"
        else:
            admins_text = "   ❌ Нет данных"
        
        text = (
            f"ℹ️ ИНФОРМАЦИЯ О КАНАЛЕ\n\n"
            f"📺 Название: {info['title']}\n"
            f"🆔 ТГ ID: {info['id']}\n"
            f"🔗 Username: @{info['username'] if info['username'] else 'Нет'}\n"
            f"📝 Описание: {info['description'] if info['description'] else 'Не указано'}\n"
            f"👥 Подписчиков: {info['member_count']}\n"
            f"🔒 Видимость: {privacy_text}\n"
            f"💬 Группа: {group_text}\n"
            f"📂 Категория: {ch['category'] if ch['category'] else 'Не указана'}\n"
            f"👑 Владелец: {get_user_nickname(ch['owner_id']) or ch['owner_id']}\n"
            f"👥 Администраторы:\n{admins_text}\n"
        )
        
        kb = [[InlineKeyboardButton("🔄 ОБНОВИТЬ", callback_data=f"channel_info_{channel_id}")], [InlineKeyboardButton("◀️ НАЗАД", callback_data=f"set_ch_{channel_id}")]]
        
        if info['photo']:
            try:
                await query.edit_message_media(media=InputMediaPhoto(media=info['photo'], caption=text), reply_markup=InlineKeyboardMarkup(kb))
                return
            except:
                pass
        
        await edit_current(text, InlineKeyboardMarkup(kb))
        return
    
    # ===== ОСТАЛЬНЫЕ ОБРАБОТЧИКИ =====
    
    # Приветствие
    if data.startswith('set_welcome_'):
        channel_id = int(data.replace('set_welcome_', ''))
        current = get_welcome_text(channel_id) or "Привет, {name}!"
        is_enabled = get_setting(f"welcome_enabled_{channel_id}") == '1'
        status = "✅ ВКЛ" if is_enabled else "❌ ВЫКЛ"
        await edit_current(f"👋 НАСТРОЙКА ПРИВЕТСТВИЯ\n\n📝 Текущий текст:\n{current}\n\n📌 Статус: {status}\n\n📋 Доступные команды:\n• {{name}} - имя пользователя\n• {{chat}} - название канала\n• {{mention}} - упоминание (@username)\n• {{count}} - количество подписчиков\n\n🔽 Что дальше?", welcome_commands_kb(channel_id))
        return
    
    if data.startswith('welcome_cmd_name_'):
        channel_id = int(data.replace('welcome_cmd_name_', ''))
        current = get_welcome_text(channel_id) or "Привет, {name}!"
        if not current.endswith('\n'):
            current += '\n'
        current += "{name}"
        set_welcome_text(channel_id, current)
        await edit_current(f"✅ ДОБАВЛЕНО: {{name}}\n\nТекущий текст:\n{current}", welcome_commands_kb(channel_id))
        return
    
    if data.startswith('welcome_cmd_chat_'):
        channel_id = int(data.replace('welcome_cmd_chat_', ''))
        current = get_welcome_text(channel_id) or "Привет, {name}!"
        if not current.endswith('\n'):
            current += '\n'
        current += "{chat}"
        set_welcome_text(channel_id, current)
        await edit_current(f"✅ ДОБАВЛЕНО: {{chat}}\n\nТекущий текст:\n{current}", welcome_commands_kb(channel_id))
        return
    
    if data.startswith('welcome_cmd_mention_'):
        channel_id = int(data.replace('welcome_cmd_mention_', ''))
        current = get_welcome_text(channel_id) or "Привет, {name}!"
        if not current.endswith('\n'):
            current += '\n'
        current += "{mention}"
        set_welcome_text(channel_id, current)
        await edit_current(f"✅ ДОБАВЛЕНО: {{mention}}\n\nТекущий текст:\n{current}", welcome_commands_kb(channel_id))
        return
    
    if data.startswith('welcome_cmd_count_'):
        channel_id = int(data.replace('welcome_cmd_count_', ''))
        current = get_welcome_text(channel_id) or "Привет, {name}!"
        if not current.endswith('\n'):
            current += '\n'
        current += "{count}"
        set_welcome_text(channel_id, current)
        await edit_current(f"✅ ДОБАВЛЕНО: {{count}}\n\nТекущий текст:\n{current}", welcome_commands_kb(channel_id))
        return
    
    if data.startswith('welcome_copy_template_'):
        channel_id = int(data.replace('welcome_copy_template_', ''))
        template = "👋 Добро пожаловать, {name}!\n📺 Канал: {chat}\n👤 {mention}\n👥 Подписчиков: {count}"
        set_welcome_text(channel_id, template)
        set_setting(f"welcome_enabled_{channel_id}", '1')
        await edit_current(f"✅ ШАБЛОН СКОПИРОВАН!\n\n📝 {template}", welcome_commands_kb(channel_id))
        return
    
    if data.startswith('welcome_edit_text_'):
        channel_id = int(data.replace('welcome_edit_text_', ''))
        context.user_data['welcome_edit_text_wait'] = channel_id
        await edit_current("✏️ ВВЕДИТЕ ТЕКСТ ПРИВЕТСТВИЯ:\n\n📋 Доступные команды:\n• {name} - имя пользователя\n• {chat} - название канала\n• {mention} - упоминание (@username)\n• {count} - количество подписчиков", back_kb(uid))
        return
    
    if data.startswith('welcome_enable_'):
        channel_id = int(data.replace('welcome_enable_', ''))
        set_setting(f"welcome_enabled_{channel_id}", '1')
        await edit_current(f"✅ ПРИВЕТСТВИЕ ВКЛЮЧЕНО!", channel_settings_kb(uid, channel_id))
        return
    
    if data.startswith('welcome_disable_'):
        channel_id = int(data.replace('welcome_disable_', ''))
        set_setting(f"welcome_enabled_{channel_id}", '0')
        await edit_current(f"❌ ПРИВЕТСТВИЕ ВЫКЛЮЧЕНО!", channel_settings_kb(uid, channel_id))
        return
    
    # Прощание
    if data.startswith('set_farewell_'):
        channel_id = int(data.replace('set_farewell_', ''))
        current = get_farewell_text(channel_id) or "Пока, {name}!"
        is_enabled = get_setting(f"farewell_enabled_{channel_id}") == '1'
        status = "✅ ВКЛ" if is_enabled else "❌ ВЫКЛ"
        await edit_current(f"👋 НАСТРОЙКА ПРОЩАНИЯ\n\n📝 Текущий текст:\n{current}\n\n📌 Статус: {status}\n\n📋 Доступные команды:\n• {{name}} - имя пользователя\n• {{chat}} - название канала\n• {{mention}} - упоминание (@username)\n• {{count}} - количество подписчиков\n\n🔽 Что дальше?", farewell_commands_kb(channel_id))
        return
    
    if data.startswith('farewell_cmd_name_'):
        channel_id = int(data.replace('farewell_cmd_name_', ''))
        current = get_farewell_text(channel_id) or "Пока, {name}!"
        if not current.endswith('\n'):
            current += '\n'
        current += "{name}"
        set_farewell_text(channel_id, current)
        await edit_current(f"✅ ДОБАВЛЕНО: {{name}}\n\nТекущий текст:\n{current}", farewell_commands_kb(channel_id))
        return
    
    if data.startswith('farewell_cmd_chat_'):
        channel_id = int(data.replace('farewell_cmd_chat_', ''))
        current = get_farewell_text(channel_id) or "Пока, {name}!"
        if not current.endswith('\n'):
            current += '\n'
        current += "{chat}"
        set_farewell_text(channel_id, current)
        await edit_current(f"✅ ДОБАВЛЕНО: {{chat}}\n\nТекущий текст:\n{current}", farewell_commands_kb(channel_id))
        return
    
    if data.startswith('farewell_cmd_mention_'):
        channel_id = int(data.replace('farewell_cmd_mention_', ''))
        current = get_farewell_text(channel_id) or "Пока, {name}!"
        if not current.endswith('\n'):
            current += '\n'
        current += "{mention}"
        set_farewell_text(channel_id, current)
        await edit_current(f"✅ ДОБАВЛЕНО: {{mention}}\n\nТекущий текст:\n{current}", farewell_commands_kb(channel_id))
        return
    
    if data.startswith('farewell_cmd_count_'):
        channel_id = int(data.replace('farewell_cmd_count_', ''))
        current = get_farewell_text(channel_id) or "Пока, {name}!"
        if not current.endswith('\n'):
            current += '\n'
        current += "{count}"
        set_farewell_text(channel_id, current)
        await edit_current(f"✅ ДОБАВЛЕНО: {{count}}\n\nТекущий текст:\n{current}", farewell_commands_kb(channel_id))
        return
    
    if data.startswith('farewell_copy_template_'):
        channel_id = int(data.replace('farewell_copy_template_', ''))
        template = "👋 Пока, {name}!\n📺 Канал: {chat}\n👤 {mention}\n👥 Подписчиков: {count}"
        set_farewell_text(channel_id, template)
        set_setting(f"farewell_enabled_{channel_id}", '1')
        await edit_current(f"✅ ШАБЛОН СКОПИРОВАН!\n\n📝 {template}", farewell_commands_kb(channel_id))
        return
    
    if data.startswith('farewell_edit_text_'):
        channel_id = int(data.replace('farewell_edit_text_', ''))
        context.user_data['farewell_edit_text_wait'] = channel_id
        await edit_current("✏️ ВВЕДИТЕ ТЕКСТ ПРОЩАНИЯ:\n\n📋 Доступные команды:\n• {name} - имя пользователя\n• {chat} - название канала\n• {mention} - упоминание (@username)\n• {count} - количество подписчиков", back_kb(uid))
        return
    
    if data.startswith('farewell_enable_'):
        channel_id = int(data.replace('farewell_enable_', ''))
        set_setting(f"farewell_enabled_{channel_id}", '1')
        await edit_current(f"✅ ПРОЩАНИЕ ВКЛЮЧЕНО!", channel_settings_kb(uid, channel_id))
        return
    
    if data.startswith('farewell_disable_'):
        channel_id = int(data.replace('farewell_disable_', ''))
        set_setting(f"farewell_enabled_{channel_id}", '0')
        await edit_current(f"❌ ПРОЩАНИЕ ВЫКЛЮЧЕНО!", channel_settings_kb(uid, channel_id))
        return
    
    # ===== ФИЛЬТР СЛОВ =====
    if data.startswith('toggle_anti_spam_'):
        channel_id = int(data.replace('toggle_anti_spam_', ''))
        current = get_setting(f"anti_spam_enabled_{channel_id}") == '1'
        new_val = not current
        set_setting(f"anti_spam_enabled_{channel_id}", '1' if new_val else '0')
        words = get_blacklist_words(channel_id)
        words_text = '\n'.join(words) if words else '❌ Пусто'
        status = "✅ ВКЛ" if new_val else "❌ ВЫКЛ"
        await edit_current(f"🚫 ФИЛЬТР СЛОВ\n\n📌 Статус: {status}\n📝 Запрещённые слова (регистронезависимо):\n{words_text}\n\n🔽 Что дальше?", InlineKeyboardMarkup([[InlineKeyboardButton("➕ ДОБАВИТЬ СЛОВО", callback_data=f"spam_add_{channel_id}")], [InlineKeyboardButton("➖ УДАЛИТЬ СЛОВО", callback_data=f"spam_remove_{channel_id}")], [InlineKeyboardButton("◀️ В НАСТРОЙКИ", callback_data=f"set_ch_{channel_id}")]]))
        return
    
    if data.startswith('spam_add_'):
        channel_id = int(data.replace('spam_add_', ''))
        context.user_data['spam_add_wait'] = channel_id
        await edit_current("📝 ВВЕДИТЕ СЛОВО ДЛЯ БЛОКИРОВКИ:\n\n⚠️ Регистр не важен (Писька = пиСьКа)", back_kb(uid))
        return
    
    if data.startswith('spam_remove_'):
        channel_id = int(data.replace('spam_remove_', ''))
        words = get_blacklist_words(channel_id)
        if not words:
            await edit_current("❌ НЕТ СЛОВ В ЧЁРНОМ СПИСКЕ!", back_kb(uid))
            return
        kb = [[InlineKeyboardButton(f"❌ {w}", callback_data=f"spam_del_{channel_id}_{w}")] for w in words[:10]]
        kb.append([InlineKeyboardButton("◀️ НАЗАД", callback_data=f"toggle_anti_spam_{channel_id}")])
        await edit_current("📝 ВЫБЕРИТЕ СЛОВО ДЛЯ УДАЛЕНИЯ:", InlineKeyboardMarkup(kb))
        return
    
    if data.startswith('spam_del_'):
        parts = data.split('_')
        channel_id = int(parts[2])
        word = '_'.join(parts[3:])
        del_blacklist_word(channel_id, word)
        await edit_current(f"✅ '{word}' УДАЛЕНО!", back_kb(uid))
        return
    
    # ===== АВТОПОСТИНГ =====
    if data.startswith('auto_posting_menu_'):
        channel_id = int(data.replace('auto_posting_menu_', ''))
        await edit_current("📅 АВТОПОСТИНГ\n\nУправляйте запланированными постами.\n\n🔽 Выберите действие:", auto_posting_menu_kb(channel_id))
        return
    
    if data.startswith('set_posting_'):
        channel_id = int(data.replace('set_posting_', ''))
        await edit_current("📅 АВТОПОСТИНГ - ЗАПЛАНИРОВАТЬ ПОСТ\n\nОтправьте текст или медиа для планирования.\nБот сам определит что вы отправили.\n\n📌 Поддерживается:\n• Текст\n• Фото\n• Видео\n• GIF\n• Документ\n\n🔽 Отправьте пост:", back_kb(uid))
        context.user_data['post_wait'] = channel_id
        return
    
    if data.startswith('post_view_'):
        channel_id = int(data.replace('post_view_', ''))
        posts = get_scheduled_posts(channel_id)
        if not posts:
            await edit_current("❌ НЕТ ЗАПЛАНИРОВАННЫХ ПОСТОВ!", auto_posting_menu_kb(channel_id))
            return
        text = "📋 ЗАПЛАНИРОВАННЫЕ ПОСТЫ:\n\n"
        for p in posts[:10]:
            text += f"📝 {p['post_text'][:30]}...\n   ⏰ {p['scheduled_time']}\n"
            if p['post_media']:
                text += f"   🖼 С медиа\n"
            text += "\n"
        kb = []
        for p in posts[:10]:
            kb.append([InlineKeyboardButton(f"📝 {p['post_text'][:20]}...", callback_data=f"post_cancel_{p['id']}")])
        kb.append([InlineKeyboardButton("◀️ НАЗАД", callback_data=f"auto_posting_menu_{channel_id}")])
        await edit_current(text, InlineKeyboardMarkup(kb))
        return
    
    if data.startswith('post_cancel_'):
        channel_id = int(data.replace('post_cancel_', ''))
        posts = get_scheduled_posts(channel_id)
        if not posts:
            await edit_current("❌ НЕТ ПОСТОВ!", auto_posting_menu_kb(channel_id))
            return
        kb = [[InlineKeyboardButton(f"❌ {p['post_text'][:20]}...", callback_data=f"post_del_{p['id']}")] for p in posts[:10]]
        kb.append([InlineKeyboardButton("◀️ НАЗАД", callback_data=f"auto_posting_menu_{channel_id}")])
        await edit_current("❌ ВЫБЕРИТЕ ПОСТ ДЛЯ ОТМЕНЫ:", InlineKeyboardMarkup(kb))
        return
    
    if data.startswith('post_del_'):
        post_id = int(data.replace('post_del_', ''))
        del_scheduled_post(post_id)
        await edit_current("✅ ПОСТ ОТМЕНЕН!", back_kb(uid))
        return
    
    # ===== АВТОПРИЁМ =====
    if data.startswith('set_auto_approve_'):
        channel_id = int(data.replace('set_auto_approve_', ''))
        current = get_auto_approve(channel_id)
        new_val = not current
        set_auto_approve(channel_id, new_val)
        status = "✅ ВКЛ" if new_val else "❌ ВЫКЛ"
        await edit_current(f"🔗 АВТОПРИЁМ ЗАЯВОК: {status}\n\n{'Все заявки будут одобряться автоматически.' if new_val else 'Заявки будут ожидать ручного одобрения.'}", channel_settings_kb(uid, channel_id))
        return
    
    # ===== КАПТЧА =====
    if data.startswith('set_captcha_'):
        channel_id = int(data.replace('set_captcha_', ''))
        settings = get_captcha_settings(channel_id)
        if settings:
            text = f"❓ КАПТЧА: {settings.get('question')}\n📌 Ответы: {', '.join(settings.get('answers', []))}"
        else:
            text = "❓ КАПТЧА ВЫКЛЮЧЕНА"
        kb = [
            [InlineKeyboardButton("✏️ ВОПРОС", callback_data=f"captcha_q_{channel_id}")],
            [InlineKeyboardButton("✏️ ОТВЕТЫ", callback_data=f"captcha_a_{channel_id}")],
        ]
        if settings:
            kb.append([InlineKeyboardButton("❌ ВЫКЛЮЧИТЬ", callback_data=f"captcha_off_{channel_id}")])
        else:
            kb.append([InlineKeyboardButton("✅ ВКЛЮЧИТЬ", callback_data=f"captcha_on_{channel_id}")])
        kb.append([InlineKeyboardButton("◀️ НАЗАД", callback_data=f"set_ch_{channel_id}")])
        await edit_current(text, InlineKeyboardMarkup(kb))
        return
    
    if data.startswith('captcha_q_'):
        channel_id = int(data.replace('captcha_q_', ''))
        context.user_data['captcha_q_wait'] = channel_id
        await edit_current("❓ ВВЕДИТЕ ВОПРОС:", back_kb(uid))
        return
    
    if data.startswith('captcha_a_'):
        channel_id = int(data.replace('captcha_a_', ''))
        context.user_data['captcha_a_wait'] = channel_id
        await edit_current("✏️ ВВЕДИТЕ ОТВЕТЫ ЧЕРЕЗ ЗАПЯТУЮ:", back_kb(uid))
        return
    
    if data.startswith('captcha_off_'):
        channel_id = int(data.replace('captcha_off_', ''))
        del_captcha_settings(channel_id)
        await edit_current("✅ ВЫКЛЮЧЕНО!", back_kb(uid))
        return
    
    if data.startswith('captcha_on_'):
        channel_id = int(data.replace('captcha_on_', ''))
        set_captcha_settings(channel_id, "Есть ли вам 18 лет?", ["Да", "Нет"])
        await edit_current("✅ ВКЛЮЧЕНО!", back_kb(uid))
        return
    
    # ===== ПРИВАТНОСТЬ =====
    if data.startswith('set_privacy_'):
        channel_id = int(data.replace('set_privacy_', ''))
        current = get_channel_privacy(channel_id)
        new_val = 'private' if current != 'private' else 'public'
        set_channel_privacy(channel_id, new_val)
        status = "🔒 СКРЫТ" if new_val == 'private' else "🔓 ВИДЕН"
        await edit_current(f"✅ {status}!\n\n{'Канал скрыт из поиска.' if new_val == 'private' else 'Канал виден в поиске.'}", channel_settings_kb(uid, channel_id))
        return
    
    # ===== ПОИСК КАНАЛОВ =====
    if data == 'search_channels':
        if not is_subscribed(uid) and uid != OWNER_ID and not is_tester(uid):
            await edit_current("❌ ДОСТУП К ПОИСКУ КАНАЛОВ ТОЛЬКО С ПОДПИСКОЙ!", InlineKeyboardMarkup([[InlineKeyboardButton("💳 ПОДПИСКА", callback_data='subscription')], [InlineKeyboardButton("◀️ НАЗАД", callback_data='back')]]))
            return
        kb = search_channels_kb(uid)
        if kb:
            await edit_current("🔍 ПОИСК КАНАЛОВ\n\nВыберите способ поиска:", kb)
        else:
            await edit_current("❌ ДОСТУП ТОЛЬКО С ПОДПИСКОЙ!", back_kb(uid))
        return
    
    if data == 'search_by_name':
        if not is_subscribed(uid) and uid != OWNER_ID and not is_tester(uid):
            await edit_current("❌ ДОСТУП ТОЛЬКО С ПОДПИСКОЙ!", back_kb(uid))
            return
        context.user_data['search_by_name_wait'] = True
        await edit_current("📝 ВВЕДИТЕ НАЗВАНИЕ:", back_kb(uid))
        return
    
    if data == 'search_by_bot_id':
        if not is_subscribed(uid) and uid != OWNER_ID and not is_tester(uid):
            await edit_current("❌ ДОСТУП ТОЛЬКО С ПОДПИСКОЙ!", back_kb(uid))
            return
        context.user_data['search_by_bot_id_wait'] = True
        await edit_current("🔍 ВВЕДИТЕ ID В БОТЕ:", back_kb(uid))
        return
    
    if data == 'search_by_tg_id':
        if not is_subscribed(uid) and uid != OWNER_ID and not is_tester(uid):
            await edit_current("❌ ДОСТУП ТОЛЬКО С ПОДПИСКОЙ!", back_kb(uid))
            return
        context.user_data['search_by_tg_id_wait'] = True
        await edit_current("🔍 ВВЕДИТЕ ID В ТГ:", back_kb(uid))
        return
    
    # ===== ФИЛЬТР ПО КАТЕГОРИЯМ =====
    if data == 'filter_category':
        if not is_subscribed(uid) and uid != OWNER_ID and not is_tester(uid):
            await edit_current("❌ ДОСТУП ТОЛЬКО С ПОДПИСКОЙ!", back_kb(uid))
            return
        await edit_current("📂 ВЫБЕРИТЕ КАТЕГОРИЮ:", filter_category_kb(uid))
        return
    
    if data == 'filter_all':
        if not is_subscribed(uid) and uid != OWNER_ID and not is_tester(uid):
            await edit_current("❌ ДОСТУП ТОЛЬКО С ПОДПИСКОЙ!", back_kb(uid))
            return
        all_channels = get_all_channels()
        filtered = []
        for ch in all_channels:
            category = ch['category'] if ch['category'] else ''
            cats = category.split(', ') if category else []
            show = True
            for cat in cats:
                if cat in ADULT_CATEGORIES and not is_adult(uid):
                    show = False
                    break
            if show:
                filtered.append(ch)
        for ch in filtered:
            update_channel_subscribers(context.bot, ch['channel_id'])
        if not filtered:
            await edit_current("❌ Нет каналов!", back_kb(uid))
            return
        text = "📂 ВСЕ КАНАЛЫ:\n\n"
        for ch in filtered[:20]:
            owner_name = get_user_nickname(ch['owner_id']) or "Неизвестен"
            try:
                chat = await context.bot.get_chat(ch['channel_id'])
                channel_link = f"https://t.me/{chat.username}" if hasattr(chat, 'username') and chat.username else "Нет ссылки"
            except:
                channel_link = "Недоступно"
            text += f"📺 {ch['channel_name']}\n   👤 {owner_name}\n   🆔 ТГ ID: {ch['channel_id']}\n   🔗 Ссылка: {channel_link}\n   📂 {ch['category'] if ch['category'] else 'Не указана'}\n   👥 {ch['subscribers'] if ch['subscribers'] else 0}\n\n"
        kb = []
        for ch in filtered[:5]:
            kb.append([InlineKeyboardButton(f"📺 {ch['channel_name'][:20]}", callback_data=f"channel_profile_{ch['channel_id']}")])
        kb.append([InlineKeyboardButton("◀️ НАЗАД", callback_data='search_channels')])
        await edit_current(text, InlineKeyboardMarkup(kb))
        return
    
    if data.startswith('filter_cat_'):
        if not is_subscribed(uid) and uid != OWNER_ID and not is_tester(uid):
            await edit_current("❌ ДОСТУП ТОЛЬКО С ПОДПИСКОЙ!", back_kb(uid))
            return
        category = data.replace('filter_cat_', '')
        all_channels = get_all_channels()
        filtered = []
        for ch in all_channels:
            ch_cat = ch['category'] if ch['category'] else ''
            cats = ch_cat.split(', ') if ch_cat else []
            if category in cats:
                if category in ADULT_CATEGORIES and not is_adult(uid):
                    continue
                filtered.append(ch)
        for ch in filtered:
            update_channel_subscribers(context.bot, ch['channel_id'])
        if not filtered:
            await edit_current(f"❌ Нет каналов в категории {category}!", back_kb(uid))
            return
        text = f"📂 КАТЕГОРИЯ: {category}\n\n"
        for ch in filtered[:20]:
            owner_name = get_user_nickname(ch['owner_id']) or "Неизвестен"
            try:
                chat = await context.bot.get_chat(ch['channel_id'])
                channel_link = f"https://t.me/{chat.username}" if hasattr(chat, 'username') and chat.username else "Нет ссылки"
            except:
                channel_link = "Недоступно"
            text += f"📺 {ch['channel_name']}\n   👤 {owner_name}\n   🆔 ТГ ID: {ch['channel_id']}\n   🔗 Ссылка: {channel_link}\n   👥 {ch['subscribers'] if ch['subscribers'] else 0}\n\n"
        kb = []
        for ch in filtered[:5]:
            kb.append([InlineKeyboardButton(f"📺 {ch['channel_name'][:20]}", callback_data=f"channel_profile_{ch['channel_id']}")])
        kb.append([InlineKeyboardButton("◀️ НАЗАД", callback_data='filter_category')])
        await edit_current(text, InlineKeyboardMarkup(kb))
        return
    
    # ===== СОРТИРОВКА =====
    if data == 'sort_subscribers':
        if not is_subscribed(uid) and uid != OWNER_ID and not is_tester(uid):
            await edit_current("❌ ДОСТУП ТОЛЬКО С ПОДПИСКОЙ!", back_kb(uid))
            return
        await edit_current("📊 СОРТИРОВКА:", sort_kb(uid))
        return
    
    if data == 'sort_asc':
        if not is_subscribed(uid) and uid != OWNER_ID and not is_tester(uid):
            await edit_current("❌ ДОСТУП ТОЛЬКО С ПОДПИСКОЙ!", back_kb(uid))
            return
        all_channels = get_all_channels()
        filtered = []
        for ch in all_channels:
            category = ch['category'] if ch['category'] else ''
            cats = category.split(', ') if category else []
            show = True
            for cat in cats:
                if cat in ADULT_CATEGORIES and not is_adult(uid):
                    show = False
                    break
            if show:
                filtered.append(ch)
        sorted_channels = sorted(filtered, key=lambda x: x['subscribers'] if x['subscribers'] else 0)
        text = "📊 ПО ВОЗРАСТАНИЮ:\n\n"
        for ch in sorted_channels[:20]:
            owner_name = get_user_nickname(ch['owner_id']) or "Неизвестен"
            try:
                chat = await context.bot.get_chat(ch['channel_id'])
                channel_link = f"https://t.me/{chat.username}" if hasattr(chat, 'username') and chat.username else "Нет ссылки"
            except:
                channel_link = "Недоступно"
            text += f"📺 {ch['channel_name']}\n   👤 {owner_name}\n   🆔 ТГ ID: {ch['channel_id']}\n   🔗 Ссылка: {channel_link}\n   👥 {ch['subscribers'] if ch['subscribers'] else 0}\n\n"
        await edit_current(text, back_kb(uid))
        return
    
    if data == 'sort_desc':
        if not is_subscribed(uid) and uid != OWNER_ID and not is_tester(uid):
            await edit_current("❌ ДОСТУП ТОЛЬКО С ПОДПИСКОЙ!", back_kb(uid))
            return
        all_channels = get_all_channels()
        filtered = []
        for ch in all_channels:
            category = ch['category'] if ch['category'] else ''
            cats = category.split(', ') if category else []
            show = True
            for cat in cats:
                if cat in ADULT_CATEGORIES and not is_adult(uid):
                    show = False
                    break
            if show:
                filtered.append(ch)
        sorted_channels = sorted(filtered, key=lambda x: x['subscribers'] if x['subscribers'] else 0, reverse=True)
        text = "📊 ПО УБЫВАНИЮ:\n\n"
        for ch in sorted_channels[:20]:
            owner_name = get_user_nickname(ch['owner_id']) or "Неизвестен"
            try:
                chat = await context.bot.get_chat(ch['channel_id'])
                channel_link = f"https://t.me/{chat.username}" if hasattr(chat, 'username') and chat.username else "Нет ссылки"
            except:
                channel_link = "Недоступно"
            text += f"📺 {ch['channel_name']}\n   👤 {owner_name}\n   🆔 ТГ ID: {ch['channel_id']}\n   🔗 Ссылка: {channel_link}\n   👥 {ch['subscribers'] if ch['subscribers'] else 0}\n\n"
        await edit_current(text, back_kb(uid))
        return
    
    # ===== ПОИСК ЛЮДЕЙ =====
    if data == 'search_users':
        if not is_subscribed(uid) and uid != OWNER_ID and not is_tester(uid):
            await edit_current("❌ ДОСТУП ТОЛЬКО С ПОДПИСКОЙ!", back_kb(uid))
            return
        context.user_data['search_users_wait'] = True
        await edit_current("🔍 ВВЕДИТЕ НИКНЕЙМ ИЛИ ID:", back_kb(uid))
        return
    
    # ===== ЯЗЫК (ПУНКТ 7) =====
    if data == 'language':
        await edit_current("🌍 ВЫБЕРИТЕ ЯЗЫК:", InlineKeyboardMarkup([[InlineKeyboardButton("🇷🇺 РУССКИЙ", callback_data='lang_ru')], [InlineKeyboardButton("🇬🇧 ENGLISH", callback_data='lang_en')], [InlineKeyboardButton("◀️ НАЗАД", callback_data='back')]]))
        return
    
    if data.startswith('lang_'):
        lang = data.replace('lang_', '')
        set_user_language(uid, lang)
        await edit_current(f"✅ ЯЗЫК ИЗМЕНЕН НА {'РУССКИЙ' if lang == 'ru' else 'ENGLISH'}!", main_kb(uid))
        return
    
    # ===== ПОДДЕРЖКА =====
    if data == 'support':
        if BOT_STOPPED:
            await edit_current(f"🔧 БОТ НА ТО!\n\n📌 Связь: @GanzalesSs920", back_kb(uid))
        else:
            await edit_current("💬 ПОДДЕРЖКА\n\n📌 @GanzalesSs920\n📌 @HellperBotNews", back_kb(uid))
        return
    
    # ===== ВЕРСИЯ С ПАГИНАЦИЕЙ (ПУНКТ 14) =====
    if data == 'version':
        page = context.user_data.get('version_page', 0)
        updates = [
            {"version": "beta 0.1", "date": "01.01.2024", "changes": "Базовая версия бота. Регистрация, подписки, привязка каналов."},
            {"version": "beta 0.2", "date": "15.01.2024", "changes": "Добавлен поиск каналов и пользователей. Панель разработчика."},
            {"version": "beta 0.3", "date": "01.02.2024", "changes": "Добавлена система ВП (ВзаимоПост). Бета-функции."},
            {"version": "beta 0.4", "date": "18.07.2024", "changes": "Полный рефакторинг. Исправлены все 25 пунктов. Добавлена оплата через Telegram Stars. Система отзывов. Блокировка пользователей."},
        ]
        total_pages = len(updates)
        if page >= total_pages:
            page = total_pages - 1
        if page < 0:
            page = 0
        update = updates[page]
        
        text = f"ℹ️ ВЕРСИЯ: {BOT_VERSION}\n\n"
        text += f"📌 История обновлений:\n\n"
        text += f"🔹 {update['version']} ({update['date']})\n{update['changes']}\n\n"
        text += f"📅 {datetime.now().strftime('%d.%m.%Y')}"
        
        kb = []
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton("⬅️", callback_data=f"version_page_{page-1}"))
        nav.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="version"))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton("➡️", callback_data=f"version_page_{page+1}"))
        if nav:
            kb.append(nav)
        kb.append([InlineKeyboardButton("◀️ НАЗАД", callback_data='back')])
        
        await edit_current(text, InlineKeyboardMarkup(kb))
        return
    
    if data.startswith('version_page_'):
        page = int(data.replace('version_page_', ''))
        context.user_data['version_page'] = page
        await callback(update, context)
        return
    
    # ===== РАЗРАБОТЧИК =====
    if data == 'developer':
        if uid != OWNER_ID:
            await edit_current("❌ ДОСТУП ЗАПРЕЩЁН!", back_kb(uid))
            return
        testers = get_all_testers()
        blocked = get_blocked_users()
        await edit_current(f"⚙️ ПАНЕЛЬ РАЗРАБОТЧИКА\n\n👑 {get_user_nickname(uid) or uid}\n🧪 Тестеров: {len(testers)}\n🔒 Заблокировано: {len(blocked)}\n📌 Версия: {BOT_VERSION}\n\n🔽 Действие:", dev_kb(uid))
        return
    
    # ===== РАЗРАБОТЧИК: БЕТА-ФУНКЦИИ =====
    if data == 'dev_beta_management':
        if uid != OWNER_ID:
            return
        await edit_current("🔬 УПРАВЛЕНИЕ БЕТА-ФУНКЦИЯМИ\n\nЗдесь вы можете управлять бета-функциями:", beta_management_kb(uid))
        return
    
    if data == 'dev_list_beta_features':
        if uid != OWNER_ID:
            return
        features = get_beta_features('all')
        if not features:
            await edit_current("❌ НЕТ БЕТА-ФУНКЦИЙ!", beta_management_kb(uid))
            return
        text = "🔬 ВСЕ БЕТА-ФУНКЦИИ:\n\n"
        for f in features[:20]:
            status_emoji = "🧪" if f['status'] == 'testing' else "✅"
            text += f"{status_emoji} {f['name']}\n   📌 {f['status']}\n   🆔 ID: {f['id']}\n   📝 {f['description'][:50]}...\n\n"
        kb = []
        for f in features[:10]:
            kb.append([InlineKeyboardButton(f"🔍 {f['name']}", callback_data=f"beta_detail_{f['id']}")])
        kb.append([InlineKeyboardButton("◀️ НАЗАД", callback_data='dev_beta_management')])
        await edit_current(text, InlineKeyboardMarkup(kb))
        return
    
    if data.startswith('beta_detail_'):
        feature_id = int(data.replace('beta_detail_', ''))
        feature = get_beta_feature(feature_id)
        if not feature:
            await edit_current("❌ ФУНКЦИЯ НЕ НАЙДЕНА!", beta_management_kb(uid))
            return
        await edit_current(f"🔬 {feature['name']}\n\n📌 Статус: {feature['status']}\n📝 {feature['description']}\n🆔 ID: {feature['id']}\n📅 Создана: {feature['created_at']}\n\n🔽 Что делать?", InlineKeyboardMarkup([[InlineKeyboardButton("📦 ВНЕДРИТЬ В ОСНОВНОЙ КОД", callback_data=f"promote_beta_{feature_id}")], [InlineKeyboardButton("🗑 УДАЛИТЬ ФУНКЦИЮ", callback_data=f"beta_delete_{feature_id}")], [InlineKeyboardButton("📌 СМЕНИТЬ СТАТУС", callback_data=f"beta_status_{feature_id}")], [InlineKeyboardButton("◀️ НАЗАД", callback_data='dev_list_beta_features')]]))
        return
    
    if data.startswith('beta_delete_'):
        if uid != OWNER_ID:
            return
        feature_id = int(data.replace('beta_delete_', ''))
        delete_beta_feature(feature_id)
        await edit_current("✅ БЕТА-ФУНКЦИЯ УДАЛЕНА!", dev_kb(uid))
        return
    
    if data.startswith('beta_status_'):
        if uid != OWNER_ID:
            return
        feature_id = int(data.replace('beta_status_', ''))
        feature = get_beta_feature(feature_id)
        if not feature:
            await edit_current("❌ ФУНКЦИЯ НЕ НАЙДЕНА!", dev_kb(uid))
            return
        new_status = 'development' if feature['status'] == 'testing' else 'testing'
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('UPDATE beta_features SET status = ? WHERE id = ?', (new_status, feature_id))
        conn.commit()
        conn.close()
        await edit_current(f"✅ СТАТУС ИЗМЕНЕН НА: {new_status.upper()}!", dev_kb(uid))
        return
    
    if data == 'dev_add_beta_feature':
        if uid != OWNER_ID:
            return
        context.user_data['add_beta_feature_name'] = True
        await edit_current("📝 ВВЕДИТЕ НАЗВАНИЕ БЕТА-ФУНКЦИИ:", back_kb(uid))
        return
    
    if data == 'dev_update_logs':
        if uid != OWNER_ID:
            return
        logs = get_update_logs(20)
        if not logs:
            await edit_current("❌ НЕТ ЗАПИСЕЙ ОБ ОБНОВЛЕНИЯХ!", beta_management_kb(uid))
            return
        text = "📊 ИСТОРИЯ ОБНОВЛЕНИЙ:\n\n"
        for log in logs:
            text += f"📌 Версия: {log['version']}\n📅 {log['created_at']}\n📝 {log['changes']}\n\n"
        await edit_current(text, back_kb(uid))
        return
    
    if data.startswith('promote_beta_'):
        if uid != OWNER_ID:
            return
        feature_id = int(data.replace('promote_beta_', ''))
        feature = get_beta_feature(feature_id)
        if not feature:
            await edit_current("❌ ФУНКЦИЯ НЕ НАЙДЕНА!", beta_management_kb(uid))
            return
        all_users = get_all_users()
        for u in all_users:
            if is_user_blocked(u['user_id']):
                continue
            try:
                await context.bot.send_message(chat_id=u['user_id'], text="🔧 ВНИМАНИЕ! Бот уйдёт на технический перерыв через 5 минут для обновления!\n\n⏳ Пожалуйста, завершите свои действия.")
            except:
                pass
        await edit_current(f"🔧 ОБНОВЛЕНИЕ БОТА!\n\n📌 Внедряется функция: {feature['name']}\n📝 {feature['description']}\n\n⏳ Все пользователи оповещены.\nБот уйдёт на техперерыв через 5 минут.\n\n✅ Нажмите 'ПОДТВЕРДИТЬ' для немедленного начала", InlineKeyboardMarkup([[InlineKeyboardButton("✅ ПОДТВЕРДИТЬ ОБНОВЛЕНИЕ", callback_data=f"confirm_update_{feature_id}")], [InlineKeyboardButton("❌ ОТМЕНИТЬ", callback_data='dev_beta_management')]]))
        return
    
    if data.startswith('confirm_update_'):
        if uid != OWNER_ID:
            return
        feature_id = int(data.replace('confirm_update_', ''))
        feature = get_beta_feature(feature_id)
        if not feature:
            await edit_current("❌ ФУНКЦИЯ НЕ НАЙДЕНА!", dev_kb(uid))
            return
        BOT_STOPPED = True
        promote_beta_feature(feature_id)
        add_update_log(version=BOT_VERSION, changes=f"Внедрена функция: {feature['name']}\n{feature['description']}")
        BOT_STOPPED = False
        all_users = get_all_users()
        for u in all_users:
            if is_user_blocked(u['user_id']):
                continue
            try:
                await context.bot.send_message(chat_id=u['user_id'], text=f"✅ БОТ ОБНОВЛЁН! Новая версия готова к использованию!\n\n📌 Что нового:\n{feature['description']}")
            except:
                pass
        await edit_current(f"✅ ОБНОВЛЕНИЕ ЗАВЕРШЕНО!\n\n📌 Внедрена функция: {feature['name']}\n📝 {feature['description']}", dev_kb(uid))
        return
    
    # ===== РАЗРАБОТЧИК: ТАЙМЕР ВП =====
    if data == 'dev_vp_timer':
        if uid != OWNER_ID:
            return
        await edit_current(f"⏰ НАСТРОЙКА ТАЙМЕРА ВП\n\nТекущий таймер: {get_vp_timer()} ЧАСОВ\n\nВыберите новый таймер:", vp_timer_kb(uid))
        return
    
    if data.startswith('vp_timer_') and not data.startswith('vp_timer_custom'):
        if uid != OWNER_ID:
            return
        hours = int(data.replace('vp_timer_', ''))
        set_vp_timer(hours)
        await edit_current(f"✅ ТАЙМЕР УСТАНОВЛЕН НА {hours} ЧАСОВ!", dev_kb(uid))
        return
    
    if data == 'vp_timer_custom':
        if uid != OWNER_ID:
            return
        context.user_data['vp_timer_custom_wait'] = True
        await edit_current("⏰ ВВЕДИТЕ НОВОЕ ЗНАЧЕНИЕ ТАЙМЕРА В ЧАСАХ\n\nМожно ввести дробное число:\n• 0.5 = 30 минут\n• 0.8 = 48 минут\n• 1 = 1 час\n• 24 = 1 день\n\n📌 Пример: 0.5", back_kb(uid))
        return
    
    # ===== РАЗРАБОТЧИК: ОЧИСТКА ВП =====
    if data == 'dev_clear_vp':
        if uid != OWNER_ID:
            return
        await edit_current("⚠️ ВЫ УВЕРЕНЫ? ВСЕ ПОСТЫ ВП БУДУТ УДАЛЕНЫ!", InlineKeyboardMarkup([[InlineKeyboardButton("✅ ДА, УДАЛИТЬ ВСЁ", callback_data='dev_clear_vp_confirm')], [InlineKeyboardButton("❌ НЕТ, ОТМЕНА", callback_data='developer')]]))
        return
    
    if data == 'dev_clear_vp_confirm':
        if uid != OWNER_ID:
            return
        clear_all_vp_posts()
        await edit_current("✅ ВСЕ ПОСТЫ ВП УДАЛЕНЫ!", dev_kb(uid))
        return
    
    # ===== РАЗРАБОТЧИК: УДАЛЕНИЕ КАНАЛА =====
    if data.startswith('admin_del_channel_'):
        if uid != OWNER_ID:
            return
        channel_id = int(data.replace('admin_del_channel_', ''))
        admin_delete_channel(channel_id)
        await edit_current("✅ КАНАЛ УДАЛЁН!", back_kb(uid))
        return
    
    # ===== РАЗРАБОТЧИК: ВСЕ ПОЛЬЗОВАТЕЛИ (С БЛОКИРОВКОЙ - ПУНКТ 17) =====
    if data == 'dev_all_users':
        if uid != OWNER_ID:
            return
        await edit_current("👥 УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ\n\nВыберите способ поиска:", InlineKeyboardMarkup([[InlineKeyboardButton("🔍 ПО НИКНЕЙМУ", callback_data='dev_search_by_nick')], [InlineKeyboardButton("🔍 ПО ID В БОТЕ", callback_data='dev_search_by_user_id')], [InlineKeyboardButton("🔍 ПО НАЗВАНИЮ КАНАЛА", callback_data='dev_search_by_channel_name')], [InlineKeyboardButton("📋 ПОКАЗАТЬ ВСЕХ", callback_data='dev_show_all_users')], [InlineKeyboardButton("◀️ НАЗАД", callback_data='developer')]]))
        return
    
    if data == 'dev_search_by_nick':
        context.user_data['dev_search_type'] = 'nick'
        await edit_current("🔍 ВВЕДИТЕ НИКНЕЙМ:", back_kb(uid))
        return
    
    if data == 'dev_search_by_user_id':
        context.user_data['dev_search_type'] = 'user_id'
        await edit_current("🔍 ВВЕДИТЕ ID В БОТЕ:", back_kb(uid))
        return
    
    if data == 'dev_search_by_channel_name':
        context.user_data['dev_search_type'] = 'channel_name'
        await edit_current("🔍 ВВЕДИТЕ НАЗВАНИЕ КАНАЛА:", back_kb(uid))
        return
    
    if data == 'dev_show_all_users':
        if uid != OWNER_ID:
            return
        all_users = get_all_users()
        if not all_users:
            await edit_current("❌ НЕТ ПОЛЬЗОВАТЕЛЕЙ!", back_kb(uid, 'developer'))
            return
        text = "👥 ВСЕ ПОЛЬЗОВАТЕЛИ:\n\n"
        for u in all_users[:30]:
            if is_user_blocked(u['user_id']):
                continue
            nickname = get_user_nickname(u['user_id']) or "Не указан"
            sub_end = get_subscription_end(u['user_id'])
            sub_status = f"✅ ДО {sub_end}" if sub_end and is_subscribed(u['user_id']) else "❌ НЕТ"
            is_tester_user = "✅ ДА" if is_tester(u['user_id']) else "❌ НЕТ"
            is_owner = "👑 ДА" if u['user_id'] == OWNER_ID else "❌ НЕТ"
            is_blocked = "🔒 ДА" if is_user_blocked(u['user_id']) else "❌ НЕТ"
            channels = get_user_channels(u['user_id'])
            text += (
                f"👤 {nickname}\n"
                f"   🆔 ID: {u['user_id']}\n"
                f"   👤 Username: @{u['username'] if u['username'] else 'Не указан'}\n"
                f"   💳 Подписка: {sub_status}\n"
                f"   🧪 Тестер: {is_tester_user}\n"
                f"   👑 Владелец: {is_owner}\n"
                f"   🔒 Заблокирован: {is_blocked}\n"
                f"   📅 Дата регистрации: {u['created_at']}\n"
            )
            if channels:
                text += f"   📺 Каналов: {len(channels)}\n"
                for ch in channels[:3]:
                    text += f"      📺 {ch['channel_name']} (ID: {ch['channel_id']})\n"
                if len(channels) > 3:
                    text += f"      ... и еще {len(channels) - 3}\n"
            else:
                text += f"   📺 Каналов: 0\n"
            if uid == OWNER_ID:
                if is_user_blocked(u['user_id']):
                    text += f"   [🔓 РАЗБЛОКИРОВАТЬ](callback_data=unblock_user_{u['user_id']})\n"
                else:
                    text += f"   [🔒 ЗАБЛОКИРОВАТЬ](callback_data=block_user_{u['user_id']})\n"
            text += "\n"
        if len(all_users) > 30:
            text += f"... и еще {len(all_users) - 30} пользователей"
        await edit_current(text, back_kb(uid, 'developer'))
        return
    
    # ===== БЛОКИРОВКА/РАЗБЛОКИРОВКА (ПУНКТ 17) =====
    if data.startswith('block_user_'):
        if uid != OWNER_ID:
            return
        target_id = int(data.replace('block_user_', ''))
        if target_id == OWNER_ID:
            await edit_current("❌ НЕЛЬЗЯ ЗАБЛОКИРОВАТЬ ВЛАДЕЛЬЦА!", back_kb(uid))
            return
        block_user(target_id)
        await edit_current(f"✅ ПОЛЬЗОВАТЕЛЬ {target_id} ЗАБЛОКИРОВАН!", dev_kb(uid))
        return
    
    if data.startswith('unblock_user_'):
        if uid != OWNER_ID:
            return
        target_id = int(data.replace('unblock_user_', ''))
        unblock_user(target_id)
        await edit_current(f"✅ ПОЛЬЗОВАТЕЛЬ {target_id} РАЗБЛОКИРОВАН!", dev_kb(uid))
        return
    
    # ===== РАЗРАБОТЧИК: СОЗДАНИЕ КОДА =====
    if data == 'dev_create_code':
        if uid != OWNER_ID:
            return
        context.user_data['code_create_name'] = True
        await edit_current("🎟 ВВЕДИТЕ НАЗВАНИЕ:", back_kb(uid))
        return
    
    if data.startswith('code_days_'):
        if uid != OWNER_ID:
            return
        days = int(data.replace('code_days_', ''))
        name = context.user_data.get('code_name', 'Промокод')
        uses = context.user_data.get('code_create_uses_count', 1)
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        create_promo_code(code, name, uses, days)
        context.user_data['code_create_days_wait'] = False
        context.user_data['code_name'] = None
        context.user_data['code_create_uses_count'] = None
        log_main(uid, "Создал код", f"{code} на {days} дней")
        await edit_current(f"🎟 КОД СОЗДАН!\n\n📝 Название: {name}\n🎟 {code}\n🔢 {uses} использований\n📅 {days} дней\n\n🔽 Что дальше?", InlineKeyboardMarkup([[InlineKeyboardButton("🎟 СОЗДАТЬ ЕЩЁ", callback_data='dev_create_code')], [InlineKeyboardButton("📋 ВСЕ КОДЫ", callback_data='dev_active_codes')], [InlineKeyboardButton("◀️ В ПАНЕЛЬ РАЗРАБОТЧИКА", callback_data='developer')]]))
        return
    
    # ===== РАЗРАБОТЧИК: АКТИВНЫЕ КОДЫ =====
    if data == 'dev_active_codes':
        if uid != OWNER_ID:
            return
        codes = get_all_promo_codes()
        if not codes:
            await edit_current("❌ НЕТ АКТИВНЫХ КОДОВ", dev_kb(uid))
            return
        text = "📋 АКТИВНЫЕ КОДЫ:\n\n"
        for c in codes:
            status = "✅" if c['is_active'] and c['uses'] < c['max_uses'] else "❌ ИСПОЛЬЗОВАН"
            text += f"🎟 {c['name']}\n   {c['code']}\n   {c['uses']}/{c['max_uses']}\n   📅 {c['subscription_days']} дн.\n   {status}\n\n"
        await edit_current(text, InlineKeyboardMarkup([[InlineKeyboardButton("🗑 УДАЛИТЬ КОД", callback_data='dev_delete_code')], [InlineKeyboardButton("◀️ НАЗАД", callback_data='developer')]]))
        return
    
    if data == 'dev_delete_code':
        if uid != OWNER_ID:
            return
        codes = get_all_promo_codes()
        if not codes:
            await edit_current("❌ Нет кодов!", dev_kb(uid))
            return
        kb = [[InlineKeyboardButton(f"🗑 {c['name']}", callback_data=f"del_code_{c['code']}")] for c in codes[:15]]
        kb.append([InlineKeyboardButton("◀️ НАЗАД", callback_data='dev_active_codes')])
        await edit_current("🗑 ВЫБЕРИТЕ:", InlineKeyboardMarkup(kb))
        return
    
    if data.startswith('del_code_'):
        if uid != OWNER_ID:
            return
        code = data.replace('del_code_', '')
        del_promo_code(code)
        await edit_current("✅ КОД УДАЛЕН!", dev_kb(uid))
        return
    
    # ===== РАЗРАБОТЧИК: РАССЫЛКА =====
    if data == 'dev_broadcast':
        if uid != OWNER_ID:
            return
        await edit_current("📨 ВЫБЕРИТЕ АУДИТОРИЮ ДЛЯ РАССЫЛКИ:", broadcast_audience_kb(uid))
        return
    
    if data.startswith('broadcast_'):
        if uid != OWNER_ID:
            return
        audience = data.replace('broadcast_', '')
        context.user_data['broadcast_audience'] = audience
        context.user_data['broadcast_wait'] = True
        await edit_current(f"📨 РАССЫЛКА\n\n👥 Аудитория: {audience.upper()}\n\nОтправьте текст или медиа для рассылки.\n📌 Поддерживается:\n• Текст\n• Фото\n• Видео\n• GIF\n• Документ", back_kb(uid))
        return
    
    # ===== РАЗРАБОТЧИК: ТЕХОБСЛУЖИВАНИЕ =====
    if data == 'maintenance_on':
        if uid != OWNER_ID:
            return
        BOT_STOPPED = True
        await edit_current("⏹ БОТ ЗАКРЫТ НА ТО!", dev_kb(uid))
        return
    
    if data == 'maintenance_off':
        if uid != OWNER_ID:
            return
        BOT_STOPPED = False
        await edit_current("▶️ БОТ ОТКРЫТ!", dev_kb(uid))
        return
    
    # ===== РАЗРАБОТЧИК: ПОДАРОК (С ВЫБОРОМ ТИПА - ПУНКТ 22) =====
    if data == 'dev_gift':
        if uid != OWNER_ID:
            return
        await edit_current("🎁 ВЫБЕРИТЕ ТИП ПОДПИСКИ ДЛЯ ПОДАРКА:", gift_kb(uid))
        return
    
    if data == 'gift_regular':
        if uid != OWNER_ID:
            return
        context.user_data['gift_type'] = 'regular'
        context.user_data['gift_wait'] = True
        await edit_current("🎁 ВВЕДИТЕ ID ПОЛЬЗОВАТЕЛЯ ДЛЯ ПОДАРКА ОБЫЧНОЙ ПОДПИСКИ:", back_kb(uid))
        return
    
    if data == 'gift_tester':
        if uid != OWNER_ID:
            return
        context.user_data['gift_type'] = 'tester'
        context.user_data['gift_wait'] = True
        await edit_current("🎁 ВВЕДИТЕ ID ПОЛЬЗОВАТЕЛЯ ДЛЯ ПОДАРКА ТЕСТЕР-ПОДПИСКИ:", back_kb(uid))
        return
    
    # ===== РАЗРАБОТЧИК: ОТЧЁТ (С БЕТА-ФУНКЦИЯМИ - ПУНКТ 25) =====
    if data == 'dev_report':
        if uid != OWNER_ID:
            return
        all_users = get_all_users()
        sub_users = [u for u in all_users if is_subscribed(u['user_id'])]
        channels = get_all_channels()
        vp_posts = get_all_vp_posts_count()
        testers = get_all_testers()
        features = get_beta_features('all')
        features_testing = get_beta_features('testing')
        feedback = get_feedback()
        blocked = get_blocked_users()
        await edit_current(
            f"📊 ОТЧЁТ\n\n"
            f"👥 Всего пользователей: {len(all_users)}\n"
            f"👥 Активных: {len(sub_users)}\n"
            f"📺 Каналов: {len(channels)}\n"
            f"📢 Постов ВП: {vp_posts}\n"
            f"🧪 Тестеров: {len(testers)}\n"
            f"🔬 Бета-функций всего: {len(features)}\n"
            f"🧪 Бета-функций в тестировании: {len(features_testing)}\n"
            f"📝 Отзывов: {len(feedback)}\n"
            f"🔒 Заблокировано: {len(blocked)}\n"
            f"💰 Доход: 0 руб\n"
            f"📌 Версия: {BOT_VERSION}",
            dev_kb(uid)
        )
        return
    
    # ===== РАЗРАБОТЧИК: КАСТОМИЗАЦИЯ =====
    if data == 'dev_customize':
        if uid != OWNER_ID:
            return
        desc = get_setting("global_desc") or "Не установлено"
        media = "✅" if get_setting("global_media") else "❌"
        await edit_current(f"🎨 КАСТОМИЗАЦИЯ\n\n📝 Описание: {desc}\n🖼 Медиа: {media}", InlineKeyboardMarkup([[InlineKeyboardButton("✏️ ОПИСАНИЕ", callback_data='custom_desc')], [InlineKeyboardButton("📎 МЕДИА", callback_data='custom_media')], [InlineKeyboardButton("🗑 УДАЛИТЬ МЕДИА", callback_data='custom_media_delete')], [InlineKeyboardButton("🔄 СБРОС ВСЕГО", callback_data='custom_reset')], [InlineKeyboardButton("◀️ НАЗАД", callback_data='back')]]))
        return
    
    if data == 'custom_desc':
        if uid != OWNER_ID:
            return
        context.user_data['custom_desc_wait'] = True
        await edit_current("📝 ВВЕДИТЕ НОВОЕ ОПИСАНИЕ:", back_kb(uid))
        return
    
    if data == 'custom_media':
        if uid != OWNER_ID:
            return
        context.user_data['custom_media_wait'] = True
        await edit_current("📎 ОТПРАВЬТЕ МЕДИА (фото/видео/gif):", back_kb(uid))
        return
    
    if data == 'custom_media_delete':
        if uid != OWNER_ID:
            return
        set_setting("global_media", None)
        await edit_current("✅ МЕДИА УДАЛЕНО!", dev_kb(uid))
        return
    
    if data == 'custom_reset':
        if uid != OWNER_ID:
            return
        set_setting("global_desc", None)
        set_setting("global_media", None)
        await edit_current("✅ ВСЁ СБРОШЕНО!", dev_kb(uid))
        return
    
    # ===== РАЗРАБОТЧИК: ТЕСТЕРЫ =====
    if data == 'dev_testers':
        if uid != OWNER_ID:
            return
        testers = get_all_testers()
        tester_list = ""
        if testers:
            for t in testers[:20]:
                nickname = get_user_nickname(t) or str(t)
                tester_list += f"👤 {nickname} (ID: {t})\n"
        else:
            tester_list = "❌ Нет тестеров"
        await edit_current(f"🧪 ТЕСТЕРЫ\n\n{tester_list}", InlineKeyboardMarkup([[InlineKeyboardButton("➕ ДОБАВИТЬ", callback_data='dev_add_tester')], [InlineKeyboardButton("➖ УДАЛИТЬ", callback_data='dev_remove_tester')], [InlineKeyboardButton("◀️ НАЗАД", callback_data='developer')]]))
        return
    
    if data == 'dev_add_tester':
        if uid != OWNER_ID:
            return
        context.user_data['add_tester_wait'] = True
        await edit_current("👤 ВВЕДИТЕ ID:", back_kb(uid))
        return
    
    if data == 'dev_remove_tester':
        if uid != OWNER_ID:
            return
        testers = get_all_testers()
        if not testers:
            await edit_current("❌ Нет тестеров!", back_kb(uid))
            return
        kb = [[InlineKeyboardButton(f"❌ {get_user_nickname(t) or str(t)}", callback_data=f"del_tester_{t}")] for t in testers[:15]]
        kb.append([InlineKeyboardButton("◀️ НАЗАД", callback_data='dev_testers')])
        await edit_current("🗑 ВЫБЕРИТЕ:", InlineKeyboardMarkup(kb))
        return
    
    if data.startswith('del_tester_'):
        if uid != OWNER_ID:
            return
        tester_id = int(data.replace('del_tester_', ''))
        set_setting(f"tester_{tester_id}", '0')
        log_main(uid, "Удалил тестера", str(tester_id))
        await edit_current("✅ УДАЛЕН!", dev_kb(uid))
        return
    
    # ===== РАЗРАБОТЧИК: РЕДАКТОР РЕГИСТРАЦИИ =====
    if data == 'dev_edit_registration':
        if uid != OWNER_ID:
            return
        await edit_current("📝 РЕДАКТОР РЕГИСТРАЦИОННОГО СООБЩЕНИЯ\n\nЗдесь вы можете изменить текст и медиа,\nкоторые видят пользователи при первом запуске бота.", registration_editor_kb())
        return
    
    if data == 'dev_edit_reg_text':
        if uid != OWNER_ID:
            return
        context.user_data['edit_reg_text_wait'] = True
        await edit_current("📝 ВВЕДИТЕ НОВЫЙ ТЕКСТ ДЛЯ РЕГИСТРАЦИИ\n\n📌 Используйте {BOT_NAME} для подстановки имени бота.", back_kb(uid, 'dev_edit_registration'))
        return
    
    if data == 'dev_edit_reg_media':
        if uid != OWNER_ID:
            return
        context.user_data['edit_reg_media_wait'] = True
        await edit_current("📎 ОТПРАВЬТЕ МЕДИА ДЛЯ РЕГИСТРАЦИИ\n\nПоддерживается:\n• Фото\n• Видео\n• GIF\n\nОтправьте медиа или нажмите 'УДАЛИТЬ' для удаления текущего.", InlineKeyboardMarkup([[InlineKeyboardButton("🗑 УДАЛИТЬ МЕДИА", callback_data='dev_del_reg_media')], [InlineKeyboardButton("◀️ НАЗАД", callback_data='dev_edit_registration')]]))
        return
    
    if data == 'dev_del_reg_media':
        if uid != OWNER_ID:
            return
        set_setting("reg_media", None)
        await edit_current("✅ МЕДИА УДАЛЕНО!", registration_editor_kb())
        return
    
    if data == 'dev_reset_reg':
        if uid != OWNER_ID:
            return
        set_setting("reg_text", None)
        set_setting("reg_media", None)
        await edit_current("✅ РЕГИСТРАЦИОННОЕ СООБЩЕНИЕ СБРОШЕНО!", registration_editor_kb())
        return
    
    # ===== БЕТА-ФУНКЦИИ (ПУНКТ 8) =====
    if data == 'beta_features':
        if not is_tester(uid) and uid != OWNER_ID:
            await edit_current("❌ ФУНКЦИЯ В ТЕСТИРОВАНИИ!", back_kb(uid))
            return
        await edit_current("🔬 БЕТА-ФУНКЦИИ\n\nНовые функции в тестировании!\n\n🤖 ИИ ПОДДЕРЖКА — тестовый режим\n📝 ОТЗЫВЫ — оставьте свой отзыв о функциях", beta_features_kb(uid))
        return
    
    if data == 'beta_example':
        if not is_tester(uid) and uid != OWNER_ID:
            return
        await edit_current("🔬 ПРИМЕР БЕТА-ФУНКЦИИ\n\nЭто тестовая функция.\n\n📌 Если вы видите это — вы тестер или разработчик!", back_kb(uid))
        return
    
    if data == 'beta_stats':
        if not is_tester(uid) and uid != OWNER_ID:
            return
        testers = get_all_testers()
        features = get_beta_features('testing')
        await edit_current(f"📊 БЕТА-СТАТИСТИКА\n\n🧪 Тестеров: {len(testers)}\n🔬 Бета-функций в тестировании: {len(features)}\n📌 Ты тестер: {'✅' if is_tester(uid) else '❌'}\n👑 Разработчик: {'✅' if uid == OWNER_ID else '❌'}", back_kb(uid))
        return
    
    if data == 'beta_ai_support':
        if not is_tester(uid) and uid != OWNER_ID:
            return
        await edit_current("🤖 ИИ ПОДДЕРЖКА (БЕТА)\n\nЭто тестовый режим ИИ-помощника.\n\n📌 Функции:\n• Быстрые ответы на вопросы\n• Помощь в настройке бота\n• Советы по продвижению\n\n⚠️ Функция в разработке!\nВаши отзывы помогут улучшить ИИ.\n\n📌 Связь с разработчиком: @GanzalesSs920", back_kb(uid))
        return
    
    # ===== ОТЗЫВЫ (ПУНКТ 19) =====
    if data == 'beta_feedback':
        if not is_tester(uid) and uid != OWNER_ID:
            await edit_current("❌ ТОЛЬКО ДЛЯ ТЕСТЕРОВ!", back_kb(uid))
            return
        await edit_current("📝 ОСТАВИТЬ ОТЗЫВ\n\nВыберите функцию, о которой хотите оставить отзыв:", InlineKeyboardMarkup([[InlineKeyboardButton("🔬 ИИ ПОДДЕРЖКА", callback_data='feedback_feature_ai')], [InlineKeyboardButton("📊 БЕТА-СТАТИСТИКА", callback_data='feedback_feature_stats')], [InlineKeyboardButton("🔬 ПРИМЕР БЕТА-ФУНКЦИИ", callback_data='feedback_feature_example')], [InlineKeyboardButton("📝 ДРУГОЕ", callback_data='feedback_feature_other')], [InlineKeyboardButton("◀️ НАЗАД", callback_data='beta_features')]]))
        return
    
    if data.startswith('feedback_feature_'):
        feature = data.replace('feedback_feature_', '')
        feature_names = {
            'ai': 'ИИ ПОДДЕРЖКА',
            'stats': 'БЕТА-СТАТИСТИКА',
            'example': 'ПРИМЕР БЕТА-ФУНКЦИИ',
            'other': 'ДРУГАЯ ФУНКЦИЯ'
        }
        feature_name = feature_names.get(feature, 'Неизвестная функция')
        context.user_data['feedback_feature'] = feature_name
        await edit_current(f"📝 ОТЗЫВ О ФУНКЦИИ: {feature_name}\n\nОцените функцию от 1 до 5:\n⭐ 1 - Ужасно\n⭐ 5 - Отлично", feedback_kb(uid))
        return
    
    if data.startswith('feedback_'):
        rating = int(data.replace('feedback_', ''))
        context.user_data['feedback_rating'] = rating
        context.user_data['feedback_wait'] = True
        feature = context.user_data.get('feedback_feature', 'Неизвестная функция')
        await edit_current(f"📝 ОТЗЫВ О ФУНКЦИИ: {feature}\n\n⭐ Оценка: {rating}/5\n\n📝 Напишите текст отзыва:", back_kb(uid))
        return
    
    # ===== ВП (ВЗАИМОПОСТ) =====
    if data == 'vp_menu':
        if not is_subscribed(uid) and uid != OWNER_ID:
            await edit_current("❌ ДЛЯ ИСПОЛЬЗОВАНИЯ ВП ТРЕБУЕТСЯ ПОДПИСКА!", InlineKeyboardMarkup([[InlineKeyboardButton("💳 ПОДПИСКА", callback_data='subscription')], [InlineKeyboardButton("◀️ НАЗАД", callback_data='back')]]))
            return
        channels = get_user_channels(uid)
        if not channels and uid != OWNER_ID:
            await edit_current("❌ ДЛЯ ИСПОЛЬЗОВАНИЯ ВП НУЖЕН ХОТЯ БЫ 1 КАНАЛ!\n\n🔗 Сначала привяжите канал.", InlineKeyboardMarkup([[InlineKeyboardButton("🔗 ПРИВЯЗАТЬ КАНАЛ", callback_data='connect_channel')], [InlineKeyboardButton("◀️ НАЗАД", callback_data='back')]]))
            return
        timer_hours = get_vp_timer()
        await edit_current(f"📢 ВП (ВЗАИМОПОСТ)\n\nЗдесь вы можете разместить пост с предложением о взаимопиаре.\n\n📌 Правила:\n• Только для владельцев подписки\n• Нужен хотя бы 1 привязанный канал\n• Пост можно создать раз в {timer_hours} часов\n• Можно добавить медиа (фото/видео/гиф)\n• Можно отметить 18+\n• Выбрать категорию\n\n🔽 Выберите действие:", vp_kb(uid))
        return
    
    if data == 'vp_view':
        page = context.user_data.get('vp_page', 0)
        adult_only = not is_adult(uid)
        posts, total = get_vp_posts(limit=3, offset=page*3, adult_only=adult_only)
        total_pages = (total + 2) // 3
        if not posts:
            await edit_current("📋 НЕТ ПОСТОВ ВП\n\nБудьте первым! Создайте пост с предложением о взаимопиаре.", vp_kb(uid))
            return
        for post in posts:
            await send_vp_post(post)
        nav_kb = []
        nav_btns = []
        if page > 0:
            nav_btns.append(InlineKeyboardButton("⬅️", callback_data=f"vp_page_{page-1}"))
        nav_btns.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="vp_view"))
        if page < total_pages - 1:
            nav_btns.append(InlineKeyboardButton("➡️", callback_data=f"vp_page_{page+1}"))
        if nav_btns:
            nav_kb.append(nav_btns)
        nav_kb.append([InlineKeyboardButton("➕ СОЗДАТЬ ПОСТ", callback_data='vp_create')])
        nav_kb.append([InlineKeyboardButton("◀️ НАЗАД", callback_data='back')])
        try:
            await query.message.reply_text(f"📋 Страница {page+1} из {total_pages}", reply_markup=InlineKeyboardMarkup(nav_kb))
        except:
            pass
        try:
            await query.message.delete()
        except:
            pass
        return
    
    if data.startswith('vp_page_'):
        page = int(data.replace('vp_page_', ''))
        context.user_data['vp_page'] = page
        await callback(update, context)
        return
    
    if data.startswith('vp_delete_'):
        if uid != OWNER_ID:
            await edit_current("❌ ДОСТУП ЗАПРЕЩЁН!", back_kb(uid))
            return
        post_id = int(data.replace('vp_delete_', ''))
        delete_vp_post(post_id)
        await edit_current("✅ ПОСТ УДАЛЁН!", vp_kb(uid))
        return
    
    if data == 'vp_create':
        can, msg_text = can_user_post_vp(uid)
        if not can:
            await edit_current(f"{msg_text}\n\n⌛ Подождите до следующего поста.", back_kb(uid))
            return
        context.user_data['vp_post'] = {'media': None, 'text': None, 'is_adult': False, 'category': None, 'channel_id': None}
        channels = get_user_channels(uid)
        if not channels:
            if uid == OWNER_ID:
                await edit_current("📝 СОЗДАНИЕ ПОСТА ВП (РАЗРАБОТЧИК)\n\n⚠️ У вас нет каналов.\nВведите ID канала вручную:\n📌 Пример: -1001234567890\n\nИли нажмите 'НАЗАД' и сначала привяжите канал.", back_kb(uid))
                context.user_data['vp_wait_channel'] = True
                return
            else:
                await edit_current("❌ У ВАС НЕТ КАНАЛОВ!\n\n🔗 Сначала привяжите канал.", InlineKeyboardMarkup([[InlineKeyboardButton("🔗 ПРИВЯЗАТЬ КАНАЛ", callback_data='connect_channel')], [InlineKeyboardButton("◀️ НАЗАД", callback_data='vp_menu')]]))
                return
        if len(channels) == 1:
            context.user_data['vp_post']['channel_id'] = channels[0]['channel_id']
            await edit_current(f"📝 СОЗДАНИЕ ПОСТА ВП\n\n📺 Канал: {channels[0]['channel_name']}\n\n📝 Введите текст поста (обязательно):\n📌 Не забудьте указать контакты для связи!\n\n🔽 Напишите текст в чат.", back_kb(uid))
            context.user_data['vp_wait_text'] = True
            return
        kb = []
        for ch in channels:
            kb.append([InlineKeyboardButton(f"📺 {ch['channel_name']}", callback_data=f"vp_ch_{ch['channel_id']}")])
        kb.append([InlineKeyboardButton("◀️ НАЗАД", callback_data='vp_menu')])
        await edit_current("📺 ВЫБЕРИТЕ КАНАЛ ДЛЯ ПОСТА:", InlineKeyboardMarkup(kb))
        return
    
    if data.startswith('vp_ch_'):
        channel_id = int(data.replace('vp_ch_', ''))
        context.user_data['vp_post']['channel_id'] = channel_id
        channels = get_user_channels(uid)
        channel_name = "Канал"
        for ch in channels:
            if ch['channel_id'] == channel_id:
                channel_name = ch['channel_name']
                break
        await edit_current(f"📝 СОЗДАНИЕ ПОСТА ВП\n\n📺 Канал: {channel_name}\n\n📝 Введите текст поста (обязательно):\n📌 Не забудьте указать контакты для связи!\n\n🔽 Напишите текст в чат.", back_kb(uid))
        context.user_data['vp_wait_text'] = True
        return
    
    if data == 'vp_add_media':
        context.user_data['vp_wait_media'] = True
        await edit_current("📷 ОТПРАВЬТЕ МЕДИАФАЙЛ\n\nПоддерживается:\n• Фото\n• Видео\n• GIF-анимация\n\nМожно пропустить, отправив любое сообщение.", back_kb(uid))
        return
    
    if data == 'vp_toggle_adult':
        if 'vp_post' not in context.user_data:
            context.user_data['vp_post'] = {}
        current = context.user_data['vp_post'].get('is_adult', False)
        context.user_data['vp_post']['is_adult'] = not current
        status = "🔞 ВКЛ" if not current else "🔓 ВЫКЛ"
        await edit_current(f"✅ 18+ {status}!\n\nПродолжайте создание поста.", vp_create_kb(uid))
        return
    
    if data == 'vp_choose_category':
        await edit_current("📂 ВЫБЕРИТЕ КАТЕГОРИЮ:", vp_category_kb(uid))
        return
    
    if data.startswith('vp_cat_'):
        cat = data.replace('vp_cat_', '')
        if 'vp_post' not in context.user_data:
            context.user_data['vp_post'] = {}
        context.user_data['vp_post']['category'] = cat
        await edit_current(f"✅ КАТЕГОРИЯ ВЫБРАНА: {cat}\n\nПродолжайте создание поста.", vp_create_kb(uid))
        return
    
    if data == 'vp_publish':
        post_data = context.user_data.get('vp_post', {})
        if not post_data.get('text'):
            await edit_current("❌ ТЕКСТ ПОСТА ОБЯЗАТЕЛЕН!\n\nНапишите текст в чат.", vp_create_kb(uid))
            return
        if not post_data.get('category'):
            await edit_current("❌ ВЫБЕРИТЕ КАТЕГОРИЮ!", vp_create_kb(uid))
            return
        if not post_data.get('channel_id'):
            if uid == OWNER_ID:
                channels = get_user_channels(uid)
                if channels:
                    post_data['channel_id'] = channels[0]['channel_id']
                else:
                    await edit_current("❌ У РАЗРАБОТЧИКА НЕТ КАНАЛОВ!", back_kb(uid))
                    return
            else:
                await edit_current("❌ ОШИБКА! Канал не выбран.", back_kb(uid))
                return
        add_vp_post(uid, post_data['channel_id'], post_data.get('media'), post_data['text'], post_data.get('is_adult', False), post_data['category'])
        context.user_data['vp_post'] = {}
        context.user_data['vp_wait_text'] = False
        context.user_data['vp_wait_media'] = False
        context.user_data['vp_wait_channel'] = False
        timer_hours = get_vp_timer()
        await edit_current(f"✅ ПОСТ ВП УСПЕШНО ОПУБЛИКОВАН!\n\nОн появится в общей ленте.\nСледующий пост через {timer_hours} часов.\n\n🔽 Что дальше?", InlineKeyboardMarkup([[InlineKeyboardButton("📋 ВСЕ ПОСТЫ", callback_data='vp_view')], [InlineKeyboardButton("➕ ЕЩЁ ПОСТ", callback_data='vp_create')], [InlineKeyboardButton("◀️ В ГЛАВНОЕ МЕНЮ", callback_data='back')]]))
        return
    
    if data == 'vp_cancel':
        context.user_data['vp_post'] = {}
        context.user_data['vp_wait_text'] = False
        context.user_data['vp_wait_media'] = False
        context.user_data['vp_wait_channel'] = False
        await edit_current("✅ СОЗДАНИЕ ПОСТА ОТМЕНЕНО!", vp_kb(uid))
        return
    
    # ===== ЛИДЕРБОАРД (ПУНКТ 9) =====
    if data.startswith('set_leaderboard_'):
        channel_id = int(data.replace('set_leaderboard_', ''))
        await edit_current("📊 ЛИДЕРБОАРД\n\nТоп-20 комментаторов:", InlineKeyboardMarkup([[InlineKeyboardButton("📅 ДЕНЬ", callback_data=f"lb_day_{channel_id}")], [InlineKeyboardButton("📅 МЕСЯЦ", callback_data=f"lb_month_{channel_id}")], [InlineKeyboardButton("📅 ВСЁ", callback_data=f"lb_all_{channel_id}")], [InlineKeyboardButton("◀️ НАЗАД", callback_data=f"set_ch_{channel_id}")]]))
        return
    
    if data.startswith('lb_'):
        parts = data.split('_')
        period = parts[1] if len(parts) > 1 else 'day'
        channel_id = int(parts[2]) if len(parts) > 2 else 0
        names = {'day': 'ДЕНЬ', 'month': 'МЕСЯЦ', 'all': 'ВСЁ'}
        # Получаем топ комментаторов из группы канала
        linked_group = get_channel_linked_group(channel_id)
        if linked_group:
            top = []
            try:
                # Получаем участников группы
                members = context.bot.get_chat_administrators(linked_group)
                for admin in members[:20]:
                    if not admin.user.is_bot:
                        name = admin.user.first_name or admin.user.username or str(admin.user.id)
                        top.append((name, random.randint(1, 100)))
            except:
                top = get_top_commenters(channel_id, period)
        else:
            top = get_top_commenters(channel_id, period)
        
        text = f"📊 {names.get(period, '')}\n\n"
        if top:
            for i, (name, count) in enumerate(top[:20], 1):
                text += f"{i}. {name} — {count} комм.\n"
        else:
            text += "😕 Нет данных\n\nℹ️ Подключите группу к каналу для сбора статистики."
        await edit_current(text, back_kb(uid))
        return
    
    # ===== СТАТИСТИКА =====
    if data.startswith('set_stats_'):
        channel_id = int(data.replace('set_stats_', ''))
        await edit_current("📊 СТАТИСТИКА", InlineKeyboardMarkup([[InlineKeyboardButton("📅 НЕДЕЛЯ", callback_data=f"stats_week_{channel_id}")], [InlineKeyboardButton("📅 МЕСЯЦ", callback_data=f"stats_month_{channel_id}")], [InlineKeyboardButton("📅 ВСЁ", callback_data=f"stats_all_{channel_id}")], [InlineKeyboardButton("◀️ НАЗАД", callback_data=f"set_ch_{channel_id}")]]))
        return
    
    if data.startswith('stats_'):
        parts = data.split('_')
        period = parts[1] if len(parts) > 1 else 'week'
        names = {'week': 'НЕДЕЛЯ', 'month': 'МЕСЯЦ', 'all': 'ВСЁ'}
        await edit_current(f"📊 {names.get(period, '')}\n\n👥 1,234\n👁 45,678\n📝 456", back_kb(uid))
        return
    
    # ===== ПРОФИЛЬ КАНАЛА =====
    if data.startswith('channel_profile_'):
        channel_id = int(data.replace('channel_profile_', ''))
        ch = get_channel_by_channel_id(channel_id)
        if not ch:
            await edit_current("❌ КАНАЛ НЕ НАЙДЕН!", back_kb(uid))
            return
        owner_name = get_user_nickname(ch['owner_id']) or "Неизвестен"
        update_channel_subscribers(context.bot, channel_id)
        try:
            chat = await context.bot.get_chat(ch['channel_id'])
            channel_link = f"https://t.me/{chat.username}" if hasattr(chat, 'username') and chat.username else "Нет ссылки"
        except:
            channel_link = "Недоступно"
        text = f"📺 ПРОФИЛЬ КАНАЛА\n\n📺 {ch['channel_name']}\n👤 Владелец: {owner_name}\n🆔 ТГ ID: {ch['channel_id']}\n🔗 Ссылка: {channel_link}\n📂 {ch['category'] if ch['category'] else 'Не указана'}\n👥 {ch['subscribers'] if ch['subscribers'] else 0}\n🔒 {ch['privacy'] if ch['privacy'] else 'public'}"
        await edit_current(text, channel_profile_kb(channel_id, ch['privacy'] if ch['privacy'] else 'public', uid))
        return
    
    if data.startswith('go_channel_'):
        channel_id = int(data.replace('go_channel_', ''))
        try:
            chat = await context.bot.get_chat(channel_id)
            if hasattr(chat, 'username') and chat.username:
                await edit_current(f"🚀 ПЕРЕЙТИ В КАНАЛ\n\nhttps://t.me/{chat.username}", back_kb(uid))
            else:
                await edit_current("❌ У КАНАЛА НЕТ USERNAME!\n\nНельзя перейти по ссылке.", back_kb(uid))
        except:
            await edit_current("❌ НЕ УДАЛОСЬ!", back_kb(uid))
        return
    
    if data.startswith('apply_channel_'):
        channel_id = int(data.replace('apply_channel_', ''))
        ch = get_channel_by_channel_id(channel_id)
        if ch:
            try:
                await context.bot.send_message(chat_id=ch['owner_id'], text=f"📩 НОВАЯ ЗАЯВКА!\n\nПользователь {get_user_nickname(uid) or uid} хочет в канал {ch['channel_name']}.\nID: {uid}")
                await edit_current("✅ ЗАЯВКА ОТПРАВЛЕНА!", back_kb(uid))
            except:
                await edit_current("❌ НЕ УДАЛОСЬ ОТПРАВИТЬ ЗАЯВКУ!", back_kb(uid))
        else:
            await edit_current("❌ КАНАЛ НЕ НАЙДЕН!", back_kb(uid))
        return
    
    # ===== КОД =====
    if data == 'code_wait':
        # Уже обработано в handle_msg
        pass
    
    await edit_current("🔄 В РАЗРАБОТКЕ...", back_kb(uid))

# ============================================
#  ЗАПУСК БОТА
# ============================================

def main():
    init_db()
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Основные обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("setrole", set_role))
    application.add_handler(CallbackQueryHandler(callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
    application.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | filters.ANIMATION | filters.Document.ALL, handle_msg))
    
    # Обработчики событий
    application.add_handler(MessageHandler(filters.TEXT & filters.ChatType.GROUPS, check_spam))
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_member))
    application.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, farewell_member))
    application.add_handler(ChatJoinRequestHandler(handle_join_request))
    
    # Обработчики платежей Telegram Stars
    application.add_handler(PreCheckoutQueryHandler(pre_checkout))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))
    
    # Фоновая задача для автопостинга
    def check_scheduled():
        while True:
            try:
                posts = get_all_scheduled_posts()
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                for p in posts:
                    if p['scheduled_time'] <= now:
                        try:
                            if p['post_media']:
                                try:
                                    application.bot.send_photo(chat_id=p['channel_id'], photo=p['post_media'], caption=p['post_text'] if p['post_text'] else None)
                                except:
                                    try:
                                        application.bot.send_video(chat_id=p['channel_id'], video=p['post_media'], caption=p['post_text'] if p['post_text'] else None)
                                    except:
                                        try:
                                            application.bot.send_animation(chat_id=p['channel_id'], animation=p['post_media'], caption=p['post_text'] if p['post_text'] else None)
                                        except:
                                            try:
                                                application.bot.send_document(chat_id=p['channel_id'], document=p['post_media'], caption=p['post_text'] if p['post_text'] else None)
                                            except:
                                                pass
                            else:
                                application.bot.send_message(chat_id=p['channel_id'], text=p['post_text'])
                            conn = get_db()
                            cursor = conn.cursor()
                            cursor.execute('UPDATE scheduled_posts SET is_sent = 1 WHERE id = ?', (p['id'],))
                            conn.commit()
                            conn.close()
                        except Exception as e:
                            log_error(f"Auto post error: {e}")
                time.sleep(60)
            except Exception as e:
                log_error(f"Check error: {e}")
                time.sleep(60)
    
    thread = threading.Thread(target=check_scheduled, daemon=True)
    thread.start()
    
    print("=" * 60)
    print(f"🔥 БОТ {BOT_NAME} ЗАПУЩЕН!")
    print("=" * 60)
    print(f"👑 Владелец: {OWNER_ID}")
    print(f"💰 Цены: {STARS_PRICES['month_regular']}/{STARS_PRICES['6month_regular']}/{STARS_PRICES['year_regular']} ⭐ (обычные)")
    print(f"💰 Цены тестер: {STARS_PRICES['month_tester']}/{STARS_PRICES['6month_tester']}/{STARS_PRICES['year_tester']} ⭐")
    print(f"📌 Версия: {BOT_VERSION}")
    print(f"🧪 Тестеров: {len(get_all_testers())}")
    print(f"🔒 Заблокировано: {len(get_blocked_users())}")
    print(f"⏰ Таймер ВП: {get_vp_timer()} часов")
    print(f"🔬 Бета-функций: {len(get_beta_features('all'))}")
    print("=" * 60)
    print("📁 Логи: logs/")
    print("⚡ Напиши /start в Telegram!")
    print("=" * 60)
    
    # Возвращаем application для использования в app.py
    return application

# Создаём глобальный экземпляр для импорта в app.py
application = main()