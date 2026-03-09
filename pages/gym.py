import threading
import time
import sys
import os
import cv2
import numpy as np
import mss
import random
from flask import render_template, jsonify, Blueprint, request
from core.common import (
    state, add_log, press, key_down, key_up,
    is_gta_process_running_cached,
    get_settings, update_settings
)

gym_bp = Blueprint('gym', __name__)
stop_event = threading.Event()
gym_bot_active = False
gym_thread = None

gym_auto_e_active = False
gym_auto_e_thread = None
gym_auto_e_stop = threading.Event()

def get_asset_path(relative_path):
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

state["modules"]["gym"] = {
    "active": False,
    "auto_e_active": False,
    "settings": get_settings("gym"),
    "counter": 0
}

MODES = {
    'Жим лежа': {
        'qte_x': 750, 'qte_y': 500, 'qte_w': 420, 'qte_h': 420,
        'rest_timeout': 6, 'min_rest': 31, 'max_rest': 35,
        'touch_threshold': 50, 'green_threshold': 800, 'circle_threshold': 100,
        'space_delay': 0.05, 'debounce_time': 0.1, 'e_spam_attempts': 25,
        'check_interval': 0.005
    },
    'Эспандер': {
        'qte_x': 750, 'qte_y': 500, 'qte_w': 420, 'qte_h': 420,
        'rest_timeout': 9, 'min_rest': 1, 'max_rest': 2,
        'touch_threshold': 50, 'green_threshold': 800, 'circle_threshold': 100,
        'space_delay': 0.05, 'debounce_time': 0.1, 'e_spam_attempts': 25,
        'check_interval': 0.005
    }
}

def auto_e_worker():
    add_log("🍔 Авто E (само еат) запущен", page="gym")
    global gym_auto_e_active
    settings = state["modules"]["gym"]["settings"]
    auto_e_interval = settings.get("auto_e_interval", 5.0)
    
    while not gym_auto_e_stop.is_set():
        if gym_auto_e_active and is_gta_process_running_cached():
            press('e')
            add_log("🍔 Нажата E (само еат)", page="gym")
            time.sleep(auto_e_interval)
        else:
            time.sleep(1.0)

def start_auto_e():
    global gym_auto_e_active, gym_auto_e_thread, gym_auto_e_stop
    if not gym_auto_e_active:
        gym_auto_e_active = True
        gym_auto_e_stop.clear()
        if gym_auto_e_thread is None or not gym_auto_e_thread.is_alive():
            gym_auto_e_thread = threading.Thread(target=auto_e_worker, daemon=True)
            gym_auto_e_thread.start()
        state["modules"]["gym"]["auto_e_active"] = True
        add_log("✅ Авто E включен", page="gym")

def stop_auto_e():
    global gym_auto_e_active
    if gym_auto_e_active:
        gym_auto_e_active = False
        gym_auto_e_stop.set()
        state["modules"]["gym"]["auto_e_active"] = False
        add_log("⏹️ Авто E выключен", page="gym")

def toggle_auto_e():
    if state["modules"]["gym"]["auto_e_active"]:
        stop_auto_e()
    else:
        start_auto_e()
    return state["modules"]["gym"]["auto_e_active"]

def capture_frame(mode_name):
    m = MODES[mode_name]
    mon = {'left': m['qte_x'], 'top': m['qte_y'], 'width': m['qte_w'], 'height': m['qte_h']}
    with mss.mss() as sct:
        img = np.array(sct.grab(mon))
    return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

def detect_touch(mode_name):
    frame = capture_frame(mode_name)
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    gm = cv2.inRange(hsv, (40, 50, 50), (80, 255, 255))
    wm = cv2.inRange(hsv, (0, 0, 180), (180, 40, 255))
    dilated = cv2.dilate(wm, np.ones((3, 3), np.uint8))
    ov = cv2.bitwise_and(gm, dilated)
    return (cv2.countNonZero(gm), cv2.countNonZero(ov))

def detect_circles_count(mode_name):
    frame = capture_frame(mode_name)
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    gm = cv2.inRange(hsv, (40, 50, 50), (80, 255, 255))
    wm = cv2.inRange(hsv, (0, 0, 180), (180, 40, 255))
    return cv2.countNonZero(gm) + cv2.countNonZero(wm)

def spam_e(mode_name):
    m = MODES[mode_name]
    for _ in range(m['e_spam_attempts']):
        press('e')
        if detect_circles_count(mode_name) > m['circle_threshold']:
            return
        time.sleep(0.5)

def gym_worker():
    add_log(">>> Модуль Качалка запущен", page="gym")
    data = state["modules"]["gym"]
    settings = data["settings"]
    mode_name = settings.get("mode", "Жим лежа")
    m = MODES[mode_name]

    last_activity = time.time()
    is_resting = False
    last_press_time = 0

    try:
        while data["active"] and not stop_event.is_set():
            if not is_gta_process_running_cached():
                time.sleep(1.0)
                continue

            now = time.time()

            if is_resting:
                rest_duration = random.randint(m['min_rest'], m['max_rest'])
                if now - last_activity > rest_duration:
                    is_resting = False
                    threading.Thread(target=spam_e, args=(mode_name,), daemon=True).start()
                    last_activity = now
                else:
                    time.sleep(0.1)
                    continue

            if now - last_activity > m['rest_timeout']:
                is_resting = True
                last_activity = now
                continue

            gp, ov = detect_touch(mode_name)
            if gp > m['green_threshold'] and ov >= m['touch_threshold']:
                if now - last_press_time >= m['debounce_time']:
                    time.sleep(m['space_delay'])
                    press('space')
                    last_press_time = now
                    last_activity = now
                    data["counter"] += 1
                    add_log(f"💪 Нажат пробел | Счет: {data['counter']}", page="gym")

            if stop_event.wait(m['check_interval']):
                break

    except Exception as e:
        add_log(f"❌ Ошибка качалки: {e}", level="ERROR", page="gym")
    finally:
        data["active"] = False
        add_log(">>> Модуль Качалка остановлен", page="gym")

def toggle_gym():
    global gym_bot_active, gym_thread
    data = state["modules"]["gym"]
    
    if not data["active"]:
        data["active"] = True
        gym_bot_active = True
        stop_event.clear()
        gym_thread = threading.Thread(target=gym_worker, daemon=True)
        gym_thread.start()
        add_log("✅ Модуль Качалка запущен", page="gym")
    else:
        data["active"] = False
        gym_bot_active = False
        stop_event.set()
        add_log("⏹️ Модуль Качалка остановлен", page="gym")

@gym_bp.route('/gym')
def render_gym():
    return render_template(
        'gym.html',
        active=state["modules"]["gym"]["active"],
        auto_e_active=state["modules"]["gym"]["auto_e_active"],
        settings=state["modules"]["gym"]["settings"],
        counter=state["modules"]["gym"]["counter"],
        modes=list(MODES.keys())
    )

@gym_bp.route('/api/gym/toggle', methods=['POST'])
def api_toggle():
    toggle_gym()
    return jsonify({"status": "ok", "active": state["modules"]["gym"]["active"]})

@gym_bp.route('/api/gym/auto_e/toggle', methods=['POST'])
def api_auto_e_toggle():
    new_state = toggle_auto_e()
    return jsonify({
        "status": "ok", 
        "auto_e_active": new_state
    })

@gym_bp.route('/api/gym/settings', methods=['POST'])
def api_settings():
    data = request.json
    if data:
        state["modules"]["gym"]["settings"] = data
        update_settings("gym", data, page="gym")
        add_log(f"⚙️ Настройки качалки обновлены", page="gym")
    return jsonify({"status": "ok"})

@gym_bp.route('/api/gym/stats', methods=['GET'])
def api_stats():
    return jsonify({"counter": state["modules"]["gym"]["counter"]})