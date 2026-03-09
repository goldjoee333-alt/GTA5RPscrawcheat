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

cooking_bp = Blueprint('cooking', __name__)
stop_event = threading.Event()
cooking_thread = None
cooking_active = False

def get_asset_path(relative_path):
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

RECIPES = ["смузи", "фрукты", "фруктовый салат"]

INGREDIENT_MAP = {
    "смузи": [
        {"name": "knife2.png", "key": "e", "category": "cook"},
        {"name": "frukti.png", "key": "e", "category": "cook"},
        {"name": "myaso.png", "key": "e", "category": "cook"},
        {"name": "ovoshi.png", "key": "e", "category": "cook"},
        {"name": "fire2.png", "key": "e", "category": "cook"},
        {"name": "whisk2.png", "key": "e", "category": "cook"},
    ],
    "фрукты": [
        {"name": "frukti.png", "key": "e", "category": "cook"},
        {"name": "knife2.png", "key": "e", "category": "cook"},
    ],
    "фруктовый салат": [
        {"name": "fruktisalat.png", "key": "e", "category": "cook"},
        {"name": "knife2.png", "key": "e", "category": "cook"},
    ]
}

if "cooking" not in state["modules"]:
    state["modules"]["cooking"] = {
        "active": False,
        "settings": get_settings("cooking"),
        "counter": 0
    }

cooking_auto_runner = auto_run_manager.create_runner("cooking", page="cooking")

class CookingBot:
    def __init__(self):
        self.templates = {}
        self.is_running = False
        self.last_screenshot = None
        self.last_screenshot_time = 0
        self.screenshot_interval = 0.005
        self.counter = 0
        self.last_press_time = 0
        self.min_press_interval = 0.05
        self.load_templates()

    def load_templates(self):
        cook_dir = get_asset_path(os.path.join('static', 'assets', 'cook'))
        if not os.path.exists(cook_dir):
            add_log(f"⚠️ Папка {cook_dir} не найдена", page="cooking")
            return False
        
        loaded = 0
        for recipe_name, ingredients in INGREDIENT_MAP.items():
            for ingredient in ingredients:
                img_name = ingredient["name"]
                img_path = os.path.join(cook_dir, img_name)
                if os.path.exists(img_path):
                    img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
                    if img is not None:
                        key = f"{recipe_name}_{img_name}"
                        self.templates[key] = {
                            'image': img,
                            'key': ingredient["key"],
                            'path': img_path,
                            'recipe': recipe_name,
                            'name': img_name
                        }
                        loaded += 1
        add_log(f"✅ Загружено шаблонов кулинарии: {loaded}", page="cooking")
        return loaded > 0

    def ultra_fast_screenshot(self):
        now = time.time()
        if now - self.last_screenshot_time >= self.screenshot_interval:
            try:
                self.last_screenshot = ImageGrab.grab()
                self.last_screenshot_time = now
            except:
                return None
        return self.last_screenshot

    def find_ingredient(self, recipe_name):
        scr = self.ultra_fast_screenshot()
        if scr is None:
            return None
        
        try:
            gray = cv2.cvtColor(np.array(scr), cv2.COLOR_RGB2GRAY)
            
            for key, tmpl in self.templates.items():
                if recipe_name in key:
                    result = cv2.matchTemplate(gray, tmpl['image'], cv2.TM_CCOEFF_NORMED)
                    _, max_val, _, max_loc = cv2.minMaxLoc(result)
                    
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

    def cooking_loop(self, recipe_name, click_delay, cycle_delay):
        add_log(f">>> Кулинария запущена (режим: {recipe_name})", page="cooking")
        
        if not self.templates:
            add_log("❌ Нет шаблонов", level="ERROR", page="cooking")
            self.is_running = False
            return
        
        self.is_running = True
        press_count = 0
        cycle_start = time.time()
        
        while self.is_running and not stop_event.is_set():
            if not is_gta_process_running_cached():
                time.sleep(1.0)
                continue
            
            now = time.time()
            if now - cycle_start >= cycle_delay:
                cycle_start = now
            
            key = self.find_ingredient(recipe_name)
            if key and self.can_press():
                import keyboard
                keyboard.press(key)
                time.sleep(click_delay)
                keyboard.release(key)
                
                self.counter += 1
                press_count += 1
                state["modules"]["cooking"]["counter"] = self.counter
                
                if press_count % 10 == 0:
                    add_log(f"🍳 Нажата {key.upper()} | Счет: {self.counter}", page="cooking")
            
            time.sleep(0.005)
        
        self.is_running = False
        add_log(">>> Кулинария остановлена", page="cooking")

    def stop_bot(self):
        self.is_running = False

cooking_bot_instance = None

def get_cooking_bot():
    global cooking_bot_instance
    if cooking_bot_instance is None:
        cooking_bot_instance = CookingBot()
    return cooking_bot_instance

def toggle_cooking():
    global cooking_thread, cooking_bot_instance
    
    bot = get_cooking_bot()
    data = state["modules"]["cooking"]
    
    if not data["active"]:
        settings = data.get("settings", {})
        recipe_name = settings.get("mode", "смузи")
        click_delay = float(settings.get("click_delay", 0.08))
        cycle_delay = float(settings.get("cycle_delay", 5.7))
        
        bot.load_templates()
        bot.counter = data.get("counter", 0)
        
        data["active"] = True
        stop_event.clear()
        
        bot.is_running = False
        cooking_thread = threading.Thread(target=bot.cooking_loop, args=(recipe_name, click_delay, cycle_delay), daemon=True)
        cooking_thread.start()
        
        add_log(f"✅ Кулинария запущена (режим: {recipe_name})", page="cooking")
        return True
    else:
        data["active"] = False
        stop_event.set()
        bot.stop_bot()
        
        data["counter"] = bot.counter
        
        add_log("⏹️ Кулинария остановлена", page="cooking")
        return True

def toggle_auto_run():
    result = cooking_auto_runner.toggle()
    state["modules"]["cooking"]["auto_run_active"] = cooking_auto_runner.is_active()
    return result

@cooking_bp.route('/cooking')
def render_cooking():
    bot = get_cooking_bot()
    
    module_state = state["modules"]["cooking"]
    active = module_state.get("active", False)
    settings = module_state.get("settings", {})
    counter = bot.counter if bot else module_state.get("counter", 0)
    
    return render_template(
        'cooking.html',
        active=active,
        settings=settings,
        counter=counter,
        recipes=RECIPES
    )

@cooking_bp.route('/api/cooking/toggle', methods=['POST'])
def api_toggle():
    data = request.get_json()
    
    if data and 'settings' in data:
        s = data['settings']
        settings = {
            'mode': s.get('mode', 'смузи'),
            'click_delay': float(s.get('click_delay', 0.08)),
            'cycle_delay': float(s.get('cycle_delay', 5.7))
        }
        state["modules"]["cooking"]["settings"] = settings
        update_settings("cooking", settings, page="cooking")
    
    result = toggle_cooking()
    return jsonify({
        "status": "ok" if result else "error",
        "active": state["modules"]["cooking"]["active"]
    })

@cooking_bp.route('/api/cooking/auto_run/toggle', methods=['POST'])
def api_auto_run_toggle():
    new_state = toggle_auto_run()
    return jsonify({
        "status": "ok", 
        "auto_run_active": new_state
    })

@cooking_bp.route('/api/cooking/settings', methods=['POST'])
def api_settings():
    data = request.json
    if data:
        state["modules"]["cooking"]["settings"] = data
        update_settings("cooking", data, page="cooking")
        add_log(f"⚙️ Настройки кулинарии обновлены", page="cooking")
    return jsonify({"status": "ok"})

@cooking_bp.route('/api/cooking/stats', methods=['GET'])
def api_stats():
    bot = get_cooking_bot()
    counter = bot.counter if bot else state["modules"]["cooking"].get("counter", 0)
    return jsonify({"counter": counter})

@cooking_bp.route('/api/cooking/reset_counter', methods=['POST'])
def api_reset_counter():
    bot = get_cooking_bot()
    if bot:
        bot.counter = 0
    state["modules"]["cooking"]["counter"] = 0
    add_log("🔄 Счетчик кулинарии сброшен", page="cooking")
    return jsonify({"status": "ok", "counter": 0})