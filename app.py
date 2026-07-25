import os
import threading
import logging
from flask import Flask, jsonify
from config import PORT, USE_WEBHOOK, WEBHOOK_URL
from db import get_db, put_db, init_db

logger = logging.getLogger(__name__)
app = Flask(__name__)

@app.route('/')
def index():
    return jsonify({"status": "Bot is running!", "webhook": USE_WEBHOOK})

@app.route('/health')
def health():
    """Health check с проверкой соединения с БД."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT 1')
        cursor.fetchone()
        put_db(conn)
        return jsonify({"status": "OK", "database": "connected"})
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({"status": "ERROR", "database": str(e)}), 500

def run_flask():
    logger.info(f"Starting Flask on port {PORT}")
    app.run(host='0.0.0.0', port=PORT, threaded=True)

def start_flask_thread():
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    return flask_thread