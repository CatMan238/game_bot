import os
import threading
import time
from main import main

if __name__ == '__main__':
    # Запускаем бота в отдельном потоке
    thread = threading.Thread(target=main)
    thread.start()
    # Держим процесс живым
    while True:
        time.sleep(60)