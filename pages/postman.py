import threading
import time
import os
import sys
import pyautogui
import keyboard
from flask import render_template, jsonify, Blueprint, request
from core.common import (
    state, add_log,
    is_gta_process_running_cached,
    get_settings, update_settings
)
from core.autodrive import auto_drive_manager

postman_bp = Blueprint('postman', __name__)
stop_event = threading.Event()
postman_thread = None

auto_drive_active = False

def get_asset_path(relative_path):
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

def ensure_postman_state():
    if "postman" not in state["modules"]:
        state["modules"]["postman"] = {
            "active": False,
            "settings": get_settings("postman"),
            "counter": 0
        }
    else:
        if "settings" not in state["modules"]["postman"]:
            state["modules"]["postman"]["settings"] = get_settings("postman")
        if "counter" not in state["modules"]["postman"]:
            state["modules"]["postman"]["counter"] = 0
        if "active" not in state["modules"]["postman"]:
            state["modules"]["postman"]["active"] = False

ensure_postman_state()

postman_drive_runner = auto_drive_manager.create_runner("postman", page="postman")

USER_PATH = os.path.expanduser("~")
TEMPLATE_PATH = get_asset_path(os.path.join('static', 'assets', 'post', 'post.png'))
ALT_TEMPLATE_PATH = get_asset_path(os.path.join('static', 'assets', 'post', 'post.png'))

def get_template_path():
    if os.path.exists(TEMPLATE_PATH):
        return TEMPLATE_PATH
    elif os.path.exists(ALT_TEMPLATE_PATH):
        return ALT_TEMPLATE_PATH
    return None

def toggle_auto_drive():
    global auto_drive_active
    auto_drive_active = not auto_drive_active
    
    if auto_drive_active:
        postman_drive_runner.start()
        add_log("▶️ Ручная автоезда (W+Shift+0) ВКЛ", page="postman")
    else:
        postman_drive_runner.stop()
        add_log("⏸️ Ручная автоезда (W+Shift+0) ВЫКЛ", page="postman")
    
    return auto_drive_active

def toggle_postman():
    global postman_thread
    data = state["modules"]["postman"]
    
    if not data["active"]:
        data["active"] = True
        stop_event.clear()
        postman_thread = threading.Thread(target=postman_bot_loop, daemon=True)
        postman_thread.start()
        add_log("✅ Почтальон (авторежим) запущен", page="postman")
        return True
    else:
        data["active"] = False
        stop_event.set()
        add_log("⏹️ Почтальон (авторежим) остановлен", page="postman")
        return True

def postman_bot_loop():
    data = state["modules"]["postman"]
    settings = data.get("settings", {})
    confidence = float(settings.get("confidence", 0.7))
    cooldown = float(settings.get("click_cooldown", 2.5))
    template_path = get_template_path()

    add_log("🚚 Почтальон (авторежим) поток запущен", page="postman")

    if not template_path:
        add_log("❌ Шаблон post.png не найден", level="ERROR", page="postman")
        data["active"] = False
        return

    postman_drive_runner.start()

    last_click = 0
    try:
        while data["active"] and not stop_event.is_set():
            if not is_gta_process_running_cached():
                time.sleep(1.0)
                continue

            now = time.time()
            if now - last_click >= cooldown:
                try:
                    location = pyautogui.locateOnScreen(
                        template_path,
                        confidence=confidence,
                        grayscale=True
                    )
                    if location:
                        pyautogui.mouseDown(button='left')
                        time.sleep(0.12)
                        pyautogui.mouseUp(button='left')

                        data["counter"] += 1
                        add_log(f"🖱️ Клик #{data['counter']}", page="postman")
                        last_click = now
                except:
                    pass

            if keyboard.is_pressed('esc'):
                add_log("⏹️ Остановка по ESC", page="postman")
                break

            time.sleep(0.05)

    except Exception as e:
        add_log(f"❌ Критическая ошибка: {e}", level="ERROR", page="postman")
    finally:
        postman_drive_runner.stop()
        pyautogui.mouseUp(button='left')
        add_log("⏹️ Почтальон полностью остановлен", page="postman")
        data["active"] = False

@postman_bp.route('/postman')
def render_postman():
    ensure_postman_state()
    module_state = state["modules"]["postman"]
    active = module_state.get("active", False)
    settings = module_state.get("settings", {})
    counter = module_state.get("counter", 0)
    template_exists = get_template_path() is not None

    return render_template(
        'postman.html',
        active=active,
        settings=settings,
        counter=counter,
        template_exists=template_exists,
        auto_drive_active=auto_drive_active
    )

@postman_bp.route('/api/postman/control', methods=['POST'])
def api_control():
    data = request.json
    action = data.get('action')
    module_state = state["modules"]["postman"]

    if action == 'start_bot':
        if not module_state["active"]:
            toggle_postman()
    elif action == 'stop_bot':
        if module_state["active"]:
            toggle_postman()
    elif action == 'toggle_drive':
        toggle_auto_drive()

    return jsonify({
        "status": "ok",
        "active": module_state["active"],
        "auto_drive_active": auto_drive_active,
        "counter": module_state["counter"]
    })

@postman_bp.route('/api/postman/settings', methods=['POST'])
def api_settings():
    data = request.json
    if data:
        state["modules"]["postman"]["settings"] = data
        update_settings("postman", data, page="postman")
        add_log(f"⚙️ Настройки почтальона обновлены", page="postman")
    return jsonify({"status": "ok"})

@postman_bp.route('/api/postman/stats', methods=['GET'])
def api_stats():
    return jsonify({"counter": state["modules"]["postman"]["counter"]})

@postman_bp.route('/api/postman/reset_counter', methods=['POST'])
def api_reset_counter():
    ensure_postman_state()
    state["modules"]["postman"]["counter"] = 0
    add_log("🔄 Счетчик почтальона сброшен", page="postman")
    return jsonify({"status": "ok", "counter": 0})

@postman_bp.route('/api/postman/toggle', methods=['POST'])
def api_toggle():
    result = toggle_postman()
    return jsonify({
        "status": "ok",
        "active": result
    })

@postman_bp.route('/api/postman/auto_drive/toggle', methods=['POST'])
def api_auto_drive_toggle():
    new_state = toggle_auto_drive()
    return jsonify({
        "status": "ok",
        "auto_drive_active": new_state
    })