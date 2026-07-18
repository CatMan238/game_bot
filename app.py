import os
import threading
import time
from main import main

if __name__ == '__main__':
    # Запускаем бота в отдельном потоке с event loop
    def run_bot():
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        main()  # Здесь main() синхронная, но внутри запускает свой event loop
    
    thread = threading.Thread(target=run_bot)
    thread.start()
    
    # Открываем порт для Render
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('0.0.0.0', int(os.environ.get('PORT', 8080))))
    sock.listen()
    
    while True:
        time.sleep(60)