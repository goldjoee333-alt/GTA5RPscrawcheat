import json
import os
import sys
from flask import Blueprint, render_template, jsonify, request
from core.common import add_log

bonus_bp = Blueprint('bonuspoint', __name__)

def get_asset_path(relative_path):
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

DATA_FILE = get_asset_path(os.path.join('configs', 'bp.json'))

DEFAULT_TASKS = [
    ("Посетить любой сайт в браузере", 1, 2),
    ("Зайти в любой канал в Brawl", 1, 2),
    ("Поставить лайк любой анкете в Match", 1, 2),
    ("Прокрутить за DP серебрянный или золотой кейс", 10, 20),
    ("Кинуть мяч питомцу 15 раз", 2, 4),
    ("15 выполненных питомцем команд", 2, 4),
    ("Ставка в колесе удачи в казино (межсерверное колесо)", 3, 6),
    ("Проехать 1 станцию на метро", 2, 4),
    ("Поймать 20 рыб", 4, 8),
    ("Выполнить 2 квеста любых клубов", 4, 8),
    ("Починить деталь в автосервисе", 1, 2),
    ("Забросить 2 мяча в баскетболе", 1, 2),
    ("Забить 2 гола в футболе", 1, 2),
    ("Победить в армрестлинге", 1, 2),
    ("Победить в дартс", 1, 2),
    ("Забить 10 голов в волейболе", 1, 2),
    ("Поиграть 1 минуту в настольный теннис", 1, 2),
    ("Поиграть 1 минуту в большой теннис", 1, 2),
    ("Сыграть в мафию в казино", 3, 6),
    ("Сделать платеж по лизингу", 1, 2),
    ("Посадить траву в теплице", 4, 8),
    ("Запустить переработку обезболивающих в лаборатории", 4, 8),
    ("Принять участие в двух аирдропах", 2, 4),
    ("3 часа в онлайне (можно выполнять многократно за день)", 2, 4),
    ("Нули в казино", 2, 4),
    ("25 действий на стройке", 2, 4),
    ("25 действий в порту", 2, 4),
    ("25 действий в шахте", 2, 4),
    ("3 победы в Дэнс Баттлах", 2, 4),
    ("Заказ материалов для бизнеса вручную", 1, 2),
    ("20 подходов в тренажерном зале", 1, 2),
    ("Успешная тренировка в тире", 1, 2),
    ("10 посылок на почте", 1, 2),
    ("Арендовать киностудию", 2, 4),
    ("Купить лотерейный билет", 1, 2),
    ("Выиграть гонку в картинге", 1, 2),
    ("10 действий на ферме", 1, 2),
    ("Потушить 25 'огоньков' пожарным", 1, 2),
    ("Выкопать 1 сокровище (не мусор)", 1, 2),
    ("Проехать 1 уличную гонку", 1, 2),
    ("Выполнить 3 заказа дальнобойщиком", 2, 4),
    ("Два раза оплатить смену внешности у хирурга в EMS", 2, 4),
    ("Добавить 5 видео в кинотеатре", 1, 2),
    ("Выиграть 5 игр в тренировочном комплексе со ставкой (от 100$)", 1, 2),
    ("Выиграть 3 любых игры на арене со ставкой (от 100$)", 1, 2),
    ("2 круга на любом маршруте автобусника", 2, 4),
    ("5 раз снять 100% шкуру с животных", 2, 4),
]

def load_state():
    if not os.path.exists(DATA_FILE):
        return {
            "vip": False,
            "server_x2": False,
            "tasks": [{"name": name, "base": base, "vip": vip, "checked": False} for name, base, vip in DEFAULT_TASKS]
        }
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_state(state_data):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(state_data, f, ensure_ascii=False, indent=2)

@bonus_bp.route('/bonuspoint')
def bonuspoint():
    state_data = load_state()
    return render_template('bonuspoint.html', state=state_data)

@bonus_bp.route('/api/bp/toggle_task', methods=['POST'])
def toggle_task():
    data = request.get_json()
    index = data.get('index')
    checked = data.get('checked')
    if index is None or checked is None:
        return jsonify({"status": "error"}), 400

    state_data = load_state()
    state_data['tasks'][index]['checked'] = checked
    save_state(state_data)
    return jsonify({"status": "ok"})

@bonus_bp.route('/api/bp/toggle_vip', methods=['POST'])
def toggle_vip():
    data = request.get_json()
    vip = data.get('vip')
    state_data = load_state()
    state_data['vip'] = vip
    save_state(state_data)
    return jsonify({"status": "ok"})

@bonus_bp.route('/api/bp/toggle_x2', methods=['POST'])
def toggle_x2():
    data = request.get_json()
    x2 = data.get('x2')
    state_data = load_state()
    state_data['server_x2'] = x2
    save_state(state_data)
    return jsonify({"status": "ok"})

@bonus_bp.route('/api/bp/clear_checked', methods=['POST'])
def clear_checked():
    state_data = load_state()
    for task in state_data['tasks']:
        task['checked'] = False
    save_state(state_data)
    return jsonify({"status": "ok"})

@bonus_bp.route('/api/bp/add_task', methods=['POST'])
def add_task():
    data = request.get_json()
    name = data.get('name')
    bp_text = data.get('bp')
    
    if not name or not bp_text or '/' not in bp_text:
        return jsonify({"status": "error", "message": "Неверный формат"}), 400

    try:
        base, vip = map(int, bp_text.split('/'))
    except:
        return jsonify({"status": "error", "message": "Неверный формат BP"}), 400

    state_data = load_state()
    state_data['tasks'].append({"name": name, "base": base, "vip": vip, "checked": False})
    save_state(state_data)
    add_log(f"➕ Добавлена задача: {name}", page="bonuspoint")
    return jsonify({"status": "ok"})

@bonus_bp.route('/api/bp/delete_task', methods=['POST'])
def delete_task():
    data = request.get_json()
    index = data.get('index')
    
    state_data = load_state()
    if 0 <= index < len(state_data['tasks']):
        task_name = state_data['tasks'][index]['name']
        state_data['tasks'].pop(index)
        save_state(state_data)
        add_log(f"🗑️ Удалена задача: {task_name}", page="bonuspoint")
        return jsonify({"status": "ok"})
    return jsonify({"status": "error", "message": "Индекс вне диапазона"}), 400

@bonus_bp.route('/api/bp/get_tasks', methods=['GET'])
def get_tasks():
    state_data = load_state()
    return jsonify(state_data['tasks'])

@bonus_bp.route('/api/bp/get_state', methods=['GET'])
def get_state():
    state_data = load_state()
    return jsonify(state_data)