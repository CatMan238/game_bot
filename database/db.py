import sqlite3
from datetime import datetime, timedelta
import json
from config import OWNER_ID

DATABASE_PATH = "bot.db"

def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def add_column_if_not_exists(cursor, table, column, column_type):
    try:
        cursor.execute(f"SELECT {column} FROM {table} LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")
        return True
    return False

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # Все таблицы (как в оригинале)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            language TEXT DEFAULT 'ru',
            registered INTEGER DEFAULT 0,
            adult_verified INTEGER DEFAULT 0,
            name_changes INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    add_column_if_not_exists(cursor, 'users', 'registered', 'INTEGER DEFAULT 0')
    add_column_if_not_exists(cursor, 'users', 'adult_verified', 'INTEGER DEFAULT 0')
    add_column_if_not_exists(cursor, 'users', 'name_changes', 'INTEGER DEFAULT 0')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS nicknames (
            user_id INTEGER PRIMARY KEY,
            nickname TEXT UNIQUE,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS subscriptions (
            user_id INTEGER PRIMARY KEY,
            end_date TEXT,
            auto_renew INTEGER DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payments_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            currency TEXT DEFAULT 'XTR',
            status TEXT,
            payment_id TEXT,
            plan_type TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id INTEGER UNIQUE,
            channel_name TEXT,
            owner_id INTEGER,
            category TEXT,
            privacy TEXT DEFAULT 'public',
            subscribers INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS blacklist_words (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id INTEGER,
            word TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scheduled_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id INTEGER,
            post_text TEXT,
            post_media TEXT,
            scheduled_time TEXT,
            is_sent INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS promo_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE,
            name TEXT,
            max_uses INTEGER,
            subscription_days INTEGER,
            uses INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vp_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            channel_id INTEGER,
            media TEXT,
            text TEXT,
            is_adult INTEGER DEFAULT 0,
            category TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
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
    
    # Добавляем владельца
    cursor.execute('INSERT OR IGNORE INTO users (user_id, registered, adult_verified) VALUES (?, 1, 1)', (OWNER_ID,))
    end_date = (datetime.now() + timedelta(days=3650)).strftime('%Y-%m-%d')
    cursor.execute('INSERT OR REPLACE INTO subscriptions (user_id, end_date, auto_renew) VALUES (?, ?, 1)', (OWNER_ID, end_date))
    
    conn.commit()
    conn.close()

# ============================================
#  ПОЛЬЗОВАТЕЛИ
# ============================================
def create_user(user_id, username):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)', (user_id, username))
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = get_db()
    cursor = conn.cursor()
    user = cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)).fetchone()
    conn.close()
    return user

def get_all_users():
    conn = get_db()
    cursor = conn.cursor()
    users = cursor.execute('SELECT * FROM users ORDER BY created_at DESC').fetchall()
    conn.close()
    return users

def get_user_language(user_id):
    user = get_user(user_id)
    return user['language'] if user else 'ru'

def set_user_language(user_id, language):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET language = ? WHERE user_id = ?', (language, user_id))
    conn.commit()
    conn.close()

def is_registered(user_id):
    conn = get_db()
    cursor = conn.cursor()
    user = cursor.execute('SELECT registered FROM users WHERE user_id = ?', (user_id,)).fetchone()
    conn.close()
    return user is not None and user['registered'] == 1

def set_registered(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET registered = 1 WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def is_adult(user_id):
    if user_id == OWNER_ID:
        return True
    conn = get_db()
    cursor = conn.cursor()
    user = cursor.execute('SELECT adult_verified FROM users WHERE user_id = ?', (user_id,)).fetchone()
    conn.close()
    return user is not None and user['adult_verified'] == 1

def set_adult(user_id, value):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET adult_verified = ? WHERE user_id = ?', (1 if value else 0, user_id))
    conn.commit()
    conn.close()

def get_name_changes(user_id):
    conn = get_db()
    cursor = conn.cursor()
    user = cursor.execute('SELECT name_changes FROM users WHERE user_id = ?', (user_id,)).fetchone()
    conn.close()
    return user['name_changes'] if user else 0

def increment_name_changes(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET name_changes = name_changes + 1 WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

# ============================================
#  НИКНЕЙМЫ
# ============================================
def get_user_nickname(user_id):
    conn = get_db()
    cursor = conn.cursor()
    result = cursor.execute('SELECT nickname FROM nicknames WHERE user_id = ?', (user_id,)).fetchone()
    conn.close()
    return result['nickname'] if result else None

def set_user_nickname(user_id, nickname):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO nicknames (user_id, nickname, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)', (user_id, nickname))
    conn.commit()
    conn.close()

def is_nickname_taken(nickname):
    conn = get_db()
    cursor = conn.cursor()
    result = cursor.execute('SELECT user_id FROM nicknames WHERE nickname = ?', (nickname,)).fetchone()
    conn.close()
    return result is not None

# ============================================
#  ПОДПИСКИ
# ============================================
def get_subscription_end(user_id):
    conn = get_db()
    cursor = conn.cursor()
    result = cursor.execute('SELECT end_date FROM subscriptions WHERE user_id = ?', (user_id,)).fetchone()
    conn.close()
    return result['end_date'] if result else None

def set_subscription(user_id, end_date):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO subscriptions (user_id, end_date, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)', (user_id, end_date))
    conn.commit()
    conn.close()

def is_subscribed(user_id):
    if user_id == OWNER_ID:
        return True
    end_date = get_subscription_end(user_id)
    if end_date:
        try:
            return datetime.strptime(end_date, '%Y-%m-%d') >= datetime.now()
        except:
            return False
    return False

def set_auto_renew(user_id, enabled):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE subscriptions SET auto_renew = ? WHERE user_id = ?', (1 if enabled else 0, user_id))
    conn.commit()
    conn.close()

def get_auto_renew(user_id):
    conn = get_db()
    cursor = conn.cursor()
    result = cursor.execute('SELECT auto_renew FROM subscriptions WHERE user_id = ?', (user_id,)).fetchone()
    conn.close()
    return result['auto_renew'] == 1 if result else 0

# ============================================
#  ИСТОРИЯ ПЛАТЕЖЕЙ (для звёзд)
# ============================================
def add_payment_history(user_id, amount, status, payment_id, plan_type):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO payments_history (user_id, amount, currency, status, payment_id, plan_type)
        VALUES (?, ?, 'XTR', ?, ?, ?)
    ''', (user_id, amount, status, payment_id, plan_type))
    conn.commit()
    conn.close()

def get_payment_history(user_id, limit=10):
    conn = get_db()
    cursor = conn.cursor()
    history = cursor.execute('''
        SELECT * FROM payments_history WHERE user_id = ? ORDER BY created_at DESC LIMIT ?
    ''', (user_id, limit)).fetchall()
    conn.close()
    return history

# ============================================
#  КАНАЛЫ
# ============================================
def add_channel_db(channel_id, channel_name, owner_id, category, privacy='public', subscribers=0):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''INSERT OR REPLACE INTO channels (channel_id, channel_name, owner_id, category, privacy, subscribers) VALUES (?, ?, ?, ?, ?, ?)''', (channel_id, channel_name, owner_id, category, privacy, subscribers))
    conn.commit()
    conn.close()
    return True

def del_channel_db(channel_id, owner_id=None):
    conn = get_db()
    cursor = conn.cursor()
    if owner_id:
        cursor.execute('DELETE FROM channels WHERE channel_id = ? AND owner_id = ?', (channel_id, owner_id))
    else:
        cursor.execute('DELETE FROM channels WHERE channel_id = ?', (channel_id,))
    conn.commit()
    conn.close()

def get_user_channels(owner_id):
    conn = get_db()
    cursor = conn.cursor()
    channels = cursor.execute('SELECT * FROM channels WHERE owner_id = ? ORDER BY created_at DESC', (owner_id,)).fetchall()
    conn.close()
    return channels

def get_all_channels():
    conn = get_db()
    cursor = conn.cursor()
    channels = cursor.execute('SELECT * FROM channels ORDER BY created_at DESC').fetchall()
    conn.close()
    return channels

def get_channel_by_channel_id(channel_id):
    conn = get_db()
    cursor = conn.cursor()
    channel = cursor.execute('SELECT * FROM channels WHERE channel_id = ?', (channel_id,)).fetchone()
    conn.close()
    return channel

def update_channel_subscribers_db(channel_id, subscribers):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE channels SET subscribers = ? WHERE channel_id = ?', (subscribers, channel_id))
    conn.commit()
    conn.close()

def get_channel_privacy(channel_id):
    conn = get_db()
    cursor = conn.cursor()
    result = cursor.execute('SELECT privacy FROM channels WHERE channel_id = ?', (channel_id,)).fetchone()
    conn.close()
    return result['privacy'] if result else 'public'

def set_channel_privacy(channel_id, privacy):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE channels SET privacy = ? WHERE channel_id = ?', (privacy, channel_id))
    conn.commit()
    conn.close()

def admin_delete_channel(channel_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM channels WHERE channel_id = ?', (channel_id,))
    cursor.execute('DELETE FROM blacklist_words WHERE channel_id = ?', (channel_id,))
    cursor.execute('DELETE FROM scheduled_posts WHERE channel_id = ?', (channel_id,))
    conn.commit()
    conn.close()

# ===== СВЯЗАННАЯ ГРУППА =====
def get_channel_linked_group(channel_id):
    return get_setting(f"linked_group_{channel_id}")

def set_channel_linked_group(channel_id, group_id):
    set_setting(f"linked_group_{channel_id}", str(group_id))

# ============================================
#  АВТОПРИЁМ
# ============================================
def get_auto_approve(channel_id):
    return get_setting(f"auto_approve_{channel_id}") == '1'

def set_auto_approve(channel_id, enabled):
    set_setting(f"auto_approve_{channel_id}", '1' if enabled else '0')

# ============================================
#  ПРИВЕТСТВИЕ (ДОБАВЛЕНО)
# ============================================
def set_welcome_text(channel_id, text):
    set_setting(f"welcome_text_{channel_id}", text)

def get_welcome_text(channel_id):
    return get_setting(f"welcome_text_{channel_id}")

# ============================================
#  ПРОЩАНИЕ (ДОБАВЛЕНО)
# ============================================
def set_farewell_text(channel_id, text):
    set_setting(f"farewell_text_{channel_id}", text)

def get_farewell_text(channel_id):
    return get_setting(f"farewell_text_{channel_id}")

# ============================================
#  КАПТЧА (ДОБАВЛЕНО)
# ============================================
def set_captcha_settings(channel_id, question, answers):
    data = json.dumps({"question": question, "answers": answers})
    set_setting(f"captcha_{channel_id}", data)

def get_captcha_settings(channel_id):
    data = get_setting(f"captcha_{channel_id}")
    if data:
        try:
            return json.loads(data)
        except:
            return None
    return None

def del_captcha_settings(channel_id):
    set_setting(f"captcha_{channel_id}", None)

# ============================================
#  ЛИДЕРБОАРД (ЗАГЛУШКА)
# ============================================
def get_top_commenters(channel_id, period):
    # В реальном проекте здесь должен быть запрос к БД со статистикой
    # Пока возвращаем пустой список, чтобы не падать
    return []

# ============================================
#  ЧЁРНЫЙ СПИСОК
# ============================================
def add_blacklist_word(channel_id, word):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO blacklist_words (channel_id, word) VALUES (?, ?)', (channel_id, word.lower()))
    conn.commit()
    conn.close()

def get_blacklist_words(channel_id):
    conn = get_db()
    cursor = conn.cursor()
    rows = cursor.execute('SELECT word FROM blacklist_words WHERE channel_id = ?', (channel_id,)).fetchall()
    conn.close()
    return [r['word'] for r in rows]

def del_blacklist_word(channel_id, word):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM blacklist_words WHERE channel_id = ? AND word = ?', (channel_id, word.lower()))
    conn.commit()
    conn.close()

# ============================================
#  ЗАПЛАНИРОВАННЫЕ ПОСТЫ
# ============================================
def add_scheduled_post(channel_id, text, media, scheduled_time):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO scheduled_posts (channel_id, post_text, post_media, scheduled_time) VALUES (?, ?, ?, ?)', (channel_id, text, media, scheduled_time))
    conn.commit()
    conn.close()

def get_scheduled_posts(channel_id):
    conn = get_db()
    cursor = conn.cursor()
    posts = cursor.execute('SELECT * FROM scheduled_posts WHERE channel_id = ? AND is_sent = 0 ORDER BY scheduled_time ASC', (channel_id,)).fetchall()
    conn.close()
    return posts

def get_all_scheduled_posts():
    conn = get_db()
    cursor = conn.cursor()
    posts = cursor.execute('SELECT * FROM scheduled_posts WHERE is_sent = 0 ORDER BY scheduled_time ASC').fetchall()
    conn.close()
    return posts

def get_due_scheduled_posts():
    conn = get_db()
    cursor = conn.cursor()
    posts = cursor.execute('SELECT * FROM scheduled_posts WHERE is_sent = 0 AND scheduled_time <= datetime("now") ORDER BY scheduled_time ASC').fetchall()
    conn.close()
    return posts

def del_scheduled_post(post_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM scheduled_posts WHERE id = ?', (post_id,))
    conn.commit()
    conn.close()

# ============================================
#  ПРОМОКОДЫ
# ============================================
def create_promo_code(code, name, max_uses, days):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO promo_codes (code, name, max_uses, subscription_days) VALUES (?, ?, ?, ?)', (code, name, max_uses, days))
    conn.commit()
    conn.close()

def get_promo_code(code):
    conn = get_db()
    cursor = conn.cursor()
    result = cursor.execute('SELECT * FROM promo_codes WHERE code = ? AND is_active = 1', (code,)).fetchone()
    conn.close()
    return result

def use_promo_code(code):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE promo_codes SET uses = uses + 1 WHERE code = ?', (code,))
    conn.commit()
    conn.close()

def get_all_promo_codes():
    conn = get_db()
    cursor = conn.cursor()
    codes = cursor.execute('SELECT * FROM promo_codes ORDER BY created_at DESC').fetchall()
    conn.close()
    return codes

def del_promo_code(code):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM promo_codes WHERE code = ?', (code,))
    conn.commit()
    conn.close()

# ============================================
#  НАСТРОЙКИ
# ============================================
def get_setting(key):
    conn = get_db()
    cursor = conn.cursor()
    result = cursor.execute('SELECT value FROM settings WHERE key = ?', (key,)).fetchone()
    conn.close()
    return result['value'] if result else None

def set_setting(key, value):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (key, value))
    conn.commit()
    conn.close()

# ============================================
#  ВП (ВЗАИМОПОСТ)
# ============================================
def get_vp_timer():
    timer = get_setting("vp_timer")
    if timer:
        try:
            return int(timer)
        except:
            pass
    return 12

def set_vp_timer(hours):
    set_setting("vp_timer", str(hours))

def add_vp_post(user_id, channel_id, media, text, is_adult, category):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO vp_posts (user_id, channel_id, media, text, is_adult, category) VALUES (?, ?, ?, ?, ?, ?)', (user_id, channel_id, media, text, 1 if is_adult else 0, category))
    conn.commit()
    conn.close()
    return True

def get_vp_posts(limit=3, offset=0, adult_only=True):
    conn = get_db()
    cursor = conn.cursor()
    if adult_only:
        posts = cursor.execute('SELECT * FROM vp_posts WHERE is_adult = 0 ORDER BY created_at DESC LIMIT ? OFFSET ?', (limit, offset)).fetchall()
    else:
        posts = cursor.execute('SELECT * FROM vp_posts ORDER BY created_at DESC LIMIT ? OFFSET ?', (limit, offset)).fetchall()
    total = cursor.execute('SELECT COUNT(*) FROM vp_posts').fetchone()[0]
    conn.close()
    return posts, total

def get_all_vp_posts_count():
    conn = get_db()
    cursor = conn.cursor()
    count = cursor.execute('SELECT COUNT(*) FROM vp_posts').fetchone()[0]
    conn.close()
    return count

def get_vp_post(post_id):
    conn = get_db()
    cursor = conn.cursor()
    post = cursor.execute('SELECT * FROM vp_posts WHERE id = ?', (post_id,)).fetchone()
    conn.close()
    return post

def delete_vp_post(post_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM vp_posts WHERE id = ?', (post_id,))
    conn.commit()
    conn.close()

def clear_all_vp_posts():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM vp_posts')
    conn.commit()
    conn.close()

def get_last_vp_post_time(user_id):
    conn = get_db()
    cursor = conn.cursor()
    result = cursor.execute('SELECT created_at FROM vp_posts WHERE user_id = ? ORDER BY created_at DESC LIMIT 1', (user_id,)).fetchone()
    conn.close()
    if result:
        return datetime.strptime(result[0], '%Y-%m-%d %H:%M:%S')
    return None

def can_user_post_vp(user_id):
    if user_id == OWNER_ID:
        return True, "✅ РАЗРАБОТЧИК — БЕЗ ОГРАНИЧЕНИЙ!"
    if not is_subscribed(user_id):
        return False, "❌ ТРЕБУЕТСЯ ПОДПИСКА!"
    channels = get_user_channels(user_id)
    if not channels:
        return False, "❌ НУЖЕН ХОТЯ БЫ 1 ПРИВЯЗАННЫЙ КАНАЛ!"
    timer_hours = get_vp_timer()
    last_post = get_last_vp_post_time(user_id)
    if last_post:
        hours_passed = (datetime.now() - last_post).total_seconds() / 3600
        if hours_passed < timer_hours:
            remaining = timer_hours - hours_passed
            return False, f"⏳ ПОДОЖДИТЕ {int(remaining)} ЧАСОВ ДО СЛЕДУЮЩЕГО ПОСТА!"
    return True, "✅ МОЖНО СОЗДАВАТЬ ПОСТ"

# ============================================
#  УВЕДОМЛЕНИЯ
# ============================================
def mark_all_notifications_read(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE notifications SET read = 1 WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def add_notification(user_id, notif_type, content, link_data=None):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO notifications (user_id, type, content, link_data) VALUES (?, ?, ?, ?)', (user_id, notif_type, content, link_data))
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

# ============================================
#  УДАЛЕНИЕ ПРОФИЛЯ
# ============================================
def delete_user_profile(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM users WHERE user_id = ?', (user_id,))
    cursor.execute('DELETE FROM nicknames WHERE user_id = ?', (user_id,))
    cursor.execute('DELETE FROM subscriptions WHERE user_id = ?', (user_id,))
    cursor.execute('DELETE FROM channels WHERE owner_id = ?', (user_id,))
    cursor.execute('DELETE FROM settings WHERE key LIKE ?', (f"blocked_{user_id}",))
    cursor.execute('DELETE FROM vp_posts WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()
    return True