import socket
import threading
import time
import json


def get_ip_address():
    try:
        # 创建一个socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # 尝试连接外部服务器以获取IP地址
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return ""


print(get_ip_address())
if get_ip_address():
    IP = get_ip_address()
else:
    IP = socket.gethostbyname(socket.gethostname())
PORT = 8888
BUFLEN = 1024


class server():
    def __init__(self, ip=IP, port=PORT, buf=BUFLEN):
        self.addr = self.ip, self.port = ip, port
        self.buf = buf

    def socket_init(self):
        self.listenSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.send_udp_clinet_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        send_udp_ip_thread = threading.Thread(target=self.send_udp_clinet)
        send_udp_ip_thread.daemon = True
        send_udp_ip_thread.start()
        self.listenSocket.bind(self.addr)
        self.listenSocket.listen(5)

    def send_udp_clinet(self):
        local_info_dict = {"server_ip": self.addr[0], "server_port": self.addr[1]}
        local_info = json.dumps(local_info_dict)
        while True:
            for i in range(1, 255):
                self.send_udp_clinet_socket.sendto(local_info.encode(),
                                                   (self.ip[:self.ip.rfind('.')] + f'.{i}', self.port))

            time.sleep(5)

    def server_accept(self):
        print(f'服务器启动成功，端口{self.port}等待连接……')
        self.datasocket, addr = self.listenSocket.accept()
        print(f'{addr[0]}已连接')

    def server_start(self):
        while True:
            recved = self.datasocket.recv(self.buf)
            if recved == 'exit':
                break
            if recved != '':
                print('收到客户端信息：', recved.decode())
                self.datasocket.send(f'服务端已接收到您的信息:{recved.decode()}'.encode())
        self.datasocket.close()
        self.listenSocket.close()


class client():
    def __init__(self, ip=IP, port=PORT, buf=BUFLEN):
        self.addr = self.ip, self.port = ip, port
        self.send_udp_ip = self.ip
        self.recv_udp_client_info = ''
        self.buf = buf

    def client_init(self):
        self.dataSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.recv_udp_server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def recv_udp_server(self):
        self.recv_udp_server_socket.bind(self.addr)
        while self.recv_udp_client_info == '':
            self.recv_udp_client_info, addr = self.recv_udp_server_socket.recvfrom(self.buf)
            time.sleep(0.5)
            if self.recv_udp_client_info != '':
                self.recv_udp_client_info = json.loads(self.recv_udp_client_info)

    def client_connect(self):
        self.recv_udp_server()
        if self.recv_udp_client_info != '':
            self.dataSocket.connect((self.recv_udp_client_info['server_ip'], self.recv_udp_client_info['server_port']))
            print('已连接服务端：', self.recv_udp_client_info)

    def client_send_msg(self, msg):
        self.dataSocket.send(msg.encode())

    def client_start(self):
        while True:
            msg = input('>>')
            if msg != '':
                self.client_send_msg(msg)
                if msg == 'exit':
                    break
                data = self.dataSocket.recv(self.buf)
                if data != '':
                    print(data.decode())
        self.dataSocket.close()


server1 = server()
client1 = client()
mode = input()

if mode == '1':
    server1.socket_init()
    server1.server_accept()
    server1.server_start()
if mode == '2':
    client1.client_init()
    client1.client_connect()
    client1.client_start()