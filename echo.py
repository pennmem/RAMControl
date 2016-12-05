"""Echo server used to test TCP connections."""

import socket

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.bind(("192.168.137.200", 8888))

sock.setsockopt(socket.SOL_SOCKET, socket.TCP_NODELAY, 1)
sock.setblocking(True)

sock.listen(1)

while True:
    print("Waiting...")
    try:
        conn, addr = sock.accept()
        print("Incoming connection from " + str(addr))

        while True:
            data = conn.recv(len("ping"))
            conn.send("pong")
    except Exception as e:
        conn.close()
        if type(e) is socket.error:
            print("Connection closed")
        else:
            raise e
