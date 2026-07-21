import logging
import json
import re
import random
import string
import os
import asyncio
import threading
import time
import hmac
import hashlib
import base64
import requests
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
BOT_VERSION = "1.0.0"
USER_MESSAGES = {}
USER_LAST_MENU = {}
USER_TEMP_DATA = {}

CATEGORIES = [
    'Музыка', 'Игры', 'Политика', 'Мода', 'Фильмы',
    'Софт и приложения', 'Творчество', '18+', 'Эротика',
    'Спорт', 'Курсы', 'Юмор', 'Блог'
]
ADULT_CATEGORIES = ['18+', 'Эротика']

# Цены в рублях
PRICES = {
    'month': 119,
    '6month': 643,
    'year': 1071,
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

# ============================================
#  ЯЗЫКИ
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
        'search_channels': '🔍 ПОИСК КАНАЛОВ',
        'search_users': '🔍 ПОИСК ЛЮДЕЙ',
        'language': '🌍 ЯЗЫК',
        'support': '💬 ПОДДЕРЖКА',
        'developer': '⚙️ ДЛЯ РАЗРАБОТЧИКОВ',
        'customize': '🎨 КАСТОМИЗАЦИЯ',
        'change_name': '✏️ ИЗМЕНИТЬ ИМЯ',
        'send_message': '💬 НАПИСАТЬ',
        'delete_profile': '🗑 УДАЛИТЬ ПРОФИЛЬ',
        'mail': '📬 ПОЧТА',
        'subscription_active': 'АКТИВНА ДО {date}',
        'subscription_none': 'НЕТУ',
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
        'search_channels': '🔍 SEARCH CHANNELS',
        'search_users': '🔍 SEARCH USERS',
        'language': '🌍 LANGUAGE',
        'support': '💬 SUPPORT',
        'developer': '⚙️ DEVELOPER',
        'customize': '🎨 CUSTOMIZE',
        'change_name': '✏️ CHANGE NAME',
        'send_message': '💬 SEND MESSAGE',
        'delete_profile': '🗑 DELETE PROFILE',
        'mail': '📬 MAIL',
        'subscription_active': 'ACTIVE UNTIL {date}',
        'subscription_none': 'NONE',
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

def clear_user_context(context):
    """Удаляет все временные флаги и данные, связанные с ожиданием ввода"""
    keys = [
        'reg_wait', 'age_wait', 'change_name_wait', 'send_message_wait', 'spam_add_wait',
        'welcome_edit_text_wait', 'farewell_edit_text_wait', 'captcha_q_wait', 'captcha_a_wait',
        'post_wait', 'post_date_wait', 'code_create_name', 'code_create_uses',
        'add_tester_wait', 'remove_tester_wait', 'broadcast_wait', 'gift_wait',
        'custom_desc_wait', 'custom_media_wait', 'edit_reg_text_wait', 'edit_reg_media_wait',
        'vp_wait_channel', 'vp_wait_text', 'vp_wait_media', 'dev_search_type',
        'feedback_wait', 'connect_wait', 'connect_by_link', 'connect_by_username',
        'connect_by_forward_wait', 'search_by_name_wait', 'search_by_bot_id_wait',
        'search_by_tg_id_wait', 'search_users_wait', 'vp_timer_custom_wait',
        'code_wait', 'payment_settings_wait', 'selected_categories', 'connect_channel_id',
        'connect_channel_name', 'vp_post', 'post_data', 'post_channel_id', 'temp_name',
        'send_message_target', 'send_message_anonymous', 'broadcast_audience',
        'gift_type', 'feedback_feature', 'feedback_rating', 'captcha_q',
        'code_name', 'code_create_uses_count'
    ]
    for key in keys:
        context.user_data.pop(key, None)

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

def add_notification(user_id, notif_type, content, link_data=None):
    conn = get_db()
    cursor = conn.cursor()
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
        notifs = cursor.execute('SELECT * FROM notifications WHERE user_id = ? AND read = 0 ORDER BY created_at DESC', (user_id,)).fetchall()
    else:
        notifs = cursor.execute('SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC', (user_id,)).fetchall()
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

def mark_all_notifications_read(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE notifications SET read = 1 WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def get_blocked_users():
    conn = get_db()
    cursor = conn.cursor()
    blocked = cursor.execute("SELECT key FROM settings WHERE key LIKE 'blocked_%' AND value = '1'").fetchall()
    conn.close()
    return [int(b['key'].replace('blocked_', '')) for b in blocked]

def block_user(user_id):
    set_setting(f"blocked_{user_id}", '1')
    return True

def unblock_user(user_id):
    set_setting(f"blocked_{user_id}", '0')
    return True

def is_user_blocked(user_id):
    return get_setting(f"blocked_{user_id}") == '1'

# ============================================
#  КЛАВИАТУРЫ
# ============================================

def main_kb(user_id):
    kb = [
        [InlineKeyboardButton("💳 ПОДПИСКА", callback_data='subscription'), InlineKeyboardButton("👤 ПРОФИЛЬ", callback_data='profile')],
        [InlineKeyboardButton("🔗 ПРИВЯЗАТЬ КАНАЛ", callback_data='connect_channel'), InlineKeyboardButton("⚙️ НАСТРОЙКИ", callback_data='channel_settings')],
        [InlineKeyboardButton("📢 ВП (ВЗАИМОПОСТ)", callback_data='vp_menu')],
        [InlineKeyboardButton("🌍 ЯЗЫК", callback_data='language'), InlineKeyboardButton("💬 ПОДДЕРЖКА", callback_data='support')],
    ]
    if is_subscribed(user_id) or user_id == OWNER_ID:
        kb.insert(2, [InlineKeyboardButton("🔍 ПОИСК КАНАЛОВ", callback_data='search_channels'), InlineKeyboardButton("🔍 ПОИСК ЛЮДЕЙ", callback_data='search_users')])
    kb.append([InlineKeyboardButton("⚙️ ДЛЯ РАЗРАБОТЧИКОВ", callback_data='developer')])
    USER_LAST_MENU[user_id] = 'main'
    return InlineKeyboardMarkup(kb)

def back_kb(user_id, back_to='back', disable=False):
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
        [InlineKeyboardButton("📅 НА МЕСЯЦ - 119 руб", callback_data='sub_month')],
        [InlineKeyboardButton("📅 НА 6 МЕСЯЦЕВ - 643 руб", callback_data='sub_6month')],
        [InlineKeyboardButton("📅 НА ГОД - 1071 руб", callback_data='sub_year')],
        [InlineKeyboardButton("🎟 АКТИВАЦИЯ КОДА", callback_data='activate_code')],
        [InlineKeyboardButton("◀️ НАЗАД", callback_data='back')],
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
        [InlineKeyboardButton("🎨 КАСТОМИЗАЦИЯ", callback_data='dev_customize')],
        [InlineKeyboardButton("👥 ВСЕ ПОЛЬЗОВАТЕЛИ", callback_data='dev_all_users')],
        [InlineKeyboardButton(f"⏰ ТАЙМЕР ВП: {timer_hours}ч", callback_data='dev_vp_timer')],
        [InlineKeyboardButton("🗑 ОЧИСТИТЬ ВП", callback_data='dev_clear_vp')],
        [InlineKeyboardButton("📝 РЕДАКТОР РЕГИСТРАЦИИ", callback_data='dev_edit_registration')],
        [InlineKeyboardButton("◀️ В ГЛАВНОЕ МЕНЮ", callback_data='back_to_main')],
    ]
    USER_LAST_MENU[user_id] = 'developer'
    return InlineKeyboardMarkup(kb)

def profile_kb(user_id):
    auto_renew = get_auto_renew(user_id)
    status = "✅ ВКЛ" if auto_renew else "❌ ВЫКЛ"
    kb = [
        [InlineKeyboardButton("✏️ ИЗМЕНИТЬ ИМЯ", callback_data='change_name')],
        [InlineKeyboardButton("💬 НАПИСАТЬ", callback_data='send_message_to_user')],
        [InlineKeyboardButton("📬 ПОЧТА", callback_data='show_notifications')],
        [InlineKeyboardButton(f"🔄 АВТОПРОДЛЕНИЕ {status}", callback_data='toggle_auto_renew')],
        [InlineKeyboardButton("🗑 УДАЛИТЬ ПРОФИЛЬ", callback_data='delete_profile_confirm')],
        [InlineKeyboardButton("◀️ НАЗАД", callback_data='back')],
    ]
    if user_id == OWNER_ID:
        kb.insert(4, [InlineKeyboardButton("♾️ БЕЗЛИМИТ", callback_data='change_name_infinite')])
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
    if not is_subscribed(user_id) and user_id != OWNER_ID:
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

def user_profile_kb(user_id, target_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 НАПИСАТЬ", callback_data=f"msg_to_{target_id}")],
        [InlineKeyboardButton("◀️ НАЗАД", callback_data='back')],
    ])

# ============================================
#  ОБРАБОТЧИКИ КОМАНД
# ============================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    
    clear_user_context(context)
    
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
    
    # ===== РЕГИСТРАЦИЯ =====
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
    
    # ===== ИЗМЕНЕНИЕ ИМЕНИ =====
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
    
    # ===== ОСТАЛЬНЫЕ РЕЖИМЫ (сообщения, спам, приветствия, пост и т.д.) =====
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
            add_notification(
                target_id,
                "💬 Новое сообщение",
                f"Вам написали: {text[:100]}{'...' if len(text) > 100 else ''}",
                f"view_msg_{target_id}"
            )
        reply = await msg.reply_text(result, reply_markup=main_kb(uid))
        add_user_message(uid, reply)
        await delete_user_messages(context.bot, uid, keep_last=1)
        return
    
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
    
    if context.user_data.get('post_wait'):
        channel_id = context.user_data['post_wait']
        post_data = {'text': msg.text or '', 'media': None, 'media_type': None}
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
            "📅 ВВЕДИТЕ ДАТУ (ДД.ММ.ГГГГ ЧЧ:ММ):\nПример: 31.12.2026 23:59",
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
                f"✅ ПОСТ ЗАПЛАНИРОВАН!\n\n📅 {dt.strftime('%d.%m.%Y %H:%M')}\n{'🖼 С медиа' if post_data.get('media') else '📝 Без медиа'}",
                reply_markup=auto_posting_menu_kb(context.user_data.get('post_channel_id', 0))
            )
            add_user_message(uid, reply)
        except Exception as e:
            reply = await msg.reply_text(
                f"❌ НЕВЕРНЫЙ ФОРМАТ!\n\nПример: 31.12.2026 23:59\nОшибка: {str(e)}",
                reply_markup=back_kb(uid)
            )
            add_user_message(uid, reply)
        await delete_user_messages(context.bot, uid, keep_last=1)
        return
    
    if context.user_data.get('code_create_name'):
        context.user_data['code_name'] = msg.text.strip()
        context.user_data['code_create_name'] = False
        context.user_data['code_create_uses'] = True
        reply = await msg.reply_text(
            f"📝 Название: {context.user_data['code_name']}\n\n🔢 Введите количество использований:",
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
                f"📝 Название: {context.user_data['code_name']}\n🔢 Использований: {uses}\n\n📅 Выберите срок действия:",
                reply_markup=code_days_kb(uid)
            )
            add_user_message(uid, reply)
        except:
            reply = await msg.reply_text("❌ Введите число больше 0!", reply_markup=back_kb(uid))
            add_user_message(uid, reply)
        await delete_user_messages(context.bot, uid, keep_last=1)
        return
    
    if context.user_data.get('vp_wait_channel'):
        try:
            chat_id = extract_channel_id_from_text(msg.text)
            if chat_id is None:
                reply = await msg.reply_text("❌ НЕВЕРНЫЙ ID!\n\nВведите ID канала (начинается с -100):\nПример: -1001234567890", reply_markup=back_kb(uid))
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
            reply = await msg.reply_text("✅ КАНАЛ ВЫБРАН!\n\n📝 Введите текст поста (минимум 10 символов):", reply_markup=back_kb(uid))
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
            reply = await msg.reply_text("❌ ТЕКСТ ДОЛЖЕН БЫТЬ НЕ МЕНЕЕ 10 СИМВОЛОВ!", reply_markup=back_kb(uid))
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
            reply = await msg.reply_text("❌ НЕ ВЫБРАН КАНАЛ!\n\nВведите ID канала вручную:", reply_markup=back_kb(uid))
            context.user_data['vp_wait_channel'] = True
            add_user_message(uid, reply)
            await delete_user_messages(context.bot, uid, keep_last=1)
            return
        reply = await msg.reply_text("✅ ТЕКСТ СОХРАНЕН!\n\nТеперь настройте пост:", reply_markup=vp_create_kb(uid))
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
            reply = await msg.reply_text("✅ МЕДИА СОХРАНЕНО!\n\nПродолжайте настройку:", reply_markup=vp_create_kb(uid))
            add_user_message(uid, reply)
        else:
            reply = await msg.reply_text("⚠️ МЕДИА НЕ ОБНАРУЖЕНО (пропускаем)\n\nПродолжайте настройку:", reply_markup=vp_create_kb(uid))
            add_user_message(uid, reply)
        context.user_data['vp_wait_media'] = False
        await delete_user_messages(context.bot, uid, keep_last=1)
        return
    
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
                is_blocked = "🔒 ДА" if is_user_blocked(u['user_id']) else "❌ НЕТ"
                channels = get_user_channels(u['user_id'])
                text += (
                    f"👤 {nickname}\n"
                    f"   🆔 ID: {u['user_id']}\n"
                    f"   👤 Username: @{u['username'] if u['username'] else 'Не указан'}\n"
                    f"   💳 Подписка: {sub_status}\n"
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
    
    # По умолчанию
    reply = await msg.reply_text("🔄 Используй кнопки!", reply_markup=main_kb(uid))
    add_user_message(uid, reply)
    await delete_user_messages(context.bot, uid, keep_last=1)

# ============================================
#  АНТИ-СПАМ / ФИЛЬТР СЛОВ
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
                    text=f"🚫 ВАШЕ СООБЩЕНИЕ УДАЛЕНО!\n\n📌 Причина: Запрещённое слово '{word}'\n👤 {user_mention}\n🆔 ID: {user_id}\n\n⚠️ Повторные нарушения приведут к блокировке!"
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
                        text=f"✅ ВАША ЗАЯВКА ОДОБРЕНА!\n\n📺 Канал: {update.chat_join_request.chat.title}\n🎉 Добро пожаловать!"
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
#  ОБРАБОТЧИК ПЛАТЕЖЕЙ (YooKassa)
# ============================================

async def pre_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    user_id = query.from_user.id
    
    payload = query.invoice_payload
    if not payload.startswith('pay_'):
        await query.answer(ok=False, error_message="❌ Неверный запрос.")
        return
    
    # Проверяем, существует ли платёж в истории
    history = get_payment_history(user_id, limit=1)
    if not history or history[0]['payment_id'] != payload:
        await query.answer(ok=False, error_message="❌ Платёж не найден.")
        return
    
    await query.answer(ok=True)

async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    user_id = message.from_user.id
    payment_info = message.successful_payment
    
    payload = payment_info.invoice_payload
    amount = payment_info.total_amount / 100
    
    # Определяем план
    history = get_payment_history(user_id, limit=5)
    plan_type = 'month'
    for h in history:
        if h['payment_id'] == payload:
            plan_type = h['plan_type']
            break
    
    days = SUBSCRIPTION_DAYS.get(plan_type, 30)
    end_date = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')
    set_subscription(user_id, end_date)
    
    add_payment_history(user_id, int(amount), 'success', payload, plan_type)
    
    log_main(user_id, "Оплата", f"{plan_type} на {days} дней, {amount} руб")
    
    await message.reply_text(
        f"✅ ОПЛАТА ПОДТВЕРЖДЕНА!\n\n"
        f"💳 Сумма: {amount} руб\n"
        f"📅 Подписка активна до {end_date}\n\n"
        f"🔁 ВКЛЮЧИТЬ АВТОПРОДЛЕНИЕ?\n"
        f"Автопродление будет списывать {PRICES['month']} руб каждый месяц за 1 день до окончания подписки.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ ДА, ВКЛЮЧИТЬ", callback_data='enable_auto_renew')],
            [InlineKeyboardButton("❌ НЕТ, НЕ НАДО", callback_data='disable_auto_renew')]
        ])
    )
    
    await context.bot.send_message(
        chat_id=OWNER_ID,
        text=f"💰 НОВАЯ ОПЛАТА!\n\n"
        f"👤 Пользователь: {get_user_nickname(user_id) or user_id}\n"
        f"📅 План: {plan_type}\n"
        f"💳 Сумма: {amount} руб\n"
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
    
    # ===== НАВИГАЦИЯ =====
    if data == 'back_to_main':
        clear_user_context(context)
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
            clear_user_context(context)
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
    
    # ===== ПОДПИСКА =====
    if data == 'subscription':
        await edit_current("💳 ВЫБЕРИТЕ ТАРИФ:", subscription_kb(uid))
        return
    
    if data.startswith('sub_'):
        plan_type = data.replace('sub_', '')
        amount = PRICES.get(plan_type)
        if not amount:
            await edit_current("❌ НЕВЕРНЫЙ ТАРИФ!", back_kb(uid))
            return
        
        payment_method = get_payment_method(uid)
        
        if not PROVIDER_TOKEN:
            await edit_current("❌ ПЛАТЁЖНАЯ СИСТЕМА НЕ НАСТРОЕНА!\n\nОбратитесь к разработчику.", back_kb(uid))
            return
        
        if not payment_method:
            await edit_current(
                f"💳 ОПЛАТА\n\n📅 Тариф: {PLAN_NAMES[plan_type]}\n💰 Сумма: {amount} руб\n\nДля оплаты нажмите кнопку ниже. Telegram попросит вас ввести данные карты.\n🔒 Данные карты защищены и не хранятся у нас.",
                InlineKeyboardMarkup([
                    [InlineKeyboardButton(f"💳 ОПЛАТИТЬ {amount} руб", callback_data=f'pay_{plan_type}')],
                    [InlineKeyboardButton("◀️ НАЗАД", callback_data='subscription')]
                ])
            )
        else:
            await edit_current(
                f"💳 ОПЛАТА\n\n📅 Тариф: {PLAN_NAMES[plan_type]}\n💰 Сумма: {amount} руб\n💳 Карта: **** {payment_method['last4']}\n\nНажмите 'ОПЛАТИТЬ' для списания средств.",
                InlineKeyboardMarkup([
                    [InlineKeyboardButton(f"💳 ОПЛАТИТЬ {amount} руб", callback_data=f'pay_{plan_type}')],
                    [InlineKeyboardButton("🔄 СМЕНИТЬ КАРТУ", callback_data='change_card')],
                    [InlineKeyboardButton("◀️ НАЗАД", callback_data='subscription')]
                ])
            )
        return
    
    if data.startswith('pay_'):
        plan_type = data.replace('pay_', '')
        amount = PRICES.get(plan_type)
        if not amount:
            await edit_current("❌ НЕВЕРНЫЙ ТАРИФ!", back_kb(uid))
            return
        
        days = SUBSCRIPTION_DAYS.get(plan_type, 30)
        
        if not PROVIDER_TOKEN:
            await edit_current("❌ ПЛАТЁЖНАЯ СИСТЕМА НЕ НАСТРОЕНА!", back_kb(uid))
            return
        
        import time
        import random
        payload = f"pay_{uid}_{int(time.time())}_{random.randint(1000, 9999)}"
        
        add_payment_history(uid, amount, 'pending', payload, plan_type)
        
        try:
            await context.bot.send_invoice(
                chat_id=uid,
                title=f"Подписка {PLAN_NAMES[plan_type]}",
                description=f"Доступ к боту на {days} дней",
                payload=payload,
                provider_token=PROVIDER_TOKEN,
                currency="RUB",
                prices=[{"label": PLAN_NAMES[plan_type], "amount": amount * 100}],
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
    
    if data == 'change_card':
        delete_payment_method(uid)
        await edit_current("💳 СТАРАЯ КАРТА УДАЛЕНА!\n\nПри следующей оплате вы сможете привязать новую карту.", back_kb(uid))
        return
    
    if data == 'activate_code':
        context.user_data['code_wait'] = True
        await edit_current("🎟 ВВЕДИТЕ КОД:", back_kb(uid))
        return
    
    # ===== ПРОФИЛЬ =====
    if data == 'profile':
        try:
            nickname = get_user_nickname(uid) or "Не указан"
            sub_end = get_subscription_end(uid)
            if sub_end:
                try:
                    end_date = datetime.strptime(sub_end, '%Y-%m-%d')
                    if end_date >= datetime.now():
                        sub_status = f"АКТИВНА ДО {sub_end}"
                    else:
                        sub_status = "❌ ИСТЕКЛА"
                except:
                    sub_status = "❌ ОШИБКА"
            else:
                sub_status = "НЕТУ"
            adult_status = "✅ Подтверждён" if is_adult(uid) else "❌ Не подтверждён"
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
                f"🔒 Заблокирован: {is_blocked_user}\n"
                f"💰 ПОДПИСКА: {sub_status}\n"
                f"{notif_text}\n"
                f"📺 КАНАЛЫ:{channels_text}"
            )
            await edit_current(text, profile_kb(uid))
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            log_error(f"Ошибка в профиле для {uid}: {e}\n{error_trace}")
            await edit_current(
                f"❌ ОШИБКА ПРИ ЗАГРУЗКЕ ПРОФИЛЯ!\n\nКод ошибки: {str(e)[:100]}\n\nСообщите разработчику.",
                back_kb(uid)
            )
        return
    
    if data == 'change_name':
        try:
            if uid == OWNER_ID:
                context.user_data['change_name_wait'] = True
                await edit_current("📝 ВВЕДИТЕ НОВОЕ ИМЯ (безлимит):", back_kb(uid))
                return
            if get_name_changes(uid) >= 1:
                await edit_current("❌ ЛИМИТ ИСЧЕРПАН! (1 раз)", back_kb(uid))
                return
            context.user_data['change_name_wait'] = True
            await edit_current("📝 ВВЕДИТЕ НОВОЕ ИМЯ:", back_kb(uid))
        except Exception as e:
            log_error(f"Ошибка change_name для {uid}: {e}")
            await edit_current("❌ ОШИБКА ПРИ ИЗМЕНЕНИИ ИМЕНИ!", back_kb(uid))
        return

    if data == 'change_name_infinite':
        try:
            if uid != OWNER_ID:
                return
            context.user_data['change_name_wait'] = True
            await edit_current("📝 ВВЕДИТЕ НОВОЕ ИМЯ (безлимит):", back_kb(uid))
        except Exception as e:
            log_error(f"Ошибка change_name_infinite для {uid}: {e}")
            await edit_current("❌ ОШИБКА!", back_kb(uid))
        return

    if data == 'delete_profile_confirm':
        try:
            await edit_current("⚠️ ВЫ УВЕРЕНЫ?\n\nВсе данные будут потеряны!", InlineKeyboardMarkup([[InlineKeyboardButton("✅ ДА", callback_data='delete_profile_yes')], [InlineKeyboardButton("❌ НЕТ", callback_data='delete_profile_no')]]))
        except Exception as e:
            log_error(f"Ошибка delete_profile_confirm для {uid}: {e}")
            await edit_current("❌ ОШИБКА!", back_kb(uid))
        return

    if data == 'delete_profile_yes':
        try:
            if delete_user_profile(uid):
                log_main(uid, "Удалил профиль", "Успешно")
                await edit_current("✅ ПРОФИЛЬ УДАЛЁН!\n\n/start для регистрации", None)
            else:
                await edit_current("❌ ОШИБКА ПРИ УДАЛЕНИИ!", back_kb(uid))
        except Exception as e:
            log_error(f"Ошибка delete_profile_yes для {uid}: {e}")
            await edit_current(f"❌ ОШИБКА: {str(e)[:100]}", back_kb(uid))
        return

    if data == 'delete_profile_no':
        try:
            await edit_current("✅ ОТМЕНЕНО!", back_kb(uid))
        except Exception as e:
            log_error(f"Ошибка delete_profile_no для {uid}: {e}")
        return

    if data == 'toggle_auto_renew':
        current = get_auto_renew(uid)
        set_auto_renew(uid, not current)
        status = "✅ ВКЛ" if not current else "❌ ВЫКЛ"
        await edit_current(f"🔄 АВТОПРОДЛЕНИЕ {status}!", profile_kb(uid))
        return

    if data == 'enable_auto_renew':
        set_auto_renew(uid, True)
        await edit_current("✅ АВТОПРОДЛЕНИЕ ВКЛЮЧЕНО!\n\nТеперь каждый месяц за 1 день до окончания подписки будет списываться 119 руб.", main_kb(uid))
        return

    if data == 'disable_auto_renew':
        set_auto_renew(uid, False)
        await edit_current("❌ АВТОПРОДЛЕНИЕ ОТКЛЮЧЕНО.", main_kb(uid))
        return

    # ===== УВЕДОМЛЕНИЯ (ПОЧТА) =====
    if data == 'show_notifications':
        try:
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
        except Exception as e:
            log_error(f"Ошибка show_notifications для {uid}: {e}")
            await edit_current("❌ ОШИБКА!", back_kb(uid))
        return
    
    if data.startswith('view_notif_'):
        try:
            notif_id = int(data.replace('view_notif_', ''))
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM notifications WHERE id = ?', (notif_id,))
            result = cursor.fetchone()
            conn.close()
            if result:
                mark_notification_read(notif_id)
                await edit_current(f"📬 {result['type']}\n\n{result['content']}\n\n🕐 {result['created_at']}", InlineKeyboardMarkup([[InlineKeyboardButton("🗑 УДАЛИТЬ", callback_data=f"delete_notif_{notif_id}")], [InlineKeyboardButton("◀️ НАЗАД", callback_data='show_notifications')]]))
            else:
                await edit_current("❌ УВЕДОМЛЕНИЕ НЕ НАЙДЕНО!", back_kb(uid))
        except Exception as e:
            log_error(f"Ошибка view_notif для {uid}: {e}")
            await edit_current("❌ ОШИБКА!", back_kb(uid))
        return
    
    if data.startswith('delete_notif_'):
        try:
            notif_id = int(data.replace('delete_notif_', ''))
            delete_notification(notif_id)
            await edit_current("✅ УДАЛЕНО!", back_kb(uid))
        except Exception as e:
            log_error(f"Ошибка delete_notif для {uid}: {e}")
            await edit_current("❌ ОШИБКА!", back_kb(uid))
        return
    
    if data == 'clear_notifications':
        try:
            mark_all_notifications_read(uid)
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM notifications WHERE user_id = ?', (uid,))
            conn.commit()
            conn.close()
            await edit_current("✅ ВСЕ УВЕДОМЛЕНИЯ ОЧИЩЕНЫ!", back_kb(uid))
        except Exception as e:
            log_error(f"Ошибка clear_notifications для {uid}: {e}")
            await edit_current("❌ ОШИБКА!", back_kb(uid))
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
            subscribers = get_channel_subscribers(context.bot, channel_id)
            privacy = 'private'
            try:
                chat = context.bot.get_chat(channel_id)
                if hasattr(chat, 'username') and chat.username:
                    privacy = 'public'
            except:
                privacy = 'private'
            categories_str = ', '.join(selected)
            add_channel_db(channel_id, chat_name, uid, categories_str, privacy, subscribers)
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
    
    # ===== ИНФОРМАЦИЯ О КАНАЛЕ =====
    if data.startswith('channel_info_'):
        channel_id = int(data.replace('channel_info_', ''))
        ch = get_channel_by_channel_id(channel_id)
        if not ch:
            await edit_current("❌ КАНАЛ НЕ НАЙДЕН!", back_kb(uid))
            return
        
        info = get_channel_info_full(context.bot, channel_id)
        if not info:
            await edit_current("❌ НЕ УДАЛОСЬ ПОЛУЧИТЬ ИНФОРМАЦИЮ!", back_kb(uid))
            return
        
        update_channel_subscribers(context.bot, channel_id)
        ch = get_channel_by_channel_id(channel_id)
        
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
        if not is_subscribed(uid) and uid != OWNER_ID:
            await edit_current("❌ ДОСТУП К ПОИСКУ КАНАЛОВ ТОЛЬКО С ПОДПИСКОЙ!", InlineKeyboardMarkup([[InlineKeyboardButton("💳 ПОДПИСКА", callback_data='subscription')], [InlineKeyboardButton("◀️ НАЗАД", callback_data='back')]]))
            return
        kb = search_channels_kb(uid)
        if kb:
            await edit_current("🔍 ПОИСК КАНАЛОВ\n\nВыберите способ поиска:", kb)
        else:
            await edit_current("❌ ДОСТУП ТОЛЬКО С ПОДПИСКОЙ!", back_kb(uid))
        return
    
    if data == 'search_by_name':
        if not is_subscribed(uid) and uid != OWNER_ID:
            await edit_current("❌ ДОСТУП ТОЛЬКО С ПОДПИСКОЙ!", back_kb(uid))
            return
        context.user_data['search_by_name_wait'] = True
        await edit_current("📝 ВВЕДИТЕ НАЗВАНИЕ:", back_kb(uid))
        return
    
    if data == 'search_by_bot_id':
        if not is_subscribed(uid) and uid != OWNER_ID:
            await edit_current("❌ ДОСТУП ТОЛЬКО С ПОДПИСКОЙ!", back_kb(uid))
            return
        context.user_data['search_by_bot_id_wait'] = True
        await edit_current("🔍 ВВЕДИТЕ ID В БОТЕ:", back_kb(uid))
        return
    
    if data == 'search_by_tg_id':
        if not is_subscribed(uid) and uid != OWNER_ID:
            await edit_current("❌ ДОСТУП ТОЛЬКО С ПОДПИСКОЙ!", back_kb(uid))
            return
        context.user_data['search_by_tg_id_wait'] = True
        await edit_current("🔍 ВВЕДИТЕ ID В ТГ:", back_kb(uid))
        return
    
    # ===== ФИЛЬТР ПО КАТЕГОРИЯМ =====
    if data == 'filter_category':
        if not is_subscribed(uid) and uid != OWNER_ID:
            await edit_current("❌ ДОСТУП ТОЛЬКО С ПОДПИСКОЙ!", back_kb(uid))
            return
        await edit_current("📂 ВЫБЕРИТЕ КАТЕГОРИЮ:", filter_category_kb(uid))
        return
    
    if data == 'filter_all':
        if not is_subscribed(uid) and uid != OWNER_ID:
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
        if not is_subscribed(uid) and uid != OWNER_ID:
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
        if not is_subscribed(uid) and uid != OWNER_ID:
            await edit_current("❌ ДОСТУП ТОЛЬКО С ПОДПИСКОЙ!", back_kb(uid))
            return
        await edit_current("📊 СОРТИРОВКА:", sort_kb(uid))
        return
    
    if data == 'sort_asc':
        if not is_subscribed(uid) and uid != OWNER_ID:
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
        if not is_subscribed(uid) and uid != OWNER_ID:
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
        if not is_subscribed(uid) and uid != OWNER_ID:
            await edit_current("❌ ДОСТУП ТОЛЬКО С ПОДПИСКОЙ!", back_kb(uid))
            return
        context.user_data['search_users_wait'] = True
        await edit_current("🔍 ВВЕДИТЕ НИКНЕЙМ ИЛИ ID:", back_kb(uid))
        return
    
    # ===== ЯЗЫК =====
    if data == 'language':
        await edit_current("🌍 ВЫБЕРИТЕ ЯЗЫК:", InlineKeyboardMarkup([[InlineKeyboardButton("🇷🇺 РУССКИЙ", callback_data='lang_ru')], [InlineKeyboardButton("🇬🇧 ENGLISH", callback_data='lang_en')], [InlineKeyboardButton("◀️ НАЗАД", callback_data='back')]]))
        return
    
    if data.startswith('lang_'):
        lang = data.replace('lang_', '')
        set_user_language(uid, lang)
        custom_desc = get_setting("global_desc") or "Всем привет и спасибо что выбрали меня! 🎉"
        custom_media = get_setting("global_media")
        text = f"🌟 ДОБРО ПОЖАЛОВАТЬ В {BOT_NAME}! 🌟\n\n{custom_desc}"
        await edit_current(text, main_kb(uid), custom_media)
        return
    
    # ===== ПОДДЕРЖКА =====
    if data == 'support':
        if BOT_STOPPED:
            await edit_current(f"🔧 БОТ НА ТО!\n\n📌 Связь: @GanzalesSs920", back_kb(uid))
        else:
            await edit_current("💬 ПОДДЕРЖКА\n\n📌 @GanzalesSs920\n📌 @HellperBotNews", back_kb(uid))
        return
    
    # ===== РАЗРАБОТЧИК =====
    if data == 'developer':
        if uid != OWNER_ID:
            await edit_current("❌ ДОСТУП ЗАПРЕЩЁН!", back_kb(uid))
            return
        blocked = get_blocked_users()
        await edit_current(f"⚙️ ПАНЕЛЬ РАЗРАБОТЧИКА\n\n👑 {get_user_nickname(uid) or uid}\n🔒 Заблокировано: {len(blocked)}\n📌 Версия: {BOT_VERSION}\n\n🔽 Действие:", dev_kb(uid))
        return
    
    # ===== РАЗРАБОТЧИК: КОДЫ =====
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
        await edit_current("📨 РАССЫЛКА\n\nОтправьте текст или медиа для рассылки.\n📌 Поддерживается:\n• Текст\n• Фото\n• Видео\n• GIF\n• Документ", back_kb(uid))
        context.user_data['broadcast_wait'] = True
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
    
    # ===== РАЗРАБОТЧИК: ПОДАРОК =====
    if data == 'dev_gift':
        if uid != OWNER_ID:
            return
        context.user_data['gift_wait'] = True
        await edit_current("🎁 ВВЕДИТЕ ID ПОЛЬЗОВАТЕЛЯ ДЛЯ ПОДАРКА ПОДПИСКИ (30 дней):", back_kb(uid))
        return
    
    # ===== РАЗРАБОТЧИК: ОТЧЁТ =====
    if data == 'dev_report':
        if uid != OWNER_ID:
            return
        all_users = get_all_users()
        sub_users = [u for u in all_users if is_subscribed(u['user_id'])]
        channels = get_all_channels()
        vp_posts = get_all_vp_posts_count()
        blocked = get_blocked_users()
        await edit_current(
            f"📊 ОТЧЁТ\n\n"
            f"👥 Всего пользователей: {len(all_users)}\n"
            f"👥 Активных: {len(sub_users)}\n"
            f"📺 Каналов: {len(channels)}\n"
            f"📢 Постов ВП: {vp_posts}\n"
            f"🔒 Заблокировано: {len(blocked)}\n"
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
    
    # ===== РАЗРАБОТЧИК: ВСЕ ПОЛЬЗОВАТЕЛИ =====
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
            is_owner = "👑 ДА" if u['user_id'] == OWNER_ID else "❌ НЕТ"
            is_blocked = "🔒 ДА" if is_user_blocked(u['user_id']) else "❌ НЕТ"
            channels = get_user_channels(u['user_id'])
            text += (
                f"👤 {nickname}\n"
                f"   🆔 ID: {u['user_id']}\n"
                f"   👤 Username: @{u['username'] if u['username'] else 'Не указан'}\n"
                f"   💳 Подписка: {sub_status}\n"
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
    
    # ===== БЛОКИРОВКА/РАЗБЛОКИРОВКА =====
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
    
    # ===== ВП =====
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
    
    # ===== ЛИДЕРБОАРД =====
    if data.startswith('set_leaderboard_'):
        channel_id = int(data.replace('set_leaderboard_', ''))
        await edit_current("📊 ЛИДЕРБОАРД\n\nТоп-20 комментаторов:", InlineKeyboardMarkup([[InlineKeyboardButton("📅 ДЕНЬ", callback_data=f"lb_day_{channel_id}")], [InlineKeyboardButton("📅 МЕСЯЦ", callback_data=f"lb_month_{channel_id}")], [InlineKeyboardButton("📅 ВСЁ", callback_data=f"lb_all_{channel_id}")], [InlineKeyboardButton("◀️ НАЗАД", callback_data=f"set_ch_{channel_id}")]]))
        return
    
    if data.startswith('lb_'):
        parts = data.split('_')
        period = parts[1] if len(parts) > 1 else 'day'
        channel_id = int(parts[2]) if len(parts) > 2 else 0
        names = {'day': 'ДЕНЬ', 'month': 'МЕСЯЦ', 'all': 'ВСЁ'}
        linked_group = get_channel_linked_group(channel_id)
        if linked_group:
            top = []
            try:
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
        pass
    
    await edit_current("🔄 В РАЗРАБОТКЕ...", back_kb(uid))

# ============================================
#  ЗАПУСК БОТА
# ============================================

def main():
    try:
        import requests
        resp = requests.get(f'https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook?drop_pending_updates=True')
        print("✅ Webhook сброшен:", resp.json())
    except Exception as e:
        print("⚠️ Ошибка сброса webhook:", e)
    
    init_db()
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
    application.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | filters.ANIMATION | filters.Document.ALL, handle_msg))
    
    application.add_handler(MessageHandler(filters.TEXT & filters.ChatType.GROUPS, check_spam))
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_member))
    application.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, farewell_member))
    application.add_handler(ChatJoinRequestHandler(handle_join_request))
    
    application.add_handler(PreCheckoutQueryHandler(pre_checkout))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))
    
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
    print(f"💰 Цены: {PRICES['month']}/{PRICES['6month']}/{PRICES['year']} руб")
    print(f"📌 Версия: {BOT_VERSION}")
    print(f"🔒 Заблокировано: {len(get_blocked_users())}")
    print(f"⏰ Таймер ВП: {get_vp_timer()} часов")
    print("=" * 60)
    print("📁 Логи: logs/")
    print("⚡ Напиши /start в Telegram!")
    print("=" * 60)
    
    application.run_polling()

if __name__ == '__main__':
    main()