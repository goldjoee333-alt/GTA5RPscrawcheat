import threading
import time
import sys
import os
import mss
import cv2
import numpy as np
from flask import render_template, jsonify, Blueprint, request
from core.common import (
    state, add_log,
    is_gta_process_running_cached,
    get_settings, update_settings
)
from core.autorun import auto_run_manager
import ctypes
from ctypes import wintypes

cow_bp = Blueprint('cow', __name__)
stop_event = threading.Event()
cow_thread = None
auto_e_active = False
auto_e_thread = None
auto_e_stop = threading.Event()

def get_asset_path(relative_path):
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

def ensure_cow_state():
    if "cow" not in state["modules"]:
        state["modules"]["cow"] = {
            "active": False,
            "auto_run_active": False,
            "auto_e_active": False,
            "settings": get_settings("cow"),
            "counter": 0
        }
    else:
        if "auto_run_active" not in state["modules"]["cow"]:
            state["modules"]["cow"]["auto_run_active"] = False
        if "auto_e_active" not in state["modules"]["cow"]:
            state["modules"]["cow"]["auto_e_active"] = False
        if "settings" not in state["modules"]["cow"]:
            state["modules"]["cow"]["settings"] = get_settings("cow")
        if "counter" not in state["modules"]["cow"]:
            state["modules"]["cow"]["counter"] = 0

ensure_cow_state()

cow_auto_runner = auto_run_manager.create_runner("cow", page="cow")

RED_BAR_REGION = {'x': 1220, 'y': 670, 'width': 30, 'height': 150}
LETTER_REGION = {
    'A': {'x': 880, 'y': 850, 'width': 50, 'height': 50},
    'D': {'x': 1030, 'y': 850, 'width': 50, 'height': 50}
}
WHITE_THRESHOLD = 200
RED_THRESHOLD = 80
CHECK_INTERVAL = 0.05

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

VK_CODES = {
    'a': 0x41,
    'd': 0x44,
    'e': 0x45
}

class FastInput:
    user32 = ctypes.windll.user32
    
    @staticmethod
    def send_keyboard_input(wVk, dwFlags):
        x = INPUT(type=INPUT_KEYBOARD)
        x.ki.wVk = wVk
        x.ki.wScan = 0
        x.ki.dwFlags = dwFlags
        x.ki.time = 0
        x.ki.dwExtraInfo = None
        return FastInput.user32.SendInput(1, ctypes.byref(x), ctypes.sizeof(x))
    
    @staticmethod
    def press_key(key, hold_time=0.05):
        if key.lower() in VK_CODES:
            vk = VK_CODES[key.lower()]
            
            FastInput.send_keyboard_input(vk, KEYEVENTF_KEYDOWN)
            time.sleep(hold_time)
            FastInput.send_keyboard_input(vk, KEYEVENTF_KEYUP)
            return True
        return False

class CowBot:
    def __init__(self):
        self.is_running = False
        self.last_press_time = 0
        self.press_delay = 0.3
        self.red_bar_active = False
        self.counter = 0

    def set_press_delay(self, delay):
        self.press_delay = delay

    def capture_region(self, reg):
        try:
            with mss.mss() as sct:
                mon = {
                    'left': reg['x'],
                    'top': reg['y'],
                    'width': reg['width'],
                    'height': reg['height']
                }
                img = np.array(sct.grab(mon))
                return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        except:
            return None

    def get_letter_brightness(self, letter):
        img = self.capture_region(LETTER_REGION[letter])
        if img is None:
            return 0
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return np.mean(gray)

    def check_red_bar(self):
        img = self.capture_region(RED_BAR_REGION)
        if img is None:
            return False
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        m1 = cv2.inRange(hsv, (0, 100, 100), (10, 255, 255))
        m2 = cv2.inRange(hsv, (170, 100, 100), (180, 255, 255))
        red = cv2.bitwise_or(m1, m2)
        red_pix = cv2.countNonZero(red)
        total = RED_BAR_REGION['width'] * RED_BAR_REGION['height']
        perc = red_pix / total * 100
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        avg = np.mean(gray)
        return perc > 30 or avg < RED_THRESHOLD

    def check_active_letter(self):
        a = self.get_letter_brightness('A')
        d = self.get_letter_brightness('D')
        
        if a == 0 or d == 0:
            return None
        
        if a > WHITE_THRESHOLD and a > d + 20:
            return 'A'
        if d > WHITE_THRESHOLD and d > a + 20:
            return 'D'
        if a > WHITE_THRESHOLD and d > WHITE_THRESHOLD:
            return 'A' if a > d else 'D'
        return None

    def can_press(self):
        now = time.time()
        if now - self.last_press_time >= self.press_delay:
            self.last_press_time = now
            return True
        return False

    def cow_loop(self):
        time.sleep(0.5)
        self.is_running = True
        press_count = 0
        error_count = 0
        
        add_log("🐄 Ферма запущена", page="cow")
        
        while self.is_running and not stop_event.is_set():
            try:
                if not is_gta_process_running_cached():
                    time.sleep(1.0)
                    continue
                
                red = self.check_red_bar()
                if red != self.red_bar_active:
                    self.red_bar_active = red
                
                if not self.red_bar_active:
                    act = self.check_active_letter()
                    if act and self.can_press():
                        FastInput.press_key(act, hold_time=0.05)
                        self.counter += 1
                        press_count += 1
                        state["modules"]["cow"]["counter"] = self.counter
                        
                        if press_count % 10 == 0:
                            add_log(f"🐄 Нажата {act} | Счет: {self.counter}", page="cow")
                        error_count = 0
                
                time.sleep(CHECK_INTERVAL)
                
            except Exception as e:
                error_count += 1
                add_log(f"❌ Ошибка фермы: {e}", level="ERROR", page="cow")
                if error_count > 10:
                    break
                time.sleep(1)
        
        self.is_running = False
        add_log(f"⏹️ Ферма остановлена. Всего нажатий: {self.counter}", page="cow")

    def stop_bot(self):
        self.is_running = False

def auto_e_worker():
    global auto_e_active
    data = state["modules"]["cow"]
    settings = data.get("settings", {})
    interval = float(settings.get("auto_e_interval", 0.1))
    
    add_log(f"🤖 Авто E запущен (интервал {interval} сек)", page="cow")
    press_count = 0
    error_count = 0
    
    while not auto_e_stop.is_set():
        try:
            if auto_e_active and is_gta_process_running_cached():
                FastInput.press_key('e', hold_time=0.01)
                press_count += 1
                
                if press_count % 50 == 0:
                    add_log(f"🔄 Авто E: нажата E (всего: {press_count})", page="cow")
                error_count = 0
            
            time.sleep(interval)
            
        except Exception as e:
            error_count += 1
            add_log(f"❌ Ошибка авто E: {e}", level="ERROR", page="cow")
            if error_count > 5:
                break
            time.sleep(1)
    
    add_log(f"⏹️ Авто E остановлен (всего нажатий: {press_count})", page="cow")

def toggle_auto_e():
    global auto_e_active, auto_e_thread, auto_e_stop
    
    data = state["modules"]["cow"]
    
    if not data.get("auto_e_active", False):
        data["auto_e_active"] = True
        auto_e_active = True
        auto_e_stop.clear()
        
        if auto_e_thread is None or not auto_e_thread.is_alive():
            auto_e_thread = threading.Thread(target=auto_e_worker, daemon=True)
            auto_e_thread.start()
        
        add_log("✅ Авто E запущен", page="cow")
        return True
    else:
        data["auto_e_active"] = False
        auto_e_active = False
        auto_e_stop.set()
        add_log("⏹️ Авто E остановлен", page="cow")
        return False

def toggle_auto_run():
    result = cow_auto_runner.toggle()
    state["modules"]["cow"]["auto_run_active"] = cow_auto_runner.is_active()
    return result

cow_bot_instance = None

def get_cow_bot():
    global cow_bot_instance
    if cow_bot_instance is None:
        cow_bot_instance = CowBot()
    return cow_bot_instance

def toggle_cow():
    global cow_thread, cow_bot_instance
    
    ensure_cow_state()
    bot = get_cow_bot()
    data = state["modules"]["cow"]
    
    if not data["active"]:
        settings = data.get("settings", {})
        bot.press_delay = float(settings.get("press_delay", 0.3))
        bot.counter = data.get("counter", 0)
        
        data["active"] = True
        stop_event.clear()
        
        bot.is_running = False
        cow_thread = threading.Thread(target=bot.cow_loop, daemon=True)
        cow_thread.start()
        
        add_log("✅ Ферма запущена", page="cow")
        return True
    else:
        data["active"] = False
        stop_event.set()
        bot.stop_bot()
        
        data["counter"] = bot.counter
        
        add_log("⏹️ Ферма остановлена", page="cow")
        return True

@cow_bp.route('/cow')
def render_cow():
    ensure_cow_state()
    bot = get_cow_bot()
    
    module_state = state["modules"]["cow"]
    active = module_state.get("active", False)
    auto_run_active = module_state.get("auto_run_active", False)
    auto_e_active = module_state.get("auto_e_active", False)
    settings = module_state.get("settings", {})
    counter = bot.counter if bot else module_state.get("counter", 0)
    
    return render_template(
        'cow.html',
        active=active,
        auto_run_active=auto_run_active,
        auto_e_active=auto_e_active,
        settings=settings,
        counter=counter
    )

@cow_bp.route('/api/cow/toggle', methods=['POST'])
def api_toggle():
    data = request.get_json()
    
    if data and 'settings' in data:
        s = data['settings']
        settings = {
            'press_delay': float(s.get('press_delay', 0.3)),
            'auto_e_interval': float(s.get('auto_e_interval', 0.1))
        }
        state["modules"]["cow"]["settings"] = settings
        update_settings("cow", settings, page="cow")
    
    result = toggle_cow()
    return jsonify({
        "status": "ok" if result else "error",
        "active": state["modules"]["cow"]["active"]
    })

@cow_bp.route('/api/cow/auto_run/toggle', methods=['POST'])
def api_auto_run_toggle():
    new_state = toggle_auto_run()
    return jsonify({
        "status": "ok",
        "auto_run_active": new_state
    })

@cow_bp.route('/api/cow/auto_e/toggle', methods=['POST'])
def api_auto_e_toggle():
    result = toggle_auto_e()
    return jsonify({
        "status": "ok",
        "auto_e_active": result
    })

@cow_bp.route('/api/cow/stats', methods=['GET'])
def api_stats():
    bot = get_cow_bot()
    counter = bot.counter if bot else state["modules"]["cow"].get("counter", 0)
    return jsonify({"counter": counter})

@cow_bp.route('/api/cow/reset_counter', methods=['POST'])
def api_reset_counter():
    ensure_cow_state()
    bot = get_cow_bot()
    if bot:
        bot.counter = 0
    state["modules"]["cow"]["counter"] = 0
    add_log("🔄 Счетчик фермы сброшен", page="cow")
    return jsonify({"status": "ok", "counter": 0})