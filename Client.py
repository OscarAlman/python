import socket
import threading

def receive_messages(sock):
    while True:
        try:
            message = sock.recv(1024).decode()
            print(message)
        except:
            break



def start_client():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(("127.0.0.1", 5555))

    threading.Thread(target=receive_messages, args=(sock,), daemon=True).start()

    while True:
        msg = input(">>")
        sock.send(msg.encode())

if __name__ == "__main__":
    start_client()
