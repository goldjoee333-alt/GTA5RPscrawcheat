/**
 * hotkey.js - Запись хоткеев
 * SCRawCheat
 */

(function() {
    // Инициализация при загрузке страницы
    document.addEventListener('DOMContentLoaded', function() {
        initializeHotkeyInputs();
    });

    /**
     * Инициализация всех полей ввода хоткеев
     */
    function initializeHotkeyInputs() {
        const hotkeyInputs = document.querySelectorAll('.hotkey-input');

        hotkeyInputs.forEach(function(input) {
            if (input.dataset.hotkeyInitialized === 'true') return;

            let selectedHotkey = input.value ? input.value.toLowerCase() : 'f5';

            // Сохраняем начальное значение
            if (!input.value || input.value === '...') {
                input.value = selectedHotkey.toUpperCase();
            } else {
                selectedHotkey = input.value.toLowerCase();
            }

            // Обработчик клика - начинаем запись
            input.addEventListener('click', function(e) {
                e.preventDefault();
                this.value = '...';
                this.classList.add('active');
                this.dataset.recording = 'true';
            });

            // Обработчик нажатия клавиш
            input.addEventListener('keydown', function(e) {
                e.preventDefault();

                if (this.dataset.recording !== 'true') return;

                const code = e.code;

                // Игнорируем модификаторы отдельно
                if (code.includes('Shift') || code.includes('Control') ||
                    code.includes('Alt') || code.includes('Meta') ||
                    code === 'Tab' || code === 'Escape') {
                    return;
                }

                let key = '';

                if (code.startsWith('Key')) {
                    key = code.replace('Key', '').toLowerCase();
                } else if (code.startsWith('Digit')) {
                    key = code.replace('Digit', '');
                } else if (code.startsWith('F') && code.length <= 3) {
                    key = code.toLowerCase();
                } else {
                    key = code.toLowerCase();
                }

                selectedHotkey = key;
                this.value = key.toUpperCase();
                this.classList.remove('active');
                this.dataset.recording = 'false';
                this.blur();

                // Сохраняем в глобальной переменной для текущей страницы
                if (typeof window.setSelectedHotkey === 'function') {
                    window.setSelectedHotkey(key);
                }
            });

            // Обработчик потери фокуса
            input.addEventListener('blur', function() {
                if (this.value === '...' || this.value === '') {
                    this.value = selectedHotkey.toUpperCase();
                }
                this.classList.remove('active');
                this.dataset.recording = 'false';
            });

            input.dataset.hotkeyInitialized = 'true';

            // Сохраняем в объекте окна для доступа из других модулей
            if (!window.hotkeyInputs) {
                window.hotkeyInputs = {};
            }
            window.hotkeyInputs[input.id || 'hotkey-default'] = {
                input: input,
                getValue: function() { return selectedHotkey; }
            };
        });
    }

    /**
     * Получить выбранный хоткей
     */
    window.getSelectedHotkey = function(inputId) {
        if (inputId && window.hotkeyInputs && window.hotkeyInputs[inputId]) {
            return window.hotkeyInputs[inputId].getValue();
        }

        // По умолчанию ищем первый .hotkey-input
        const input = document.querySelector('.hotkey-input');
        if (input && input.value && input.value !== '...') {
            return input.value.toLowerCase();
        }
        return 'f5';
    };

    /**
     * Установить выбранный хоткей
     */
    window.setSelectedHotkey = function(key, inputId) {
        if (inputId && window.hotkeyInputs && window.hotkeyInputs[inputId]) {
            const input = window.hotkeyInputs[inputId].input;
            input.value = key.toUpperCase();
        }
    };
})();