import os
import sys
import asyncio
import threading
import json
import random
import string
import logging
from datetime import datetime, timedelta, timezone

from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
    ChatMemberHandler,
)
from telegram.constants import ChatType

import pytz
from telegram_bot_calendar import DetailedTelegramCalendar

# ============ ЛОКАЛЬНЫЕ ИМПОРТЫ ============
from config import (
    BOT_TOKEN, OWNER_ID, PORT, USE_WEBHOOK, WEBHOOK_URL,
    PRICES, PRICES_RUB, PLAN_NAMES, SUBSCRIPTION_DAYS,
    TIMEZONES, CARD_NUMBER, logger as cfg_logger
)
from db import (
    init_db, create_user, get_user, is_registered, set_registered,
    is_adult, set_adult, get_user_nickname, set_user_nickname,
    is_nickname_taken, get_user_timezone, set_user_timezone,
    get_user_language, set_user_language,
    get_subscription_end, extend_subscription, is_subscribed,
    add_payment_history, add_pending_payment, get_pending_payment, update_pending_payment_status,
    get_channel_by_channel_id, add_channel_db, del_channel_db, get_user_channels,
    get_all_channels, get_channel_privacy, set_channel_privacy,
    set_welcome_text, get_welcome_text, set_farewell_text, get_farewell_text,
    set_auto_approve, get_auto_approve,
    set_captcha_settings, get_captcha_settings, del_captcha_settings,
    add_blacklist_word, get_blacklist_words, del_blacklist_word,
    add_scheduled_post, get_scheduled_posts, del_scheduled_post, mark_post_sent, get_due_scheduled_posts,
    create_promo_code, get_promo_code, use_promo_code, get_all_promo_codes, del_promo_code,
    add_comment_stat, get_top_commenters, get_channel_stats,
    add_crosspost_target, remove_crosspost_target, get_crosspost_targets,
    create_giveaway, get_active_giveaways, get_giveaway, close_giveaway,
    add_giveaway_participant, get_giveaway_participants,
    get_blocked_users, block_user, unblock_user, is_user_blocked,
    add_notification, get_user_notifications, mark_all_notifications_read,
    get_all_users, get_all_users_with_sub, get_all_users_without_sub,
    is_bot_admin, add_bot_admin, remove_bot_admin,
    get_setting, set_setting,
    update_channel_subscribers_db, add_subscribers_snapshot,
    set_channel_linked_group_db, get_channel_by_linked_group,
    cleanup_old_data,
)

# ============ ЛОГИРОВАНИЕ ============
logger = logging.getLogger(__name__)

# ============ ЗАГРУЗКА ЯЗЫКА ============
def get_lang(user_id):
    lang = get_user_language(user_id)
    if lang == 'en':
        from en import LANGUAGE
    else:
        from ru import LANGUAGE
    return LANGUAGE

def t(user_id, key, **kwargs):
    """Получить перевод."""
    text = get_lang(user_id).get(key, key)
    if kwargs:
        try:
            text = text.format(**kwargs)
        except Exception:
            pass
    return text

# ============ СОСТОЯНИЯ ConversationHandler ============
(
    REG_NAME, REG_AGE, REG_TZ,
    POST_TEXT, POST_MEDIA, POST_TIME, POST_DATE,
    CODE_ENTER,
    BROADCAST_TEXT,
    SEARCH_QUERY,
    CHANNEL_ID_ENTER, CHANNEL_LINK_ENTER, CHANNEL_CAT_ENTER,
    GIVEAWAY_TITLE, GIVEAWAY_WINNERS,
    PAYMENT_SCREENSHOT,
    ADMIN_GIFT_ID, ADMIN_GIFT_PLAN,
    DEV_MAKE_ADMIN, DEV_REMOVE_ADMIN,
    SETTINGS_NAME,
) = range(20)

# ============ ГЛОБАЛЬНЫЕ ============
application = None
bot_loop = None

# ============ ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ============

def is_owner(user_id):
    return user_id == OWNER_ID

def is_admin(user_id):
    return is_owner(user_id) or is_bot_admin(user_id)

async def check_blocked(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """True если пользователь заблокирован и сообщение обработано."""
    uid = update.effective_user.id
    if is_user_blocked(uid):
        lang = get_lang(uid)
        text = lang.get('blocked', '❌ ВАШ АККАУНТ ЗАБЛОКИРОВАН!')
        if update.message:
            await update.message.reply_text(text)
        elif update.callback_query:
            await update.callback_query.answer(text, show_alert=True)
        return True
    return False

async def check_maintenance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """True если бот на ТО и сообщение обработано."""
    uid = update.effective_user.id
    if is_owner(uid):
        return False
    if get_setting('maintenance') == '1':
        lang = get_lang(uid)
        text = lang.get('bot_stopped', '🔧 БОТ ЗАКРЫТ НА ТЕХНИЧЕСКОЕ ОБСЛУЖИВАНИЕ!')
        if update.message:
            await update.message.reply_text(text)
        elif update.callback_query:
            await update.callback_query.answer(text, show_alert=True)
        return True
    return False

def ensure_user(user_id, username):
    """Создать пользователя если его нет."""
    create_user(user_id, username)

# ============ КЛАВИАТУРЫ ============

def main_menu_keyboard(user_id):
    """Главное меню inline."""
    lang = get_lang(user_id)
    kb = [
        [InlineKeyboardButton(lang['profile'], callback_data='menu_profile'),
         InlineKeyboardButton(lang['subscription'], callback_data='menu_sub')],
        [InlineKeyboardButton(lang['connect_channel'], callback_data='menu_connect'),
         InlineKeyboardButton(lang['channel_settings'], callback_data='menu_ch_settings')],
        [InlineKeyboardButton(lang['search_channels'], callback_data='menu_search_ch'),
         InlineKeyboardButton(lang['search_users'], callback_data='menu_search_u')],
        [InlineKeyboardButton(lang['language'], callback_data='menu_lang'),
         InlineKeyboardButton(lang['support'], callback_data='menu_support')],
        [InlineKeyboardButton(lang['customize'], callback_data='menu_custom')],
    ]
    if is_admin(user_id):
        kb.append([InlineKeyboardButton(lang['developer'], callback_data='menu_dev')])
    return InlineKeyboardMarkup(kb)

def dev_menu_keyboard(user_id):
    lang = get_lang(user_id)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(lang['create_code'], callback_data='dev_create_code')],
        [InlineKeyboardButton(lang['active_codes'], callback_data='dev_codes')],
        [InlineKeyboardButton(lang['broadcast'], callback_data='dev_broadcast')],
        [InlineKeyboardButton(lang['maintenance'], callback_data='dev_maintenance')],
        [InlineKeyboardButton(lang['gift_subscription'], callback_data='dev_gift')],
        [InlineKeyboardButton(lang['payment_report'], callback_data='dev_report')],
        [InlineKeyboardButton(lang['make_admin'], callback_data='dev_make_admin')],
        [InlineKeyboardButton(lang['back'], callback_data='back_main')],
    ])

def sub_menu_keyboard(user_id):
    lang = get_lang(user_id)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(lang['monthly'].format(price=PRICES['month']), callback_data='sub_month')],
        [InlineKeyboardButton(lang['half_year'].format(price=PRICES['6month']), callback_data='sub_6month')],
        [InlineKeyboardButton(lang['yearly'].format(price=PRICES['year']), callback_data='sub_year')],
        [InlineKeyboardButton(lang['pay_stars'], callback_data='sub_pay_stars')],
        [InlineKeyboardButton(lang['pay_card'], callback_data='sub_pay_card')],
        [InlineKeyboardButton(lang['activate_code'], callback_data='sub_code')],
        [InlineKeyboardButton(lang['back'], callback_data='back_main')],
    ])

def back_keyboard(user_id, data='back_main'):
    lang = get_lang(user_id)
    return InlineKeyboardMarkup([[InlineKeyboardButton(lang['back'], callback_data=data)]])

# ============ ХЕНДЛЕРЫ: РЕГИСТРАЦИЯ ============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    username = update.effective_user.username or str(uid)
    ensure_user(uid, username)

    if await check_blocked(update, context):
        return ConversationHandler.END
    if await check_maintenance(update, context):
        return ConversationHandler.END

    if is_registered(uid):
        lang = get_lang(uid)
        await update.message.reply_text(
            lang['main_description'],
            reply_markup=main_menu_keyboard(uid)
        )
        return ConversationHandler.END
    else:
        lang = get_lang(uid)
        await update.message.reply_text(lang['enter_name'])
        return REG_NAME

async def reg_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    name = update.message.text.strip()
    lang = get_lang(uid)

    if len(name) < 2:
        await update.message.reply_text("❌ Минимум 2 символа!")
        return REG_NAME
    if not all(c.isalnum() or c == '_' for c in name):
        await update.message.reply_text("❌ Только буквы, цифры и _!")
        return REG_NAME
    if is_nickname_taken(name):
        await update.message.reply_text("❌ Имя занято!")
        return REG_NAME

    context.user_data['reg_name'] = name
    await update.message.reply_text(lang['enter_age'], reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton(lang['yes'], callback_data='age_yes'),
         InlineKeyboardButton(lang['no'], callback_data='age_no')]
    ]))
    return REG_AGE

async def reg_age_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    lang = get_lang(uid)

    if query.data == 'age_no':
        await query.edit_message_text("🔞 Доступ запрещён.")
        return ConversationHandler.END

    set_adult(uid, True)

    buttons = [[InlineKeyboardButton(label, callback_data=f"tz_{tz}")] for tz, label in TIMEZONES]
    await query.edit_message_text(lang['enter_timezone'], reply_markup=InlineKeyboardMarkup(buttons))
    return REG_TZ

async def reg_tz_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    tz = query.data.replace("tz_", "")
    lang = get_lang(uid)

    set_user_timezone(uid, tz)
    name = context.user_data.get('reg_name', 'User')
    set_user_nickname(uid, name)
    set_registered(uid)

    adult_text = "18+ ✅" if is_adult(uid) else "18+ ❌"
    await query.edit_message_text(
        lang['registration_done'].format(name=name, uid=uid, adult=adult_text)
    )
    await context.bot.send_message(
        uid,
        lang['main_description'],
        reply_markup=main_menu_keyboard(uid)
    )
    return ConversationHandler.END

# ============ ХЕНДЛЕРЫ: МЕНЮ И CALLBACKS ============

async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    lang = get_lang(uid)
    data = query.data

    if data == 'menu_profile':
        nick = get_user_nickname(uid) or "—"
        tz = get_user_timezone(uid)
        adult = "18+ ✅" if is_adult(uid) else "18+ ❌"
        sub_end = get_subscription_end(uid)
        sub_text = lang['subscription_active'].format(date=sub_end) if sub_end and is_subscribed(uid) else lang['subscription_none']
        blocked = "❌" if is_user_blocked(uid) else "✅"
        ch_count = len(get_user_channels(uid))
        notif_count = len(get_user_notifications(uid))

        text = lang['profile_text'].format(
            nickname=nick, uid=uid, tz=tz, adult=adult,
            blocked=blocked, sub=sub_text, notif=notif_count, ch_count=ch_count
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ " + lang['enter_new_name'], callback_data='profile_edit_name')],
            [InlineKeyboardButton("🗑 Удалить профиль", callback_data='profile_delete')],
            [InlineKeyboardButton(lang['back'], callback_data='back_main')],
        ])
        await query.edit_message_text(text, reply_markup=kb)

    elif data == 'menu_sub':
        await query.edit_message_text(lang['subscription'], reply_markup=sub_menu_keyboard(uid))

    elif data == 'menu_connect':
        if not is_subscribed(uid):
            await query.edit_message_text(lang['need_subscription'], reply_markup=back_keyboard(uid))
            return
        await query.edit_message_text(
            lang['enter_channel_id'] + "\n\n" + lang['forward_post'],
            reply_markup=back_keyboard(uid)
        )
        context.user_data['awaiting'] = 'channel_id'

    elif data == 'menu_ch_settings':
        channels = get_user_channels(uid)
        if not channels:
            await query.edit_message_text(lang['no_channels'], reply_markup=back_keyboard(uid))
            return
        buttons = [[InlineKeyboardButton(ch['channel_name'] or str(ch['channel_id']), callback_data=f"chset_{ch['channel_id']}")] for ch in channels]
        buttons.append([InlineKeyboardButton(lang['back'], callback_data='back_main')])
        await query.edit_message_text(lang['select_channel'], reply_markup=InlineKeyboardMarkup(buttons))

    elif data == 'menu_search_ch':
        await query.edit_message_text(lang['enter_search_query'], reply_markup=back_keyboard(uid))
        context.user_data['awaiting'] = 'search_channels'

    elif data == 'menu_search_u':
        await query.edit_message_text(lang['enter_search_query'], reply_markup=back_keyboard(uid))
        context.user_data['awaiting'] = 'search_users'

    elif data == 'menu_lang':
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🇷🇺 Русский", callback_data='lang_ru'),
             InlineKeyboardButton("🇬🇧 English", callback_data='lang_en')],
            [InlineKeyboardButton(lang['back'], callback_data='back_main')],
        ])
        await query.edit_message_text("🌍 Выберите язык / Select language:", reply_markup=kb)

    elif data == 'menu_support':
        await query.edit_message_text(f"{lang['support_contact']}\n\n{lang['support']}", reply_markup=back_keyboard(uid))

    elif data == 'menu_custom':
        await query.edit_message_text("🎨 Кастомизация (скоро)", reply_markup=back_keyboard(uid))

    elif data == 'back_main':
        await query.edit_message_text(lang['main_description'], reply_markup=main_menu_keyboard(uid))

    # ==== ЯЗЫК ====
    elif data == 'lang_ru':
        set_user_language(uid, 'ru')
        await query.edit_message_text("✅ Язык: Русский", reply_markup=main_menu_keyboard(uid))
    elif data == 'lang_en':
        set_user_language(uid, 'en')
        await query.edit_message_text("✅ Language: English", reply_markup=main_menu_keyboard(uid))

    # ==== ПОДПИСКА ====
    elif data.startswith('sub_'):
        if data == 'sub_pay_stars':
            await query.edit_message_text("⭐ Выберите тариф:", reply_markup=sub_menu_keyboard(uid))
        elif data == 'sub_pay_card':
            await query.edit_message_text("💳 Выберите тариф:", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(lang['monthly_rub'].format(price=PRICES_RUB['month']), callback_data='card_month')],
                [InlineKeyboardButton(lang['half_year_rub'].format(price=PRICES_RUB['6month']), callback_data='card_6month')],
                [InlineKeyboardButton(lang['yearly_rub'].format(price=PRICES_RUB['year']), callback_data='card_year')],
                [InlineKeyboardButton(lang['back'], callback_data='menu_sub')],
            ]))
        elif data == 'sub_code':
            await query.edit_message_text(lang['enter_code'])
            context.user_data['awaiting'] = 'promo_code'
        else:
            plan = data.replace("sub_", "")
            if plan in PRICES:
                await query.edit_message_text(f"Оплата {PLAN_NAMES[plan]} — {PRICES[plan]} ⭐\n(Реализация через sendInvoice)", reply_markup=back_keyboard(uid))

    elif data.startswith('card_'):
        plan = data.replace("card_", "")
        if plan in PRICES_RUB and CARD_NUMBER:
            amount = PRICES_RUB[plan]
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            pid = add_pending_payment(uid, plan, amount)
            text = lang['pay_instruction'].format(amount=amount, card=CARD_NUMBER, code=code)
            await query.edit_message_text(text, parse_mode='Markdown')
            nick = get_user_nickname(uid) or str(uid)
            await context.bot.send_message(
                OWNER_ID,
                lang['pay_pending_notify'].format(nickname=nick, uid=uid, plan=PLAN_NAMES[plan], amount=amount, code=code)
            )
        else:
            await query.edit_message_text("❌ Оплата картой недоступна.", reply_markup=back_keyboard(uid))

    # ==== DEV ПАНЕЛЬ ====
    elif data == 'menu_dev' or data == 'dev_panel':
        if not is_admin(uid):
            await query.answer(lang['no_access'], show_alert=True)
            return
        await query.edit_message_text(lang['developer_panel'], reply_markup=dev_menu_keyboard(uid))

    elif data == 'dev_maintenance':
        current = get_setting('maintenance') == '1'
        set_setting('maintenance', '0' if current else '1')
        status = lang['maintenance_off'] if current else lang['maintenance_on']
        await query.edit_message_text(status, reply_markup=dev_menu_keyboard(uid))

    elif data == 'dev_report':
        total = len(get_all_users())
        subs = len(get_all_users_with_sub())
        chs = len(get_all_channels())
        blocked = len(get_blocked_users())
        text = lang['report_text'].format(users=total, subs=subs, channels=chs, blocked=blocked)
        await query.edit_message_text(text, reply_markup=dev_menu_keyboard(uid))

    elif data == 'dev_broadcast':
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(lang['broadcast_all'], callback_data='bc_all')],
            [InlineKeyboardButton(lang['broadcast_subs'], callback_data='bc_subs')],
            [InlineKeyboardButton(lang['broadcast_no_subs'], callback_data='bc_nosubs')],
            [InlineKeyboardButton(lang['back'], callback_data='dev_panel')],
        ])
        await query.edit_message_text("📨 Выберите аудиторию:", reply_markup=kb)

    elif data.startswith('bc_'):
        context.user_data['bc_target'] = data
        await query.edit_message_text(lang['enter_message_text'])
        context.user_data['awaiting'] = 'broadcast'

    elif data == 'dev_codes':
        codes = get_all_promo_codes()
        if not codes:
            text = "📋 Нет активных кодов."
        else:
            text = "📋 Активные коды:\n\n"
            for c in codes:
                text += f"🎟 {c['code']} — {c['name']} ({c['uses']}/{c['max_uses']})\n"
        await query.edit_message_text(text, reply_markup=dev_menu_keyboard(uid))

    elif data == 'dev_create_code':
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
        create_promo_code(code, "Promo", 10, 30)
        await query.edit_message_text(lang['code_created'].format(name="Promo", code=code, uses=10, days=30), reply_markup=dev_menu_keyboard(uid))

    elif data == 'dev_gift':
        await query.edit_message_text(lang['enter_target_id'])
        context.user_data['awaiting'] = 'gift_id'

    elif data == 'dev_make_admin':
        await query.edit_message_text("📝 Введите ID пользователя для назначения админом:")
        context.user_data['awaiting'] = 'make_admin'

    # ==== НАСТРОЙКИ КАНАЛА ====
    elif data.startswith('chset_'):
        ch_id = int(data.replace("chset_", ""))
        channel = get_channel_by_channel_id(ch_id)
        if not channel or channel['owner_id'] != uid:
            await query.answer("❌ Нет доступа!", show_alert=True)
            return
        context.user_data['current_channel'] = ch_id
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(lang['welcome'], callback_data='ch_welcome')],
            [InlineKeyboardButton(lang['farewell'], callback_data='ch_farewell')],
            [InlineKeyboardButton(lang['auto_approve'], callback_data='ch_autoapp')],
            [InlineKeyboardButton(lang['captcha'], callback_data='ch_captcha')],
            [InlineKeyboardButton(lang['privacy'], callback_data='ch_privacy')],
            [InlineKeyboardButton(lang['anti_spam'], callback_data='ch_antispam')],
            [InlineKeyboardButton(lang['auto_posting'], callback_data='ch_autopost')],
            [InlineKeyboardButton(lang['leaderboard'], callback_data='ch_lb')],
            [InlineKeyboardButton(lang['crosspost'], callback_data='ch_cross')],
            [InlineKeyboardButton(lang['giveaway'], callback_data='ch_giveaway')],
            [InlineKeyboardButton(lang['analytics'], callback_data='ch_analytics')],
            [InlineKeyboardButton(lang['disconnect_channel'], callback_data='ch_disconnect')],
            [InlineKeyboardButton(lang['back'], callback_data='menu_ch_settings')],
        ])
        await query.edit_message_text(f"⚙️ {channel['channel_name']}\nID: {ch_id}", reply_markup=kb)

    elif data == 'ch_disconnect':
        ch_id = context.user_data.get('current_channel')
        if ch_id:
            del_channel_db(ch_id, uid)
            await query.edit_message_text(lang['channel_removed'], reply_markup=main_menu_keyboard(uid))

    elif data == 'ch_privacy':
        ch_id = context.user_data.get('current_channel')
        if ch_id:
            current = get_channel_privacy(ch_id)
            new_priv = 'private' if current == 'public' else 'public'
            set_channel_privacy(ch_id, new_priv)
            status = lang['privacy_on'] if new_priv == 'private' else lang['privacy_off']
            await query.answer(f"🔒 {status}", show_alert=True)

    elif data == 'ch_autoapp':
        ch_id = context.user_data.get('current_channel')
        if ch_id:
            current = get_auto_approve(ch_id)
            set_auto_approve(ch_id, not current)
            await query.answer("✅ Авто-приём: " + ("ВКЛ" if not current else "ВЫКЛ"), show_alert=True)

    elif data == 'ch_welcome':
        await query.edit_message_text("📝 Введите текст приветствия (или /skip):")
        context.user_data['awaiting'] = 'welcome_text'

    elif data == 'ch_farewell':
        await query.edit_message_text("📝 Введите текст прощания (или /skip):")
        context.user_data['awaiting'] = 'farewell_text'

    elif data == 'ch_autopost':
        ch_id = context.user_data.get('current_channel')
        posts = get_scheduled_posts(ch_id) if ch_id else []
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(lang['schedule'], callback_data='ap_schedule')],
            [InlineKeyboardButton(lang['view_scheduled'], callback_data='ap_view')],
            [InlineKeyboardButton(lang['cancel_scheduled'], callback_data='ap_cancel')],
            [InlineKeyboardButton(lang['back'], callback_data=f"chset_{ch_id}")],
        ])
        await query.edit_message_text(f"📅 Автопостинг\nЗапланировано: {len(posts)}", reply_markup=kb)

    elif data == 'ap_schedule':
        await query.edit_message_text(lang['enter_post_text'])
        context.user_data['awaiting'] = 'post_text'

    elif data == 'ap_view':
        ch_id = context.user_data.get('current_channel')
        posts = get_scheduled_posts(ch_id) if ch_id else []
        if not posts:
            await query.edit_message_text(lang['no_scheduled'], reply_markup=back_keyboard(uid, f"chset_{ch_id}"))
        else:
            text = "📋 Запланированные посты:\n\n"
            for p in posts[:10]:
                text += f"🆔 {p['id']} — {p['scheduled_time']}\n"
            await query.edit_message_text(text, reply_markup=back_keyboard(uid, f"chset_{ch_id}"))

    elif data == 'ap_cancel':
        ch_id = context.user_data.get('current_channel')
        posts = get_scheduled_posts(ch_id) if ch_id else []
        if not posts:
            await query.edit_message_text(lang['no_scheduled'], reply_markup=back_keyboard(uid, f"chset_{ch_id}"))
        else:
            kb = [[InlineKeyboardButton(f"❌ {p['id']}", callback_data=f"ap_del_{p['id']}")] for p in posts[:10]]
            kb.append([InlineKeyboardButton(lang['back'], callback_data=f"chset_{ch_id}")])
            await query.edit_message_text("❌ Выберите пост для отмены:", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith('ap_del_'):
        post_id = int(data.replace("ap_del_", ""))
        del_scheduled_post(post_id)
        await query.edit_message_text(lang['post_cancelled'], reply_markup=main_menu_keyboard(uid))

    elif data == 'ch_lb':
        ch_id = context.user_data.get('current_channel')
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(lang['day'], callback_data='lb_day')],
            [InlineKeyboardButton(lang['month'], callback_data='lb_month')],
            [InlineKeyboardButton(lang['all_time'], callback_data='lb_all')],
            [InlineKeyboardButton(lang['back'], callback_data=f"chset_{ch_id}")],
        ])
        await query.edit_message_text(lang['leaderboard'], reply_markup=kb)

    elif data.startswith('lb_'):
        ch_id = context.user_data.get('current_channel')
        period = data.replace("lb_", "")
        top = get_top_commenters(ch_id, period) if ch_id else []
        text = lang['lb_text'].format(period=period)
        if not top:
            text += lang['lb_empty']
        else:
            for i, (u_id, cnt) in enumerate(top[:10], 1):
                nick = get_user_nickname(u_id) or str(u_id)
                text += f"{i}. {nick} — {cnt}\n"
        await query.edit_message_text(text, reply_markup=back_keyboard(uid, f"chset_{ch_id}"))

    elif data == 'ch_analytics':
        ch_id = context.user_data.get('current_channel')
        channel = get_channel_by_channel_id(ch_id) if ch_id else None
        if channel:
            growth_data = get_subscribers_growth(ch_id, 7)
            growth = len(growth_data)
            comments = get_channel_stats(ch_id, 'week')
            group = "✅" if channel.get('linked_group_id') else "❌"
            text = lang['analytics'].format(
                subs=channel.get('subscribers', 0),
                growth=growth,
                comments=comments,
                group=group
            )
            await query.edit_message_text(text, reply_markup=back_keyboard(uid, f"chset_{ch_id}"))

    elif data == 'ch_giveaway':
        ch_id = context.user_data.get('current_channel')
        active = get_active_giveaways(ch_id) if ch_id else []
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(lang['giveaway_create'], callback_data='gw_create')],
            [InlineKeyboardButton(lang['giveaway_check'], callback_data='gw_check')],
            [InlineKeyboardButton(lang['back'], callback_data=f"chset_{ch_id}")],
        ])
        await query.edit_message_text(f"🎁 Розыгрыши (активных: {len(active)})", reply_markup=kb)

    elif data == 'gw_create':
        await query.edit_message_text(lang['giveaway_title'])
        context.user_data['awaiting'] = 'gw_title'

    elif data == 'gw_check':
        ch_id = context.user_data.get('current_channel')
        active = get_active_giveaways(ch_id) if ch_id else []
        if not active:
            await query.edit_message_text("😕 Нет активных розыгрышей.", reply_markup=back_keyboard(uid, f"chset_{ch_id}"))
        else:
            gw = active[0]
            parts = get_giveaway_participants(gw['id'])
            text = f"🎁 {gw['title']}\n👥 Участников: {len(parts)}\n🏆 Победителей: {gw['winners_count']}"
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🏆 Завершить", callback_data=f"gw_close_{gw['id']}")],
                [InlineKeyboardButton(lang['back'], callback_data=f"chset_{ch_id}")],
            ])
            await query.edit_message_text(text, reply_markup=kb)

    elif data.startswith('gw_close_'):
        gw_id = int(data.replace("gw_close_", ""))
        parts = get_giveaway_participants(gw_id)
        gw = get_giveaway(gw_id)
        if parts and gw:
            winners = random.sample(parts, min(gw['winners_count'], len(parts)))
            text = lang['giveaway_winners_text']
            for w in winners:
                text += f"@{w['username'] or w['user_id']}\n"
        else:
            text = lang['giveaway_no_participants']
        close_giveaway(gw_id)
        await query.edit_message_text(text + "\n\n" + lang['giveaway_closed'], reply_markup=main_menu_keyboard(uid))

    elif data == 'ch_cross':
        ch_id = context.user_data.get('current_channel')
        targets = get_crosspost_targets(ch_id) if ch_id else []
        text = f"📤 Кросс-постинг\n\nКаналов назначено: {len(targets)}"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(lang['crosspost_add'], callback_data='cross_add')],
            [InlineKeyboardButton(lang['crosspost_remove'], callback_data='cross_remove')],
            [InlineKeyboardButton(lang['crosspost_send'], callback_data='cross_send')],
            [InlineKeyboardButton(lang['back'], callback_data=f"chset_{ch_id}")],
        ])
        await query.edit_message_text(text, reply_markup=kb)

    elif data == 'ch_antispam':
        ch_id = context.user_data.get('current_channel')
        words = get_blacklist_words(ch_id) if ch_id else []
        text = f"🚫 Анти-спам\n\nЗапрещённые слова ({len(words)}):\n" + ", ".join(words[:20]) or "—"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Добавить слово", callback_data='as_add')],
            [InlineKeyboardButton("➖ Удалить слово", callback_data='as_del')],
            [InlineKeyboardButton(lang['back'], callback_data=f"chset_{ch_id}")],
        ])
        await query.edit_message_text(text, reply_markup=kb)

    # ==== ПРОФИЛЬ ====
    elif data == 'profile_edit_name':
        changes = get_user(uid)
        changes = changes.get('name_changes', 0) if changes else 0
        if changes >= 3 and not is_admin(uid):
            await query.answer(lang['name_limit'], show_alert=True)
            return
        await query.edit_message_text(lang['enter_new_name'])
        context.user_data['awaiting'] = 'new_name'

    elif data == 'profile_delete':
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(lang['yes'], callback_data='confirm_delete'),
             InlineKeyboardButton(lang['no'], callback_data='back_main')],
        ])
        await query.edit_message_text(lang['delete_confirm'], reply_markup=kb)

    elif data == 'confirm_delete':
        delete_user_profile(uid)
        await query.edit_message_text(lang['deleted'])

# ============ ОБРАБОТКА ТЕКСТОВЫХ СООБЩЕНИЙ (FSM) ============

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Универсальный обработчик текста для FSM и ожиданий."""
    uid = update.effective_user.id
    lang = get_lang(uid)
    text = update.message.text
    awaiting = context.user_data.get('awaiting')

    if awaiting == 'channel_id':
        try:
            ch_id = int(text.strip())
        except ValueError:
            await update.message.reply_text("❌ Введите числовой ID!")
            return
        try:
            chat = await context.bot.get_chat(ch_id)
            member = await context.bot.get_chat_member(ch_id, context.bot.id)
            if member.status not in ['administrator']:
                await update.message.reply_text(lang['not_enough_rights'])
                return
            perms = member
            can_post = getattr(perms, 'can_post_messages', False)
            if not can_post:
                await update.message.reply_text("❌ Бот должен иметь право отправлять сообщения!")
                return
        except Exception as e:
            logger.error(f"Channel check error: {e}")
            await update.message.reply_text("❌ Канал не найден или бот не добавлен.")
            return

        context.user_data['pending_channel_id'] = ch_id
        context.user_data['pending_channel_name'] = chat.title or chat.username or str(ch_id)
        cats = [[InlineKeyboardButton("📂 Общее", callback_data='cat_general')],
                [InlineKeyboardButton("📂 Новости", callback_data='cat_news')],
                [InlineKeyboardButton("📂 Игры", callback_data='cat_games')]]
        await update.message.reply_text("📂 Выберите категорию:", reply_markup=InlineKeyboardMarkup(cats))
        context.user_data['awaiting'] = 'channel_cat'
        return

    elif awaiting == 'promo_code':
        code = text.strip().upper()
        promo = get_promo_code(code)
        if not promo:
            await update.message.reply_text(lang['code_invalid'])
        elif promo['uses'] >= promo['max_uses']:
            await update.message.reply_text(lang['code_used'])
        else:
            use_promo_code(code)
            extend_subscription(uid, promo['subscription_days'])
            end = get_subscription_end(uid)
            await update.message.reply_text(lang['code_activated'].format(date=end))
        context.user_data['awaiting'] = None

    elif awaiting == 'broadcast':
        target = context.user_data.get('bc_target', 'bc_all')
        sent = 0
        if target == 'bc_all':
            users = get_all_users()
        elif target == 'bc_subs':
            users = get_all_users_with_sub()
        else:
            users = get_all_users_without_sub()

        for u in users:
            try:
                await context.bot.send_message(u['user_id'], text)
                sent += 1
            except Exception:
                pass
        await update.message.reply_text(lang['broadcast_done'].format(sent=sent))
        context.user_data['awaiting'] = None

    elif awaiting == 'gift_id':
        try:
            target_id = int(text.strip())
        except ValueError:
            await update.message.reply_text("❌ Введите числовой ID!")
            return
        context.user_data['gift_target'] = target_id
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(PLAN_NAMES['month'], callback_data='gift_month')],
            [InlineKeyboardButton(PLAN_NAMES['6month'], callback_data='gift_6month')],
            [InlineKeyboardButton(PLAN_NAMES['year'], callback_data='gift_year')],
        ])
        await update.message.reply_text("Выберите подписку:", reply_markup=kb)
        context.user_data['awaiting'] = 'gift_plan'

    elif awaiting == 'new_name':
        name = text.strip()
        if len(name) < 2 or not all(c.isalnum() or c == '_' for c in name):
            await update.message.reply_text("❌ Неверный формат!")
            return
        if is_nickname_taken(name) and get_user_nickname(uid) != name:
            await update.message.reply_text("❌ Имя занято!")
            return
        set_user_nickname(uid, name)
        increment_name_changes(uid)
        await update.message.reply_text(lang['name_changed'].format(name=name), reply_markup=main_menu_keyboard(uid))
        context.user_data['awaiting'] = None

    elif awaiting == 'welcome_text':
        ch_id = context.user_data.get('current_channel')
        if ch_id:
            set_welcome_text(ch_id, text)
            await update.message.reply_text(lang['saved'], reply_markup=back_keyboard(uid, f"chset_{ch_id}"))
        context.user_data['awaiting'] = None

    elif awaiting == 'farewell_text':
        ch_id = context.user_data.get('current_channel')
        if ch_id:
            set_farewell_text(ch_id, text)
            await update.message.reply_text(lang['saved'], reply_markup=back_keyboard(uid, f"chset_{ch_id}"))
        context.user_data['awaiting'] = None

    elif awaiting == 'post_text':
        context.user_data['post_text'] = text
        await update.message.reply_text(lang['enter_post_media'] + "\n(или /skip)")
        context.user_data['awaiting'] = 'post_media'

    elif awaiting == 'search_channels':
        query = text.lower()
        channels = get_all_channels()
        results = [ch for ch in channels if query in (ch['channel_name'] or "").lower() or query in str(ch['channel_id'])]
        if not results:
            await update.message.reply_text(lang['not_found'])
        else:
            text_resp = lang['search_results'].format(count=len(results)) + "\n\n"
            for ch in results[:20]:
                priv = "🔒" if ch['privacy'] == 'private' else "🔓"
                text_resp += f"{priv} {ch['channel_name']} — {ch['subscribers']} подп.\n"
            await update.message.reply_text(text_resp)
        context.user_data['awaiting'] = None

    elif awaiting == 'search_users':
        query = text.lower()
        users = get_all_users()
        results = [u for u in users if query in (get_user_nickname(u['user_id']) or "").lower() or query in str(u['user_id'])]
        if not results:
            await update.message.reply_text(lang['not_found'])
        else:
            text_resp = lang['search_results'].format(count=len(results)) + "\n\n"
            for u in results[:20]:
                nick = get_user_nickname(u['user_id']) or "—"
                text_resp += f"👤 {nick} (ID: {u['user_id']})\n"
            await update.message.reply_text(text_resp)
        context.user_data['awaiting'] = None

    elif awaiting == 'make_admin':
        try:
            target = int(text.strip())
        except ValueError:
            await update.message.reply_text("❌ Введите ID!")
            return
        add_bot_admin(target)
        await update.message.reply_text(lang['admin_added'].format(uid=target))
        context.user_data['awaiting'] = None

    elif awaiting == 'as_add_word':
        ch_id = context.user_data.get('current_channel')
        if ch_id:
            add_blacklist_word(ch_id, text)
            await update.message.reply_text("✅ Слово добавлено!", reply_markup=back_keyboard(uid, f"chset_{ch_id}"))
        context.user_data['awaiting'] = None

async def skip_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пропуск медиа в автопостинге."""
    if context.user_data.get('awaiting') == 'post_media':
        context.user_data['post_media'] = None
        await ask_post_time(update, context)

async def ask_post_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    lang = get_lang(uid)
    tz = get_user_timezone(uid)
    now = datetime.now(pytz.timezone(tz)).strftime("%H:%M")
    await update.message.reply_text(lang['time_enter'].format(tz=tz, now=now))
    context.user_data['awaiting'] = 'post_time'

async def media_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка медиа для автопостинга."""
    if context.user_data.get('awaiting') == 'post_media':
        if update.message.photo:
            context.user_data['post_media'] = {'type': 'photo', 'file_id': update.message.photo[-1].file_id}
        elif update.message.video:
            context.user_data['post_media'] = {'type': 'video', 'file_id': update.message.video.file_id}
        elif update.message.document:
            context.user_data['post_media'] = {'type': 'document', 'file_id': update.message.document.file_id}
        else:
            await update.message.reply_text("❌ Неподдерживаемый формат.")
            return
        await ask_post_time(update, context)

async def time_entered(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка времени для автопостинга."""
    uid = update.effective_user.id
    lang = get_lang(uid)
    text = update.message.text.strip()
    try:
        hour, minute = map(int, text.split(':'))
        tz = pytz.timezone(get_user_timezone(uid))
        now = datetime.now(tz)
        scheduled = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if scheduled < now:
            scheduled += timedelta(days=1)
        context.user_data['post_time'] = scheduled.astimezone(pytz.UTC)
        calendar, step = DetailedTelegramCalendar().build()
        await update.message.reply_text(lang['calendar_select'], reply_markup=calendar)
        context.user_data['awaiting'] = 'post_date'
    except ValueError:
        await update.message.reply_text(lang['invalid_time'])

async def calendar_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка календаря."""
    uid = update.effective_user.id
    lang = get_lang(uid)
    query = update.callback_query
    result, key, step = DetailedTelegramCalendar().process(query.data)
    if not result and key:
        await query.edit_message_text(lang['calendar_select'], reply_markup=key)
    elif result:
        await query.answer()
        ch_id = context.user_data.get('current_channel')
        post_data = {
            'text': context.user_data.get('post_text', ''),
            'media': context.user_data.get('post_media')
        }
        scheduled_time = datetime.combine(result, context.user_data['post_time'].time())
        scheduled_time = pytz.UTC.localize(scheduled_time)
        post_id = add_scheduled_post(ch_id, json.dumps(post_data), scheduled_time)
        await query.edit_message_text(lang['post_scheduled'].format(time=scheduled_time.strftime("%Y-%m-%d %H:%M UTC")))
        context.user_data['awaiting'] = None

# ============ GIVEAWAY CONVERSATION ============

async def gw_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['gw_title'] = update.message.text
    await update.message.reply_text(t(update.effective_user.id, 'giveaway_winners'))
    return GIVEAWAY_WINNERS

async def gw_winners(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    lang = get_lang(uid)
    try:
        count = int(update.message.text)
    except ValueError:
        await update.message.reply_text("❌ Введите число!")
        return GIVEAWAY_WINNERS

    ch_id = context.user_data.get('current_channel')
    title = context.user_data.get('gw_title', 'Giveaway')
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🎉 Участвовать", callback_data=f"gw_join_{ch_id}")]])
    msg = await context.bot.send_message(ch_id, f"🎁 {title}\n\nНажмите кнопку для участия!", reply_markup=kb)
    create_giveaway(ch_id, title, count, message_id=msg.message_id)
    await update.message.reply_text(lang['giveaway_published'])
    return ConversationHandler.END

async def gw_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    # Получаем giveaway по каналу
    ch_id = int(query.data.replace("gw_join_", ""))
    active = get_active_giveaways(ch_id)
    if active:
        add_giveaway_participant(active[0]['id'], uid, query.from_user.username)
    await query.answer("✅ Вы участвуете!", show_alert=True)

# ============ КАНАЛЬНЫЕ СОБЫТИЯ ============

async def chat_member_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приветствие и прощание в каналах."""
    member = update.chat_member
    ch_id = member.chat.id
    user = member.from_user

    if member.new_chat_member.status == 'member' and member.old_chat_member.status != 'member':
        welcome = get_welcome_text(ch_id)
        if welcome:
            try:
                await context.bot.send_message(ch_id, welcome)
            except Exception:
                pass
        captcha = get_captcha_settings(ch_id)
        if captcha:
            pass

    elif member.new_chat_member.status in ['left', 'kicked'] and member.old_chat_member.status == 'member':
        farewell = get_farewell_text(ch_id)
        if farewell:
            try:
                await context.bot.send_message(ch_id, farewell)
            except Exception:
                pass

async def group_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Анти-спам и статистика комментариев в группах."""
    if not update.message or not update.message.from_user:
        return
    group_id = update.message.chat.id
    channel = get_channel_by_linked_group(group_id)
    if not channel:
        return
    ch_id = channel['channel_id']
    uid = update.message.from_user.id

    add_comment_stat(ch_id, uid, update.message.message_id)

    words = get_blacklist_words(ch_id)
    if words:
        text = update.message.text or ""
        if any(w in text.lower() for w in words):
            try:
                await update.message.delete()
            except Exception:
                pass

# ============ ФОНОВЫЕ ЗАДАЧИ ============

async def scheduled_posts_job(context: ContextTypes.DEFAULT_TYPE):
    """Отправка запланированных постов."""
    posts = get_due_scheduled_posts()
    for post in posts:
        try:
            data = json.loads(post['post_data'])
            text = data.get('text', '')
            media = data.get('media')
            ch_id = post['channel_id']

            if media:
                if media['type'] == 'photo':
                    await context.bot.send_photo(ch_id, photo=media['file_id'], caption=text)
                elif media['type'] == 'video':
                    await context.bot.send_video(ch_id, video=media['file_id'], caption=text)
                else:
                    await context.bot.send_document(ch_id, document=media['file_id'], caption=text)
            else:
                await context.bot.send_message(ch_id, text)

            mark_post_sent(post['id'])
        except Exception as e:
            logger.error(f"Scheduled post error: {e}")

async def subscribers_snapshot_job(context: ContextTypes.DEFAULT_TYPE):
    """Снимок подписчиков для аналитики."""
    channels = get_all_channels()
    for ch in channels:
        try:
            chat = await context.bot.get_chat(ch['channel_id'])
            count = chat.members_count if hasattr(chat, 'members_count') else 0
            update_channel_subscribers_db(ch['channel_id'], count)
            add_subscribers_snapshot(ch['channel_id'], count)
        except Exception:
            pass

# ============ НАСТРОЙКА ХЕНДЛЕРОВ ============

def setup_handlers(application: Application):
    # Conversation: Регистрация
    reg_conv = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            REG_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_name)],
            REG_AGE: [CallbackQueryHandler(reg_age_callback, pattern='^age_')],
            REG_TZ: [CallbackQueryHandler(reg_tz_callback, pattern='^tz_')],
        },
        fallbacks=[CommandHandler('start', start)],
    )
    application.add_handler(reg_conv)

    # Conversation: Giveaway
    gw_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(lambda u, c: u.callback_query.edit_message_text(t(u.effective_user.id, 'giveaway_title')) or GIVEAWAY_TITLE, pattern='^gw_create$')],
        states={
            GIVEAWAY_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, gw_title)],
            GIVEAWAY_WINNERS: [MessageHandler(filters.TEXT & ~filters.COMMAND, gw_winners)],
        },
        fallbacks=[CommandHandler('start', start)],
    )
    application.add_handler(gw_conv)

    # Callbacks
    application.add_handler(CallbackQueryHandler(menu_callback, pattern='^(menu_|back_|sub_|card_|lang_|dev_|bc_|chset_|ch_|lb_|gw_|ap_|cat_|confirm_|profile_)'))
    application.add_handler(CallbackQueryHandler(gw_join_callback, pattern='^gw_join_'))
    application.add_handler(CallbackQueryHandler(calendar_handler, pattern='^cbcal_'))

    # Текст
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    application.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | filters.Document.ALL, media_handler))
    application.add_handler(CommandHandler('skip', skip_media))

    # Канальные события
    application.add_handler(ChatMemberHandler(chat_member_handler, ChatMemberHandler.CHAT_MEMBER))
    application.add_handler(MessageHandler(filters.ChatType.GROUPS & ~filters.COMMAND, group_message_handler))

    # Фоновые задачи (job_queue PTB)
    application.job_queue.run_repeating(scheduled_posts_job, interval=60, first=10)
    application.job_queue.run_repeating(subscribers_snapshot_job, interval=3600, first=60)
    application.job_queue.run_repeating(lambda c: cleanup_old_data(90), interval=86400, first=3600)

# ============ FLASK + WEBHOOK ============

flask_app = Flask(__name__)

@flask_app.route('/')
def index():
    return jsonify({"status": "Bot is running!", "mode": "webhook"})

@flask_app.route('/health')
def health():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT 1')
        cursor.fetchone()
        put_db(conn)
        return jsonify({"status": "OK", "database": "connected"})
    except Exception as e:
        return jsonify({"status": "ERROR", "database": str(e)}), 500

@flask_app.route('/webhook', methods=['POST'])
def webhook():
    """Принимаем webhook от Telegram и передаём в PTB."""
    if application is None or bot_loop is None:
        return jsonify({"error": "Bot not initialized"}), 503

    data = request.get_json(force=True)
    update = Update.de_json(data, application.bot)

    asyncio.run_coroutine_threadsafe(
        application.update_queue.put(update),
        bot_loop
    )
    return jsonify({"ok": True})

def run_flask():
    logger.info(f"Flask starting on port {PORT}")
    flask_app.run(host='0.0.0.0', port=PORT, threaded=True)

def run_bot():
    """Запуск PTB Application в отдельном потоке с event loop."""
    global application, bot_loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    bot_loop = loop

    application = Application.builder().token(BOT_TOKEN).build()
    setup_handlers(application)

    loop.run_until_complete(application.initialize())
    loop.run_until_complete(application.start())

    if USE_WEBHOOK and WEBHOOK_URL:
        webhook_path = f"{WEBHOOK_URL}/webhook"
        loop.run_until_complete(application.bot.set_webhook(webhook_path))
        logger.info(f"Webhook set to {webhook_path}")
    else:
        loop.run_until_complete(application.updater.start_polling())
        logger.info("Started polling (webhook not configured)")

    loop.run_forever()

# ============ ТОЧКА ВХОДА ============

if __name__ == '__main__':
    init_db()

    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()

    run_flask()