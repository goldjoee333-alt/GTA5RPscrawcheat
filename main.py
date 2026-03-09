#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import threading
from flask import Flask, send_from_directory
from pynput import keyboard
from core.common import hotkey_manager, get_settings, CHEAT_NAME, VERSION
import webview
import socket
import time
import ctypes
import sys
import os
import traceback

# ===== ФИКС ПУТЕЙ ДЛЯ КОМПИЛЯЦИИ =====
def get_base_path():
    """Определяет базовый путь при запуске из exe или исходников"""
    if getattr(sys, 'frozen', False):
        # Запуск из скомпилированного exe
        base_path = sys._MEIPASS
        print(f"✅ Запуск из exe, базовый путь: {base_path}")
    else:
        # Запуск из исходников
        base_path = os.path.dirname(os.path.abspath(__file__))
        print(f"✅ Запуск из исходников, базовый путь: {base_path}")
    return base_path

# ===== ДОБАВЛЯЕМ ПУТИ В sys.path =====
base_path = get_base_path()
if base_path not in sys.path:
    sys.path.insert(0, base_path)

# ===== ОТЛАДКА: ЛОВИМ ВСЕ ОШИБКИ =====
def show_error_and_exit(error_msg):
    """Показывает ошибку в консоли и MessageBox, потом ждет нажатия Enter"""
    print("\n" + "="*60)
    print("❌ КРИТИЧЕСКАЯ ОШИБКА ❌")
    print(str(error_msg))
    print("="*60)
    print("\nПОЛНАЯ ИНФОРМАЦИЯ:")
    traceback.print_exc()
    print("\n" + "="*60)
    print("Окно закроется через 10 секунд или нажмите Enter...")
    print("="*60)
    
    try:
        ctypes.windll.user32.MessageBoxW(0, str(error_msg), "SCRawCheat - Ошибка", 0x10 | 0x1)
    except:
        pass
    
    def wait_enter():
        try:
            input()
        except:
            pass
        os._exit(1)
    
    wait_thread = threading.Thread(target=wait_enter, daemon=True)
    wait_thread.start()
    time.sleep(10)
    os._exit(1)

# Ловим все исключения на верхнем уровне
try:
    # ===== АВТОЗАПУСК ОТ АДМИНИСТРАТОРА =====
    def is_admin():
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False

    def run_as_admin():
        try:
            script = os.path.abspath(sys.argv[0])
            params = ' '.join([f'"{arg}"' for arg in sys.argv[1:]])
            
            ctypes.windll.user32.MessageBoxW(0, 
                "Скрипт будет перезапущен от имени администратора.\n"
                "Нажмите 'Да' в окне UAC.", 
                "Требуются права администратора", 0x40 | 0x1)
            
            ret = ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, f'"{script}" {params}', None, 1
            )
            
            if ret <= 32:
                print("❌ Не удалось получить права администратора")
                input("Нажмите Enter для выхода...")
                sys.exit(1)
            else:
                sys.exit(0)
        except Exception as e:
            print(f"❌ Ошибка при запросе прав администратора: {e}")
            input("Нажмите Enter для выхода...")
            sys.exit(1)

    # Проверяем права администратора при запуске
    if not is_admin():
        print("="*60)
        print(f"{CHEAT_NAME} v{VERSION} - ЗАПУСК")
        print("="*60)
        print("⚠️ Для корректной работы требуются права администратора!")
        print("Скрипт будет перезапущен с правами администратора")
        print("="*60)
        time.sleep(2)
        run_as_admin()
    else:
        print("="*60)
        print(f"{CHEAT_NAME} v{VERSION} - ЗАПУСК")
        print("="*60)
        print("✅ Права администратора получены")
        print("✅ Консоль активна (для отладки)")
        print("="*60)

    # ===== ОСНОВНОЙ КОД =====
    # Импортируем модули с отловом ошибок
    try:
        print("📦 Импорт pages...")
        from pages import pages_bp
        print("✅ pages импортирован")
    except Exception as e:
        show_error_and_exit(f"❌ Ошибка импорта pages: {e}")

    try:
        print("📦 Импорт core.api...")
        from core.api import fetch_online_once, check_update_once
        print("✅ core.api импортирован")
    except Exception as e:
        show_error_and_exit(f"❌ Ошибка импорта core.api: {e}")

    # Создаем Flask приложение с правильными путями
    try:
        print("🔧 Создание Flask приложения...")
        
        # Определяем пути для шаблонов и статики
        if getattr(sys, 'frozen', False):
            # В скомпилированном exe
            template_folder = os.path.join(sys._MEIPASS, 'templates')
            static_folder = os.path.join(sys._MEIPASS, 'static')
        else:
            # В исходниках
            template_folder = 'templates'
            static_folder = 'static'
        
        print(f"📁 Папка шаблонов: {template_folder}")
        print(f"📁 Папка статики: {static_folder}")
        print(f"📁 Существует шаблонов: {os.path.exists(template_folder)}")
        print(f"📁 Существует статика: {os.path.exists(static_folder)}")
        
        app = Flask(__name__,
                   template_folder=template_folder,
                   static_folder=static_folder,
                   static_url_path='/static')  # Явно указываем URL путь
        
        app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
        app.config['DEBUG'] = False
        app.config['ENV'] = 'production'
        app.register_blueprint(pages_bp)
        
        # ===== ПРИНУДИТЕЛЬНАЯ РАЗДАЧА СТАТИКИ =====
        @app.route('/static/<path:filename>')
        def serve_static(filename):
            """Основной маршрут для статических файлов"""
            try:
                return send_from_directory(app.static_folder, filename)
            except Exception as e:
                print(f"❌ Ошибка загрузки статики {filename}: {e}")
                return "File not found", 404

        @app.route('/assets/<path:filename>')
        def serve_assets(filename):
            """Маршрут для assets (для обратной совместимости)"""
            try:
                return send_from_directory(os.path.join(app.static_folder, 'assets'), filename)
            except Exception as e:
                print(f"❌ Ошибка загрузки assets {filename}: {e}")
                return "File not found", 404

        @app.route('/static/assets/<path:filename>')
        def serve_static_assets(filename):
            """Маршрут для static/assets"""
            try:
                return send_from_directory(os.path.join(app.static_folder, 'assets'), filename)
            except Exception as e:
                print(f"❌ Ошибка загрузки static/assets {filename}: {e}")
                return "File not found", 404

        @app.route('/static/assets/<category>/<path:filename>')
        def serve_category(category, filename):
            """Маршрут для static/assets/category/"""
            try:
                return send_from_directory(os.path.join(app.static_folder, 'assets', category), filename)
            except Exception as e:
                print(f"❌ Ошибка загрузки {category}/{filename}: {e}")
                return "File not found", 404

        # Маршрут для отладки
        @app.route('/debug-static')
        def debug_static():
            """Отладочная информация о путях"""
            import glob
            static_files = {}
            
            # Собираем информацию о файлах в static
            if os.path.exists(app.static_folder):
                for root, dirs, files in os.walk(app.static_folder):
                    rel_path = os.path.relpath(root, app.static_folder)
                    if files:
                        static_files[rel_path] = files[:5]  # Первые 5 файлов
            
            return {
                'static_folder': app.static_folder,
                'template_folder': app.template_folder,
                'static_exists': os.path.exists(app.static_folder) if app.static_folder else False,
                'template_exists': os.path.exists(app.template_folder) if app.template_folder else False,
                'frozen': getattr(sys, 'frozen', False),
                'meipass': sys._MEIPASS if getattr(sys, 'frozen', False) else None,
                'static_files': static_files
            }
        
        print("✅ Flask приложение создано")
    except Exception as e:
        show_error_and_exit(f"❌ Ошибка создания Flask приложения: {e}")

    window = None

    class WindowAPI:
        def minimize(self):
            global window
            if window:
                try:
                    window.minimize()
                except:
                    pass
        
        def close(self):
            global window
            if window:
                try:
                    window.destroy()
                except:
                    pass
        
        def move(self, x, y):
            global window
            if window:
                try:
                    window.move(int(x), int(y))
                except:
                    pass
        
        def get_position(self):
            global window
            if window:
                try:
                    return {'x': window.x, 'y': window.y}
                except:
                    pass
            return {'x': 0, 'y': 0}
        
        def set_size(self, width, height):
            global window
            if window:
                try:
                    window.resize(int(width), int(height))
                except:
                    pass

    window_api = WindowAPI()

    @app.context_processor
    def inject_ui_sounds():
        try:
            conf = get_settings("settings")
            return dict(
                vgamepad_available=True,
                ui_sounds={
                    "switch_hover": conf.get("switch_hover", True),
                    "switch_click": conf.get("switch_click", True),
                    "volume_hover": conf.get("volume_hover", 35),
                    "volume_click": conf.get("volume_click", 45),
                    "background": conf.get("background", "bot")
                }
            )
        except Exception as e:
            print(f"⚠️ Ошибка в inject_ui_sounds: {e}")
            return dict(ui_sounds={})

    def on_press(key):
        try:
            if hasattr(key, 'char') and key.char is not None:
                k = key.char.lower()
            elif hasattr(key, 'name'):
                k = key.name.lower()
            else:
                k = str(key).replace('Key.', '').lower()
            
            if k in hotkey_manager.actions:
                try:
                    hotkey_manager.actions[k]()
                except Exception as e:
                    print(f"⚠️ Ошибка хоткея {k}: {e}")
            else:
                print(f"ℹ️ Неизвестная клавиша: {k}")
        except Exception as e:
            print(f"⚠️ Ошибка хоткея: {e}")

    def start_flask():
        try:
            print("🚀 Запуск Flask сервера на порту 5000...")
            app.run(port=5000, use_reloader=False, threaded=True, debug=False, host='127.0.0.1')
        except Exception as e:
            show_error_and_exit(f"❌ Ошибка Flask: {e}")

    def wait_for_port(port, timeout=5.0):
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                with socket.create_connection(('127.0.0.1', port), timeout=0.1):
                    return True
            except:
                time.sleep(0.02)
        return False

    def get_center_position(width, height):
        try:
            user32 = ctypes.windll.user32
            screen_width = user32.GetSystemMetrics(0)
            screen_height = user32.GetSystemMetrics(1)
            x = (screen_width - width) // 2
            y = (screen_height - height) // 2
            return x, y
        except:
            return 100, 100

    # ===== ФУНКЦИЯ ДЛЯ СКРЫТИЯ КОНСОЛИ =====
    def hide_console():
        try:
            console_window = ctypes.windll.kernel32.GetConsoleWindow()
            if console_window:
                ctypes.windll.user32.ShowWindow(console_window, 0)
        except:
            pass

    if __name__ == '__main__':
        try:
            print("🎧 Запуск слушателя клавиатуры...")
            listener = keyboard.Listener(on_press=on_press)
            listener.daemon = True
            listener.start()
            print("✅ Слушатель клавиатуры запущен")
        except Exception as e:
            show_error_and_exit(f"❌ Ошибка слушателя: {e}")

        print("🔄 Запуск потоков...")
        threading.Thread(target=start_flask, daemon=True).start()
        threading.Thread(target=fetch_online_once, daemon=True).start()
        threading.Thread(target=check_update_once, daemon=True).start()
        
        if wait_for_port(5000):
            win_width, win_height = 800, 600
            x, y = get_center_position(win_width, win_height)
            
            try:
                print("🪟 Создание окна webview...")
                window = webview.create_window(
                    f'{CHEAT_NAME} v{VERSION}',
                    'http://127.0.0.1:5000/index',
                    width=win_width,
                    height=win_height,
                    x=x,
                    y=y,
                    frameless=True,
                    easy_drag=False,
                    js_api=window_api,
                    background_color='#000000'
                )
                print(f"✅ Окно создано ({win_width}x{win_height}), запуск webview...")
                
                webview.start(debug=False)
            except Exception as e:
                show_error_and_exit(f"❌ Ошибка окна: {e}")
        else:
            show_error_and_exit("❌ Flask не запустился за 5 секунд")
        
        try:
            listener.stop()
        except:
            pass

except Exception as e:
    # Ловим любые ошибки на верхнем уровне
    show_error_and_exit(f"❌ Необработанная ошибка: {e}")