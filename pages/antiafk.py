import threading
import random
import time
import sys
import os
from flask import render_template, jsonify, request, Blueprint
from core.common import (
    state, add_log,
    is_gta_process_running_cached,
    get_settings, update_settings
)
import keyboard

antiafk_bp = Blueprint('antiafk', __name__)
stop_event = threading.Event()
antiafk_thread = None
afk_last_action_time = 0
afk_action_interval = 30
antiafk_active = False

def get_asset_path(relative_path):
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

if "antiafk" not in state["modules"]:
    state["modules"]["antiafk"] = {
        "active": False,
        "settings": get_settings("antiafk")
    }

def afk_loop():
    global afk_last_action_time, antiafk_active
    
    afk_last_action_time = time.time()
    
    while antiafk_active and not stop_event.is_set():
        try:
            now = time.time()
            if now - afk_last_action_time >= afk_action_interval:
                key = random.choice(['w', 'a', 's', 'd'])
                space = random.random() < 0.3
                
                add_log(f"🎮 АнтиАФК: НАЖИМАЕМ [{key.upper()}]" + (" + ПРОБЕЛ" if space else ""), page="antiafk")
                
                keyboard.press(key)
                if space:
                    time.sleep(random.uniform(0.05, 0.15))
                    keyboard.press('space')
                
                time.sleep(random.uniform(0.5, 1.5))
                
                keyboard.release(key)
                if space:
                    keyboard.release('space')
                
                afk_last_action_time = now
            
            if keyboard.is_pressed('end'):
                add_log("⏹️ АнтиАФК остановлен по END", page="antiafk")
                break
            
            time.sleep(0.1)
        except Exception as e:
            add_log(f"❌ Ошибка АнтиАФК: {e}", level="ERROR", page="antiafk")
            time.sleep(1)
    
    for k in ['w', 'a', 's', 'd', 'space']:
        try:
            keyboard.release(k)
        except:
            pass
    
    add_log(">>> АнтиАФК остановлен", page="antiafk")

def toggle_antiafk():
    global antiafk_thread, antiafk_active, afk_action_interval
    
    data = state["modules"]["antiafk"]
    settings = data.get("settings", {})
    afk_action_interval = float(settings.get("action_interval", 30.0))
    
    if not data["active"]:
        data["active"] = True
        antiafk_active = True
        stop_event.clear()
        
        antiafk_thread = threading.Thread(target=afk_loop, daemon=True)
        antiafk_thread.start()
        
        add_log(f"✅ АнтиАФК запущен (интервал {afk_action_interval} сек)", page="antiafk")
    else:
        data["active"] = False
        antiafk_active = False
        stop_event.set()
        add_log("⏹️ АнтиАФК остановлен", page="antiafk")

@antiafk_bp.route('/antiafk')
def render_antiafk():
    return render_template(
        'antiafk.html',
        active=state["modules"]["antiafk"]["active"],
        settings=state["modules"]["antiafk"]["settings"]
    )

@antiafk_bp.route('/api/antiafk/toggle', methods=['POST'])
def api_toggle():
    data = request.get_json()
    
    if data and 'settings' in data:
        s = data['settings']
        settings = {
            'action_interval': float(s.get('action_interval', 30.0))
        }
        state["modules"]["antiafk"]["settings"] = settings
        update_settings("antiafk", settings, page="antiafk")
    
    toggle_antiafk()
    
    return jsonify({
        "status": "ok",
        "active": state["modules"]["antiafk"]["active"]
    })

@antiafk_bp.route('/api/antiafk/settings', methods=['POST'])
def api_settings():
    data = request.json
    if data:
        state["modules"]["antiafk"]["settings"] = data
        update_settings("antiafk", data, page="antiafk")
        add_log(f"⚙️ Настройки антиафк обновлены", page="antiafk")
    return jsonify({"status": "ok"})