import socket
import math
import threading
x=0

clientsocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
clientsocket.connect(('192.168.1.242', 8090))

while True:
    x=x+1
    
    clientsocket.send(str(x).encode())

    clientsocket.close()        