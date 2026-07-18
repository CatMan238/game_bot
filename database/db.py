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
    """Проверяет наличие колонки и добавляет её если отсутствует"""
    try:
        cursor.execute(f"SELECT {column} FROM {table} LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")
        return True
    return False

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # ===== ПОЛЬЗОВАТЕЛИ =====
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            language TEXT DEFAULT 'ru',
            subscription_end TEXT,
            is_owner INTEGER DEFAULT 0,
            is_banned INTEGER DEFAULT 0,
            registered INTEGER DEFAULT 0,
            adult_verified INTEGER DEFAULT 0,
            name_changes INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Добавляем недостающие колонки (миграция)
    add_column_if_not_exists(cursor, 'users', 'registered', 'INTEGER DEFAULT 0')
    add_column_if_not_exists(cursor, 'users', 'adult_verified', 'INTEGER DEFAULT 0')
    add_column_if_not_exists(cursor, 'users', 'name_changes', 'INTEGER DEFAULT 0')
    
    # ===== КАНАЛЫ =====
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id INTEGER UNIQUE,
            channel_name TEXT,
            owner_id INTEGER,
            category TEXT,
            subscription_end TEXT,
            privacy TEXT DEFAULT 'public',
            subscribers INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # ===== ЧЁРНЫЙ СПИСОК СЛОВ =====
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS blacklist_words (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id INTEGER,
            word TEXT
        )
    ''')
    
    # ===== ЗАПЛАНИРОВАННЫЕ ПОСТЫ =====
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
    
    # ===== ПРОМОКОДЫ =====
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
    
    # ===== ПАРТНЁРСТВА =====
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS partnerships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_channel_id INTEGER,
            to_channel_id INTEGER,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # ===== НАСТРОЙКИ (ГЛОБАЛЬНЫЕ) =====
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    
    # ===== ВП ПОСТЫ =====
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
    
    # ===== БЕТА-ФИЧИ =====
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS beta_features (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            code TEXT,
            description TEXT,
            status TEXT DEFAULT 'testing',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            promoted_at TIMESTAMP
        )
    ''')
    
    # ===== ЛОГ ОБНОВЛЕНИЙ =====
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS update_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version TEXT,
            changes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # ===== НИКНЕЙМЫ (ОТДЕЛЬНАЯ ТАБЛИЦА ДЛЯ НАДЁЖНОСТИ) =====
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS nicknames (
            user_id INTEGER PRIMARY KEY,
            nickname TEXT UNIQUE,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # ===== ПОДПИСКИ (ОТДЕЛЬНАЯ ТАБЛИЦА) =====
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS subscriptions (
            user_id INTEGER PRIMARY KEY,
            end_date TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # ===== ДОБАВЛЯЕМ ВЛАДЕЛЬЦА =====
    cursor.execute('''
        INSERT OR IGNORE INTO users (user_id, is_owner, registered, adult_verified) 
        VALUES (?, 1, 1, 1)
    ''', (OWNER_ID,))
    
    # Подписка для владельца на 10 лет
    end_date = (datetime.now() + timedelta(days=3650)).strftime('%Y-%m-%d')
    cursor.execute('''
        INSERT OR REPLACE INTO subscriptions (user_id, end_date) 
        VALUES (?, ?)
    ''', (OWNER_ID, end_date))
    
    conn.commit()
    conn.close()

# ============================================
#  ПОЛЬЗОВАТЕЛИ
# ============================================

def create_user(user_id, username):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR IGNORE INTO users (user_id, username) 
        VALUES (?, ?)
    ''', (user_id, username))
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
    cursor.execute('''
        INSERT OR REPLACE INTO nicknames (user_id, nickname, updated_at) 
        VALUES (?, ?, CURRENT_TIMESTAMP)
    ''', (user_id, nickname))
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
    cursor.execute('''
        INSERT OR REPLACE INTO subscriptions (user_id, end_date, updated_at) 
        VALUES (?, ?, CURRENT_TIMESTAMP)
    ''', (user_id, end_date))
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

# ============================================
#  КАНАЛЫ
# ============================================

def add_channel_db(channel_id, channel_name, owner_id, category, subscription_end, privacy='public', subscribers=0):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO channels 
        (channel_id, channel_name, owner_id, category, subscription_end, privacy, subscribers) 
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (channel_id, channel_name, owner_id, category, subscription_end, privacy, subscribers))
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

def get_channel_by_id(channel_id):
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

def get_channel_subscribers_count(channel_id):
    conn = get_db()
    cursor = conn.cursor()
    result = cursor.execute('SELECT subscribers FROM channels WHERE channel_id = ?', (channel_id,)).fetchone()
    conn.close()
    return result['subscribers'] if result else 0

def admin_delete_channel(channel_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM channels WHERE channel_id = ?', (channel_id,))
    cursor.execute('DELETE FROM blacklist_words WHERE channel_id = ?', (channel_id,))
    cursor.execute('DELETE FROM scheduled_posts WHERE channel_id = ?', (channel_id,))
    conn.commit()
    conn.close()

# ============================================
#  БЛЭКЛИСТ
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
    cursor.execute('''
        INSERT INTO scheduled_posts (channel_id, post_text, post_media, scheduled_time) 
        VALUES (?, ?, ?, ?)
    ''', (channel_id, text, media, scheduled_time))
    conn.commit()
    conn.close()

def get_scheduled_posts(channel_id):
    conn = get_db()
    cursor = conn.cursor()
    posts = cursor.execute('''
        SELECT * FROM scheduled_posts 
        WHERE channel_id = ? AND is_sent = 0 AND scheduled_time > datetime('now')
        ORDER BY scheduled_time ASC
    ''', (channel_id,)).fetchall()
    conn.close()
    return posts

def get_all_scheduled_posts():
    conn = get_db()
    cursor = conn.cursor()
    posts = cursor.execute('''
        SELECT * FROM scheduled_posts 
        WHERE is_sent = 0 AND scheduled_time > datetime('now')
        ORDER BY scheduled_time ASC
    ''',).fetchall()
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
    cursor.execute('''
        INSERT INTO promo_codes (code, name, max_uses, subscription_days) 
        VALUES (?, ?, ?, ?)
    ''', (code, name, max_uses, days))
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
#  НАСТРОЙКИ (ГЛОБАЛЬНЫЕ)
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
#  ТЕСТЕРЫ
# ============================================

def is_tester(user_id):
    return get_setting(f"tester_{user_id}") == '1'

def get_all_testers():
    conn = get_db()
    cursor = conn.cursor()
    testers = cursor.execute("SELECT key FROM settings WHERE key LIKE 'tester_%' AND value = '1'").fetchall()
    conn.close()
    return [int(t['key'].replace('tester_', '')) for t in testers]

# ============================================
#  НАСТРОЙКИ КАНАЛОВ
# ============================================

def get_welcome_text(channel_id):
    return get_setting(f"welcome_{channel_id}")

def set_welcome_text(channel_id, text):
    set_setting(f"welcome_{channel_id}", text)

def get_farewell_text(channel_id):
    return get_setting(f"farewell_{channel_id}")

def set_farewell_text(channel_id, text):
    set_setting(f"farewell_{channel_id}", text)

def get_captcha_settings(channel_id):
    q = get_setting(f"captcha_{channel_id}")
    if q:
        try:
            return json.loads(q)
        except:
            return None
    return None

def set_captcha_settings(channel_id, question, answers):
    set_setting(f"captcha_{channel_id}", json.dumps({'question': question, 'answers': answers}))

def del_captcha_settings(channel_id):
    set_setting(f"captcha_{channel_id}", None)

def get_auto_approve(channel_id):
    return get_setting(f"auto_approve_{channel_id}") == '1'

def set_auto_approve(channel_id, enabled):
    set_setting(f"auto_approve_{channel_id}", '1' if enabled else '0')

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
    cursor.execute('''
        INSERT INTO vp_posts (user_id, channel_id, media, text, is_adult, category)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, channel_id, media, text, 1 if is_adult else 0, category))
    conn.commit()
    conn.close()
    return True

def get_vp_posts(limit=3, offset=0, adult_only=True):
    conn = get_db()
    cursor = conn.cursor()
    
    if adult_only:
        posts = cursor.execute('''
            SELECT * FROM vp_posts 
            WHERE is_adult = 0
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        ''', (limit, offset)).fetchall()
    else:
        posts = cursor.execute('''
            SELECT * FROM vp_posts 
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        ''', (limit, offset)).fetchall()
    
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
    result = cursor.execute('''
        SELECT created_at FROM vp_posts 
        WHERE user_id = ? 
        ORDER BY created_at DESC 
        LIMIT 1
    ''', (user_id,)).fetchone()
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
#  БЕТА-ФИЧИ
# ============================================

def add_beta_feature(name, code, description):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO beta_features (name, code, description, status)
        VALUES (?, ?, ?, 'testing')
    ''', (name, code, description))
    conn.commit()
    conn.close()
    return cursor.lastrowid

def get_beta_features(status='testing'):
    conn = get_db()
    cursor = conn.cursor()
    if status == 'all':
        features = cursor.execute('SELECT * FROM beta_features ORDER BY created_at DESC').fetchall()
    else:
        features = cursor.execute('SELECT * FROM beta_features WHERE status = ? ORDER BY created_at DESC', (status,)).fetchall()
    conn.close()
    return features

def get_beta_feature(feature_id):
    conn = get_db()
    cursor = conn.cursor()
    feature = cursor.execute('SELECT * FROM beta_features WHERE id = ?', (feature_id,)).fetchone()
    conn.close()
    return feature

def promote_beta_feature(feature_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE beta_features SET status = 'promoted', promoted_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (feature_id,))
    conn.commit()
    conn.close()

def delete_beta_feature(feature_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM beta_features WHERE id = ?', (feature_id,))
    conn.commit()
    conn.close()

# ============================================
#  ЛОГ ОБНОВЛЕНИЙ
# ============================================

def add_update_log(version, changes):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO update_log (version, changes)
        VALUES (?, ?)
    ''', (version, changes))
    conn.commit()
    conn.close()

def get_update_logs(limit=20):
    conn = get_db()
    cursor = conn.cursor()
    logs = cursor.execute('''
        SELECT * FROM update_log 
        ORDER BY created_at DESC 
        LIMIT ?
    ''', (limit,)).fetchall()
    conn.close()
    return logs

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
    cursor.execute('DELETE FROM settings WHERE key LIKE ?', (f"tester_{user_id}",))
    cursor.execute('DELETE FROM vp_posts WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()
    return True