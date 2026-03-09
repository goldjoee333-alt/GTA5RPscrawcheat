#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import threading
import time
import keyboard
from typing import Dict, Optional
from .common import add_log, is_gta_process_running_cached

class AutoRunManager:
    """
    Менеджер автобега для всех модулей
    Позволяет запускать/останавливать автобег для порта, фермы, шахты и т.д.
    """
    
    def __init__(self):
        self.runners: Dict[str, 'AutoRunRunner'] = {}
        
    def create_runner(self, name: str, page: str = "system") -> 'AutoRunRunner':
        """
        Создает новый раннер для автобега
        """
        if name not in self.runners:
            self.runners[name] = AutoRunRunner(name, page)
        return self.runners[name]
    
    def get_runner(self, name: str) -> Optional['AutoRunRunner']:
        """
        Получает раннер по имени
        """
        return self.runners.get(name)
    
    def stop_all(self):
        """
        Останавливает все автобеги
        """
        for runner in self.runners.values():
            runner.stop()
        add_log("⏹️ Все автобеги остановлены", page="system")


class AutoRunRunner:
    """
    Отдельный раннер для одного модуля
    """
    
    def __init__(self, name: str, page: str = "system"):
        self.name = name
        self.page = page
        self.active = False
        self.stop_event = threading.Event()
        self.thread: Optional[threading.Thread] = None
        
    def _worker(self):
        """
        Основной рабочий поток
        """
        while not self.stop_event.is_set():
            if self.active and is_gta_process_running_cached():
                keyboard.press('w')
                keyboard.press('shift')
                time.sleep(0.1)
            else:
                keyboard.release('w')
                keyboard.release('shift')
                time.sleep(0.1)
        
        # Освобождаем клавиши при остановке
        keyboard.release('w')
        keyboard.release('shift')
        
    def start(self):
        """
        Запускает автобег
        """
        if not self.active:
            self.active = True
            self.stop_event.clear()
            
            if self.thread is None or not self.thread.is_alive():
                self.thread = threading.Thread(target=self._worker, daemon=True)
                self.thread.start()
                
            add_log(f"✅ Автобег [{self.name}] запущен", page=self.page)
            return True
        return False
    
    def stop(self):
        """
        Останавливает автобег
        """
        if self.active:
            self.active = False
            self.stop_event.set()
            
            if self.thread and self.thread.is_alive():
                self.thread.join(timeout=1.0)
                
            add_log(f"⏹️ Автобег [{self.name}] остановлен", page=self.page)
            return True
        return False
    
    def toggle(self):
        """
        Переключает состояние автобега
        """
        if self.active:
            return self.stop()
        else:
            return self.start()
    
    def is_active(self) -> bool:
        """
        Возвращает текущее состояние
        """
        return self.active


# Глобальный экземпляр менеджера
auto_run_manager = AutoRunManager()

__all__ = [
    'auto_run_manager',
    'AutoRunRunner',
    'AutoRunManager'
]