

import socket
import threading


# List of connected clients
clients = []∏



def broadcast(message, sender_socket):
    """Send a message to all clients except the sender."""
    for client in clients:
       
       # if client != sender_socket:
            try:
                client.send(message)
            except:
                client.close()
                clients.remove(client)

def handle_client(client_socket):
    """Handle messages from a single client."""
    while True:
        try:
            message = client_socket.recv(1024)
            if not message:
                break
            
            broadcast(message, client_socket)
        except:
            print(" exiting ")
            break
        

    # Remove client on disconnect
    clients.remove(client_socket)
    client_socket.close()

def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("0.0.0.0", 5555))  # Listen on all interfaces, port 5555
    server.listen()

    print("Chat server running on port 5555")

    while True:
        client_socket, addr = server.accept()
        print(f"New connection from {addr}")

        clients.append(client_socket)

        thread = threading.Thread(target=handle_client, args=(client_socket,))
        thread.start()

if __name__ == "__main__":
    start_server()
