import psycopg2
import psycopg2.extras
import psycopg2.pool
import json
import os
import logging
from datetime import datetime, timedelta, timezone
from config import OWNER_ID, DATABASE_URL, logger as _logger

logger = logging.getLogger(__name__)

# ============================================
#  ПУЛ СОЕДИНЕНИЙ (вместо нового TCP на каждый запрос)
# ============================================
_pool = None

def _get_pool():
    global _pool
    if _pool is None:
        url = DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        try:
            _pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=20,
                dsn=url
            )
            logger.info("Connection pool created (min=1, max=20)")
        except Exception as e:
            logger.error(f"Failed to create connection pool: {e}")
            raise
    return _pool

def get_db():
    """Получить соединение из пула. НЕ ЗАБУДЬТЕ вернуть через put_db(conn)!"""
    return _get_pool().getconn()

def put_db(conn):
    """Вернуть соединение в пул."""
    if conn:
        _get_pool().putconn(conn)

# ============================================
#  ИНИЦИАЛИЗАЦИЯ БД
# ============================================
def init_db():
    conn = get_db()
    try:
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                language TEXT DEFAULT 'ru',
                timezone TEXT DEFAULT 'UTC',
                registered INTEGER DEFAULT 0,
                adult_verified INTEGER DEFAULT 0,
                name_changes INTEGER DEFAULT 0,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS nicknames (
                user_id BIGINT PRIMARY KEY,
                nickname TEXT UNIQUE,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subscriptions (
                user_id BIGINT PRIMARY KEY,
                end_date TEXT,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS payments_history (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                amount INTEGER,
                currency TEXT DEFAULT 'XTR',
                status TEXT,
                payment_id TEXT,
                plan_type TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS channels (
                id SERIAL PRIMARY KEY,
                channel_id BIGINT UNIQUE,
                channel_name TEXT,
                owner_id BIGINT,
                category TEXT,
                privacy TEXT DEFAULT 'public',
                subscribers INTEGER DEFAULT 0,
                linked_group_id BIGINT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS blacklist_words (
                id SERIAL PRIMARY KEY,
                channel_id BIGINT,
                word TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scheduled_posts (
                id SERIAL PRIMARY KEY,
                channel_id BIGINT,
                post_data TEXT,
                scheduled_time TIMESTAMP WITH TIME ZONE,
                is_sent INTEGER DEFAULT 0,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS promo_codes (
                id SERIAL PRIMARY KEY,
                code TEXT UNIQUE,
                name TEXT,
                max_uses INTEGER,
                subscription_days INTEGER,
                uses INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS comments_stats (
                id SERIAL PRIMARY KEY,
                channel_id BIGINT,
                user_id BIGINT,
                message_id BIGINT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS channel_subscribers_snapshots (
                id SERIAL PRIMARY KEY,
                channel_id BIGINT,
                subscribers INTEGER,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS crosspost_targets (
                id SERIAL PRIMARY KEY,
                from_channel_id BIGINT,
                to_channel_id BIGINT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(from_channel_id, to_channel_id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS giveaways (
                id SERIAL PRIMARY KEY,
                channel_id BIGINT,
                title TEXT,
                winners_count INTEGER,
                message_id BIGINT,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS giveaway_participants (
                id SERIAL PRIMARY KEY,
                giveaway_id INTEGER,
                user_id BIGINT,
                username TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(giveaway_id, user_id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pending_payments (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                plan_type TEXT,
                amount_rub INTEGER,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notifications (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                type TEXT,
                content TEXT,
                link_data TEXT,
                read INTEGER DEFAULT 0,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS blocked_users (
                user_id BIGINT PRIMARY KEY,
                blocked_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                reason TEXT
            )
        ''')

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_comments_channel_created ON comments_stats(channel_id, created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_scheduled_due ON scheduled_posts(is_sent, scheduled_time)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_channels_owner ON channels(owner_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_payments_user ON payments_history(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_notif_user_read ON notifications(user_id, read)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_channel ON channel_subscribers_snapshots(channel_id, created_at)")

        cursor.execute("SELECT key, value FROM settings WHERE key LIKE 'blocked_%' AND value = '1'")
        old_blocks = cursor.fetchall()
        for row in old_blocks:
            try:
                uid = int(row[0].replace("blocked_", ""))
                cursor.execute(
                    "INSERT INTO blocked_users (user_id) VALUES (%s) ON CONFLICT DO NOTHING", (uid,)
                )
            except ValueError:
                pass
        if old_blocks:
            cursor.execute("DELETE FROM settings WHERE key LIKE 'blocked_%'")
            logger.info(f"Migrated {len(old_blocks)} old blocks to blocked_users table")

        conn.commit()
        logger.info("Database initialized")
    except Exception as e:
        conn.rollback()
        logger.error(f"init_db error: {e}")
        raise
    finally:
        put_db(conn)

    _ensure_owner()

def _ensure_owner():
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            '''INSERT INTO users (user_id, username, registered, adult_verified, timezone)
            VALUES (%s, %s, 1, 1, %s)
            ON CONFLICT (user_id) DO UPDATE SET registered = 1, adult_verified = 1''',
            (OWNER_ID, 'owner', 'Europe/Moscow')
        )
        end_date = (datetime.now(timezone.utc) + timedelta(days=3650)).strftime('%Y-%m-%d')
        cursor.execute(
            '''INSERT INTO subscriptions (user_id, end_date) VALUES (%s, %s)
            ON CONFLICT (user_id) DO UPDATE SET end_date = EXCLUDED.end_date''',
            (OWNER_ID, end_date)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"_ensure_owner error: {e}")
    finally:
        put_db(conn)

def create_user(user_id, username):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO users (user_id, username) VALUES (%s, %s) ON CONFLICT (user_id) DO NOTHING',
            (user_id, username)
        )
        conn.commit()
    finally:
        put_db(conn)

def get_user(user_id):
    conn = get_db()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute('SELECT * FROM users WHERE user_id = %s', (user_id,))
        return cursor.fetchone()
    finally:
        put_db(conn)

def get_all_users():
    conn = get_db()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute('SELECT * FROM users ORDER BY created_at DESC')
        return cursor.fetchall()
    finally:
        put_db(conn)

def get_all_users_with_sub():
    conn = get_db()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute('''
            SELECT u.* FROM users u
            JOIN subscriptions s ON u.user_id = s.user_id
            WHERE s.end_date >= CURRENT_DATE
        ''')
        return cursor.fetchall()
    finally:
        put_db(conn)

def get_all_users_without_sub():
    conn = get_db()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute('''
            SELECT u.* FROM users u
            LEFT JOIN subscriptions s ON u.user_id = s.user_id
            WHERE s.end_date IS NULL OR s.end_date < CURRENT_DATE
        ''')
        return cursor.fetchall()
    finally:
        put_db(conn)

def get_user_language(user_id):
    user = get_user(user_id)
    return user.get('language', 'ru') if user else 'ru'

def set_user_language(user_id, language):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET language = %s WHERE user_id = %s', (language, user_id))
        conn.commit()
    finally:
        put_db(conn)

def get_user_timezone(user_id):
    user = get_user(user_id)
    return user.get('timezone') if user and user.get('timezone') else 'UTC'

def set_user_timezone(user_id, tz):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET timezone = %s WHERE user_id = %s', (tz, user_id))
        conn.commit()
    finally:
        put_db(conn)

def is_registered(user_id):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT registered FROM users WHERE user_id = %s', (user_id,))
        row = cursor.fetchone()
        return row is not None and row[0] == 1
    finally:
        put_db(conn)

def set_registered(user_id):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET registered = 1 WHERE user_id = %s', (user_id,))
        conn.commit()
    finally:
        put_db(conn)

def is_adult(user_id):
    if user_id == OWNER_ID:
        return True
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT adult_verified FROM users WHERE user_id = %s', (user_id,))
        row = cursor.fetchone()
        return row is not None and row[0] == 1
    finally:
        put_db(conn)

def set_adult(user_id, value):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET adult_verified = %s WHERE user_id = %s', (1 if value else 0, user_id))
        conn.commit()
    finally:
        put_db(conn)

def get_name_changes(user_id):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT name_changes FROM users WHERE user_id = %s', (user_id,))
        row = cursor.fetchone()
        return row[0] if row else 0
    finally:
        put_db(conn)

def increment_name_changes(user_id):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET name_changes = name_changes + 1 WHERE user_id = %s', (user_id,))
        conn.commit()
    finally:
        put_db(conn)

def delete_user_profile(user_id):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT channel_id FROM channels WHERE owner_id = %s', (user_id,))
        channels = [r[0] for r in cursor.fetchall()]

        for ch_id in channels:
            cursor.execute('DELETE FROM blacklist_words WHERE channel_id = %s', (ch_id,))
            cursor.execute('DELETE FROM scheduled_posts WHERE channel_id = %s', (ch_id,))
            cursor.execute('DELETE FROM comments_stats WHERE channel_id = %s', (ch_id,))
            cursor.execute('DELETE FROM channel_subscribers_snapshots WHERE channel_id = %s', (ch_id,))
            cursor.execute('DELETE FROM crosspost_targets WHERE from_channel_id = %s OR to_channel_id = %s', (ch_id, ch_id))
            cursor.execute('DELETE FROM giveaways WHERE channel_id = %s', (ch_id,))

        cursor.execute('DELETE FROM giveaway_participants WHERE user_id = %s', (user_id,))
        cursor.execute('DELETE FROM pending_payments WHERE user_id = %s', (user_id,))
        cursor.execute('DELETE FROM notifications WHERE user_id = %s', (user_id,))
        cursor.execute('DELETE FROM payments_history WHERE user_id = %s', (user_id,))
        cursor.execute('DELETE FROM channels WHERE owner_id = %s', (user_id,))
        cursor.execute('DELETE FROM subscriptions WHERE user_id = %s', (user_id,))
        cursor.execute('DELETE FROM nicknames WHERE user_id = %s', (user_id,))
        cursor.execute('DELETE FROM blocked_users WHERE user_id = %s', (user_id,))
        cursor.execute('DELETE FROM users WHERE user_id = %s', (user_id,))
        conn.commit()
        logger.info(f"User {user_id} profile fully deleted")
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"delete_user_profile error: {e}")
        return False
    finally:
        put_db(conn)

def get_user_nickname(user_id):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT nickname FROM nicknames WHERE user_id = %s', (user_id,))
        row = cursor.fetchone()
        return row[0] if row else None
    finally:
        put_db(conn)

def set_user_nickname(user_id, nickname):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO nicknames (user_id, nickname, updated_at)
            VALUES (%s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id) DO UPDATE SET nickname = EXCLUDED.nickname, updated_at = CURRENT_TIMESTAMP
        ''', (user_id, nickname))
        conn.commit()
    finally:
        put_db(conn)

def is_nickname_taken(nickname):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM nicknames WHERE nickname = %s', (nickname,))
        return cursor.fetchone() is not None
    finally:
        put_db(conn)

def get_subscription_end(user_id):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT end_date FROM subscriptions WHERE user_id = %s', (user_id,))
        row = cursor.fetchone()
        return row[0] if row else None
    finally:
        put_db(conn)

def set_subscription(user_id, end_date):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO subscriptions (user_id, end_date, updated_at)
            VALUES (%s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id) DO UPDATE SET end_date = EXCLUDED.end_date, updated_at = CURRENT_TIMESTAMP
        ''', (user_id, end_date))
        conn.commit()
    finally:
        put_db(conn)

def extend_subscription(user_id, days):
    end_date = get_subscription_end(user_id)
    base = datetime.now(timezone.utc)
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d').replace(tzinfo=timezone.utc)
            if end_dt.date() >= base.date():
                base = end_dt
        except Exception:
            pass
    new_end = (base + timedelta(days=days)).strftime('%Y-%m-%d')
    set_subscription(user_id, new_end)

def is_subscribed(user_id):
    if user_id == OWNER_ID:
        return True
    end_date = get_subscription_end(user_id)
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
            return end_dt >= datetime.now(timezone.utc).date()
        except Exception:
            return False
    return False

def add_payment_history(user_id, amount, status, payment_id, plan_type):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO payments_history (user_id, amount, currency, status, payment_id, plan_type)
            VALUES (%s, %s, 'XTR', %s, %s, %s)
        ''', (user_id, amount, status, payment_id, plan_type))
        conn.commit()
    finally:
        put_db(conn)

def add_channel_db(channel_id, channel_name, owner_id, category, privacy='public', subscribers=0, linked_group_id=None):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT owner_id FROM channels WHERE channel_id = %s', (channel_id,))
        existing = cursor.fetchone()
        if existing and existing[0] != owner_id:
            logger.warning(f"Channel {channel_id} already owned by {existing[0]}, rejecting takeover by {owner_id}")
            return False

        cursor.execute('''
            INSERT INTO channels (channel_id, channel_name, owner_id, category, privacy, subscribers, linked_group_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (channel_id) DO UPDATE SET
                channel_name = EXCLUDED.channel_name,
                category = EXCLUDED.category,
                privacy = EXCLUDED.privacy,
                subscribers = EXCLUDED.subscribers,
                linked_group_id = EXCLUDED.linked_group_id
        ''', (channel_id, channel_name, owner_id, category, privacy, subscribers, linked_group_id))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"add_channel_db error: {e}")
        return False
    finally:
        put_db(conn)

def del_channel_db(channel_id, owner_id=None):
    conn = get_db()
    try:
        cursor = conn.cursor()
        if owner_id:
            cursor.execute('DELETE FROM channels WHERE channel_id = %s AND owner_id = %s', (channel_id, owner_id))
        else:
            cursor.execute('DELETE FROM channels WHERE channel_id = %s', (channel_id,))
        conn.commit()
    finally:
        put_db(conn)

def get_user_channels(owner_id):
    conn = get_db()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute('SELECT * FROM channels WHERE owner_id = %s ORDER BY created_at DESC', (owner_id,))
        return cursor.fetchall()
    finally:
        put_db(conn)

def get_all_channels():
    conn = get_db()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute('SELECT * FROM channels ORDER BY created_at DESC')
        return cursor.fetchall()
    finally:
        put_db(conn)

def get_channel_by_channel_id(channel_id):
    conn = get_db()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute('SELECT * FROM channels WHERE channel_id = %s', (channel_id,))
        return cursor.fetchone()
    finally:
        put_db(conn)

def get_channel_by_linked_group(group_id):
    conn = get_db()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute('SELECT * FROM channels WHERE linked_group_id = %s', (group_id,))
        return cursor.fetchone()
    finally:
        put_db(conn)

def update_channel_subscribers_db(channel_id, subscribers):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('UPDATE channels SET subscribers = %s WHERE channel_id = %s', (subscribers, channel_id))
        conn.commit()
    finally:
        put_db(conn)

def add_subscribers_snapshot(channel_id, subscribers):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO channel_subscribers_snapshots (channel_id, subscribers) VALUES (%s, %s)',
            (channel_id, subscribers)
        )
        conn.commit()
    finally:
        put_db(conn)

def get_subscribers_growth(channel_id, days=7):
    conn = get_db()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute('''
            SELECT subscribers, created_at FROM channel_subscribers_snapshots
            WHERE channel_id = %s AND created_at >= CURRENT_TIMESTAMP - INTERVAL '%s days'
            ORDER BY created_at ASC
        ''', (channel_id, days))
        return cursor.fetchall()
    finally:
        put_db(conn)

def get_avg_views_estimate(channel_id):
    return 0

def get_channel_privacy(channel_id):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT privacy FROM channels WHERE channel_id = %s', (channel_id,))
        row = cursor.fetchone()
        return row[0] if row else 'public'
    finally:
        put_db(conn)

def set_channel_privacy(channel_id, privacy):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('UPDATE channels SET privacy = %s WHERE channel_id = %s', (privacy, channel_id))
        conn.commit()
    finally:
        put_db(conn)

def admin_delete_channel(channel_id):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM channels WHERE channel_id = %s', (channel_id,))
        cursor.execute('DELETE FROM blacklist_words WHERE channel_id = %s', (channel_id,))
        cursor.execute('DELETE FROM scheduled_posts WHERE channel_id = %s', (channel_id,))
        cursor.execute('DELETE FROM comments_stats WHERE channel_id = %s', (channel_id,))
        cursor.execute('DELETE FROM channel_subscribers_snapshots WHERE channel_id = %s', (channel_id,))
        cursor.execute('DELETE FROM crosspost_targets WHERE from_channel_id = %s OR to_channel_id = %s', (channel_id, channel_id))
        cursor.execute('DELETE FROM giveaways WHERE channel_id = %s', (channel_id,))
        conn.commit()
    finally:
        put_db(conn)

def set_channel_linked_group_db(channel_id, group_id):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('UPDATE channels SET linked_group_id = %s WHERE channel_id = %s', (group_id, channel_id))
        conn.commit()
    finally:
        put_db(conn)

def get_auto_approve(channel_id):
    return get_setting(f"auto_approve_{channel_id}") == '1'

def set_auto_approve(channel_id, enabled):
    set_setting(f"auto_approve_{channel_id}", '1' if enabled else '0')

def set_welcome_text(channel_id, text):
    set_setting(f"welcome_text_{channel_id}", text)

def get_welcome_text(channel_id):
    return get_setting(f"welcome_text_{channel_id}")

def set_farewell_text(channel_id, text):
    set_setting(f"farewell_text_{channel_id}", text)

def get_farewell_text(channel_id):
    return get_setting(f"farewell_text_{channel_id}")

def set_captcha_settings(channel_id, question, correct_answer):
    data = json.dumps({"question": question, "correct": correct_answer})
    set_setting(f"captcha_{channel_id}", data)

def get_captcha_settings(channel_id):
    data = get_setting(f"captcha_{channel_id}")
    if data:
        try:
            return json.loads(data)
        except Exception:
            return None
    return None

def del_captcha_settings(channel_id):
    set_setting(f"captcha_{channel_id}", None)

def add_blacklist_word(channel_id, word):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('INSERT INTO blacklist_words (channel_id, word) VALUES (%s, %s)', (channel_id, word.lower()))
        conn.commit()
    finally:
        put_db(conn)

def get_blacklist_words(channel_id):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT word FROM blacklist_words WHERE channel_id = %s', (channel_id,))
        return [r[0] for r in cursor.fetchall()]
    finally:
        put_db(conn)

def del_blacklist_word(channel_id, word):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM blacklist_words WHERE channel_id = %s AND word = %s', (channel_id, word.lower()))
        conn.commit()
    finally:
        put_db(conn)

def add_scheduled_post(channel_id, post_data, scheduled_time):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO scheduled_posts (channel_id, post_data, scheduled_time) VALUES (%s, %s, %s) RETURNING id',
            (channel_id, post_data, scheduled_time)
        )
        row = cursor.fetchone()
        conn.commit()
        return row[0]
    finally:
        put_db(conn)

def get_scheduled_posts(channel_id):
    conn = get_db()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(
            'SELECT * FROM scheduled_posts WHERE channel_id = %s AND is_sent = 0 ORDER BY scheduled_time ASC',
            (channel_id,)
        )
        return cursor.fetchall()
    finally:
        put_db(conn)

def get_all_scheduled_posts():
    conn = get_db()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute('SELECT * FROM scheduled_posts WHERE is_sent = 0 ORDER BY scheduled_time ASC')
        return cursor.fetchall()
    finally:
        put_db(conn)

def get_due_scheduled_posts():
    conn = get_db()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(
            'SELECT * FROM scheduled_posts WHERE is_sent = 0 AND scheduled_time <= CURRENT_TIMESTAMP ORDER BY scheduled_time ASC'
        )
        return cursor.fetchall()
    finally:
        put_db(conn)

def del_scheduled_post(post_id):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM scheduled_posts WHERE id = %s', (post_id,))
        conn.commit()
    finally:
        put_db(conn)

def mark_post_sent(post_id):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('UPDATE scheduled_posts SET is_sent = 1 WHERE id = %s', (post_id,))
        conn.commit()
    finally:
        put_db(conn)

def create_promo_code(code, name, max_uses, days):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO promo_codes (code, name, max_uses, subscription_days) VALUES (%s, %s, %s, %s)',
            (code, name, max_uses, days)
        )
        conn.commit()
    finally:
        put_db(conn)

def get_promo_code(code):
    conn = get_db()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute('SELECT * FROM promo_codes WHERE code = %s AND is_active = 1', (code,))
        return cursor.fetchone()
    finally:
        put_db(conn)

def use_promo_code(code):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('UPDATE promo_codes SET uses = uses + 1 WHERE code = %s', (code,))
        conn.commit()
    finally:
        put_db(conn)

def get_all_promo_codes():
    conn = get_db()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute('SELECT * FROM promo_codes ORDER BY created_at DESC')
        return cursor.fetchall()
    finally:
        put_db(conn)

def del_promo_code(code):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM promo_codes WHERE code = %s', (code,))
        conn.commit()
    finally:
        put_db(conn)

def get_setting(key):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT value FROM settings WHERE key = %s', (key,))
        row = cursor.fetchone()
        return row[0] if row else None
    finally:
        put_db(conn)

def set_setting(key, value):
    conn = get_db()
    try:
        cursor = conn.cursor()
        if value is None:
            cursor.execute('DELETE FROM settings WHERE key = %s', (key,))
        else:
            cursor.execute('''
                INSERT INTO settings (key, value) VALUES (%s, %s)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
            ''', (key, value))
        conn.commit()
    finally:
        put_db(conn)

def get_vp_timer():
    timer = get_setting("vp_timer")
    if timer:
        try:
            return int(timer)
        except ValueError:
            pass
    return 12

def set_vp_timer(hours):
    set_setting("vp_timer", str(hours))

def add_notification(user_id, notif_type, content, link_data=None):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO notifications (user_id, type, content, link_data) VALUES (%s, %s, %s, %s)',
            (user_id, notif_type, content, link_data)
        )
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"add_notification error: {e}")
        return False
    finally:
        put_db(conn)

def get_user_notifications(user_id, unread_only=True):
    conn = get_db()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        if unread_only:
            cursor.execute(
                'SELECT * FROM notifications WHERE user_id = %s AND read = 0 ORDER BY created_at DESC',
                (user_id,)
            )
        else:
            cursor.execute(
                'SELECT * FROM notifications WHERE user_id = %s ORDER BY created_at DESC',
                (user_id,)
            )
        return cursor.fetchall()
    finally:
        put_db(conn)

def mark_notification_read(notif_id):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('UPDATE notifications SET read = 1 WHERE id = %s', (notif_id,))
        conn.commit()
    finally:
        put_db(conn)

def delete_notification(notif_id):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM notifications WHERE id = %s', (notif_id,))
        conn.commit()
    finally:
        put_db(conn)

def mark_all_notifications_read(user_id):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('UPDATE notifications SET read = 1 WHERE user_id = %s', (user_id,))
        conn.commit()
    finally:
        put_db(conn)

def get_blocked_users():
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM blocked_users')
        return [r[0] for r in cursor.fetchall()]
    finally:
        put_db(conn)

def block_user(user_id, reason=None):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO blocked_users (user_id, reason) VALUES (%s, %s) ON CONFLICT (user_id) DO UPDATE SET reason = EXCLUDED.reason',
            (user_id, reason)
        )
        conn.commit()
        return True
    finally:
        put_db(conn)

def unblock_user(user_id):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM blocked_users WHERE user_id = %s', (user_id,))
        conn.commit()
        return True
    finally:
        put_db(conn)

def is_user_blocked(user_id):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT 1 FROM blocked_users WHERE user_id = %s', (user_id,))
        return cursor.fetchone() is not None
    finally:
        put_db(conn)

def add_comment_stat(channel_id, user_id, message_id):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO comments_stats (channel_id, user_id, message_id) VALUES (%s, %s, %s)',
            (channel_id, user_id, message_id)
        )
        conn.commit()
    finally:
        put_db(conn)

def get_top_commenters(channel_id, period='all'):
    conn = get_db()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        if period == 'day':
            cursor.execute('''
                SELECT user_id, COUNT(*) as cnt FROM comments_stats 
                WHERE channel_id = %s AND created_at >= CURRENT_TIMESTAMP - INTERVAL '1 day'
                GROUP BY user_id ORDER BY cnt DESC LIMIT 20
            ''', (channel_id,))
        elif period == 'month':
            cursor.execute('''
                SELECT user_id, COUNT(*) as cnt FROM comments_stats 
                WHERE channel_id = %s AND created_at >= CURRENT_TIMESTAMP - INTERVAL '30 days'
                GROUP BY user_id ORDER BY cnt DESC LIMIT 20
            ''', (channel_id,))
        else:
            cursor.execute('''
                SELECT user_id, COUNT(*) as cnt FROM comments_stats 
                WHERE channel_id = %s 
                GROUP BY user_id ORDER BY cnt DESC LIMIT 20
            ''', (channel_id,))
        rows = cursor.fetchall()
        return [(r['user_id'], r['cnt']) for r in rows]
    finally:
        put_db(conn)

def get_channel_stats(channel_id, period='week'):
    conn = get_db()
    try:
        cursor = conn.cursor()
        if period == 'week':
            cursor.execute(
                'SELECT COUNT(*) FROM comments_stats WHERE channel_id = %s AND created_at >= CURRENT_TIMESTAMP - INTERVAL '7 days'',
                (channel_id,)
            )
        elif period == 'month':
            cursor.execute(
                'SELECT COUNT(*) FROM comments_stats WHERE channel_id = %s AND created_at >= CURRENT_TIMESTAMP - INTERVAL '30 days'',
                (channel_id,)
            )
        else:
            cursor.execute('SELECT COUNT(*) FROM comments_stats WHERE channel_id = %s', (channel_id,))
        return cursor.fetchone()[0]
    finally:
        put_db(conn)

def add_crosspost_target(from_channel_id, to_channel_id):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO crosspost_targets (from_channel_id, to_channel_id) VALUES (%s, %s) ON CONFLICT DO NOTHING',
            (from_channel_id, to_channel_id)
        )
        conn.commit()
    finally:
        put_db(conn)

def remove_crosspost_target(from_channel_id, to_channel_id):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            'DELETE FROM crosspost_targets WHERE from_channel_id = %s AND to_channel_id = %s',
            (from_channel_id, to_channel_id)
        )
        conn.commit()
    finally:
        put_db(conn)

def get_crosspost_targets(from_channel_id):
    conn = get_db()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute('SELECT * FROM crosspost_targets WHERE from_channel_id = %s', (from_channel_id,))
        return cursor.fetchall()
    finally:
        put_db(conn)

def create_giveaway(channel_id, title, winners_count, message_id=None):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO giveaways (channel_id, title, winners_count, message_id) VALUES (%s, %s, %s, %s) RETURNING id',
            (channel_id, title, winners_count, message_id)
        )
        row = cursor.fetchone()
        conn.commit()
        return row[0]
    finally:
        put_db(conn)

def get_active_giveaways(channel_id):
    conn = get_db()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute('SELECT * FROM giveaways WHERE channel_id = %s AND status = %s', (channel_id, 'active'))
        return cursor.fetchall()
    finally:
        put_db(conn)

def get_giveaway(giveaway_id):
    conn = get_db()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute('SELECT * FROM giveaways WHERE id = %s', (giveaway_id,))
        return cursor.fetchone()
    finally:
        put_db(conn)

def close_giveaway(giveaway_id):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('UPDATE giveaways SET status = %s WHERE id = %s', ('closed', giveaway_id))
        conn.commit()
    finally:
        put_db(conn)

def add_giveaway_participant(giveaway_id, user_id, username):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO giveaway_participants (giveaway_id, user_id, username) VALUES (%s, %s, %s)
            ON CONFLICT DO NOTHING
        ''', (giveaway_id, user_id, username))
        conn.commit()
    finally:
        put_db(conn)

def get_giveaway_participants(giveaway_id):
    conn = get_db()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute('SELECT * FROM giveaway_participants WHERE giveaway_id = %s', (giveaway_id,))
        return cursor.fetchall()
    finally:
        put_db(conn)

def add_pending_payment(user_id, plan_type, amount_rub):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO pending_payments (user_id, plan_type, amount_rub) VALUES (%s, %s, %s) RETURNING id',
            (user_id, plan_type, amount_rub)
        )
        row = cursor.fetchone()
        conn.commit()
        return row[0]
    finally:
        put_db(conn)

def get_pending_payment(payment_id):
    conn = get_db()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute('SELECT * FROM pending_payments WHERE id = %s', (payment_id,))
        return cursor.fetchone()
    finally:
        put_db(conn)

def update_pending_payment_status(payment_id, status):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('UPDATE pending_payments SET status = %s WHERE id = %s', (status, payment_id))
        conn.commit()
    finally:
        put_db(conn)

def get_pending_payments_for_user(user_id):
    conn = get_db()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(
            'SELECT * FROM pending_payments WHERE user_id = %s AND status = %s ORDER BY created_at DESC',
            (user_id, 'pending')
        )
        return cursor.fetchall()
    finally:
        put_db(conn)

def is_bot_admin(user_id):
    return get_setting(f"bot_admin_{user_id}") == '1'

def add_bot_admin(user_id):
    set_setting(f"bot_admin_{user_id}", '1')

def remove_bot_admin(user_id):
    set_setting(f"bot_admin_{user_id}", '0')

def cleanup_old_data(days=90):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM comments_stats WHERE created_at < CURRENT_TIMESTAMP - INTERVAL '%s days'', (days,))
        cursor.execute('DELETE FROM channel_subscribers_snapshots WHERE created_at < CURRENT_TIMESTAMP - INTERVAL '%s days'', (days,))
        cursor.execute('DELETE FROM giveaway_participants WHERE created_at < CURRENT_TIMESTAMP - INTERVAL '%s days'', (days,))
        cursor.execute('DELETE FROM notifications WHERE read = 1 AND created_at < CURRENT_TIMESTAMP - INTERVAL '%s days'', (days,))
        conn.commit()
        logger.info(f"Cleanup completed for data older than {days} days")
    except Exception as e:
        conn.rollback()
        logger.error(f"cleanup_old_data error: {e}")
    finally:
        put_db(conn)