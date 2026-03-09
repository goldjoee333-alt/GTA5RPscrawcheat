@echo off
chcp 65001 >nul
title SCRawCheat - Простая компиляция
color 0A

echo ========================================
echo    SCRawCheat - Простая компиляция
echo ========================================
echo.
echo Текущая папка: %CD%
echo.

:: Переходим в папку с проектом (на всякий случай)
cd /d C:\Users\troll\Documents\scrawcheats

:: Проверяем что мы в правильной папке
if not exist "main.py" (
    echo [ОШИБКА] Файл main.py не найден!
    echo Убедитесь что вы в папке с проектом
    pause
    exit /b
)

echo [OK] Найден main.py
echo.

:: Чистим старые файлы
if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"
if exist "*.spec" del /q "*.spec"

:: Запускаем компиляцию
echo Компиляция...
echo.

C:\Python311\python.exe -m PyInstaller --noconfirm --windowed --uac-admin --distpath="dist" --workpath="build/temp" --icon=static/icons/bot.ico --add-data "templates;templates" --add-data "static;static" --add-data "core;core" --add-data "pages;pages" --hidden-import=flask --hidden-import=flask_socketio --hidden-import=engineio --hidden-import=socketio --hidden-import=werkzeug --hidden-import=jinja2 --hidden-import=markupsafe --hidden-import=itsdangerous --hidden-import=click --hidden-import=pyautogui --hidden-import=keyboard --hidden-import=pynput --hidden-import=PIL --hidden-import=numpy --hidden-import=cv2 --hidden-import=mss --hidden-import=psutil --hidden-import=pydirectinput --hidden-import=webview --collect-all flask --collect-all flask_socketio --collect-all engineio --collect-all socketio --collect-all pyautogui --collect-all pynput main.py

echo.
if %errorlevel% equ 0 (
    echo ========================================
    echo    ✅ КОМПИЛЯЦИЯ УСПЕШНА!
    echo ========================================
    echo.
    echo Файл создан: dist\main.exe
    
    :: Создаем простой start.bat
    (
    echo @echo off
    echo chcp 65001 ^>nul
    echo title SCRawCheat
    echo color 0A
    echo cd /d "%%~dp0"
    echo start "" "main.exe"
    echo echo Программа запущена...
    echo pause
    ) > dist\start.bat
    
    echo Создан файл запуска: dist\start.bat
    echo.
    dir dist\main.exe
) else (
    echo ========================================
    echo    ❌ ОШИБКА КОМПИЛЯЦИИ
    echo ========================================
)

pause