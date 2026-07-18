import os
import threading
from main import main
from flask import Flask

app = Flask(__name__)

@app.route('/')
def index():
    return "Bot is running!"

@app.route('/health')
def health():
    return "OK"

if __name__ == '__main__':
    # Запускаем бота в отдельном потоке
    thread = threading.Thread(target=main)
    thread.start()
    # Запускаем Flask для поддержки порта
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))