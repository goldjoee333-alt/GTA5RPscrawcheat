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

demorgan_bp = Blueprint('demorgan', __name__)
stop_event = threading.Event()
demorgan_thread = None

def get_asset_path(relative_path):
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

def ensure_demorgan_state():
    if "demorgan" not in state["modules"]:
        state["modules"]["demorgan"] = {
            "active": False,
            "auto_run_active": False,
            "settings": get_settings("demorgan"),
            "counter": 0
        }
    else:
        if "auto_run_active" not in state["modules"]["demorgan"]:
            state["modules"]["demorgan"]["auto_run_active"] = False
        if "settings" not in state["modules"]["demorgan"]:
            state["modules"]["demorgan"]["settings"] = get_settings("demorgan")
        if "counter" not in state["modules"]["demorgan"]:
            state["modules"]["demorgan"]["counter"] = 0
        if "active" not in state["modules"]["demorgan"]:
            state["modules"]["demorgan"]["active"] = False

ensure_demorgan_state()

demorgan_auto_runner = auto_run_manager.create_runner("demorgan", page="demorgan")

class WinAPI:
    user32 = ctypes.windll.user32
    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP = 0x0004

    @staticmethod
    def GetCursorPos():
        point = wintypes.POINT()
        WinAPI.user32.GetCursorPos(ctypes.byref(point))
        return (point.x, point.y)

    @staticmethod
    def SetCursorPos(x, y):
        return WinAPI.user32.SetCursorPos(x, y)

    @staticmethod
    def mouse_event(dwFlags, dx=0, dy=0, dwData=0, dwExtraInfo=0):
        WinAPI.user32.mouse_event(dwFlags, dx, dy, dwData, dwExtraInfo)

class DemorganBot:
    def __init__(self):
        self.templates_shveika = {}
        self.templates_tokar = {}
        self.is_running = False
        self.confidence = 0.7
        self.click_interval = 0.5
        self.tokar_pause = 65
        self.shveika_pause = 85
        self.mode = 'швейка'
        self.last_screenshot = None
        self.last_screenshot_time = 0
        self.screenshot_interval = 0.01
        self.counter = 0
        self.X1, self.Y1 = 765, 314
        self.X2, self.Y2 = 1183, 806
        self.load_templates()

    def load_templates(self):
        shveika_dir = get_asset_path(os.path.join('static', 'assets', 'shveika'))
        if os.path.exists(shveika_dir):
            for filename in os.listdir(shveika_dir):
                if filename.lower().endswith('.png'):
                    name = os.path.splitext(filename)[0]
                    if name.isdigit():
                        num = int(name)
                    else:
                        num = name
                    path = os.path.join(shveika_dir, filename)
                    img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
                    if img is not None:
                        self.templates_shveika[num] = img
                        add_log(f"✅ Загружен шаблон швейки: {filename}", page="demorgan")
                    else:
                        add_log(f"❌ Не удалось загрузить {filename}", page="demorgan")
        else:
            add_log(f"⚠️ Папка {shveika_dir} не найдена", page="demorgan")

        tokar_dir = get_asset_path(os.path.join('static', 'assets', 'tokar'))
        if os.path.exists(tokar_dir):
            for filename in os.listdir(tokar_dir):
                if filename.lower().endswith('.png'):
                    name = os.path.splitext(filename)[0]
                    path = os.path.join(tokar_dir, filename)
                    img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
                    if img is not None:
                        self.templates_tokar[name] = img
                        add_log(f"✅ Загружен шаблон токаря: {filename}", page="demorgan")
                    else:
                        add_log(f"❌ Не удалось загрузить {filename}", page="demorgan")
        else:
            add_log(f"⚠️ Папка {tokar_dir} не найдена", page="demorgan")

        add_log(f"📊 Загружено шаблонов: швейка {len(self.templates_shveika)}, токарь {len(self.templates_tokar)}", page="demorgan")

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

    def find_template_position_shveika(self, num):
        if num not in self.templates_shveika:
            return None
        scr = self.ultra_fast_screenshot(bbox=(self.X1, self.Y1, self.X2, self.Y2))
        if scr is None:
            return None
        try:
            gray = cv2.cvtColor(np.array(scr), cv2.COLOR_RGB2GRAY)
            tmpl = self.templates_shveika[num]
            res = cv2.matchTemplate(gray, tmpl, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)
            if max_val >= self.confidence:
                h, w = tmpl.shape
                return (max_loc[0] + w // 2 + self.X1, max_loc[1] + h // 2 + self.Y1, max_val)
        except:
            return None
        return None

    def find_template_position_tokar(self, name):
        if name not in self.templates_tokar:
            return None
        scr = self.ultra_fast_screenshot()
        if scr is None:
            return None
        try:
            gray = cv2.cvtColor(np.array(scr), cv2.COLOR_RGB2GRAY)
            tmpl = self.templates_tokar[name]
            res = cv2.matchTemplate(gray, tmpl, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)
            if max_val >= self.confidence:
                h, w = tmpl.shape
                return (max_loc[0] + w // 2, max_loc[1] + h // 2, max_val)
        except:
            return None
        return None

    def instant_click(self, x, y):
        try:
            orig = WinAPI.GetCursorPos()
        except:
            orig = None
        try:
            WinAPI.SetCursorPos(x, y)
            time.sleep(0.01)
            WinAPI.mouse_event(WinAPI.MOUSEEVENTF_LEFTDOWN)
            time.sleep(0.02)
            WinAPI.mouse_event(WinAPI.MOUSEEVENTF_LEFTUP)
            if orig:
                WinAPI.SetCursorPos(orig[0], orig[1])
            return True
        except:
            return False

    def shveika_loop(self):
        add_log("🧵 Режим: Швейка", page="demorgan")
        while self.is_running and not stop_event.is_set():
            if not is_gta_process_running_cached():
                time.sleep(1.0)
                continue

            positions = {}
            for num in list(self.templates_shveika.keys()):
                pos = self.find_template_position_shveika(num)
                if pos:
                    positions[num] = pos[:2]

            if len(positions) > 0:
                add_log(f"✅ Найдено {len(positions)} точек", page="demorgan")
                sorted_keys = sorted(positions.keys(), key=lambda k: (isinstance(k, int), k))
                for key in sorted_keys:
                    if not self.is_running:
                        break
                    x, y = positions[key]
                    if self.instant_click(x, y):
                        self.counter += 1
                        state["modules"]["demorgan"]["counter"] = self.counter
                        add_log(f"🖱️ Клик по {key} | Счет: {self.counter}", page="demorgan")
                        time.sleep(self.click_interval)
                add_log(f"💤 Пауза {self.shveika_pause} сек...", page="demorgan")
                for _ in range(self.shveika_pause):
                    if not self.is_running or stop_event.is_set():
                        break
                    time.sleep(1)
            else:
                time.sleep(0.5)

    def tokar_loop(self):
        add_log("🔧 Режим: Токарь", page="demorgan")
        while self.is_running and not stop_event.is_set():
            if not is_gta_process_running_cached():
                time.sleep(1.0)
                continue

            found = False
            for name in self.templates_tokar.keys():
                pos = self.find_template_position_tokar(name)
                if pos:
                    x, y, conf = pos
                    add_log(f"🔧 Найден шаблон {name} (точность {conf:.2f})", page="demorgan")
                    if self.instant_click(x, y):
                        self.counter += 1
                        state["modules"]["demorgan"]["counter"] = self.counter
                        add_log(f"🖱️ Клик по {name} | Счет: {self.counter}", page="demorgan")
                        found = True
                        break
            if found:
                add_log(f"💤 Пауза {self.tokar_pause} сек...", page="demorgan")
                for _ in range(self.tokar_pause):
                    if not self.is_running or stop_event.is_set():
                        break
                    time.sleep(1)
            else:
                time.sleep(0.5)

    def demorgan_loop(self):
        add_log(">>> Деморган запущен", page="demorgan")
        if self.mode == "швейка":
            self.shveika_loop()
        else:
            self.tokar_loop()
        self.is_running = False
        add_log(">>> Деморган остановлен", page="demorgan")

    def stop_bot(self):
        self.is_running = False

demorgan_bot_instance = None

def get_demorgan_bot():
    global demorgan_bot_instance
    if demorgan_bot_instance is None:
        demorgan_bot_instance = DemorganBot()
    return demorgan_bot_instance

def toggle_demorgan():
    global demorgan_thread, demorgan_bot_instance
    ensure_demorgan_state()
    bot = get_demorgan_bot()
    data = state["modules"]["demorgan"]

    if not data["active"]:
        settings = data.get("settings", {})
        bot.mode = settings.get("mode", "швейка")
        bot.confidence = float(settings.get("confidence", 0.7))
        bot.click_interval = float(settings.get("click_interval", 0.5))
        bot.tokar_pause = int(settings.get("tokar_pause", 65))
        bot.shveika_pause = int(settings.get("shveika_pause", 85))
        bot.counter = data.get("counter", 0)

        data["active"] = True
        stop_event.clear()
        bot.is_running = False
        demorgan_thread = threading.Thread(target=bot.demorgan_loop, daemon=True)
        demorgan_thread.start()
        add_log(f"✅ Деморган запущен (режим: {bot.mode})", page="demorgan")
        return True
    else:
        data["active"] = False
        stop_event.set()
        bot.stop_bot()
        data["counter"] = bot.counter
        add_log("⏹️ Деморган остановлен", page="demorgan")
        return True

def toggle_auto_run():
    result = demorgan_auto_runner.toggle()
    state["modules"]["demorgan"]["auto_run_active"] = demorgan_auto_runner.is_active()
    return result

@demorgan_bp.route('/demorgan')
def render_demorgan():
    ensure_demorgan_state()
    bot = get_demorgan_bot()
    module_state = state["modules"]["demorgan"]
    return render_template(
        'demorgan.html',
        active=module_state.get("active", False),
        auto_run_active=module_state.get("auto_run_active", False),
        settings=module_state.get("settings", {}),
        counter=bot.counter if bot else module_state.get("counter", 0)
    )

@demorgan_bp.route('/api/demorgan/toggle', methods=['POST'])
def api_toggle():
    result = toggle_demorgan()
    return jsonify({
        "status": "ok" if result else "error",
        "active": state["modules"]["demorgan"]["active"]
    })

@demorgan_bp.route('/api/demorgan/auto_run/toggle', methods=['POST'])
def api_auto_run_toggle():
    new_state = toggle_auto_run()
    return jsonify({
        "status": "ok", 
        "auto_run_active": new_state
    })

@demorgan_bp.route('/api/demorgan/settings', methods=['POST'])
def api_settings():
    data = request.json
    if data:
        state["modules"]["demorgan"]["settings"] = data
        update_settings("demorgan", data, page="demorgan")
        bot = get_demorgan_bot()
        if bot:
            bot.mode = data.get("mode", "швейка")
            bot.confidence = float(data.get("confidence", 0.7))
            bot.click_interval = float(data.get("click_interval", 0.5))
            bot.tokar_pause = int(data.get("tokar_pause", 65))
            bot.shveika_pause = int(data.get("shveika_pause", 85))
        add_log(f"⚙️ Настройки деморгана обновлены", page="demorgan")
    return jsonify({"status": "ok"})

@demorgan_bp.route('/api/demorgan/stats', methods=['GET'])
def api_stats():
    bot = get_demorgan_bot()
    counter = bot.counter if bot else state["modules"]["demorgan"]["counter"]
    return jsonify({"counter": counter})

@demorgan_bp.route('/api/demorgan/reset_counter', methods=['POST'])
def api_reset_counter():
    ensure_demorgan_state()
    bot = get_demorgan_bot()
    if bot:
        bot.counter = 0
    state["modules"]["demorgan"]["counter"] = 0
    add_log("🔄 Счетчик деморгана сброшен", page="demorgan")
    return jsonify({"status": "ok", "counter": 0})