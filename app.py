import os
import threading
import time
from main import main

def run_flask():
    """Запускаем Flask для порта"""
    from flask import Flask
    app = Flask(__name__)
    
    @app.route('/')
    def index():
        return "Bot is running!"
    
    @app.route('/health')
    def health():
        return "OK"
    
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

if __name__ == '__main__':
    # Запускаем Flask в фоновом потоке
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    # Бота запускаем в основном потоке
    main()