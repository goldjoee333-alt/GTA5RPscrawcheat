from flask import Blueprint, Response, jsonify, render_template, request, send_from_directory
import time
import os
import queue
import requests
from core.common import (
    hotkey_manager, state, clients, add_log,
    VERSION, CHEAT_NAME, is_gta_process_running_cached, get_gta_pids
)
import core.common as common

api = Blueprint('api', __name__)

@api.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(api.root_path, 'static'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')

@api.route('/index')
def index():
    return render_template('index.html', version=VERSION, online=common.cached_online, update_info=common.cached_update)

@api.route('/api/set_active_tab/<name>', methods=['POST'])
def set_active_tab(name):
    state["current_page"] = name
    add_log(f"Активная вкладка: {name}", page="system")
    
    try:
        hotkey_manager.clear()
        try:
            page_module = __import__(f"pages.{name}", fromlist=['register_hotkeys'])
            if hasattr(page_module, 'register_hotkeys'):
                page_module.register_hotkeys(hotkey_manager)
                add_log(f"Хоткеи для {name} зарегистрированы", page="system")
        except Exception as e:
            add_log(f"Модуль {name} не имеет хоткеев: {e}", "INFO", page="system")
    except Exception as e:
        add_log(f"Ошибка регистрации хоткеев: {e}", "ERROR", page="system")
    
    return jsonify({"status": "ok"})

@api.route('/api/events')
def events():
    def stream():
        q = queue.Queue()
        clients.append(q)
        
        for log in state["logs"][-20:]:
            yield f"data: {log}\n\n"
        
        try:
            while True:
                yield f"data: {q.get()}\n\n"
        except GeneratorExit:
            clients.remove(q)
    
    return Response(stream(), mimetype='text/event-stream')

@api.route('/api/get_logs')
def get_logs():
    return jsonify({"logs": state["logs"]})

@api.route('/api/get_online')
def get_online():
    return jsonify({"online": common.cached_online})

@api.route('/api/port/stats', methods=['GET'])
def get_port_stats():
    return jsonify(state["modules"]["port"]["stats"])

@api.route('/api/port/set_money', methods=['POST'])
def set_money_per_click():
    data = request.json
    amount = data.get('amount', 132)
    state["modules"]["port"]["stats"]["money_per_click"] = amount
    add_log(f"💰 Заработок за нажатие изменен на: {amount}$", page="port")
    return jsonify({"status": "ok"})

@api.route('/api/gta/status', methods=['GET'])
def api_gta_status():
    """Проверяет, запущен ли процесс GTA 5 и возвращает список PID"""
    running = is_gta_process_running_cached()
    processes = get_gta_pids()
    return jsonify({
        "running": running,
        "processes": processes,
        "count": len(processes)
    })

def check_update_once():
    try:
        response = requests.get("https://gitflic.ru/project/dornode/bot/blob/raw?file=version.txt", timeout=5)
        if response.status_code == 200:
            remote_version = response.text.strip()
            local_version = VERSION.strip()
            try:
                needs_update = float(remote_version) > float(local_version)
            except ValueError:
                needs_update = False
            common.cached_update = {
                "needs_update": needs_update,
                "remote_version": remote_version,
                "local_version": local_version
            }
        else:
            common.cached_update = {
                "needs_update": False,
                "error": "server_error",
                "remote_version": "",
                "local_version": VERSION
            }
    except Exception:
        common.cached_update = {
            "needs_update": False,
            "error": "network_error",
            "remote_version": "",
            "local_version": VERSION
        }

def fetch_online_once():
    try:
        response = requests.get("https://purls.ru/online.php", timeout=5)
        if response.status_code == 200:
            common.cached_online = response.text.strip()
        else:
            common.cached_online = "ошибка сервера"
    except Exception:
        common.cached_online = "ошибка сети"