#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import threading
import time
import keyboard
from typing import Dict, Optional
from .common import add_log, is_gta_process_running_cached

class AutoDriveManager:
    """
    Менеджер автоезды для всех модулей
    Позволяет запускать/останавливать автоезду (W+Shift+0)
    """
    
    def __init__(self):
        self.runners: Dict[str, 'AutoDriveRunner'] = {}
        
    def create_runner(self, name: str, page: str = "system") -> 'AutoDriveRunner':
        """
        Создает новый раннер для автоезды
        """
        if name not in self.runners:
            self.runners[name] = AutoDriveRunner(name, page)
        return self.runners[name]
    
    def get_runner(self, name: str) -> Optional['AutoDriveRunner']:
        """
        Получает раннер по имени
        """
        return self.runners.get(name)
    
    def stop_all(self):
        """
        Останавливает все автоезды
        """
        for runner in self.runners.values():
            runner.stop()
        add_log("⏹️ Все автоезды остановлены", page="system")


class AutoDriveRunner:
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
                # Зажимаем W, Shift и 0
                keyboard.press('w')
                keyboard.press('shift')
                keyboard.press('0')
                time.sleep(0.1)
            else:
                # Отпускаем все клавиши
                keyboard.release('w')
                keyboard.release('shift')
                keyboard.release('0')
                time.sleep(0.1)
        
        # Освобождаем клавиши при остановке
        keyboard.release('w')
        keyboard.release('shift')
        keyboard.release('0')
        
    def start(self):
        """
        Запускает автоезду
        """
        if not self.active:
            self.active = True
            self.stop_event.clear()
            
            if self.thread is None or not self.thread.is_alive():
                self.thread = threading.Thread(target=self._worker, daemon=True)
                self.thread.start()
                
            add_log(f"✅ Автоезда (W+Shift+0) [{self.name}] запущена", page=self.page)
            return True
        return False
    
    def stop(self):
        """
        Останавливает автоезду
        """
        if self.active:
            self.active = False
            self.stop_event.set()
            
            if self.thread and self.thread.is_alive():
                self.thread.join(timeout=1.0)
                
            add_log(f"⏹️ Автоезда (W+Shift+0) [{self.name}] остановлена", page=self.page)
            return True
        return False
    
    def toggle(self):
        """
        Переключает состояние автоезды
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
auto_drive_manager = AutoDriveManager()

__all__ = [
    'auto_drive_manager',
    'AutoDriveRunner',
    'AutoDriveManager'
]