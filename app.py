import os
import threading
from flask import Flask
from main import main

app = Flask(__name__)

@app.route('/')
def index():
    return "Bot is running!"

@app.route('/health')
def health():
    return "OK"

def start_bot():
    main()  # теперь это функция из main.py

if __name__ == '__main__':
    # Запускаем бота в отдельном потоке
    bot_thread = threading.Thread(target=start_bot, daemon=True)
    bot_thread.start()
    
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)