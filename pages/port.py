import threading
import time
import random
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

port_bp = Blueprint('port', __name__)
stop_event = threading.Event()
port_thread = None

def get_asset_path(relative_path):
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

def ensure_port_state():
    if "port" not in state["modules"]:
        state["modules"]["port"] = {
            "active": False,
            "auto_run_active": False,
            "settings": get_settings("port"),
            "stats": {
                "boxes_moved": 0,
                "money_earned": 0,
                "money_per_click": 132
            }
        }
    else:
        if "auto_run_active" not in state["modules"]["port"]:
            state["modules"]["port"]["auto_run_active"] = False
        if "settings" not in state["modules"]["port"]:
            state["modules"]["port"]["settings"] = get_settings("port")
        if "stats" not in state["modules"]["port"]:
            state["modules"]["port"]["stats"] = {
                "boxes_moved": 0,
                "money_earned": 0,
                "money_per_click": 132
            }
        else:
            stats = state["modules"]["port"]["stats"]
            if "boxes_moved" not in stats:
                stats["boxes_moved"] = 0
            if "money_earned" not in stats:
                stats["money_earned"] = 0
            if "money_per_click" not in stats:
                stats["money_per_click"] = 132

ensure_port_state()

port_auto_runner = auto_run_manager.create_runner("port", page="port")

PORT_MONITOR = {'left': 600, 'top': 400, 'width': 720, 'height': 120}
PORT_TOLERANCE = 60
PORT_MIN_DELAY = 0.09
PORT_MAX_DELAY = 0.2
PORT_MIN_AREA = 400
PORT_STABILITY_CHECKS = 3
PORT_STABILITY_DELAY = 0.01
PORT_COOLDOWN = 0.5
PORT_CENTER_X = PORT_MONITOR['left'] + PORT_MONITOR['width'] // 2

VK_CODES = {
    'e': 0x45
}

class FastInput:
    user32 = ctypes.windll.user32
    KEYEVENTF_KEYUP = 0x0002
    
    @staticmethod
    def press_key(key):
        if key.lower() in VK_CODES:
            vk = VK_CODES[key.lower()]
            FastInput.user32.keybd_event(vk, 0, 0, 0)
            time.sleep(0.01)
            FastInput.user32.keybd_event(vk, 0, FastInput.KEYEVENTF_KEYUP, 0)
            return True
        return False

def port_bot_loop():
    port_last_press = 0
    last_pos = None
    stable = 0
    data = state["modules"]["port"]
    stats = data["stats"]
    count = stats.get("boxes_moved", 0)
    
    add_log("🚀 Порт-бот запущен", page="port")
    
    if not is_gta_process_running_cached():
        add_log("⚠️ GTA 5 не запущена, бот будет ждать", page="port")
    
    try:
        with mss.mss() as sct:
            while data["active"] and not stop_event.is_set():
                if not is_gta_process_running_cached():
                    time.sleep(1.0)
                    continue
                
                img = np.array(sct.grab(PORT_MONITOR))
                bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
                
                mask = cv2.inRange(hsv, (35, 90, 90), (85, 255, 255))
                cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                cur = None
                for c in cnts:
                    area = cv2.contourArea(c)
                    if area > PORT_MIN_AREA:
                        x, y, w, h = cv2.boundingRect(c)
                        center = PORT_MONITOR['left'] + x + w // 2
                        if abs(center - PORT_CENTER_X) <= PORT_TOLERANCE:
                            cur = center
                            break
                
                if cur is not None:
                    if last_pos is not None and abs(cur - last_pos) < 10:
                        stable += 1
                    else:
                        stable = 1
                    last_pos = cur
                    now = time.time()
                    
                    if stable >= PORT_STABILITY_CHECKS and now - port_last_press > PORT_COOLDOWN:
                        time.sleep(PORT_STABILITY_DELAY * 2)
                        
                        verify = np.array(sct.grab(PORT_MONITOR))
                        vbgr = cv2.cvtColor(verify, cv2.COLOR_BGRA2BGR)
                        vhsv = cv2.cvtColor(vbgr, cv2.COLOR_BGR2HSV)
                        vmask = cv2.inRange(vhsv, (35, 90, 90), (85, 255, 255))
                        vcnts, _ = cv2.findContours(vmask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                        
                        ok = False
                        for c in vcnts:
                            if cv2.contourArea(c) > PORT_MIN_AREA:
                                x, y, w, h = cv2.boundingRect(c)
                                if abs(PORT_MONITOR['left'] + x + w // 2 - PORT_CENTER_X) <= PORT_TOLERANCE:
                                    ok = True
                                    break
                        
                        if ok:
                            time.sleep(random.uniform(PORT_MIN_DELAY, PORT_MAX_DELAY))
                            FastInput.press_key('e')
                            port_last_press = now
                            stable = 0
                            last_pos = None
                            count += 1
                            stats["boxes_moved"] = count
                            stats["money_earned"] = count * stats.get("money_per_click", 132)
                            add_log(f"👍 Нажал E! Ящиков: {count} | Денег: {stats['money_earned']}$", page="port")
                else:
                    stable = 0
                    last_pos = None
                
                time.sleep(0.005)
                
    except Exception as e:
        add_log(f"❌ Критическая ошибка порта: {e}", level="ERROR", page="port")
    finally:
        data["active"] = False
        add_log("⏹️ Порт-бот остановлен", page="port")

def toggle_port():
    global port_thread
    ensure_port_state()
    data = state["modules"]["port"]
    
    if not data["active"]:
        data["active"] = True
        stop_event.clear()
        port_thread = threading.Thread(target=port_bot_loop, daemon=True)
        port_thread.start()
        add_log("✅ Порт-бот запущен", page="port")
        return True
    else:
        data["active"] = False
        stop_event.set()
        add_log("⏹️ Порт-бот остановлен", page="port")
        return True

def toggle_auto_run():
    result = port_auto_runner.toggle()
    state["modules"]["port"]["auto_run_active"] = port_auto_runner.is_active()
    return result

@port_bp.route('/port')
def render_port():
    ensure_port_state()
    
    module_state = state["modules"]["port"]
    active = module_state.get("active", False)
    auto_run_active = module_state.get("auto_run_active", False)
    settings = module_state.get("settings", {})
    stats = module_state.get("stats", {
        "boxes_moved": 0,
        "money_earned": 0,
        "money_per_click": 132
    })
    
    return render_template(
        'port.html',
        active=active,
        auto_run_active=auto_run_active,
        settings=settings,
        stats=stats
    )

@port_bp.route('/api/port/toggle', methods=['POST'])
def api_toggle():
    result = toggle_port()
    return jsonify({
        "status": "ok" if result else "error", 
        "active": state["modules"]["port"]["active"]
    })

@port_bp.route('/api/port/auto_run/toggle', methods=['POST'])
def api_auto_run_toggle():
    new_state = toggle_auto_run()
    return jsonify({
        "status": "ok", 
        "auto_run_active": new_state
    })

@port_bp.route('/api/port/set_money', methods=['POST'])
def api_set_money():
    ensure_port_state()
    data = request.json
    amount = data.get('amount', 132)
    
    if "stats" not in state["modules"]["port"]:
        state["modules"]["port"]["stats"] = {}
    
    state["modules"]["port"]["stats"]["money_per_click"] = amount
    
    boxes = state["modules"]["port"]["stats"].get("boxes_moved", 0)
    state["modules"]["port"]["stats"]["money_earned"] = boxes * amount
    
    update_settings("port", state["modules"]["port"]["settings"], page="port")
    add_log(f"💰 Заработок за нажатие изменен на: {amount}$", page="port")
    return jsonify({"status": "ok"})

@port_bp.route('/api/port/stats', methods=['GET'])
def api_get_stats():
    ensure_port_state()
    stats = state["modules"]["port"].get("stats", {
        "boxes_moved": 0,
        "money_earned": 0,
        "money_per_click": 132
    })
    return jsonify(stats)

@port_bp.route('/api/port/reset_stats', methods=['POST'])
def api_reset_stats():
    ensure_port_state()
    
    money_per_click = state["modules"]["port"]["stats"].get("money_per_click", 132)
    
    state["modules"]["port"]["stats"] = {
        "boxes_moved": 0,
        "money_earned": 0,
        "money_per_click": money_per_click
    }
    
    add_log("🔄 Статистика порта сброшена", page="port")
    return jsonify({"status": "ok", "stats": state["modules"]["port"]["stats"]})