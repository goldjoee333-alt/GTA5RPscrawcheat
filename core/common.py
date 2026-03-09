#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import threading
import time
import logging
import json
import os
import sys
import ctypes
import win32gui
import win32process
import win32con
import win32api
import queue
import subprocess
from typing import Dict, List, Callable, Any, Optional
from logging.handlers import RotatingFileHandler
import traceback
import pyautogui
import pydirectinput
import psutil
from pathlib import Path
import base64
from PIL import Image, ImageDraw
import io
import random
import cv2
import numpy as np
import mss
from pynput import mouse
import keyboard

# Настройка pydirectinput
pydirectinput.PAUSE = 0
pydirectinput.FAILSAFE = False

# ===== КОДЫ КЛАВИШ (WINAPI) =====
VK_CODES = {
    'e': 0x45, 'f': 0x46, 'h': 0x48, 'w': 0x57,
    'a': 0x41, 's': 0x53, 'd': 0x44,
    'space': 0x20, 'shift': 0x10, 'esc': 0x1B,
    'backspace': 0x08, 'up': 0x26, 'down': 0x28,
    'left': 0x25, 'right': 0x27, 'enter': 0x0D,
    'tab': 0x09, 'ctrl': 0x11, 'alt': 0x12,
    'capslock': 0x14
}

# ===== ОСНОВНЫЕ ФУНКЦИИ НАЖАТИЙ =====
def press(key):
    """Нажатие клавиши через pydirectinput"""
    try:
        pydirectinput.press(key)
        return True
    except:
        return False

def key_down(key):
    """Зажать клавишу через pydirectinput"""
    try:
        pydirectinput.keyDown(key)
        return True
    except:
        return False

def key_up(key):
    """Отпустить клавишу через pydirectinput"""
    try:
        pydirectinput.keyUp(key)
        return True
    except:
        return False

def hold_key(key, seconds):
    """Зажать клавишу на определенное время"""
    try:
        key_down(key)
        time.sleep(seconds)
        key_up(key)
        return True
    except:
        return False

def spam_key(key, count, delay=0.1):
    """Спамит клавишу несколько раз с задержкой"""
    for _ in range(count):
        press(key)
        time.sleep(delay)

# ===== ФУНКЦИИ ДЛЯ КЛИКОВ МЫШЬЮ =====
def click_left():
    """Эмулирует клик левой кнопкой мыши в текущей позиции"""
    ctypes.windll.user32.mouse_event(2, 0, 0, 0, 0)  # MOUSEEVENTF_LEFTDOWN
    time.sleep(0.01)
    ctypes.windll.user32.mouse_event(4, 0, 0, 0, 0)  # MOUSEEVENTF_LEFTUP
    print("🖱️ ЛКМ клик")

def click_right():
    """Эмулирует клик правой кнопкой мыши в текущей позиции"""
    ctypes.windll.user32.mouse_event(8, 0, 0, 0, 0)  # MOUSEEVENTF_RIGHTDOWN
    time.sleep(0.01)
    ctypes.windll.user32.mouse_event(16, 0, 0, 0, 0)  # MOUSEEVENTF_RIGHTUP

def move_mouse(x, y):
    """Перемещает курсор мыши в указанные координаты"""
    ctypes.windll.user32.SetCursorPos(x, y)

def get_mouse_pos():
    """Возвращает текущие координаты курсора"""
    point = ctypes.wintypes.POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
    return (point.x, point.y)

# ===== БЫСТРЫЙ WINAPI ВВОД (КАК В ПОРТУ) =====
class FastInput:
    user32 = ctypes.windll.user32
    KEYEVENTF_KEYUP = 0x0002

    @staticmethod
    def press_key(vk_code):
        """Быстрое нажатие клавиши через WinAPI"""
        FastInput.user32.keybd_event(vk_code, 0, 0, 0)
        time.sleep(0.01)
        FastInput.user32.keybd_event(vk_code, 0, FastInput.KEYEVENTF_KEYUP, 0)
        print(f"⌨️ Нажата клавиша {vk_code}")

    @staticmethod
    def key_down(vk_code):
        FastInput.user32.keybd_event(vk_code, 0, 0, 0)
        print(f"⌨️ Зажата клавиша {vk_code}")

    @staticmethod
    def key_up(vk_code):
        FastInput.user32.keybd_event(vk_code, 0, FastInput.KEYEVENTF_KEYUP, 0)
        print(f"⌨️ Отжата клавиша {vk_code}")

# ===== ПРОВЕРКА ПРОЦЕССА GTA (ОПЦИОНАЛЬНО) =====
def get_gta_pids():
    pids = []
    try:
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                proc_name = proc.info['name'].lower()
                if 'gta5.exe' in proc_name or 'ragemp_v.exe' in proc_name:
                    pids.append({'pid': proc.info['pid'], 'name': proc.info['name']})
            except:
                pass
    except:
        pass
    return pids

def is_gta_process_running():
    try:
        for proc in psutil.process_iter(['name']):
            try:
                proc_name = proc.info['name'].lower()
                if 'gta5.exe' in proc_name or 'ragemp_v.exe' in proc_name:
                    return True
            except:
                pass
        return False
    except:
        return False

def is_gta_window_foreground():
    """Проверяет, активно ли окно GTA 5 (убрали из использования, но оставили функцию)"""
    return True  # Всегда возвращаем True, чтобы не блокировать

_gta_process_check_last_time = 0
_gta_process_check_last_result = False
GTA_PROCESS_CHECK_INTERVAL = 1.0

def is_gta_process_running_cached():
    global _gta_process_check_last_time, _gta_process_check_last_result
    t = time.time()
    if t - _gta_process_check_last_time < GTA_PROCESS_CHECK_INTERVAL:
        return _gta_process_check_last_result
    _gta_process_check_last_time = t
    _gta_process_check_last_result = is_gta_process_running()
    return _gta_process_check_last_result

# ===== ТРЕКЕР МЫШИ (ПОВОРОТЫ, АВТОЕЗДА, СПАМ, ПОИСК) =====
class MouseTracker:
    def __init__(self):
        # Параметры поворотов
        self.last_x = None
        self.last_move_time = 0
        self.move_cooldown = 0.05
        self.min_distance = 10
        self.center_deadzone = 50
        self.a_pressed = False
        self.d_pressed = False

        # Автоезда (через WinAPI)
        self.w_pressed = False
        self.shift_pressed = False
        self.caps_pressed = False
        self.auto_drive = True

        # Спам ЛКМ
        self.spam_enabled = False
        self.spam_interval = 0.1
        self.spam_thread = None
        self.spam_running = False

        # Поиск пикселя (область)
        self.search_region = {'left': 100, 'top': 100, 'width': 800, 'height': 600}
        self.pixel_found = False

        # Общее состояние
        self.running = False
        self.listener = None
        self.screen_center_x = None
        self.screen_center_y = None

    def on_move(self, x, y):
        """Обработчик движения мыши"""
        if not self.running:
            return

        # Определяем центр экрана при первом запуске
        if self.screen_center_x is None:
            screen = pyautogui.size()
            self.screen_center_x = screen.width // 2
            self.screen_center_y = screen.height // 2
            print(f"Центр экрана определен: {self.screen_center_x}, {self.screen_center_y}")

        current_time = time.time()
        if current_time - self.last_move_time < self.move_cooldown:
            self.last_x = x
            return

        if self.last_x is not None:
            # Проверка на центральную зону
            if abs(x - self.screen_center_x) < self.center_deadzone:
                if self.a_pressed or self.d_pressed:
                    print(f"🧭 Мышь в центре (x={x}, центр={self.screen_center_x}) - руль прямо")
                    if self.a_pressed:
                        pydirectinput.keyUp('a')
                        self.a_pressed = False
                    if self.d_pressed:
                        pydirectinput.keyUp('d')
                        self.d_pressed = False
                    self.last_move_time = current_time
                    self.last_x = x
                return

            delta_x = x - self.last_x
            distance = abs(delta_x)

            if distance >= self.min_distance:
                if delta_x > 0:  # вправо
                    if not self.d_pressed:
                        if self.a_pressed:
                            pydirectinput.keyUp('a')
                            self.a_pressed = False
                        pydirectinput.keyDown('d')
                        self.d_pressed = True
                        print(f"➡️ D зажата (движение вправо на {distance}px)")
                elif delta_x < 0:  # влево
                    if not self.a_pressed:
                        if self.d_pressed:
                            pydirectinput.keyUp('d')
                            self.d_pressed = False
                        pydirectinput.keyDown('a')
                        self.a_pressed = True
                        print(f"⬅️ A зажата (движение влево на {distance}px)")
                self.last_move_time = current_time

        self.last_x = x

    def reset_steering(self):
        """Отпустить A и D"""
        if self.a_pressed:
            pydirectinput.keyUp('a')
            self.a_pressed = False
            print("⬅️ A отпущена")
        if self.d_pressed:
            pydirectinput.keyUp('d')
            self.d_pressed = False
            print("➡️ D отпущена")

    # ===== АВТОЕЗДА (ЧЕРЕЗ WINAPI) =====
    def set_auto_drive(self, enable):
        if enable:
            if not self.w_pressed:
                FastInput.key_down(VK_CODES['w'])
                self.w_pressed = True
                print("▶️ W зажата (WinAPI)")
            if not self.shift_pressed:
                FastInput.key_down(VK_CODES['shift'])
                self.shift_pressed = True
                print("▶️ Shift зажат (WinAPI)")
            if not self.caps_pressed:
                FastInput.key_down(VK_CODES['capslock'])
                self.caps_pressed = True
                print("▶️ CapsLock зажат (WinAPI)")
        else:
            if self.w_pressed:
                FastInput.key_up(VK_CODES['w'])
                self.w_pressed = False
                print("⏸️ W отпущена (WinAPI)")
            if self.shift_pressed:
                FastInput.key_up(VK_CODES['shift'])
                self.shift_pressed = False
                print("⏸️ Shift отпущен (WinAPI)")
            if self.caps_pressed:
                FastInput.key_up(VK_CODES['capslock'])
                self.caps_pressed = False
                print("⏸️ CapsLock отпущен (WinAPI)")

    # ===== ПОИСК ПИКСЕЛЯ =====
    def find_yellow_pixel(self):
        """Ищет жёлтый пиксель в заданной области"""
        try:
            with mss.mss() as sct:
                img = np.array(sct.grab(self.search_region))
                hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
                mask = cv2.inRange(hsv, (20, 100, 100), (30, 255, 255))
                found = cv2.countNonZero(mask) > 0
                if found:
                    print("🟡 Найден жёлтый пиксель")
                return found
        except Exception as e:
            print(f"❌ Ошибка поиска пикселя: {e}")
            return False

    # ===== СПАМ ЛКМ =====
    def spam_worker(self):
        """Поток для спама ЛКМ"""
        spam_count = 0
        while self.spam_running:
            if self.find_yellow_pixel():
                time.sleep(0.5)
            else:
                click_left()
                spam_count += 1
                if spam_count % 10 == 0:
                    print(f"🖱️ Спам ЛКМ: {spam_count} кликов")
                time.sleep(self.spam_interval)

    def start_spam(self):
        if not self.spam_running:
            self.spam_running = True
            self.spam_thread = threading.Thread(target=self.spam_worker, daemon=True)
            self.spam_thread.start()
            print("🖱️ Спам ЛКМ запущен")

    def stop_spam(self):
        self.spam_running = False
        if self.spam_thread:
            self.spam_thread.join(timeout=1)
        print("🖱️ Спам ЛКМ остановлен")

    # ===== ЗАПУСК/ОСТАНОВ =====
    def start(self):
        self.running = True
        self.listener = mouse.Listener(on_move=self.on_move)
        self.listener.start()
        print("👆 Отслеживание мыши запущено")
        
        if self.auto_drive:
            self.set_auto_drive(True)
        
        if self.spam_enabled:
            self.start_spam()

    def stop(self):
        self.running = False
        if self.listener:
            self.listener.stop()
        self.reset_steering()
        self.set_auto_drive(False)
        self.stop_spam()
        print("⏹️ Трекер остановлен")

# Глобальный экземпляр трекера
mouse_tracker = MouseTracker()

# ===== КОНФИГУРАЦИЯ =====
VERSION = "2.0.0"
CHEAT_NAME = "SCRawCheat"

cached_online = "загрузка..."
cached_update = {"needs_update": False, "remote_version": "", "local_version": VERSION}

COLORS = {
    "primary": "#ff0000",
    "secondary": "#8b0000",
    "accent": "#ff4444",
    "bg": "#0a0a0a",
    "bg-secondary": "#1a1a1a",
    "text": "#ffffff",
    "text-dim": "#cccccc",
    "success": "#ff4444",
    "warning": "#ff8888",
    "danger": "#8b0000"
}

CONFIG_DIR = "C:\\Users\\troll\\Documents\\scrawcheats\\configs"
os.makedirs(CONFIG_DIR, exist_ok=True)

CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
LOG_FILE = os.path.join(CONFIG_DIR, "log.txt")

# ===== ЛОГИРОВАНИЕ =====
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

file_handler = RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=5, encoding='utf-8')
file_handler.setLevel(logging.INFO)
file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)

logger = logging.getLogger(__name__)
logger.addHandler(file_handler)

clients: List[queue.Queue] = []

# ===== СОСТОЯНИЕ МОДУЛЕЙ =====
class ModuleState(dict):
    def __init__(self, active: bool = False, settings: Optional[Dict[str, Any]] = None):
        super().__init__()
        self['active'] = active
        self['settings'] = settings or {}
        self['stats'] = {
            'boxes_moved': 0,
            'money_earned': 0,
            'money_per_click': 132
        }

    @property
    def active(self) -> bool: return self['active']
    @active.setter
    def active(self, value: bool): self['active'] = value
    @property
    def settings(self) -> Dict[str, Any]: return self['settings']
    @settings.setter
    def settings(self, value: Dict[str, Any]): self['settings'] = value
    @property
    def stats(self) -> Dict[str, Any]: return self['stats']
    def add_box(self, count: int = 1):
        self['stats']['boxes_moved'] += count
        self['stats']['money_earned'] += count * self['stats']['money_per_click']
    def set_money_per_click(self, amount: int):
        self['stats']['money_per_click'] = amount

state = {
    "current_page": "index",
    "modules": {
        "antiafk": ModuleState(active=False, settings={"min_delay": 1.0, "max_delay": 3.0, "min_pause": 5.0, "max_pause": 10.0}),
        "bonuspoint": ModuleState(active=False, settings={}),
        "port": ModuleState(active=False, settings={"min_delay": 0.09, "max_delay": 0.2, "tolerance": 60, "min_area": 400}),
        "stroyka": ModuleState(active=False, settings={}),
        "cooking": ModuleState(active=False, settings={"mode": "смузи", "click_delay": 0.08, "cycle_delay": 5.7}),
        "demorgan": ModuleState(active=False, settings={"mode": "швейка", "click_interval": 0.5, "tokar_pause": 65, "shveika_pause": 85}),
        "farm": ModuleState(active=False, settings={"press_delay": 0.3, "check_interval": 0.05}),
        "gym": ModuleState(active=False, settings={"mode": "Жим лежа", "space_delay": 0.05, "debounce_time": 0.1, "rest_timeout": 6, "min_rest": 31, "max_rest": 35}),
        "taxi": ModuleState(active=False, settings={"scan_interval": 0.1, "confidence": 0.8}),
        "postman": ModuleState(active=False, settings={"min_distance": 10, "cooldown": 0.05, "center_deadzone": 50, "auto_drive": True, "spam": False, "spam_interval": 0.1})
    },
    "logs": [],
    "page_logs": {}
}

# ===== КОНФИГУРАЦИЯ ПО УМОЛЧАНИЮ =====
DEFAULT_CONFIG = {
    "settings": {"switch_hover": True, "switch_click": True, "volume_hover": 35, "volume_click": 45, "background": "bot"},
    "antiafk": {"min_delay": 1.0, "max_delay": 3.0, "min_pause": 5.0, "max_pause": 10.0},
    "port": {"min_delay": 0.09, "max_delay": 0.2, "tolerance": 60, "min_area": 400, "money_per_click": 132},
    "stroyka": {},
    "cooking": {"mode": "смузи", "click_delay": 0.08, "cycle_delay": 5.7},
    "demorgan": {"mode": "швейка", "click_interval": 0.5, "tokar_pause": 65, "shveika_pause": 85},
    "farm": {"press_delay": 0.3, "check_interval": 0.05},
    "gym": {"mode": "Жим лежа", "space_delay": 0.05, "debounce_time": 0.1, "rest_timeout": 6, "min_rest": 31, "max_rest": 35},
    "taxi": {"scan_interval": 0.1, "confidence": 0.8},
    "postman": {"min_distance": 10, "cooldown": 0.05, "center_deadzone": 50, "auto_drive": True, "spam": False, "spam_interval": 0.1}
}

# ===== ФУНКЦИИ ЛОГИРОВАНИЯ =====
def add_log(msg: str, level: str = "INFO", page: str = "global"):
    timestamp = time.strftime("%H:%M:%S")
    formatted_msg = f"[{timestamp}] [{page}] {msg}"
    state["logs"].append(formatted_msg)
    if len(state["logs"]) > 100:
        state["logs"].pop(0)
    if page not in state["page_logs"]:
        state["page_logs"][page] = []
    state["page_logs"][page].append(formatted_msg)
    if len(state["page_logs"][page]) > 50:
        state["page_logs"][page].pop(0)
    for q in clients[:]:
        try:
            q.put(formatted_msg)
        except:
            clients.remove(q)
    log_func = getattr(logger, level.lower(), logger.info)
    log_func(formatted_msg)

# ===== РАБОТА С КОНФИГАМИ =====
def load_config():
    if not os.path.exists(CONFIG_FILE):
        return DEFAULT_CONFIG.copy()
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        add_log("Конфиг поврежден, загружены стандартные настройки", level="WARNING", page="system")
        return DEFAULT_CONFIG.copy()

def save_config(config: dict, page: str = "system"):
    try:
        temp_file = CONFIG_FILE + ".tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        os.replace(temp_file, CONFIG_FILE)
        return True
    except Exception as e:
        add_log(f"Ошибка сохранения: {str(e)}", level="ERROR", page=page)
        return False

def get_settings(section: str):
    config = load_config()
    return config.get(section, DEFAULT_CONFIG.get(section, {}))

def update_settings(section: str, settings: dict, page: str = "system"):
    config = load_config()
    config[section] = settings
    return save_config(config, page=page)

# ===== МЕНЕДЖЕР ХОТКЕЕВ =====
class HotkeyManager:
    def __init__(self):
        self.actions: Dict[str, Callable[[], None]] = {}

    def register(self, key: str, callback: Callable[[], None]):
        if not callable(callback):
            raise ValueError(f"Callback для '{key}' должен быть вызываемым")
        self.actions[key.lower()] = callback
        add_log(f"Хоткей зарегистрирован: {key}", page="hotkeys")

    def unregister(self, key: str):
        key_lower = key.lower()
        if key_lower in self.actions:
            del self.actions[key_lower]
            add_log(f"Хоткей удален: {key}", page="hotkeys")

    def clear(self):
        self.actions.clear()
        add_log("Все хоткеи очищены", page="hotkeys")

    def get_action(self, key: str) -> Optional[Callable[[], None]]:
        return self.actions.get(key.lower())

hotkey_manager = HotkeyManager()

# ===== АВТООПРЕДЕЛЕНИЕ ОБЛАСТИ =====
def auto_detect_region(width_ratio=None, height_ratio=None, top_ratio=None, reference_height=None, reference_top=None):
    try:
        screen_width, screen_height = pyautogui.size()
        if width_ratio is None: width_ratio = 0.5
        if height_ratio is None: height_ratio = 0.7
        if top_ratio is None: top_ratio = 0.25
        if reference_height is not None and reference_top is not None:
            top_ratio = reference_top / reference_height
        region_width = int(screen_width * width_ratio)
        region_height = int(screen_height * height_ratio)
        return {
            "left": int((screen_width - region_width) / 2),
            "top": int(screen_height * top_ratio),
            "width": region_width,
            "height": region_height,
        }
    except:
        return {"left": 0, "top": 0, "width": 1920, "height": 1080}

# ===== ЭКСПОРТ =====
__all__ = [
    'VERSION', 'CHEAT_NAME', 'cached_online', 'cached_update', 'COLORS', 'CONFIG_DIR', 'state', 'clients',
    'add_log', 'load_config', 'save_config', 'get_settings', 'update_settings', 'hotkey_manager',
    'press', 'key_down', 'key_up', 'hold_key', 'spam_key', 'get_gta_pids', 'is_gta_process_running',
    'is_gta_process_running_cached', 'is_gta_window_foreground', 'auto_detect_region', 'mouse_tracker',
    'VK_CODES', 'click_left', 'click_right', 'move_mouse', 'get_mouse_pos', 'FastInput'
]