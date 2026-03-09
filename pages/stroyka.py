import threading
import time
import os
import sys
import cv2
import numpy as np
from PIL import ImageGrab
from flask import render_template, jsonify, Blueprint, request
from core.common import (
    state, add_log,
    is_gta_process_running_cached,
    get_settings, update_settings
)
from core.autorun import auto_run_manager
import ctypes
from ctypes import wintypes

stroyka_bp = Blueprint('stroyka', __name__)
stop_event = threading.Event()
stroyka_thread = None

def get_asset_path(relative_path):
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

def ensure_stroyka_state():
    if "stroyka" not in state["modules"]:
        state["modules"]["stroyka"] = {
            "active": False,
            "auto_run_active": False,
            "settings": get_settings("stroyka"),
            "counter": 0
        }
    else:
        if "auto_run_active" not in state["modules"]["stroyka"]:
            state["modules"]["stroyka"]["auto_run_active"] = False
        if "settings" not in state["modules"]["stroyka"]:
            state["modules"]["stroyka"]["settings"] = get_settings("stroyka")
        if "counter" not in state["modules"]["stroyka"]:
            state["modules"]["stroyka"]["counter"] = 0

ensure_stroyka_state()

stroyka_auto_runner = auto_run_manager.create_runner("stroyka", page="stroyka")

ASSETS_PATH = get_asset_path(os.path.join('static', 'assets', 'build'))
MINE_DETECTION_REGION = (920, 615, 996, 682)

PUL = ctypes.POINTER(ctypes.c_ulong)

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", PUL)
    ]

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", PUL)
    ]

class INPUT(ctypes.Structure):
    class _INPUT(ctypes.Union):
        _fields_ = [
            ("ki", KEYBDINPUT),
            ("mi", MOUSEINPUT)
        ]
    _anonymous_ = ("_input",)
    _fields_ = [
        ("type", wintypes.DWORD),
        ("_input", _INPUT)
    ]

INPUT_KEYBOARD = 1
KEYEVENTF_KEYDOWN = 0x0000
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008

VK_CODES = {
    'e': 0x45,
    'y': 0x59,
    'f': 0x46,
    'h': 0x48
}

SCAN_CODES = {
    'e': 0x12,
    'y': 0x15,
    'f': 0x21,
    'h': 0x23
}

class FastInput:
    user32 = ctypes.windll.user32
    
    @staticmethod
    def send_keyboard_input(wVk, wScan, dwFlags):
        x = INPUT(type=INPUT_KEYBOARD)
        x.ki.wVk = wVk
        x.ki.wScan = wScan
        x.ki.dwFlags = dwFlags
        x.ki.time = 0
        x.ki.dwExtraInfo = None
        return FastInput.user32.SendInput(1, ctypes.byref(x), ctypes.sizeof(x))
    
    @staticmethod
    def press_key(key):
        key_lower = key.lower()
        if key_lower in VK_CODES:
            vk = VK_CODES[key_lower]
            scan = SCAN_CODES.get(key_lower, 0)
            
            FastInput.send_keyboard_input(vk, scan, KEYEVENTF_KEYDOWN | KEYEVENTF_SCANCODE)
            time.sleep(0.01)
            FastInput.send_keyboard_input(vk, scan, KEYEVENTF_KEYUP | KEYEVENTF_SCANCODE)
            return True
        return False

IMG_KEY_MAPPING = {
    "image1.png": "e",
    "image2.png": "y",
    "image3.png": "f",
    "image4.png": "h",
}

class StroykaBot:
    def __init__(self):
        self.templates = {}
        self.mine_template = None
        self.is_running = False
        self.last_screenshot = None
        self.last_screenshot_time = 0
        self.screenshot_interval = 0.005
        self.counter = 0
        self.last_press_time = 0
        self.min_press_interval = 0.05
        self.load_templates()

    def load_templates(self):
        if not os.path.exists(ASSETS_PATH):
            add_log(f"⚠️ Папка {ASSETS_PATH} не найдена", page="stroyka")
            return False
        
        loaded = 0
        for img_name, key in IMG_KEY_MAPPING.items():
            img_path = os.path.join(ASSETS_PATH, img_name)
            if os.path.exists(img_path):
                img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
                if img is not None:
                    self.templates[img_name] = {
                        'image': img,
                        'key': key,
                        'path': img_path
                    }
                    loaded += 1
                    add_log(f"✅ Загружен шаблон: {img_name} -> {key.upper()}", page="stroyka")
        
        mine_path = os.path.join(ASSETS_PATH, 'image1.png')
        if os.path.exists(mine_path):
            self.mine_template = cv2.imread(mine_path, cv2.IMREAD_GRAYSCALE)
            if self.mine_template is not None:
                add_log("✅ Шаблон шахты загружен", page="stroyka")
        
        return loaded > 0 or self.mine_template is not None

    def ultra_fast_screenshot(self, bbox=None):
        now = time.time()
        if now - self.last_screenshot_time >= self.screenshot_interval:
            try:
                if bbox:
                    self.last_screenshot = ImageGrab.grab(bbox=bbox)
                else:
                    self.last_screenshot = ImageGrab.grab()
                self.last_screenshot_time = now
            except:
                return None
        return self.last_screenshot

    def check_mine(self):
        if self.mine_template is None:
            return False
        
        scr = self.ultra_fast_screenshot(bbox=MINE_DETECTION_REGION)
        if scr is None:
            return False
        
        try:
            gray = cv2.cvtColor(np.array(scr), cv2.COLOR_RGB2GRAY)
            result = cv2.matchTemplate(gray, self.mine_template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(result)
            return max_val > 0.7
        except:
            return False

    def check_build(self):
        scr = self.ultra_fast_screenshot()
        if scr is None:
            return None
        
        try:
            gray = cv2.cvtColor(np.array(scr), cv2.COLOR_RGB2GRAY)
            
            for img_name, tmpl in self.templates.items():
                result = cv2.matchTemplate(gray, tmpl['image'], cv2.TM_CCOEFF_NORMED)
                _, max_val, _, _ = cv2.minMaxLoc(result)
                
                if max_val > 0.7:
                    return tmpl['key']
        except:
            return None
        
        return None

    def can_press(self):
        now = time.time()
        if now - self.last_press_time >= self.min_press_interval:
            self.last_press_time = now
            return True
        return False

    def stroyka_loop(self):
        add_log(">>> Стройка/Шахта запущена", page="stroyka")
        
        if not self.templates and self.mine_template is None:
            add_log("❌ Нет шаблонов", level="ERROR", page="stroyka")
            self.is_running = False
            return
        
        self.is_running = True
        press_count = 0
        
        while self.is_running and not stop_event.is_set():
            if not is_gta_process_running_cached():
                time.sleep(1.0)
                continue
            
            if self.check_mine():
                if self.can_press():
                    FastInput.press_key('e')
                    self.counter += 1
                    press_count += 1
                    state["modules"]["stroyka"]["counter"] = self.counter
                    
                    if press_count % 10 == 0:
                        add_log(f"⛏️ Шахта: нажата E | Счет: {self.counter}", page="stroyka")
                    continue
            
            key = self.check_build()
            if key and self.can_press():
                FastInput.press_key(key)
                self.counter += 1
                press_count += 1
                state["modules"]["stroyka"]["counter"] = self.counter
                
                if press_count % 10 == 0:
                    add_log(f"🔨 Стройка: нажата {key.upper()} | Счет: {self.counter}", page="stroyka")
            
            time.sleep(0.005)
        
        self.is_running = False
        add_log(">>> Стройка/Шахта остановлена", page="stroyka")

    def stop_bot(self):
        self.is_running = False

stroyka_bot_instance = None

def get_stroyka_bot():
    global stroyka_bot_instance
    if stroyka_bot_instance is None:
        stroyka_bot_instance = StroykaBot()
    return stroyka_bot_instance

def toggle_stroyka():
    global stroyka_thread, stroyka_bot_instance
    
    ensure_stroyka_state()
    bot = get_stroyka_bot()
    data = state["modules"]["stroyka"]
    
    if not data["active"]:
        bot.load_templates()
        bot.counter = data.get("counter", 0)
        
        data["active"] = True
        stop_event.clear()
        
        bot.is_running = False
        stroyka_thread = threading.Thread(target=bot.stroyka_loop, daemon=True)
        stroyka_thread.start()
        
        add_log("✅ Стройка/Шахта запущена", page="stroyka")
        return True
    else:
        data["active"] = False
        stop_event.set()
        bot.stop_bot()
        
        data["counter"] = bot.counter
        
        add_log("⏹️ Стройка/Шахта остановлена", page="stroyka")
        return True

def toggle_auto_run():
    result = stroyka_auto_runner.toggle()
    state["modules"]["stroyka"]["auto_run_active"] = stroyka_auto_runner.is_active()
    return result

@stroyka_bp.route('/stroyka')
def render_stroyka():
    ensure_stroyka_state()
    bot = get_stroyka_bot()
    
    module_state = state["modules"]["stroyka"]
    active = module_state.get("active", False)
    auto_run_active = module_state.get("auto_run_active", False)
    settings = module_state.get("settings", {})
    counter = bot.counter if bot else module_state.get("counter", 0)
    
    return render_template(
        'stroyka.html',
        active=active,
        auto_run_active=auto_run_active,
        settings=settings,
        counter=counter
    )

@stroyka_bp.route('/api/stroyka/toggle', methods=['POST'])
def api_toggle():
    result = toggle_stroyka()
    return jsonify({
        'status': 'ok' if result else 'error',
        'active': state["modules"]["stroyka"]["active"]
    })

@stroyka_bp.route('/api/stroyka/auto_run/toggle', methods=['POST'])
def api_auto_run_toggle():
    new_state = toggle_auto_run()
    return jsonify({
        "status": "ok", 
        "auto_run_active": new_state
    })

@stroyka_bp.route('/api/stroyka/stats', methods=['GET'])
def api_stats():
    bot = get_stroyka_bot()
    counter = bot.counter if bot else state["modules"]["stroyka"].get("counter", 0)
    return jsonify({"counter": counter})

@stroyka_bp.route('/api/stroyka/reset_counter', methods=['POST'])
def api_reset_counter():
    ensure_stroyka_state()
    bot = get_stroyka_bot()
    if bot:
        bot.counter = 0
    state["modules"]["stroyka"]["counter"] = 0
    add_log("🔄 Счетчик стройки/шахты сброшен", page="stroyka")
    return jsonify({"status": "ok", "counter": 0})