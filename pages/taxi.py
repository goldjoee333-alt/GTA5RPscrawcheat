import threading
import time
import os
import cv2
import numpy as np
from PIL import ImageGrab
import keyboard
from flask import render_template, jsonify, Blueprint, request
from core.common import (
    state, add_log,
    is_gta_process_running_cached,
    get_settings, update_settings
)
import ctypes
from ctypes import wintypes
import sys

taxi_bp = Blueprint('taxi', __name__)
stop_event = threading.Event()
taxi_thread = None

def get_asset_path(relative_path):
    """Возвращает правильный путь к файлу в зависимости от того, запущено ли приложение из exe или из исходников"""
    if getattr(sys, 'frozen', False):
        # Запуск из скомпилированного exe
        base_path = sys._MEIPASS
    else:
        # Запуск из исходников
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

if "taxi" not in state["modules"]:
    state["modules"]["taxi"] = {
        "active": False,
        "settings": get_settings("taxi"),
        "counter": 0
    }

# ИСПРАВЛЕНО: используем get_asset_path
TAXI_TEMPLATE_PATH = get_asset_path(os.path.join('static', 'assets', 'taxi', 'taxi.png'))

# ========== WINAPI для быстрых кликов ==========
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

# ========== КЛАСС TAXI BOT ==========
class TaxiBot:
    def __init__(self):
        self.template = None
        self.is_running = False
        self.confidence = 0.75
        self.check_interval = 0.0001
        self.last_click = 0
        self.cooldown = 3.0
        self.last_screenshot = None
        self.last_screenshot_time = 0
        self.screenshot_interval = 0.01
        self.thread = None
        self.counter = 0

    def load_template(self):
        """Загружает шаблон taxi.png"""
        if os.path.exists(TAXI_TEMPLATE_PATH):
            try:
                self.template = cv2.imread(TAXI_TEMPLATE_PATH, cv2.IMREAD_GRAYSCALE)
                if self.template is not None:
                    add_log(f"✅ Шаблон такси загружен: {TAXI_TEMPLATE_PATH}", page="taxi")
                    return True
            except Exception as e:
                add_log(f"❌ Ошибка загрузки шаблона: {e}", level="ERROR", page="taxi")
        
        # Если нет - ищем в других местах с правильными путями
        alt_paths = [
            get_asset_path(os.path.join('static', 'assets', 'taxi', 'taxi.png')),
            get_asset_path(os.path.join('static', 'assets', 'taxi', 'принять.png'))
        ]
        
        for path in alt_paths:
            if os.path.exists(path):
                try:
                    self.template = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
                    if self.template is not None:
                        add_log(f"✅ Шаблон такси загружен: {path}", page="taxi")
                        return True
                except:
                    continue
        
        add_log(f"❌ Шаблон такси НЕ НАЙДЕН! Положите taxi.png в static/assets/taxi/", 
                level="ERROR", page="taxi")
        return False

    def ultra_fast_screenshot(self):
        """Быстрый скриншот с кэшированием"""
        now = time.time()
        if now - self.last_screenshot_time >= self.screenshot_interval:
            try:
                self.last_screenshot = ImageGrab.grab()
                self.last_screenshot_time = now
            except:
                return None
        return self.last_screenshot

    def find_button_on_screen(self):
        """Ищет кнопку такси на экране"""
        if self.template is None:
            return None
        
        scr = self.ultra_fast_screenshot()
        if scr is None:
            return None
        
        try:
            gray = cv2.cvtColor(np.array(scr), cv2.COLOR_RGB2GRAY)
            res = cv2.matchTemplate(gray, self.template, cv2.TM_CCOEFF_NORMED)
            _, maxv, _, maxloc = cv2.minMaxLoc(res)
            
            if maxv >= self.confidence:
                h, w = self.template.shape
                center_x = maxloc[0] + w // 2
                center_y = maxloc[1] + h // 2
                return (center_x, center_y, maxv)
        except:
            return None
        
        return None

    def instant_click(self, x, y):
        """Мгновенный клик в указанные координаты"""
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
            
            self.counter += 1
            state["modules"]["taxi"]["counter"] = self.counter
            
            add_log(f"🚕 КЛИК по такси #{self.counter} в ({x}, {y})", page="taxi")
            return True
        except Exception as e:
            add_log(f"❌ Ошибка клика: {e}", level="ERROR", page="taxi")
            return False

    def taxi_loop(self):
        """Основной цикл бота"""
        add_log(">>> Модуль Такси (кликер) запущен", page="taxi")
        
        if not self.load_template():
            add_log("❌ Нет шаблона такси, остановка", level="ERROR", page="taxi")
            self.is_running = False
            return
        
        self.is_running = True
        err_count = 0
        
        while self.is_running and not stop_event.is_set():
            if keyboard.is_pressed('end'):
                add_log("⏹️ Такси остановлен по END", page="taxi")
                break
            
            now = time.time()
            if now - self.last_click < self.cooldown:
                time.sleep(self.check_interval)
                continue
            
            if not is_gta_process_running_cached():
                time.sleep(1.0)
                continue
            
            result = self.find_button_on_screen()
            
            if result:
                x, y, confidence = result
                add_log(f"🎯 Найдено такси с точностью {confidence:.2f}", page="taxi")
                
                if self.instant_click(x, y):
                    self.last_click = now
                    err_count = 0
                    time.sleep(0.5)
                else:
                    err_count += 1
            else:
                time.sleep(0.005)
            
            if err_count > 50:
                add_log("🔄 Перезагрузка шаблона...", page="taxi")
                self.load_template()
                err_count = 0
            
            time.sleep(self.check_interval)
        
        self.is_running = False
        add_log(">>> Модуль Такси остановлен", page="taxi")

    def stop_bot(self):
        """Остановка бота"""
        self.is_running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)
        self.thread = None

taxi_bot_instance = None

def get_taxi_bot():
    global taxi_bot_instance
    if taxi_bot_instance is None:
        taxi_bot_instance = TaxiBot()
    return taxi_bot_instance

def toggle_taxi():
    global taxi_thread, taxi_bot_instance
    
    bot = get_taxi_bot()
    data = state["modules"]["taxi"]
    
    if not data["active"]:
        settings = data.get("settings", {})
        bot.confidence = float(settings.get("confidence", 0.75))
        bot.cooldown = float(settings.get("cooldown", 3.0))
        bot.check_interval = float(settings.get("check_interval", 0.0001))
        
        if not bot.load_template():
            add_log("❌ Не удалось запустить такси: нет шаблона", level="ERROR", page="taxi")
            return False
        
        data["active"] = True
        stop_event.clear()
        
        bot.is_running = False
        bot.counter = data.get("counter", 0)
        
        taxi_thread = threading.Thread(target=bot.taxi_loop, daemon=True)
        taxi_thread.start()
        
        add_log("✅ Модуль Такси запущен", page="taxi")
        return True
    else:
        data["active"] = False
        stop_event.set()
        bot.stop_bot()
        data["counter"] = bot.counter
        add_log("⏹️ Модуль Такси остановлен", page="taxi")
        return True

@taxi_bp.route('/taxi')
def render_taxi():
    bot = get_taxi_bot()
    template_exists = os.path.exists(TAXI_TEMPLATE_PATH)
    
    return render_template(
        'taxi.html',
        active=state["modules"]["taxi"]["active"],
        settings=state["modules"]["taxi"]["settings"],
        counter=bot.counter if bot else state["modules"]["taxi"]["counter"],
        template_exists=template_exists
    )

@taxi_bp.route('/api/taxi/toggle', methods=['POST'])
def api_toggle():
    result = toggle_taxi()
    return jsonify({
        "status": "ok" if result else "error",
        "active": state["modules"]["taxi"]["active"]
    })

@taxi_bp.route('/api/taxi/settings', methods=['POST'])
def api_settings():
    data = request.json
    if data:
        state["modules"]["taxi"]["settings"] = data
        update_settings("taxi", data, page="taxi")
        
        bot = get_taxi_bot()
        if bot:
            bot.confidence = float(data.get('confidence', 0.75))
            bot.cooldown = float(data.get('cooldown', 3.0))
            bot.check_interval = float(data.get('check_interval', 0.0001))
        
        add_log(f"⚙️ Настройки такси обновлены", page="taxi")
    
    return jsonify({"status": "ok"})

@taxi_bp.route('/api/taxi/stats', methods=['GET'])
def api_stats():
    bot = get_taxi_bot()
    counter = bot.counter if bot else state["modules"]["taxi"]["counter"]
    return jsonify({"counter": counter})

@taxi_bp.route('/api/taxi/reset_counter', methods=['POST'])
def api_reset_counter():
    bot = get_taxi_bot()
    if bot:
        bot.counter = 0
    state["modules"]["taxi"]["counter"] = 0
    add_log("🔄 Счетчик такси сброшен", page="taxi")
    return jsonify({"status": "ok", "counter": 0})