import json
import os
import queue
import socket
import struct
import threading
import time

import pygame
from pygame import freetype
from pygame.locals import *

WIDTH = 1000
HEIGHT = 600
FPS = 40

PLAYER1 = 'p1'
PLAYER2 = 'p2'

BLACK = (0, 0, 0)
WIRTE = (255, 255, 255)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)

plankspeed = 5
ballspeed = 5

GAMEMAINMENU = 'game-main-menu'
SINGLE = 'single'
MULTI = 'multi'
MULTIMODEMENU = 'multi-mode-menu'
CREATEROOMCONFIG = 'multi-createroom-config'
NEWROOMMENU = 'multi-newroom-menu'
ROOMCONFIGMENU = 'room-config-menu'
JOINROOMMENU = 'multi-joinroom-menu'
JOINWAITINFACE = 'join-wait-inface'
JOINROOMINFACE = 'multi-joinroom'
MULTISTARTGAME = 'multi-start-game'

FONTSTYLE = tuple('strong,wide,oblique,underline,antialiased,origin,vertical,pad'.split(','))


class Server():

    def __init__(self, _addr: tuple, _buf: int, schematic_data: dict, _back: int = 5):
        self.addr = self.host, self.port = _addr
        self.buf = _buf
        self.start_state = False
        self.server_sk = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.recv_clinet = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server_sk.bind(self.addr)
        self.auto_struct_obj = AutoPacker((len(schematic_data),))
        self.back = _back

    @staticmethod
    def wlan_ip():  # 公网测试/获取本地外网ip
        sk = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:

            sk.connect(('8.8.8.8', 80))
            ip = sk.getsockname()[0]
            return ip
        finally:
            sk.close()

    def start(self):
        self.client_dict = {}
        self.server_sk.listen(self.back)
        self.start_state = True
        print(f'服务器启动成功，IP地址{self.host};端口{self.port}等待连接……')
        while self.start_state:
            try:
                client_sk, client_addr = self.server_sk.accept()
                print(f'客户端1{client_addr}已连接！')
                self.client_dict[client_sk] = client_addr
                recv_data_thread = threading.Thread(target=self.recv_data, args=(client_sk,))
                recv_data_thread.daemon = True
                recv_data_thread.start()

            except OSError:
                self.remove_sk(client_sk)

    def recv_data(self, client_sk):
        print(client_sk)
        while self.start_state:
            try:
                client_data_lens = client_sk.recv(self.auto_struct_obj.size)
                if client_data_lens != '':
                    client_data_len = self.auto_struct_obj.unpack(client_data_lens)[0]
                    client_data = client_sk.recv(client_data_len)
                    # self.shared_client_data(client_data)
                    self.send_data(client_sk, client_data_lens + client_data)
            except ConnectionError:
                print('有人断开连接了！')
                self.remove_sk(client_sk)
                break

    def send_data(self, client_sk, send_cl_data):
        for sk in list(self.client_dict.keys()):
            try:
                if sk != client_sk:
                    sk.sendall(send_cl_data)

            except ConnectionError:
                print('有人断开连接了！')

    def remove_sk(self, client_sk):
        for sk in list(self.client_dict.keys()):
            if sk == client_sk:
                self.client_dict.pop(client_sk)

    def stop(self):
        if self.start_state:
            self.start_state = False
            self.server_sk.close()


class Client():
    def __init__(self, addr: tuple, buf: int, schematic_data: dict):
        self.addr = self.host, self.port = addr
        self.buf = buf
        self.client_sk = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.start_state = False
        self.auto_struct_obj = AutoPacker((len(schematic_data),))
        self.send_data_queque = queue.Queue(3)
        self.recv_data_queque = queue.Queue(3)

    def start(self, func, fps):
        self.client_sk.connect(self.addr)
        print('您已成功加入聊天室！')
        self.start_state = True
        send_data_threading = threading.Thread(target=self.send_data)
        send_data_threading.daemon = True
        send_data_threading.start()
        recv_data_threading = threading.Thread(target=self.recv_data)
        recv_data_threading.daemon = True
        recv_data_threading.start()
        user_defined_func_threading = threading.Thread(target=self.user_defined_func, args=(func, fps))
        user_defined_func_threading.daemon = True
        user_defined_func_threading.start()

    def send_data(self):
        while self.start_state:
            try:
                send_sv_data = self.send_data_queque.get()
                struct_datalen_bytes = self.auto_struct_obj.pack((len(send_sv_data),))
                send_sv_data = struct_datalen_bytes + send_sv_data
                self.client_sk.sendall(send_sv_data)
            except OSError:
                self.client_sk.close()

    def recv_data(self):
        while self.start_state:
            try:
                recv_sv_data_lens = self.client_sk.recv(self.auto_struct_obj.size)
                if recv_sv_data_lens != '':
                    server_data_len = self.auto_struct_obj.unpack(recv_sv_data_lens)[0]
                    recv_sv_data = self.client_sk.recv(server_data_len)
                    self.recv_data_queque.put(recv_sv_data)
            except ConnectionError:
                self.client_sk.close()
                print('已和服务器断开连接!')

    def get_data(self):
        if self.recv_data_queque.full():
            recv_data = self.recv_data_queque.get()
            return recv_data
        else:
            return None

    def user_defined_func(self, func, fps):
        """
        此函数用于向客户端线程动态传输数据，必须要返回值，返回值需要是dict

        :param func: 函数
        :return: None
        """
        while self.start_state:
            func_return = func()
            cs_dict = func_return
            cs_str = json.dumps(cs_dict)
            time.sleep(fps)
            self.send_data_queque.put(cs_str.encode('utf-8'))

    def stop(self):
        self.start_state = False
        self.client_sk.close()


class AutoPacker():
    def __init__(self, data_item: list | tuple):
        fmt = ''
        for item in data_item:
            if isinstance(item, int):
                fmt += 'I'
            elif isinstance(item, float):
                fmt += 'd'
            elif isinstance(item, bytes):
                if len(item) > 1:
                    fmt += f'{len(item)}s'
                else:
                    fmt += 'c'
            elif isinstance(item, str):
                if len(item) > 1:
                    fmt += f'{len(item)}s'
                else:
                    fmt += 'c'
            else:
                raise ValueError("Unsupported data type")

        self._fmt = fmt

        self._struct_obj = struct.Struct(self._fmt)
        self._data = data_item
        self.size = self._struct_obj.size

    def pack(self, data_item: list | tuple = None):
        if data_item == None:
            data_item = self._data
        bytes_str = self._struct_obj.pack(*data_item)
        return bytes_str

    def unpack(self, struct_bytes: bytes):
        return self._struct_obj.unpack(struct_bytes)


class Timer(object):
    def __init__(self):
        self.interval = 0
        self.counter = pygame.USEREVENT + 1
        self.event_number = self._unque_userevent()
        self.isactive = False
        self.isreset = False
        self.start_time = 0

    def _unque_userevent(self):
        event_number = self.counter
        self.counter += 1
        return event_number

    def start(self, interval):
        if not self.isactive:
            self.start_time = pygame.time.get_ticks()
            self.interval = interval
            pygame.time.set_timer(self.event_number, self.interval)
            self.isactive = True

    def stop(self):
        pygame.time.set_timer(self.event_number, 0)
        self.isactive = False

    def header_event(self, events):
        for event in events:
            if event.type == self.event_number:
                return True
            else:
                return False

    def update_time(self):
        last_time = pygame.time.get_ticks()
        if self.isactive:
            if last_time - self.start_time <= self.interval:
                return True
            else:
                return False
        else:
            return False


class Game(object):

    def __init__(self, screen_size):
        pygame.init()
        freetype.init()
        os.environ['SDL_IME_SHOW_UI'] = '1'
        self.screen = pygame.display.set_mode(screen_size)
        pygame.key.stop_text_input()
        self.screen_rect = self.screen.get_rect()
        self.clock = pygame.time.Clock()
        self.isstartgame = 0
        self.issingle = 1
        self.ismulti = 2
        self.iscreateroom = 3
        self.iscreateserver = 4
        self.isinputstr = 5
        self.ischangestr = 6
        self.ismulti_startgame = 7
        self.isconnect = 8
        self.game_all_status = [False, False, False, False, False, False, False, False, False]

        self.current_user = PLAYER1
        self.game_mode_state = GAMEMAINMENU
        self.game_mode_status = {'game-main-menu': self.game_main_inface,
                                 'single': self.single_game,
                                 'multi': self.multi_game,
                                 'multi-mode-menu': self.multi_mode_inface,
                                 'multi-createroom-config': self.create_room_config_inface,
                                 'multi-newroom-menu': self.new_room_menu,
                                 'room-config-menu': self.room_config_menu,
                                 'multi-joinroom-menu': self.join_room_inface,
                                 'join-wait-inface': self.wait_select_inface,
                                 'multi-joinroom': self.player2_join_room_inface,
                                 'multi-start-game': self.room_manager}
        # 最大局数为3局，每一局有5回合，每1回合赢5分为赢1回合，赢3回合为赢一局,赢2局为获胜
        self.max_big_round = 2
        self.big_round = 0
        self.small_round = 0
        self.max_score = 3
        self.max_small_round = 3
        self.small_round_state = PLAYER1
        self.round = None

        self.offset = HEIGHT // 15

        self.ball_radius = 8
        self.ball_speed = ballspeed
        self.ball_speedx, self.ball_speedy = self.ball_speed, self.ball_speed

        self.plank_width = 8
        self.plank_height = 70
        self.plank1_rect = None
        self.plank2_rect = None
        self.plank_speed = plankspeed

        self.ball_fire_state = False

        self.plank1_pos_x = WIDTH // 10 - self.plank_width
        self.plank1_default_pos_x = self.plank1_pos_x

        self.plank2_pos_x = WIDTH - (WIDTH // 10)
        self.plank2_default_pos_x = self.plank2_pos_x

        self.plank1_default_pos_y = HEIGHT // 2 - self.plank_height // 2

        self.plank2_default_pos_y = HEIGHT // 2 - self.plank_height // 2

        self.plank1_rect = pygame.draw.rect(self.screen, BLACK, (
            self.plank1_default_pos_x, self.plank1_default_pos_y, self.plank_width, self.plank_height))
        self.plank2_rect = pygame.draw.rect(self.screen, BLACK, (
            self.plank2_default_pos_x, self.plank2_default_pos_y, self.plank_width, self.plank_height))
        self.plank1_pos_y = self.plank1_rect.y
        self.plank2_pos_y = self.plank2_rect.y

        self.ball_default_pos_x = self.plank1_default_pos_x + self.plank_width + self.ball_radius / 2
        self.ball_default_pos_y = self.plank1_default_pos_y + self.plank_height // 2
        self.ball_default_pos1 = None
        self.ball_default_pos2 = None

        # self.plank_rect=pygame.Rect(self.plank1_default_pos_x,self.plank1_default_pos_y,self.plank_width,self.plank_height)

        self.ball_rect = pygame.Rect(self.ball_default_pos_x, self.ball_default_pos_y, self.ball_radius,
                                     self.ball_radius)

        self.create_room_rect = None

        self.player_dict = {
            PLAYER1: {'name': 'p1', 'icon': '默认.png', 'isjoinroom': False, 'isready': False,
                      'score': {'small': 0, 'midlle': 0, 'big': 0}},
            PLAYER2: {'name': 'p2', 'icon': '默认.png', 'isjoinroom': False, 'isready': False,
                      'score': {'small': 0, 'midlle': 0, 'big': 0}}
        }
        self.put_cs_dict = {}

        self.room_dict = {}
        self.all_client_dict = {}

        self.wait_select_time = 0
        self.wait_select_timer = Timer()

        self.default_font_size = 30
        self.default_font_size_factor = None
        self.default_font = self.game_font('simkai.ttf', (FONTSTYLE[0], FONTSTYLE[4]))
        self.game_time_font = self.game_font('simkai.ttf', (FONTSTYLE[4],))
        self.text_size = 10

        self.input_str = ''
        self.change_str = ''
        self.input_rect = None
        self.change_rect = None
        self.rect_name = ''
        self.text_rect_dict = {}
        self.need_input_rect = None
        self.need_input_str = ''
        self.need_change_rect = None
        self.need_change_str = ''
        self.input_text_dict = {}
        self.register_rect_dict = {}

        self.multi_game_server = None
        self.multi_game_client = None
        self.return_rects = []
        self.confirm_rect = None
        self.clear_list = False
        self.print_rect_list = []
        self.print_rect_state = False
        self.max_text_rect = 0

        self.game_all_data_dict = {}

    def put_cs_data(self):
        self.put_cs_dict[self.current_user] = self.player_dict[self.current_user]
        put_dict = {'game_info': {'ball_speed': self.ball_speed, 'ball_pos': self.ball_rect.center,
                                  'plank_speed': self.plank_speed, 'plank1_pos': (self.plank1_pos_x, self.plank1_pos_y),
                                  'plank2_pos': (self.plank2_pos_x, self.plank2_pos_y)},
                    'player_info': self.put_cs_dict,
                    'connect_status_info': {'is_multi_startgame': self.game_all_status[self.ismulti_startgame], }
                    }
        return put_dict

    def init(self):
        self.max_big_round = 2
        self.big_round = 0
        self.small_round = 0
        self.max_score = 3
        self.max_small_round = 3
        self.small_round_state = PLAYER1
        self.round = None

        self.offset = HEIGHT // 15

        self.ball_radius = 8
        self.ball_speed = ballspeed
        self.ball_speedx, self.ball_speedy = self.ball_speed, self.ball_speed

        self.plank_width = 8
        self.plank_height = 70
        self.plank1_rect = None
        self.plank2_rect = None
        self.plank_speed = plankspeed

        self.ball_fire_state = False

        self.plank1_pos_x = WIDTH // 10 - self.plank_width
        self.plank1_default_pos_x = self.plank1_pos_x

        self.plank2_pos_x = WIDTH - (WIDTH // 10)
        self.plank2_default_pos_x = self.plank2_pos_x

        self.plank1_default_pos_y = HEIGHT // 2 - self.plank_height // 2

        self.plank2_default_pos_y = HEIGHT // 2 - self.plank_height // 2

        self.plank1_rect = pygame.draw.rect(self.screen, BLACK, (
        self.plank1_default_pos_x, self.plank1_default_pos_y, self.plank_width, self.plank_height))
        self.plank2_rect = pygame.draw.rect(self.screen, BLACK, (
        self.plank2_default_pos_x, self.plank2_default_pos_y, self.plank_width, self.plank_height))
        self.plank1_pos_y = self.plank1_rect.y
        self.plank2_pos_y = self.plank2_rect.y

        self.ball_default_pos_x = self.plank1_default_pos_x + self.plank_width + self.ball_radius / 2
        self.ball_default_pos_y = self.plank1_default_pos_y + self.plank_height // 2
        self.ball_default_pos1 = None
        self.ball_default_pos2 = None

        self.ball_rect = pygame.Rect(self.ball_default_pos_x, self.ball_default_pos_y, self.ball_radius,
                                     self.ball_radius)

        self.create_room_rect = None

        self.player_dict = {
            PLAYER1: {'name': 'p1', 'icon': '默认.png', 'isjoinroom': False, 'isready': False,
                      'score': {'small': 0, 'midlle': 0, 'big': 0}},
            PLAYER2: {'name': 'p2', 'icon': '默认.png', 'isjoinroom': False, 'isready': False,
                      'score': {'small': 0, 'midlle': 0, 'big': 0}}
        }
        self.put_cs_dict = {}

    @staticmethod
    def game_font(font_file: str, styles: tuple, underline_adjustment: float = 1,
                  strength: float = 1 / 36):
        """
        :param font_file: 字体文件路径
        :param styles: 字体样式，类似于styles=('strong','wide','oblique'...)
        :param underline_adjustment: 下划线的位置通常是2和-2之间的数
        :param strength: 模糊度默认值为1/36，建议值为1和1/36之间
        :return : game_font() -> pygame.freetype.Font
        """
        font = pygame.freetype.Font(font_file)
        font.antialiased = False
        font.underline_adjustment = underline_adjustment
        font.strength = strength
        for style in styles:
            if style == 'strong':
                font.strong = True
            if style == 'wide':
                font.wide = True
            if style == 'oblique':
                font.oblique = True
            if style == 'underline':
                font.underline = True
            if style == 'antialiased':
                font.antialiased = True
            if style == 'origin':
                font.origin = True
            if style == 'vertical':
                font.vertical = True
            if style == 'pad':
                font.pad = True
        return font

    def game_font_render(self, font: freetype.Font, text_blit_surf: pygame.Surface, text: str, size=None,
                         fgcolor: tuple = (0, 0, 0), bgcolor: tuple = (0, 0, 0, 0),
                         draw_text_rect=pygame.Rect(0, 0, 0, 0),
                         text_pos=None,
                         rotation: int = 0):
        '''
        此函数是将字符串打印到text_blit_surf上的draw_text_rect.center或者是text_pos位置上，当不提供size和text_pos时字体大小将自动变为draw_text_rect适当大小。

        :param font: 字体
        :param text_blit_surf: 将字体绘制到此矩形
        :param text: 字符串
        :param size: 字体大小
        :param fgcolor: 字体颜色
        :param bgcolor: 字体填充颜色
        :param draw_text_rect: 字体所在地矩形
        :param text_pos:字体中心位置
        :param rotation:旋转角度
        :return:None
        '''
        if size != None:
            text_surf, text_rect = font.render(text, fgcolor, bgcolor, rotation=rotation, size=size)
            if text_pos != None:
                text_rect.center = text_pos
        else:

            text_surf, text_rect = font.render(text, fgcolor, bgcolor, rotation=rotation,
                                               size=self.adjust_textsize(self.default_font, draw_text_rect, text))
            text_rect.center = draw_text_rect.center
        text_blit_surf.blit(text_surf, text_rect)

    def adjust_textsize(self, font, darw_rect, text):
        text_surf, text_rect = font.render(text, size=self.text_size)
        text_rect_w, text_rect_h = text_rect.size
        if darw_rect.w > text_rect_w and darw_rect.h > text_rect_h:
            self.text_size += 4
        if darw_rect.w < text_rect_w and darw_rect.h < text_rect_h:
            self.text_size -= 4
        return self.text_size - 8

    def game_text_blit(self):
        time_str = f'{time.strftime("%y-%m-%d %H:%M:%S", time.localtime(time.time()))}'
        big_score_str = f'{self.player_dict[PLAYER1]["score"]["big"]}:{self.player_dict[PLAYER2]["score"]["big"]}'
        midlle_score_str = f'{self.player_dict[PLAYER1]["score"]["midlle"]}:{self.player_dict[PLAYER2]["score"]["midlle"]}'
        player1_name_str = f'{self.player_dict[PLAYER1]["name"]}'
        player2_name_str = f'{self.player_dict[PLAYER2]["name"]}'
        p1_small_score_str = f'{self.player_dict[PLAYER1]["score"]["small"]}'
        p2_small_score_str = f'{self.player_dict[PLAYER2]["score"]["small"]}'
        p1_name_small_score_str = f'{player1_name_str}:{p1_small_score_str}'
        p2_name_small_score_str = f'{player2_name_str}:{p2_small_score_str}'

        self.game_font_render(self.default_font, self.screen, big_score_str, 70, BLACK,
                              text_pos=self.big_round_rect.center)
        self.game_font_render(self.default_font, self.screen, midlle_score_str, 30, BLACK,
                              text_pos=self.score_rect.center)
        self.game_font_render(self.default_font, self.screen, p1_name_small_score_str, 30, BLACK,
                              text_pos=self.player1_name_rect.center)
        self.game_font_render(self.default_font, self.screen, p2_name_small_score_str, 30, BLACK,
                              text_pos=self.player2_name_rect.center)

    def game_line(self, keys, mouse_pos: tuple, mouse_chick_status: tuple):
        self.big_round_rect = pygame.draw.rect(self.screen, BLACK,
                                               (WIDTH // 2 - WIDTH // 4 // 2, 0, WIDTH // 4, HEIGHT // 7), 1)
        self.player1_icon_rect = pygame.draw.rect(self.screen, BLACK,
                                                  (WIDTH // 2 - WIDTH // 4 + (WIDTH // 4 // 2 - HEIGHT // 7), 0,
                                                   HEIGHT // 7, HEIGHT // 7), 1)
        self.player2_icon_rect = pygame.draw.rect(self.screen, BLACK,
                                                  (WIDTH // 2 + WIDTH // 4 // 2, 0, HEIGHT // 7, HEIGHT // 7), 1)
        self.player1_name_rect = pygame.draw.polygon(self.screen, BLACK, (
            (0, HEIGHT), (0, HEIGHT - HEIGHT // 7 + self.offset),
            (WIDTH // 2 - WIDTH // 6, HEIGHT - HEIGHT // 7 + self.offset), (WIDTH // 2 - WIDTH // 8, HEIGHT)), 3)
        self.player2_name_rect = pygame.draw.polygon(self.screen, BLACK, (
            (WIDTH // 2 + WIDTH // 8, HEIGHT), (WIDTH // 2 + WIDTH // 6, HEIGHT - HEIGHT // 7 + self.offset),
            (WIDTH, HEIGHT - HEIGHT // 7 + self.offset), (WIDTH, HEIGHT)), 3)

        self.up_bound_rect = pygame.draw.polygon(self.screen, BLACK, (
            (0, HEIGHT // 7), (WIDTH // 10, HEIGHT // 4),
            (WIDTH - (WIDTH // 10), HEIGHT // 4), (WIDTH, HEIGHT // 7)), 5)
        self.down_bound_rect = pygame.draw.polygon(self.screen, BLACK, (
            (0, HEIGHT - HEIGHT // 7 + self.offset), (WIDTH // 10, HEIGHT - HEIGHT // 4 + self.offset),
            (WIDTH - (WIDTH // 10), HEIGHT - HEIGHT // 4 + self.offset),
            (WIDTH, HEIGHT - HEIGHT // 7 + self.offset)), 5)
        self.score_rect = pygame.draw.polygon(self.screen, BLACK, (
            (WIDTH // 2 - WIDTH // 8, HEIGHT), (WIDTH // 2 - WIDTH // 6, HEIGHT - HEIGHT // 7 + self.offset),
            (WIDTH // 2 + WIDTH // 6, HEIGHT - HEIGHT // 7 + self.offset), (WIDTH // 2 + WIDTH // 8, HEIGHT)), 1)
        self.game_config_button_rect = pygame.draw.rect(self.screen, BLACK, (
        0, self.button_rect.height, self.button_rect.width / 4, self.button_rect.height), 2)
        self.game_font_render(self.default_font, self.screen, '游戏设置', fgcolor=BLACK, size=10,
                              text_pos=self.game_config_button_rect.center)

    def game_button(self, mouse_pos: tuple, mouse_chick_status: tuple):
        mouse_left, mouse_middle, mouse_right = mouse_chick_status
        back_str = '返回主界面'
        restart_str = '重新开始'
        single_str = '本地模式'
        multi_str = '在线模式'
        self.back_button_rect = pygame.draw.rect(self.screen, BLACK, (
            0, 0, self.button_rect.width / 4, self.button_rect.height), 1)

        self.restart_button_rect = pygame.draw.rect(self.screen, BLACK, (
            self.button_rect.width // 4, 0, self.button_rect.width // 4, self.button_rect.height), 1)

        self.single_button_rect = pygame.draw.rect(self.screen, BLACK, (
            self.button_rect.width // 4 * 2, 0, self.button_rect.width // 4, self.button_rect.height), 1)

        self.multi_button_rect = pygame.draw.rect(self.screen, BLACK, (
            self.button_rect.width // 4 * 3, 0, self.button_rect.width // 4, self.button_rect.height), 1)
        self.game_font_render(self.default_font, self.screen, back_str, 10, BLACK,
                              text_pos=self.back_button_rect.center)
        self.game_font_render(self.default_font, self.screen, restart_str, 10, BLACK,
                              text_pos=self.restart_button_rect.center)
        self.game_font_render(self.default_font, self.screen, single_str, 10, BLACK,
                              text_pos=self.single_button_rect.center)
        self.game_font_render(self.default_font, self.screen, multi_str, 10, BLACK,
                              text_pos=self.multi_button_rect.center)

        if mouse_left:
            def false_i(i):
                j = i
                j = False
                return j

            if self.back_button_rect.collidepoint(mouse_pos):
                self.game_all_status = [false_i(i) for i in self.game_all_status]
                # 数据初始化
                self.init()
                if self.multi_game_server:
                    self.multi_game_server.stop()
                if self.multi_game_client:
                    self.multi_game_client.stop()
                self.game_mode_state = GAMEMAINMENU

            if self.restart_button_rect.collidepoint(mouse_pos):
                self.player_dict[PLAYER1]['score']['small'] = 0
                self.player_dict[PLAYER1]['score']['midlle'] = 0
                self.player_dict[PLAYER1]['score']['big'] = 0
                self.player_dict[PLAYER2]['score']['small'] = 0
                self.player_dict[PLAYER2]['score']['midlle'] = 0
                self.player_dict[PLAYER2]['score']['big'] = 0
                self.small_round = 0
                self.big_round = 0
            if self.single_button_rect.collidepoint(mouse_pos):
                if self.game_mode_state != SINGLE:
                    # 数据初始化
                    self.init()
                    if self.multi_game_server:
                        self.multi_game_server.stop()
                    if self.multi_game_client:
                        self.multi_game_client.stop()
                    self.game_mode_state = SINGLE
                    self.game_all_status[self.isstartgame] = True

            if self.multi_button_rect.collidepoint(mouse_pos):
                # 数据初始化
                self.init()
                self.game_mode_state = MULTIMODEMENU
                self.game_all_status[self.ismulti] = True

    def player_icon(self):
        if self.all_client_dict:
            if self.current_user == PLAYER2:
                if self.all_client_dict['player_info'][PLAYER1]['isready']:
                    player2_icon_surf = pygame.transform.scale(pygame.image.load(self.player_dict[PLAYER2]['icon']), (
                    self.player2_icon_rect.width - 2, self.player2_icon_rect.height - 2)).convert_alpha()
                    player1_icon_surf = pygame.transform.scale(
                        pygame.image.load(self.all_client_dict['player_info'][PLAYER1]['icon']),
                        (self.player1_icon_rect.width - 2, self.player2_icon_rect.height - 2)).convert_alpha()
                    self.screen.blit(player1_icon_surf, self.player1_icon_rect)
                    self.screen.blit(player2_icon_surf, self.player2_icon_rect)

            if self.current_user == PLAYER1:
                if self.all_client_dict['player_info'][PLAYER2]['isready']:
                    player1_icon_surf = pygame.transform.scale(pygame.image.load(self.player_dict[PLAYER1]['icon']), (
                    self.player1_icon_rect.width - 2, self.player1_icon_rect.height - 2)).convert_alpha()
                    player2_icon_surf = pygame.transform.scale(
                        pygame.image.load(self.all_client_dict['player_info'][PLAYER2]['icon']),
                        (self.player2_icon_rect.width - 2, self.player2_icon_rect.height - 2)).convert_alpha()
                    self.screen.blit(player1_icon_surf, self.player1_icon_rect)
                    self.screen.blit(player2_icon_surf, self.player2_icon_rect)

        else:

            player1_icon_surf = pygame.transform.scale(pygame.image.load(self.player_dict[PLAYER1]['icon']), (
            self.player1_icon_rect.width - 2, self.player1_icon_rect.height - 2)).convert_alpha()
            player2_icon_surf = pygame.transform.scale(pygame.image.load(self.player_dict[PLAYER2]['icon']), (
            self.player2_icon_rect.width - 2, self.player2_icon_rect.height - 2)).convert_alpha()
            self.screen.blit(player1_icon_surf, self.player1_icon_rect)
            self.screen.blit(player2_icon_surf, self.player2_icon_rect)

    def plank_move(self, keys):
        if self.game_all_status[self.ismulti]:
            if self.current_user == PLAYER1:
                if keys[K_w]:
                    if self.plank1_rect.top < self.up_bound_rect.bottom:
                        self.plank1_pos_y += 0
                        self.plank1_rect.top = self.up_bound_rect.bottom
                    else:
                        self.plank1_pos_y -= self.plank_speed
                elif keys[K_s]:
                    if self.plank1_rect.bottom > self.down_bound_rect.top:
                        self.plank1_pos_y += 0
                        self.plank1_rect.bottom = self.down_bound_rect.top

                    else:
                        self.plank1_pos_y += self.plank_speed
                else:
                    self.plank1_pos_y += 0
                self.plank1_rect = pygame.draw.rect(self.screen, BLACK, (
                self.plank1_default_pos_x, self.plank1_pos_y, self.plank_width, self.plank_height))
                if keys[K_j] and WIDTH - self.ball_rect.x > WIDTH / 2:
                    self.ball_fire_state = True
            elif self.current_user == PLAYER2:
                if keys[K_UP]:
                    if self.plank2_rect.top < self.up_bound_rect.bottom:
                        self.plank2_pos_y += 0
                        self.plank2_rect.top = self.up_bound_rect.bottom
                    else:
                        self.plank2_pos_y -= self.plank_speed
                elif keys[K_DOWN]:
                    if self.plank2_rect.bottom > self.down_bound_rect.top:
                        self.plank2_pos_y += 0
                        self.plank2_rect.bottom = self.down_bound_rect.top
                    else:
                        self.plank2_pos_y += self.plank_speed
                else:
                    self.plank2_pos_y += 0

                self.plank2_rect = pygame.draw.rect(self.screen, BLACK, (
                self.plank2_default_pos_x, self.plank2_pos_y, self.plank_width, self.plank_height))
                if keys[K_m] and WIDTH - self.ball_rect.x < WIDTH / 2:
                    self.ball_fire_state = True
        else:
            if keys[K_w]:
                if self.plank1_rect.top < self.up_bound_rect.bottom:
                    self.plank1_pos_y += 0
                    self.plank1_rect.top = self.up_bound_rect.bottom
                else:
                    self.plank1_pos_y -= self.plank_speed
            elif keys[K_s]:
                if self.plank1_rect.bottom > self.down_bound_rect.top:
                    self.plank1_pos_y += 0
                    self.plank1_rect.bottom = self.down_bound_rect.top

                else:
                    self.plank1_pos_y += self.plank_speed
            else:
                self.plank1_pos_y += 0
            self.plank1_rect = pygame.draw.rect(self.screen, BLACK, (
                self.plank1_default_pos_x, self.plank1_pos_y, self.plank_width, self.plank_height))
            if keys[K_j] and WIDTH - self.ball_rect.x > WIDTH / 2:
                self.ball_fire_state = True
            if keys[K_UP]:
                if self.plank2_rect.top < self.up_bound_rect.bottom:
                    self.plank2_pos_y += 0
                    self.plank2_rect.top = self.up_bound_rect.bottom
                else:
                    self.plank2_pos_y -= self.plank_speed
            elif keys[K_DOWN]:
                if self.plank2_rect.bottom > self.down_bound_rect.top:
                    self.plank2_pos_y += 0
                    self.plank2_rect.bottom = self.down_bound_rect.top
                else:
                    self.plank2_pos_y += self.plank_speed
            else:
                self.plank2_pos_y += 0

            self.plank2_rect = pygame.draw.rect(self.screen, BLACK, (
                self.plank2_default_pos_x, self.plank2_pos_y, self.plank_width, self.plank_height))
            if keys[K_m] and WIDTH - self.ball_rect.x < WIDTH / 2:
                self.ball_fire_state = True

    def multi_p2plank_darw(self):
        if self.all_client_dict:
            if self.current_user == PLAYER1:
                self.plank2_rect = pygame.draw.rect(self.screen, BLACK, (
                self.all_client_dict['game_info']['plank2_pos'][0], self.all_client_dict['game_info']['plank2_pos'][1],
                self.plank_width, self.plank_height), 0)
            elif self.current_user == PLAYER2:
                self.plank1_rect = pygame.draw.rect(self.screen, BLACK, (
                self.all_client_dict['game_info']['plank1_pos'][0], self.all_client_dict['game_info']['plank1_pos'][1],
                self.plank_width, self.plank_height), 0)

    def ball_move(self):
        self.ball_rect = pygame.draw.circle(self.screen, BLACK, self.ball_rect.center, self.ball_radius, 0)
        if self.ball_rect.collidelistall((self.up_bound_rect, self.down_bound_rect)):
            self.ball_speedy = -self.ball_speedy
        if self.ball_rect.colliderect(self.plank1_rect):
            self.ball_speedx = -self.ball_speedx
        if self.ball_rect.colliderect(self.plank2_rect):
            self.ball_speedx = -self.ball_speedx

        if self.ball_fire_state:
            self.ball_rect.x += self.ball_speedx
            self.ball_rect.y += self.ball_speedy

        else:
            if self.small_round_state == PLAYER1:
                self.ball_rect.midleft = self.plank1_rect.midright
                if self.current_user == PLAYER2:
                    if self.all_client_dict:
                        self.ball_rect.center = self.all_client_dict['game_info']['ball_pos']
                        self.plank1_rect
            if self.small_round_state == PLAYER2:
                self.ball_rect.midright = self.plank2_rect.midleft
                if self.current_user == PLAYER1:
                    if self.all_client_dict:
                        self.ball_rect.center = self.all_client_dict['game_info']['ball_pos']

    def game_play(self):
        if not self.big_round >= self.max_big_round:  # 保证局数不会大等于3
            if not self.small_round >= self.max_small_round:  # 保证回合不会大等于3
                if not self.player_dict[PLAYER1]['score']['small'] >= self.max_score:  # 保证分数不会大于3
                    if self.ball_rect.x <= 0:
                        self.player_dict[PLAYER2]['score']['small'] += 1
                        self.ball_fire_state = False
                        self.small_round_state = PLAYER2

                    elif self.ball_rect.x + self.ball_radius * 2 >= WIDTH:
                        self.player_dict[PLAYER1]['score']['small'] += 1
                        self.ball_fire_state = False
                        self.small_round_state = PLAYER1

                else:  # 如果分数大于5，那么比较小分，增加获胜者中分,玩家的小分清零,增加回合数
                    if self.player_dict[PLAYER1]['score']['small'] > self.player_dict[PLAYER2]['score']['small']:
                        self.player_dict[PLAYER1]['score']['midlle'] += 1
                    else:
                        self.player_dict[PLAYER2]['score']['midlle'] += 1

                    self.player_dict[PLAYER1]['score']['small'] = 0
                    self.player_dict[PLAYER2]['score']['small'] = 0
                    self.small_round += 1

            else:  # 如果回合大等于3，那么比较中分，增加获胜者大分，玩家的中分，小分,回合数清零，增加局数
                if self.player_dict[PLAYER1]['score']['midlle'] > self.player_dict[PLAYER2]['score']['midlle']:
                    self.player_dict[PLAYER1]['score']['big'] += 1
                else:
                    self.player_dict[PLAYER2]['score']['big'] += 1
                self.player_dict[PLAYER1]['score']['small'] = 0
                self.player_dict[PLAYER2]['score']['small'] = 0
                self.player_dict[PLAYER1]['score']['midlle'] = 0
                self.player_dict[PLAYER2]['score']['midlle'] = 0
                self.small_round = 0
                self.big_round += 1

        else:  # 如果局数大等于3，则所有数据清零，游戏结束
            self.player_dict[PLAYER1]['score']['small'] = 0
            self.player_dict[PLAYER1]['score']['midlle'] = 0
            self.player_dict[PLAYER1]['score']['big'] = 0
            self.player_dict[PLAYER2]['score']['small'] = 0
            self.player_dict[PLAYER2]['score']['midlle'] = 0
            self.player_dict[PLAYER2]['score']['big'] = 0
            self.small_round = 0
            self.big_round = 0

    def game_mode(self, keys, mouse_pos: tuple, mouse_chick_status: tuple):
        mouse_left, mouse_middle, mouse_right = mouse_chick_status

        if True not in self.game_all_status:

            self.game_mode_state = GAMEMAINMENU
            self.game_mode_status[self.game_mode_state]()
            if mouse_left:
                if self.stal_rect.collidepoint(mouse_pos):
                    self.game_mode_state = SINGLE
                    self.game_all_status[self.isstartgame] = True
                    self.game_all_status[self.ismulti] = False
                    self.game_all_status[self.issingle] = True
                if self.single_rect.collidepoint(mouse_pos):
                    self.game_mode_state = MULTIMODEMENU
                    self.game_all_status[self.ismulti] = True
                    self.game_all_status[self.issingle] = False
        if self.game_mode_state == MULTIMODEMENU and self.game_all_status[self.ismulti]:
            # 数据初始化
            self.init()
            self.game_mode_status[self.game_mode_state]()
            if mouse_left:
                if self.create_room_button_rect.collidepoint(mouse_pos):
                    self.game_mode_state = CREATEROOMCONFIG
                    self.game_all_status[self.iscreateroom] = True

                if self.join_room_rect.collidepoint(mouse_pos):
                    # 数据初始化
                    self.init()
                    self.game_mode_state = JOINROOMMENU

        if self.game_mode_state == SINGLE:
            self.game_mode_status[self.game_mode_state](keys, mouse_pos, mouse_chick_status)
            if self.game_config_button_rect.collidepoint(mouse_pos) and mouse_chick_status[0]:
                self.game_mode_state = ROOMCONFIGMENU
        if self.game_mode_state == CREATEROOMCONFIG:
            self.game_mode_status[self.game_mode_state](keys, mouse_pos, mouse_chick_status)
            if self.create_room_rect.collidepoint(mouse_pos) and mouse_left:
                self.create_room()
                self.game_mode_state = NEWROOMMENU
                self.player_dict[PLAYER1]['isjoinroom'] = True
                self.player_dict[PLAYER1]['isready'] = True
                self.current_user = PLAYER1

            if self.create_room_back_multuimode_rect.collidepoint(mouse_pos) and mouse_left:
                # 数据初始化
                self.init()
                self.game_mode_state = MULTIMODEMENU

        if self.game_mode_state == NEWROOMMENU:
            self.game_mode_status[self.game_mode_state]()
            self.new_room_button_action(mouse_pos, mouse_chick_status)
        if self.game_mode_state == ROOMCONFIGMENU:
            if self.game_all_status[self.issingle]:
                self.game_mode_status[self.game_mode_state](SINGLE, keys, mouse_pos, mouse_chick_status)
            elif self.game_all_status[self.ismulti]:
                self.game_mode_status[self.game_mode_state](NEWROOMMENU, keys, mouse_pos, mouse_chick_status)

        if self.game_mode_state == JOINROOMMENU:
            self.game_mode_status[self.game_mode_state](keys, mouse_pos, mouse_chick_status)
            if self.join_room_back_multuimode_rect.collidepoint(mouse_pos) and mouse_left:
                # 数据初始化
                self.init()
                self.game_mode_state = MULTIMODEMENU
            if self.join_room_select_room_rect.collidepoint(mouse_pos) and mouse_left:
                self.game_mode_state = JOINWAITINFACE

        if self.game_mode_state == JOINWAITINFACE:
            self.game_mode_status[self.game_mode_state]()
        if self.game_mode_state == JOINROOMINFACE:
            self.game_mode_status[self.game_mode_state](keys, mouse_pos, mouse_chick_status)
        if self.game_mode_state == MULTISTARTGAME:
            self.game_mode_status[self.game_mode_state](keys, mouse_pos, mouse_chick_status)

    def game_main_inface(self):
        start_str = '弹球游戏'
        stal_str = '本地游戏'
        single_str = '在线游戏'
        self.button_rect = pygame.draw.rect(self.screen, BLACK, (0, 0, WIDTH // 4, HEIGHT // 7 // 2), width=3)

        start_rect = pygame.draw.rect(self.screen, BLACK, self.screen_rect)

        self.stal_rect = pygame.draw.rect(self.screen, WIRTE,
                                          (WIDTH / 2 - WIDTH / 8, HEIGHT / 2 + HEIGHT / 15, WIDTH / 4, HEIGHT / 10))

        self.single_rect = pygame.draw.rect(self.screen, WIRTE,
                                            (WIDTH / 2 - WIDTH / 8, HEIGHT / 2 + HEIGHT / 5, WIDTH / 4, HEIGHT / 10))

        self.game_font_render(self.default_font, self.screen, start_str, 100, BLUE, GREEN,
                              text_pos=(start_rect.centerx, start_rect.centery - HEIGHT // 5))
        self.game_font_render(self.default_font, self.screen, stal_str, 60, BLACK, text_pos=self.stal_rect.center)
        self.game_font_render(self.default_font, self.screen, single_str, 60, BLACK, text_pos=self.single_rect.center)

    def multi_mode_inface(self):
        create_room_str = '创建房间'
        join_room_str = '加入房间'
        mode_str = '创建/加入房间'
        multi_inface_rect = pygame.draw.rect(self.screen, WIRTE, (0, 0, WIDTH, HEIGHT))
        self.create_room_button_rect = pygame.draw.rect(self.screen, BLACK,
                                                        (WIDTH // 4, HEIGHT // 2, WIDTH // 6, HEIGHT // 8))
        self.join_room_rect = pygame.draw.rect(self.screen, BLACK,
                                               (WIDTH - WIDTH // 6 - WIDTH // 4, HEIGHT // 2, WIDTH // 6, HEIGHT // 8))
        mode_rect = pygame.draw.rect(self.screen, WIRTE,
                                     (WIDTH // 2 - WIDTH // 6, HEIGHT // 4, WIDTH // 3, HEIGHT // 6))
        self.game_font_render(self.default_font, self.screen, create_room_str, 40, WIRTE,
                              text_pos=self.create_room_button_rect.center)
        self.game_font_render(self.default_font, self.screen, join_room_str, 40, WIRTE,
                              text_pos=self.join_room_rect.center)
        self.game_font_render(self.default_font, self.screen, mode_str, 100, BLACK, text_pos=mode_rect.center)

    def single_game(self, keys, mouse_pos, mouse_chick_status):
        self.game_line(keys, mouse_pos, mouse_chick_status)
        self.player_icon()
        self.game_play()
        self.plank_move(keys)
        self.ball_move()
        self.game_text_blit()

    def multi_game(self, keys, mouse_pos, mouse_chick_status):
        self.game_line(keys, mouse_pos, mouse_chick_status)
        self.player_icon()
        self.game_play()
        self.plank_move(keys)
        self.multi_p2plank_darw()
        self.ball_move()
        self.game_text_blit()

    def create_room_config_inface(self, keys, mouse_pos: tuple, mouse_chick_status: tuple):

        room_name_str = '房间名称'
        player_name_str = '你的名称'
        room_config_str = '房间配置'
        create_room_str = '创建房间'
        back_str = '返回'
        server_port_str = '服务器端口'
        self.create_room_inface_rect = pygame.draw.rect(self.screen, WIRTE, (0, 0, WIDTH, HEIGHT))
        self.room_config_str_rect = pygame.draw.rect(self.screen, BLACK, (
        WIDTH // 2 - WIDTH // 8, HEIGHT // 3 - HEIGHT // 6, WIDTH // 4, HEIGHT // 12))
        self.create_room_rect = pygame.draw.rect(self.screen, BLACK, (
        WIDTH // 2 + WIDTH // 40, HEIGHT // 2 + HEIGHT // 20, WIDTH // 10, HEIGHT // 20), 5)
        self.create_room_back_multuimode_rect = pygame.draw.rect(self.screen, BLACK, (
        WIDTH // 2 - WIDTH // 8, HEIGHT // 2 + HEIGHT // 20, WIDTH // 10, HEIGHT // 20), 5)

        self.room_name_str_rect = pygame.draw.rect(self.screen, BLACK, (
        WIDTH // 2 - WIDTH // 8, HEIGHT // 2 - HEIGHT // 6, WIDTH // 12, HEIGHT // 20), 2)
        self.room_name_rect = pygame.draw.rect(self.screen, BLACK, (
        WIDTH // 3 + WIDTH // 8, HEIGHT // 2 - HEIGHT // 6, WIDTH // 6, HEIGHT // 20), 2)
        self.register_RectID(self.room_name_rect, room_name_str)
        self.create_room_player_name_str_rect = pygame.draw.rect(self.screen, BLACK, (
        WIDTH // 2 - WIDTH // 8, HEIGHT // 2 - HEIGHT // 10, WIDTH // 12, HEIGHT // 20), 2)
        self.create_room_player_name_rect = pygame.draw.rect(self.screen, BLACK, (
        WIDTH // 3 + WIDTH // 8, HEIGHT // 2 - HEIGHT // 10, WIDTH // 6, HEIGHT // 20), 2)
        self.register_RectID(self.create_room_player_name_rect, "玩家名称")
        self.create_room_server_port_str_rect = pygame.draw.rect(self.screen, BLACK, (
        WIDTH - WIDTH // 12 * 2, HEIGHT - HEIGHT / 25 - 10, WIDTH // 12, HEIGHT / 25), 3)
        self.create_room_server_port_rect = pygame.draw.rect(self.screen, BLACK, (
        WIDTH - WIDTH // 12, HEIGHT - HEIGHT / 25 - 10, WIDTH // 12, HEIGHT / 25), 3)
        self.register_RectID(self.create_room_server_port_rect, server_port_str)

        self.game_font_render(self.default_font, self.screen, room_config_str, 40, WIRTE,
                              text_pos=self.room_config_str_rect.center)
        self.game_font_render(self.default_font, self.screen, room_name_str, 14, BLACK,
                              text_pos=self.room_name_str_rect.center)
        self.game_font_render(self.default_font, self.screen, player_name_str, 14, BLACK,
                              text_pos=self.create_room_player_name_str_rect.center)
        self.game_font_render(self.default_font, self.screen, create_room_str, 16, BLACK,
                              text_pos=self.create_room_rect.center)
        self.game_font_render(self.default_font, self.screen, back_str, 16, BLACK,
                              text_pos=self.create_room_back_multuimode_rect.center)
        self.game_font_render(self.default_font, self.screen, server_port_str, 10, BLACK,
                              text_pos=self.create_room_server_port_str_rect.center)

        self.select_input_rect(
            [self.create_room_player_name_rect, self.room_name_rect, self.create_room_server_port_rect], BLACK, keys,
            mouse_pos, mouse_chick_status)

    def new_room_menu(self):
        self.get_clinet_data()
        self.input_text_dict = self.text_set_value()
        user1_name_str = '佚名'
        room_name_str = f'{user1_name_str}的房间'
        if len(self.input_text_dict['玩家名称']) > 0:
            user1_name_str = self.input_text_dict['玩家名称']
        else:
            user1_name_str = '佚名'
        if len(self.input_text_dict['房间名称']) > 0:
            room_name_str = self.input_text_dict['房间名称']
        else:
            room_name_str = f'{user1_name_str}的房间'
        self.input_text_dict['房间名称'] = room_name_str
        self.text_rect_dict['房间名称'][1] = room_name_str
        self.input_text_dict['玩家名称'] = user1_name_str
        self.text_rect_dict['玩家名称'][1] = user1_name_str

        user1_id_str = '房主'
        user2_id_str = '成员'
        user1_icon_surf = pygame.transform.scale(pygame.image.load(self.player_dict[PLAYER1]['icon']),
                                                 (WIDTH // 6, HEIGHT // 4)).convert_alpha()
        VS_str = 'VS'
        wait_join_str = '等待加入……'
        backmenu_button_str = '返回'
        room_config_button_str = '房间设置'
        startgame_button_str = '开始游戏'

        self.new_room_inface_rect = pygame.draw.rect(self.screen, WIRTE, (0, 0, WIDTH, HEIGHT))
        self.new_room_name_str_rect = pygame.draw.rect(self.screen, WIRTE, (
        WIDTH // 2 - WIDTH // 12, HEIGHT // 10 - HEIGHT // 9 // 10, WIDTH // 6, HEIGHT // 15))
        self.new_room_info_str_rect = pygame.draw.rect(self.screen, BLACK, (
        WIDTH // 2 - WIDTH // 4, HEIGHT // 5 - HEIGHT // 10 // 5, WIDTH // 2, HEIGHT // 25))
        self.user1_id_str_rect = pygame.draw.rect(self.screen, BLACK, (
        WIDTH // 4 - WIDTH // 16, HEIGHT // 2 - HEIGHT // 4, WIDTH // 8, HEIGHT // 12), 3)
        self.user1_icon_rect = pygame.draw.rect(self.screen, BLACK, (
        WIDTH // 4 - WIDTH // 12, HEIGHT // 2 - HEIGHT // 8, WIDTH // 6, HEIGHT // 4), 1)
        self.user1_name_str_rect = pygame.draw.rect(self.screen, RED, (
        WIDTH // 4 - WIDTH // 12, HEIGHT // 2 + HEIGHT // 7, WIDTH // 6, HEIGHT // 16), 3)
        self.VS_str_rect = pygame.draw.rect(self.screen, WIRTE,
                                            (WIDTH // 2 - WIDTH // 12, HEIGHT // 3, WIDTH // 6, HEIGHT // 4))
        self.back_multuimenu_button_rect = pygame.draw.rect(self.screen, BLACK, (
        WIDTH // 4 - WIDTH // 16, HEIGHT - HEIGHT // 6, WIDTH // 8, HEIGHT // 15))
        self.new_room_config_button_rect = pygame.draw.rect(self.screen, BLACK, (
        WIDTH // 2 - WIDTH // 16, HEIGHT - HEIGHT // 6, WIDTH // 8, HEIGHT // 15))
        self.startgame_button_rect = pygame.draw.rect(self.screen, BLACK, (
        WIDTH - WIDTH // 4 - WIDTH // 16, HEIGHT - HEIGHT // 6, WIDTH // 8, HEIGHT // 15))

        self.game_font_render(self.default_font, self.screen, room_name_str, 60, BLACK,
                              text_pos=self.new_room_name_str_rect.center)
        self.game_font_render(self.default_font, self.screen, user1_id_str, 50, BLACK,
                              text_pos=self.user1_id_str_rect.center)
        self.screen.blit(user1_icon_surf, self.user1_icon_rect)
        self.game_font_render(self.default_font, self.screen, user1_name_str, 30, RED,
                              text_pos=self.user1_name_str_rect.center)
        self.game_font_render(self.default_font, self.screen, VS_str, 160, BLACK, text_pos=self.VS_str_rect.center)
        self.game_font_render(self.default_font, self.screen, backmenu_button_str, 30, WIRTE,
                              text_pos=self.back_multuimenu_button_rect.center)
        self.game_font_render(self.default_font, self.screen, room_config_button_str, 30, WIRTE,
                              text_pos=self.new_room_config_button_rect.center)
        self.game_font_render(self.default_font, self.screen, startgame_button_str, 30, WIRTE,
                              text_pos=self.startgame_button_rect.center)
        if self.all_client_dict:
            if self.all_client_dict['player_info'][PLAYER2]['isjoinroom']:
                user2_name_str = self.all_client_dict['player_info'][PLAYER2]['name']

                user2_icon_surf = pygame.transform.scale(
                    pygame.image.load(self.all_client_dict['player_info'][PLAYER2]['icon']),
                    (WIDTH // 6, HEIGHT // 4)).convert_alpha()
                self.user2_id_str_rect = pygame.draw.rect(self.screen, BLACK, (
                WIDTH - WIDTH // 4 - WIDTH // 16, HEIGHT // 2 - HEIGHT // 4, WIDTH // 8, HEIGHT // 12), 3)
                self.user2_icon_rect = pygame.draw.rect(self.screen, BLACK, (
                WIDTH - WIDTH // 4 - WIDTH // 12, HEIGHT // 2 - HEIGHT // 8, WIDTH // 6, HEIGHT // 4), 1)
                self.user2_name_str_rect = pygame.draw.rect(self.screen, GREEN, (
                WIDTH - WIDTH // 4 - WIDTH // 12, HEIGHT // 2 + HEIGHT // 7, WIDTH // 6, HEIGHT // 16), 3)
                self.screen.blit(user2_icon_surf, self.user2_icon_rect)
                self.game_font_render(self.default_font, self.screen, user2_id_str, 50, BLACK,
                                      text_pos=self.user2_id_str_rect.center)
                self.game_font_render(self.default_font, self.screen, user2_name_str, 30, GREEN,
                                      text_pos=self.user2_name_str_rect.center)
        else:
            self.wait_join_room_rect = pygame.draw.rect(self.screen, BLACK, (
            WIDTH - WIDTH // 4 - WIDTH // 12, HEIGHT // 2 - HEIGHT // 8, WIDTH // 6, HEIGHT // 4))
            self.game_font_render(self.default_font, self.screen, wait_join_str, fgcolor=WIRTE,
                                  draw_text_rect=self.wait_join_room_rect)

    def get_clinet_data(self):
        if self.multi_game_client:
            cs_str = self.multi_game_client.get_data()
            if cs_str != None:
                self.all_client_dict = json.loads(cs_str.decode('utf-8'))

    def new_room_button_action(self, mouse_pos: tuple, mouse_chick_status: tuple):
        if self.back_multuimenu_button_rect.collidepoint(mouse_pos) and mouse_chick_status[0]:
            self.game_mode_state = CREATEROOMCONFIG
            self.game_all_status[self.iscreateserver] = False
            self.multi_game_server.stop()
            self.multi_game_client.stop()

        if self.new_room_config_button_rect.collidepoint(mouse_pos) and mouse_chick_status[0]:
            self.game_mode_state = ROOMCONFIGMENU
        if self.startgame_button_rect.collidepoint(mouse_pos) and mouse_chick_status[0]:
            if self.all_client_dict:
                if self.all_client_dict['player_info'][PLAYER2]['isready']:
                    self.game_mode_state = MULTISTARTGAME
                    self.game_all_status[self.ismulti_startgame] = True
                else:
                    print('还有玩家未准备！！')

    def room_config_menu(self, current_state, keys, mouse_pos: tuple, mouse_chick_status: tuple):
        new_room_config_str = "房间设置"
        ball_speed_str = '球移动速度:'
        plank_speed_str = '竖板移动速度:'
        round_mod_str = '选择回合制(默认三回合制)'
        one_round_str = '一回合制'
        one_round_help_str = '三分一回合，一回合一大分，三大分一局'
        three_round_str = '三回合制'
        three_round_help_str = '三分一回合，三回合一大分，三大分一局'
        five_round_str = '五回合制'
        five_round_help_str = '三分一回合，五回合一大分，三大分一局'
        confirm_str = '确认'
        back_str = '返回'

        if current_state == NEWROOMMENU:
            self.new_room_menu()
        elif current_state == SINGLE:
            self.game_line(keys, mouse_pos, mouse_chick_status)
        self.new_room_config_inface_rect = pygame.draw.rect(self.screen, (200, 200, 200), (
        WIDTH // 2 - WIDTH // 4, HEIGHT // 2 - HEIGHT // 4, WIDTH // 2, HEIGHT // 2))
        self.new_room_config_str_rect = pygame.draw.rect(self.screen, BLACK, (
        self.new_room_config_inface_rect.centerx - self.new_room_config_inface_rect.w // 4,
        self.new_room_config_inface_rect.centery - self.new_room_config_inface_rect.h // 3 - self.new_room_config_inface_rect.h // 10,
        self.new_room_config_inface_rect.w // 2, self.new_room_config_inface_rect.h // 8))

        self.ball_speed_frame_rect = pygame.draw.rect(self.screen, BLACK, (
        self.new_room_config_inface_rect.centerx - self.new_room_config_inface_rect.w // 4 - self.new_room_config_inface_rect.w // 8,
        self.new_room_config_inface_rect.centery - self.new_room_config_inface_rect.h // 3 + self.new_room_config_inface_rect.h // 20,
        self.new_room_config_inface_rect.w // 2 + self.new_room_config_inface_rect.w // 4,
        self.new_room_config_inface_rect.h // 8))
        self.ball_spped_str_rect = self.ball_speed_frame_rect.inflate(-self.ball_speed_frame_rect.w // 2, 0)
        self.ball_spped_rect = self.ball_speed_frame_rect.inflate(-self.ball_speed_frame_rect.w // 2, 0)
        self.register_RectID(self.ball_spped_rect, '球移动速度')
        self.ball_spped_str_rect.midleft = self.ball_speed_frame_rect.midleft
        self.ball_spped_rect.midright = self.ball_speed_frame_rect.midright

        pygame.draw.rect(self.screen, WIRTE, self.ball_spped_rect, 1)

        self.plank_speed_frame_rect = pygame.draw.rect(self.screen, BLACK, (
        self.new_room_config_inface_rect.centerx - self.new_room_config_inface_rect.w // 4 - self.new_room_config_inface_rect.w // 8,
        self.new_room_config_inface_rect.centery - self.new_room_config_inface_rect.h // 4 + self.new_room_config_inface_rect.h // 8,
        self.new_room_config_inface_rect.w // 2 + self.new_room_config_inface_rect.w // 4,
        self.new_room_config_inface_rect.h // 8))
        self.plank_spped_str_rect = self.plank_speed_frame_rect.inflate(-self.plank_speed_frame_rect.w // 2, 0)
        self.plank_spped_rect = self.plank_speed_frame_rect.inflate(-self.plank_speed_frame_rect.w // 2, 0)
        self.register_RectID(self.plank_spped_rect, "竖板移动速度")
        self.plank_spped_str_rect.midleft = self.plank_speed_frame_rect.midleft
        self.plank_spped_rect.midright = self.plank_speed_frame_rect.midright
        pygame.draw.rect(self.screen, WIRTE, self.plank_spped_rect, 1)

        self.round_frame_rect = pygame.draw.rect(self.screen, BLACK, (
        self.new_room_config_inface_rect.centerx - self.new_room_config_inface_rect.w // 4 - self.new_room_config_inface_rect.w // 8,
        self.new_room_config_inface_rect.centery + self.new_room_config_inface_rect.h // 32,
        self.new_room_config_inface_rect.w // 2 + self.new_room_config_inface_rect.w // 4,
        self.new_room_config_inface_rect.h // 3))
        self.register_RectID(self.round_frame_rect, '回合制')
        self.round_str_rect = self.round_frame_rect.inflate(0, -self.round_frame_rect.h // 4 * 3)
        self.round_str_rect.midtop = self.round_frame_rect.midtop

        self.round_one_frame_rect = self.round_frame_rect.inflate(0, -self.round_frame_rect.h // 4 * 3)
        self.round_one_str_rect = self.round_one_frame_rect.inflate(-self.round_one_frame_rect.w // 4 * 3,
                                                                    -self.round_one_frame_rect.h // 4)
        self.round_one_rect = self.round_one_frame_rect.inflate(-self.round_one_frame_rect.w // 4, 0)
        self.round_one_frame_rect.midtop = self.round_str_rect.midbottom
        self.round_one_str_rect.midright = self.round_one_frame_rect.midright
        self.round_one_rect.midleft = self.round_one_frame_rect.midleft
        self.register_RectID(self.round_one_frame_rect, '一回合制')

        self.round_three_frame_rect = self.round_frame_rect.inflate(0, -self.round_frame_rect.h // 4 * 3)
        self.round_three_str_rect = self.round_three_frame_rect.inflate(-self.round_three_frame_rect.w // 4 * 3,
                                                                        -self.round_three_frame_rect.h // 4)
        self.round_three_rect = self.round_three_frame_rect.inflate(-self.round_three_frame_rect.w // 4, 0)
        self.round_three_frame_rect.midtop = self.round_one_frame_rect.midbottom
        self.round_three_str_rect.midright = self.round_three_frame_rect.midright
        self.round_three_rect.midleft = self.round_three_frame_rect.midleft
        self.register_RectID(self.round_three_frame_rect, '三回合制')

        self.round_five_frame_rect = self.round_frame_rect.inflate(0, -self.round_frame_rect.h // 4 * 3)
        self.round_five_str_rect = self.round_five_frame_rect.inflate(-self.round_five_frame_rect.w // 4 * 3,
                                                                      -self.round_five_frame_rect.h // 4)
        self.round_five_rect = self.round_five_frame_rect.inflate(-self.round_five_frame_rect.w // 4, 0)
        self.round_five_frame_rect.midtop = self.round_three_frame_rect.midbottom
        self.round_five_str_rect.midright = self.round_five_frame_rect.midright
        self.round_five_rect.midleft = self.round_five_frame_rect.midleft
        self.register_RectID(self.round_five_frame_rect, '五回合制')

        self.confim_str_button_rect = pygame.draw.rect(self.screen, BLACK, (
        self.new_room_config_inface_rect.centerx - self.new_room_config_inface_rect.w // 3,
        self.new_room_config_inface_rect.centery + self.new_room_config_inface_rect.h // 2.7,
        self.new_room_config_inface_rect.w // 5,
        self.new_room_config_inface_rect.h // 10))
        self.back_str_button_rect = pygame.draw.rect(self.screen, BLACK, (
        self.new_room_config_inface_rect.centerx + self.new_room_config_inface_rect.w // 3 - self.new_room_config_inface_rect.w // 5,
        self.new_room_config_inface_rect.centery + self.new_room_config_inface_rect.h // 2.7,
        self.new_room_config_inface_rect.w // 5,
        self.new_room_config_inface_rect.h // 10))

        self.game_font_render(self.default_font, self.screen, new_room_config_str, fgcolor=WIRTE,
                              draw_text_rect=self.new_room_config_str_rect)
        self.game_font_render(self.default_font, self.screen, ball_speed_str, fgcolor=WIRTE,
                              draw_text_rect=self.ball_spped_str_rect)
        self.game_font_render(self.default_font, self.screen, plank_speed_str, fgcolor=WIRTE,
                              draw_text_rect=self.plank_spped_str_rect)
        self.game_font_render(self.default_font, self.screen, round_mod_str, fgcolor=WIRTE,
                              draw_text_rect=self.round_str_rect)
        self.game_font_render(self.default_font, self.screen, one_round_str, fgcolor=WIRTE,
                              draw_text_rect=self.round_one_str_rect)
        self.game_font_render(self.default_font, self.screen, one_round_help_str, fgcolor=WIRTE,
                              draw_text_rect=self.round_one_rect)

        self.game_font_render(self.default_font, self.screen, three_round_str, fgcolor=WIRTE,
                              draw_text_rect=self.round_three_str_rect)
        self.game_font_render(self.default_font, self.screen, three_round_help_str, fgcolor=WIRTE,
                              draw_text_rect=self.round_three_rect)

        self.game_font_render(self.default_font, self.screen, five_round_str, fgcolor=WIRTE,
                              draw_text_rect=self.round_five_str_rect)
        self.game_font_render(self.default_font, self.screen, five_round_help_str, fgcolor=WIRTE,
                              draw_text_rect=self.round_five_rect)

        self.game_font_render(self.default_font, self.screen, confirm_str, fgcolor=WIRTE,
                              draw_text_rect=self.confim_str_button_rect)
        self.game_font_render(self.default_font, self.screen, back_str, fgcolor=WIRTE,
                              draw_text_rect=self.back_str_button_rect)

        self.select_input_rect([self.ball_spped_rect, self.plank_spped_rect], WIRTE, keys, mouse_pos,
                               mouse_chick_status)
        self.input_strs_dict = {k: v for k, v in self.text_set_value().items() if
                                k in [ball_speed_str[0:-1:1], plank_speed_str[0:-1:1]]}
        self.select_round(mouse_pos, mouse_chick_status)
        if self.back_str_button_rect.collidepoint(mouse_pos) and mouse_chick_status[0]:
            self.text_rect_dict[ball_speed_str[0:-1:1]] = [self.text_rect_dict[ball_speed_str[0:-1:1]][0], '',
                                                           self.text_rect_dict[ball_speed_str[0:-1:1]][2]]
            self.text_rect_dict[plank_speed_str[0:-1:1]] = [self.text_rect_dict[plank_speed_str[0:-1:1]][0], '',
                                                            self.text_rect_dict[plank_speed_str[0:-1:1]][2]]
            self.input_strs_dict = {k: '' for k, v in self.input_strs_dict.items()}
            self.return_rects.clear()
            self.confirm_rect = None
            self.game_mode_state = current_state
        if self.confim_str_button_rect.collidepoint(mouse_pos) and mouse_chick_status[0]:
            self.ball_speed = int(self.input_strs_dict[ball_speed_str[0:-1:1]])
            self.plank1_pos_y = self.plank1_default_pos_y
            self.plank2_pos_y = self.plank2_default_pos_y
            self.plank_speed = int(self.input_strs_dict[plank_speed_str[0:-1:1]])

            if self.input_strs_dict['回合制'] == one_round_str:
                self.max_small_round = 1
            elif self.input_strs_dict['回合制'] == three_round_str:
                self.max_small_round = 3
            elif self.input_strs_dict['回合制'] == five_round_str:
                self.max_small_round = 5
            else:
                self.max_small_round = 3
            self.game_mode_state = current_state

    def select_round(self, mouse_pos: tuple, mouse_chick_status: tuple):
        select_rectses = [[self.round_one_frame_rect, self.round_one_str_rect, self.round_one_rect],
                          [self.round_three_frame_rect, self.round_three_str_rect, self.round_three_rect],
                          [self.round_five_frame_rect, self.round_five_str_rect, self.round_five_rect]]
        for rects in select_rectses:
            if rects[0].collidepoint(mouse_pos):
                pygame.draw.rect(self.screen, WIRTE, rects[0], 1)
                if mouse_chick_status[0]:
                    self.return_rects = [rects[0], rects[1], rects[2]]
                    self.confirm_rect = self.find_reg_rect_id(rects[0])
                if mouse_chick_status[2]:
                    self.return_rects.clear()
                    self.confirm_rect = None

        self.input_strs_dict[self.find_reg_rect_id(self.round_frame_rect)] = self.confirm_rect
        if len(self.return_rects) != 0:
            pygame.draw.rect(self.screen, GREEN, self.return_rects[0], 1)
            pygame.draw.rect(self.screen, BLUE, self.return_rects[1], 1)
            pygame.draw.rect(self.screen, RED, self.return_rects[2], 1)

    def join_room_inface(self, keys, mouse_pos: tuple, mouse_chick_status: tuple):
        join_room_str = '加入房间'
        player_name_str = '玩家名称'
        port_str = '服务器端口'
        back_str = '返回'
        select_str = '搜索房间'
        self.join_room_inface_rect = pygame.draw.rect(self.screen, WIRTE, self.screen_rect)
        self.join_room_inface_str_rect = pygame.draw.rect(self.screen, WIRTE, (
        WIDTH // 2 - WIDTH // 8, HEIGHT // 3 - HEIGHT // 6, WIDTH // 4, HEIGHT // 12))

        self.join_room_player_name_frame_rect = pygame.draw.rect(self.screen, WIRTE, (
        WIDTH // 2 - WIDTH // 8, HEIGHT // 3, WIDTH // 4, HEIGHT // 20), )
        self.join_room_player_name_str_rect = self.join_room_player_name_frame_rect.inflate(
            -self.join_room_player_name_frame_rect.w // 2, 0)
        self.join_room_player_name_rect = self.join_room_player_name_frame_rect.inflate(
            -self.join_room_player_name_frame_rect.w // 2, 0)
        self.join_room_player_name_str_rect.midleft = self.join_room_player_name_frame_rect.midleft
        self.join_room_player_name_rect.midright = self.join_room_player_name_frame_rect.midright
        self.register_RectID(self.join_room_player_name_rect, player_name_str)

        self.join_room_server_port_frame_rect = pygame.draw.rect(self.screen, WIRTE, (
        WIDTH // 2 - WIDTH // 8, HEIGHT // 3 + HEIGHT // 10, WIDTH // 4, HEIGHT // 20))
        self.join_room_server_port_str_rect = self.join_room_server_port_frame_rect.inflate(
            -self.join_room_server_port_frame_rect.w // 2, 0)
        self.join_room_server_port_rect = self.join_room_server_port_frame_rect.inflate(
            -self.join_room_server_port_frame_rect.w // 2, 0)
        self.join_room_server_port_str_rect.midleft = self.join_room_server_port_frame_rect.midleft
        self.join_room_server_port_rect.midright = self.join_room_server_port_frame_rect.midright
        self.register_RectID(self.join_room_server_port_rect, port_str)

        self.join_room_button_frame_rect = pygame.draw.rect(self.screen, WIRTE, (
        WIDTH // 2 - WIDTH // 8, HEIGHT // 2 + HEIGHT // 10, WIDTH // 4, HEIGHT // 20))
        self.join_room_back_multuimode_rect = self.join_room_button_frame_rect.inflate(
            -self.join_room_button_frame_rect.w // 3 * 1.7, 0)
        self.join_room_select_room_rect = self.join_room_button_frame_rect.inflate(
            -self.join_room_button_frame_rect.w // 3 * 1.7, 0)
        self.join_room_back_multuimode_rect.midleft = self.join_room_button_frame_rect.midleft
        self.join_room_select_room_rect.midright = self.join_room_button_frame_rect.midright

        pygame.draw.rect(self.screen, BLACK, self.join_room_player_name_str_rect, 2)
        pygame.draw.rect(self.screen, BLACK, self.join_room_player_name_rect, 2)
        pygame.draw.rect(self.screen, BLACK, self.join_room_server_port_str_rect, 2)
        pygame.draw.rect(self.screen, BLACK, self.join_room_server_port_rect, 2)
        pygame.draw.rect(self.screen, BLACK, self.join_room_back_multuimode_rect, 3)
        pygame.draw.rect(self.screen, BLACK, self.join_room_select_room_rect, 3)

        self.game_font_render(self.default_font, self.screen, join_room_str, fgcolor=BLACK, size=70,
                              text_pos=self.join_room_inface_str_rect.center)
        self.game_font_render(self.default_font, self.screen, player_name_str, fgcolor=BLACK,
                              draw_text_rect=self.join_room_player_name_str_rect)
        self.game_font_render(self.default_font, self.screen, port_str, fgcolor=BLACK,
                              draw_text_rect=self.join_room_server_port_str_rect)
        self.game_font_render(self.default_font, self.screen, back_str, fgcolor=BLACK,
                              draw_text_rect=self.join_room_back_multuimode_rect)
        self.game_font_render(self.default_font, self.screen, select_str, fgcolor=BLACK,
                              draw_text_rect=self.join_room_select_room_rect)

        self.select_input_rect([self.join_room_player_name_rect, self.join_room_server_port_rect], BLACK, keys,
                               mouse_pos, mouse_chick_status)

    def wait_select_inface(self):
        self.wait_select_timer.start(3000)
        wait_str = '正在搜索房间……'
        self.wait_select_inface_rect = pygame.draw.rect(self.screen, BLACK, self.screen.get_rect())
        self.game_font_render(self.default_font, self.screen, wait_str, size=100, fgcolor=WIRTE,
                              text_pos=self.wait_select_inface_rect.center)
        if self.wait_select_timer.isactive and self.wait_select_timer.update_time():
            self.game_mode_state = JOINWAITINFACE
        else:
            self.wait_select_timer.stop()
            self.current_user = PLAYER2
            self.game_mode_state = JOINROOMINFACE
            self.player_dict[PLAYER2]['isjoinroom'] = True
            self.find_room()

    def new_room_connect(self):
        pass

    def multi_init(self):
        self.loacal_ip = socket.gethostbyname(socket.gethostname())
        # self.wlan_ip = Server.wlan_ip()
        port = 8888
        self.addr = self.host, self.port = '127.0.0.1', port
        self.buf = 1024
        self.back = 2

    def room_manager(self, keys, mouse_pos, mouse_chick_status):
        self.get_clinet_data()
        self.multi_game(keys, mouse_pos, mouse_chick_status)

    def create_room(self):
        if not self.game_all_status[self.iscreateserver]:
            self.multi_init()
            self.multi_game_server = Server(self.addr, self.buf, self.put_cs_data(), self.back)
            self.server_threading = threading.Thread(target=self.multi_game_server.start)
            self.server_threading.daemon = True
            self.server_threading.start()
            self.find_room()
            self.game_all_status[self.iscreateserver] = True

            print('房间服务器创建成功！')

    def delete_room(self, room_ID):
        pass

    def find_room(self):
        if not self.game_all_status[self.isconnect]:
            if self.clock.get_fps() != 0:
                fps = 1 / self.clock.get_fps()
            self.multi_init()
            self.multi_game_client = Client(self.addr, self.buf, self.put_cs_data())
            self.client_threading = threading.Thread(target=self.multi_game_client.start, args=(self.put_cs_data, fps))
            self.client_threading.daemon = True
            self.client_threading.start()
            self.game_all_status[self.isconnect] = True

    def player2_join_room_inface(self, keys, mouse_pos: tuple, mouse_chick_status: tuple):
        self.get_clinet_data()
        user1_name_str = '佚名'
        user2_name_str = '佚名'
        room_name_str = f'{user1_name_str}的房间'
        user2_name_str = '玩家2'
        user1_id_str = '房主'
        user2_id_str = '成员'
        user1_icon_surf = pygame.transform.scale(pygame.image.load(self.player_dict[PLAYER2]['icon']),
                                                 (WIDTH // 6, HEIGHT // 4)).convert_alpha()
        user2_icon_surf = pygame.transform.scale(pygame.image.load(self.player_dict[PLAYER2]['icon']),
                                                 (WIDTH // 6, HEIGHT // 4)).convert_alpha()
        VS_str = 'VS'
        backmenu_button_str = '退出房间'
        no_ready_button_str = '未准备'
        ready_button_str = '准备中'

        if self.all_client_dict:
            if self.all_client_dict['player_info'][PLAYER1]['isjoinroom']:
                user1_name_str = self.all_client_dict['player_info'][PLAYER1]['name']
                user1_icon_surf = pygame.transform.scale(
                    pygame.image.load(self.all_client_dict['player_info'][PLAYER1]['icon']),
                    (WIDTH // 6, HEIGHT // 4)).convert_alpha()
        self.join_new_room_inface_rect = pygame.draw.rect(self.screen, WIRTE, (0, 0, WIDTH, HEIGHT))
        self.join_new_room_name_str_rect = pygame.draw.rect(self.screen, WIRTE, (
        WIDTH // 2 - WIDTH // 12, HEIGHT // 10 - HEIGHT // 9 // 10, WIDTH // 6, HEIGHT // 15))
        self.join_new_room_info_str_rect = pygame.draw.rect(self.screen, BLACK, (
        WIDTH // 2 - WIDTH // 4, HEIGHT // 5 - HEIGHT // 10 // 5, WIDTH // 2, HEIGHT // 25))
        self.join_user1_id_str_rect = pygame.draw.rect(self.screen, BLACK, (
        WIDTH // 4 - WIDTH // 16, HEIGHT // 2 - HEIGHT // 4, WIDTH // 8, HEIGHT // 12), 3)
        self.join_user2_id_str_rect = pygame.draw.rect(self.screen, BLACK, (
        WIDTH - WIDTH // 4 - WIDTH // 16, HEIGHT // 2 - HEIGHT // 4, WIDTH // 8, HEIGHT // 12), 3)
        self.join_user1_icon_rect = pygame.draw.rect(self.screen, BLACK, (
        WIDTH // 4 - WIDTH // 12, HEIGHT // 2 - HEIGHT // 8, WIDTH // 6, HEIGHT // 4), 1)
        self.join_user2_icon_rect = pygame.draw.rect(self.screen, BLACK, (
        WIDTH - WIDTH // 4 - WIDTH // 12, HEIGHT // 2 - HEIGHT // 8, WIDTH // 6, HEIGHT // 4), 1)
        self.join_user1_name_str_rect = pygame.draw.rect(self.screen, RED, (
        WIDTH // 4 - WIDTH // 12, HEIGHT // 2 + HEIGHT // 7, WIDTH // 6, HEIGHT // 16), 3)
        self.join_user2_name_str_rect = pygame.draw.rect(self.screen, GREEN, (
        WIDTH - WIDTH // 4 - WIDTH // 12, HEIGHT // 2 + HEIGHT // 7, WIDTH // 6, HEIGHT // 16), 3)
        self.join_room_VS_str_rect = pygame.draw.rect(self.screen, WIRTE,
                                                      (WIDTH // 2 - WIDTH // 12, HEIGHT // 3, WIDTH // 6, HEIGHT // 4))
        self.join_room_back_multuimenu_button_rect = pygame.draw.rect(self.screen, BLACK, (
        WIDTH // 4 - WIDTH // 16, HEIGHT - HEIGHT // 6, WIDTH // 8, HEIGHT // 15))
        self.ready_button_rect = pygame.draw.rect(self.screen, BLACK, (
        WIDTH - WIDTH // 4 - WIDTH // 16, HEIGHT - HEIGHT // 6, WIDTH // 8, HEIGHT // 15))

        self.game_font_render(self.default_font, self.screen, room_name_str, 60, BLACK,
                              text_pos=self.join_new_room_name_str_rect.center)
        self.game_font_render(self.default_font, self.screen, user1_id_str, 50, BLACK,
                              text_pos=self.join_user1_id_str_rect.center)
        self.game_font_render(self.default_font, self.screen, user2_id_str, 50, BLACK,
                              text_pos=self.join_user2_id_str_rect.center)
        self.screen.blit(user1_icon_surf, self.join_user1_icon_rect)
        self.screen.blit(user2_icon_surf, self.join_user2_icon_rect)
        self.game_font_render(self.default_font, self.screen, user1_name_str, 30, RED,
                              text_pos=self.join_user1_name_str_rect.center)
        self.game_font_render(self.default_font, self.screen, user2_name_str, 30, GREEN,
                              text_pos=self.join_user2_name_str_rect.center)
        self.game_font_render(self.default_font, self.screen, VS_str, 160, BLACK,
                              text_pos=self.join_room_VS_str_rect.center)
        self.game_font_render(self.default_font, self.screen, backmenu_button_str, 30, WIRTE,
                              text_pos=self.join_room_back_multuimenu_button_rect.center)
        if self.ready_button_rect.collidepoint(mouse_pos) and mouse_chick_status[0]:
            for event in self.events:
                if event.type == pygame.MOUSEBUTTONDOWN:
                    if self.player_dict[PLAYER2]['isready']:
                        self.player_dict[PLAYER2]['isready'] = False
                    else:
                        self.player_dict[PLAYER2]['isready'] = True

        if self.player_dict[PLAYER2]['isready']:
            self.game_font_render(self.default_font, self.screen, ready_button_str, fgcolor=WIRTE,
                                  draw_text_rect=self.ready_button_rect)
        else:
            self.game_font_render(self.default_font, self.screen, no_ready_button_str, fgcolor=WIRTE,
                                  draw_text_rect=self.ready_button_rect)

        if self.join_room_back_multuimenu_button_rect.collidepoint(mouse_pos) and mouse_chick_status[0]:
            self.player_dict[PLAYER2]['isjoinroom'] = False
            self.player_dict[PLAYER2]['isready'] = False
            self.multi_game_client.stop()
            self.game_all_status[self.isconnect] = False
            self.game_mode_state = JOINROOMMENU
        self.player2_monitor_start_state()

    def player2_monitor_start_state(self):
        if self.all_client_dict:
            if self.all_client_dict['connect_status_info']['is_multi_startgame']:
                self.game_mode_state = MULTISTARTGAME
                self.game_all_status[self.ismulti_startgame] = True

    def kick_out_player(self):
        pass

    def select_input_rect(self, rects, text_color, keys, mouse_pos: tuple, mouse_chick_status: tuple):
        '''
        此方法是进行文本输入，具体是通过传入的矩形列表，进行锁定矩形后传入文本打印到对应的矩形中。
        注意！！！传入的矩形一定是通过self.register_RectID()注册id的矩形，否则将无法获取您所输入的信息
        需要在类中定义：self.isinputstr(bool),self.ischangestr(bool),self.input_str(str),self.change_str(str),self.input_rect(None),
        self.change_rect(None),self.need_input_rect(None),self.need_input_str(str),self.need_change_rect(None),self.need_change_str(str),
        self.text_rect_list(list),self.max_text_rect(int)

        :param rects: 传入的矩形框列表
        :param keys: 键盘的对应值：pygame.key.get_pressed()
        :param mouse_pos:  鼠标的坐标：pygame.mouse.get_pos()
        :param mouse_chick_status: 鼠标的点击状态：pygame.mouse.get_pressed()
        :return: None
        '''
        self.max_text_rect = len(rects)
        for rect in rects:
            for rect_id, [list_rect, text, _] in self.text_rect_dict.items():  # 遍历有字符串的矩形列表所有元素
                if list_rect in rects:
                    if len(text) > 0:  # 当没有字符串时执行text_input（）当有字符串是执行text_change（）
                        if list_rect.collidepoint(mouse_pos):  # 检测当前鼠标坐标在那个矩形内
                            self.need_change_str = text  # 给需要修改的字符串和矩形赋值
                            self.need_change_rect = list_rect
                            if mouse_chick_status[0]:  # 鼠标左键点击当前鼠标坐标所在的矩形位置触发输入文字输入
                                self.game_all_status[self.ischangestr] = True  # 把输入状态更换成修改字符串
                                break

            else:  # 没有字符串时执行text_input（）

                if mouse_chick_status[0] and rect.collidepoint(mouse_pos):  # 鼠标当前坐标处于需要输入字符串的矩形内且左键已点击触发文字输入
                    self.game_all_status[self.isinputstr] = True  # 把输入状态更换成输入字符串
                    self.game_all_status[self.ischangestr] = False
                    self.need_input_rect = rect  # 给需要输入的矩形赋值

        if self.game_all_status[self.ischangestr] == True:  # 根据状态执行方法
            self.text_change(self.need_change_rect, self.need_change_str, text_color, keys, mouse_pos,
                             mouse_chick_status)
        elif self.game_all_status[self.isinputstr] == True:
            self.text_input(self.need_input_rect, text_color, keys, mouse_pos, mouse_chick_status)
        else:
            pygame.key.stop_text_input()  # 当所有状态都为False结束文本输入
            self.input_str = ''
        self.text_render(rects, text_color)  # 打印所有字符串

    def text_input(self, need_input_rect, text_color, keys, mouse_pos: tuple, mouse_chick_status: tuple):  # 文本输入方法
        self.input_rect = need_input_rect  # 基本赋值
        pygame.key.start_text_input()  # 开启文本输入模式
        pygame.key.set_text_input_rect(self.input_rect)  # 锁定文本输入矩形
        for event in self.events:  # 遍历事件
            if event.type == pygame.TEXTINPUT:  # 当event.type等于pygame.TEXTINPUT时监测事件中的字符串并提取出来
                self.input_str += event.text
            if keys[pygame.K_BACKSPACE]:  # 当按BACKSPACE键时删除最后一个字符
                self.input_str = self.input_str[:-1]  # 退格键
            if keys[pygame.K_RETURN]:  # 当按ENTER键时执行confirm_text（）并将输入状态关闭
                self.confirm_text(self.input_rect, self.input_str)
                self.game_all_status[self.isinputstr] = False
        self.game_font_render(self.default_font, self.screen, self.input_str, fgcolor=text_color,
                              draw_text_rect=self.input_rect)  # 临时打印

    def text_change(self, need_change_rect, need_change_str, test_color, keys, mouse_pos: tuple,
                    mouse_chick_status: tuple):  # 文本修改方法
        pygame.key.start_text_input()  # 开启文本输入模式
        pygame.key.set_text_input_rect(need_change_rect)  # 锁定文本输入矩形
        for rect, text, _ in self.text_rect_dict.values():  # 遍历有字符串的矩形列表
            if need_change_rect == rect and text == need_change_str:  # 锁定需修改的矩形和字符串
                for event in self.events:  # 遍历事件
                    if event.type == pygame.TEXTINPUT:  # 当event.type等于pygame.TEXTINPUT时监测事件中的字符串并提取出来
                        need_change_str += event.text  # 给需要修改的字符串赋值
                        self.change_str = need_change_str
                        self.reg_rect_edit_text(self.find_reg_rect_id(rect), self.change_str)  # 修改有字符串的矩形列表中元素的字符串
                    if event.type == KEYDOWN:  # 检测键盘是否按下
                        if keys[pygame.K_BACKSPACE]:  # 当按BACKSPACE键时删除最后一个字符
                            self.change_str = need_change_str
                            self.change_str = self.change_str[:-1]
                            self.reg_rect_edit_text(self.find_reg_rect_id(rect), self.change_str)  # 修改有字符串的矩形列表中元素的字符串

                        if keys[pygame.K_RETURN]:  # 当按ENTER键时退出修改状态
                            self.game_all_status[self.ischangestr] = False

    def register_RectID(self, rect, rect_id: str):  # 给此矩形注册ID
        '''
        此方法是给予您传入的矩形一个注册id，应是字符串

        :param rect: 需注册的矩形
        :param rect_id: 注册id
        :return:
        '''
        if rect_id not in self.register_rect_dict.keys():
            self.text_rect_dict[rect_id] = [rect, '', self.print_rect_state]  # 第一个值是矩形信息，第二个值是矩形字符串，
            self.register_rect_dict[rect_id] = rect  # 记录此矩形ID已注册

    def find_reg_rect_id(self, rect):  # 利用已经注册的矩形找到此矩形的ID
        rect_id = '此矩形未注册!'
        for k, v in self.text_rect_dict.items():
            if v[0] == rect:
                rect_id = k
        return rect_id

    def reg_rect_edit_text(self, rect_id, new_text):  # 修改或添加已注册的矩形内的文本
        for i, j in self.text_rect_dict.items():
            if self.find_reg_rect_id(j[0]) == rect_id:
                self.text_rect_dict[rect_id] = [j[0], new_text, j[2]]

    def confirm_text(self, rect, text):  # 确认字符串，传入矩形和字符串可以将此组成新的元素并加入有字符串的矩形列表
        if rect != None:
            if text != None:
                self.reg_rect_edit_text(self.find_reg_rect_id(rect), text)

    def text_render(self, render_rects, text_color):
        for i in self.text_rect_dict.values():
            if i[0] != None:
                if i[0] in render_rects:
                    self.game_font_render(self.default_font, self.screen, i[1], fgcolor=text_color, draw_text_rect=i[0])

    def text_set_value(self):
        '''
        此方法是将输入的字体都以字典的形式赋值出来

        '''
        new_dict = {}
        for k, v in self.text_rect_dict.items():
            new_dict[k] = v[1]
        return new_dict

    def start(self, fps):
        while True:
            self.clock.tick(fps)
            self.screen.fill(WIRTE)
            self.events = pygame.event.get()
            for event in self.events:
                if event.type == pygame.QUIT:
                    if self.multi_game_server:
                        self.multi_game_server.stop()
                    if self.multi_game_client:
                        self.multi_game_client.stop()
                    exit()
            keys = pygame.key.get_pressed()
            pygame.key.set_repeat()
            mouse_pos = pygame.mouse.get_pos()
            mouse_chick_status = pygame.mouse.get_pressed()

            self.game_mode(keys, mouse_pos, mouse_chick_status)
            self.game_button(mouse_pos, mouse_chick_status)

            pygame.display.update()


def main():
    game = Game((WIDTH, HEIGHT))
    game.start(FPS)


if __name__ == '__main__':
    main()
