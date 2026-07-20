import os
import requests
from flask import Flask, request
from main import application, BOT_TOKEN

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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    # Устанавливаем webhook при старте
    webhook_url = f"https://{os.environ.get('RENDER_EXTERNAL_URL', 'localhost')}/webhook"
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
    try:
        resp = requests.post(url, json={'url': webhook_url})
        print(f"Webhook set: {resp.json()}")
    except Exception as e:
        print(f"Failed to set webhook: {e}")
    # Запускаем Flask
    app.run(host='0.0.0.0', port=port)