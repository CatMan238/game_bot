import threading
import time
from main import main

if __name__ == '__main__':
    thread = threading.Thread(target=main)
    thread.start()
    
    # Открываем порт и держим его открытым
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('0.0.0.0', 8080))
    sock.listen()
    
    while True:
        time.sleep(60)