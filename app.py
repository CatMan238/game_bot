import os
import threading
from flask import Flask, request
from main import main, application, BOT_TOKEN

app = Flask(__name__)

@app.route('/')
def index():
    return "Bot is running!"

@app.route('/webhook', methods=['POST'])
def webhook():
    """Обработка входящих обновлений через webhook"""
    if request.method == 'POST':
        update = request.get_json(force=True)
        application.process_update(update)
        return 'ok', 200

@app.route('/set_webhook')
def set_webhook():
    """Установить webhook при запуске"""
    import requests
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
    webhook_url = f"https://{os.environ.get('RENDER_EXTERNAL_URL', 'localhost')}/webhook"
    resp = requests.post(url, json={'url': webhook_url})
    return resp.json()

if __name__ == '__main__':
    # Запускаем Flask
    port = int(os.environ.get('PORT', 10000))
    # Устанавливаем webhook при старте
    with app.test_client() as client:
        client.get('/set_webhook')
    # Запускаем Flask (без polling, только webhook)
    app.run(host='0.0.0.0', port=port)