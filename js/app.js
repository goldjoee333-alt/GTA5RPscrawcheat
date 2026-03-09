/**
 * app.js - Основная логика приложения
 * SCRawCheat
 */

// ===== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ =====
window.globalEventSource = null;
window.currentPageLogs = [];

// ===== ЗАГРУЗКА СТРАНИЦЫ =====
document.addEventListener('DOMContentLoaded', function() {
    console.log('SCRawCheat app.js loaded');

    // Скрываем лоадер
    const loader = document.getElementById('loader');
    if (loader) {
        setTimeout(function() {
            loader.classList.add('hidden');
        }, 500);
    }

    // Инициализируем SSE
    initEventSource();

    // Инициализируем звуки
    initSounds();

    // Инициализируем слайдеры
    initSliders();

    // Инициализируем подсказки
    initTooltips();

    // Устанавливаем активную ссылку
    updateActiveLink();
});

// ===== ЛОГИРОВАНИЕ =====
window.logManager = {
    /**
     * Добавить сообщение в лог
     */
    append: function(text) {
        const container = document.getElementById('log-container');
        if (!container) return;

        const div = document.createElement('div');
        div.textContent = text;
        container.appendChild(div);

        // Ограничиваем количество логов
        if (container.children.length > 100) {
            container.removeChild(container.firstChild);
        }

        // Прокручиваем вниз
        container.scrollTop = container.scrollHeight;
    },

    /**
     * Обработка SSE событий
     */
    handleSSE: function(event) {
        if (!event || !event.data) return;

        window.logManager.append(event.data);

        // Обновляем UI если нужно
        const data = event.data.toLowerCase();
        const isActive = data.includes('запущен') || data.includes('активирован');
        const isStopped = data.includes('остановлен') || data.includes('деактивирован');

        if (isActive && typeof window.updatePageUI === 'function') {
            window.updatePageUI(true);
        }
        if (isStopped && typeof window.updatePageUI === 'function') {
            window.updatePageUI(false);
        }
    }
};

/**
 * Обновление UI кнопки модуля
 */
window.updateModuleUI = function(btnId, active) {
    const btn = document.getElementById(btnId);
    if (!btn) return;

    btn.textContent = active ? 'ОСТАНОВИТЬ' : 'ЗАПУСТИТЬ';

    if (active) {
        btn.classList.add('running');
        btn.style.background = '';
    } else {
        btn.classList.remove('running');
        btn.style.background = '';
    }
};

/**
 * Загрузка логов модуля
 */
window.loadModuleLogs = function(moduleName) {
    const container = document.getElementById('log-container');
    if (container) {
        container.innerHTML = '';
    }

    fetch('/api/get_logs')
        .then(function(res) { return res.json(); })
        .then(function(data) {
            if (window.logManager && data.logs) {
                data.logs.forEach(function(log) {
                    if (log.includes('[' + moduleName + ']')) {
                        window.logManager.append(log);
                    }
                });
            }
        })
        .catch(function(err) {
            console.error('Ошибка загрузки логов:', err);
        });
};

/**
 * Инициализация SSE
 */
function initEventSource() {
    if (window.globalEventSource) {
        window.globalEventSource.close();
    }

    try {
        window.globalEventSource = new EventSource('/api/events');
        window.globalEventSource.onmessage = window.logManager.handleSSE;
        window.globalEventSource.onerror = function(e) {
            console.error('SSE error:', e);
            setTimeout(initEventSource, 3000);
        };
    } catch (e) {
        console.error('Error creating EventSource:', e);
    }
}

/**
 * Инициализация слайдеров
 */
function initSliders() {
    document.querySelectorAll('input[type="range"]').forEach(function(slider) {
        if (slider.dataset.initialized === 'true') return;

        function update() {
            const min = parseFloat(slider.min) || 0;
            const max = parseFloat(slider.max) || 100;
            const val = parseFloat(slider.value) || min;
            const percent = ((val - min) / (max - min)) * 100;
            slider.style.setProperty('--range-progress', percent + '%');
        }

        update();
        slider.addEventListener('input', update);
        slider.dataset.initialized = 'true';
    });
}

/**
 * Обновление активной ссылки в меню
 */
function updateActiveLink() {
    const currentPath = window.location.pathname;
    document.querySelectorAll('.nav-links a').forEach(function(link) {
        const href = link.getAttribute('href');
        if (href === currentPath) {
            link.classList.add('active');
        } else {
            link.classList.remove('active');
        }
    });
}

/**
 * Воспроизведение звука
 */
function quickPlay(type, event) {
    const config = window.UI_CONFIG;
    if (!config) return;

    // Не играем звук на toggle-switch (они обрабатываются отдельно)
    if (event && event.target) {
        const toggle = event.target.closest('.toggle-switch');
        if (toggle) return;
    }

    let audioId = (type === 'hover') ? 'hover-sound' : 'click-sound';
    let isEnabled = (type === 'hover') ? config.hoverEnabled : config.clickEnabled;
    let volume = (type === 'hover') ? config.hoverVol : config.clickVol;

    if (isEnabled) {
        const audio = document.getElementById(audioId);
        if (audio) {
            audio.volume = volume;
            audio.currentTime = 0;
            audio.play().catch(function(err) {
                // Игнорируем ошибки воспроизведения
            });
        }
    }
}

// Обработчики звуков
const handleHover = function(e) { quickPlay('hover', e); };
const handleClick = function(e) { quickPlay('click', e); };

/**
 * Инициализация звуков
 */
function initSounds() {
    const soundElements = document.querySelectorAll(
        '.module-switch, .btn-action, .nav-links a, button, .slider, .hotkey-input'
    );

    soundElements.forEach(function(el) {
        if (el.dataset.soundInit === 'true') return;

        el.addEventListener('mouseenter', handleHover);
        el.addEventListener('click', handleClick);
        el.dataset.soundInit = 'true';
    });
}

/**
 * Инициализация подсказок
 */
function initTooltips() {
    let tooltipContainer = document.getElementById('global-tooltip');
    if (!tooltipContainer) {
        tooltipContainer = document.createElement('div');
        tooltipContainer.id = 'global-tooltip';
        tooltipContainer.className = 'custom-tooltip';
        document.body.appendChild(tooltipContainer);
    }

    const navItems = document.querySelectorAll('.nav-item[data-tooltip]');

    navItems.forEach(function(item) {
        const tooltipText = item.getAttribute('data-tooltip');
        if (!tooltipText) return;

        item.addEventListener('mouseenter', function(e) {
            const isClosed = !document.body.classList.contains('sidebar-open');
            if (!isClosed) return;

            const rect = item.getBoundingClientRect();
            tooltipContainer.textContent = tooltipText;
            tooltipContainer.style.left = (rect.right + 10) + 'px';
            tooltipContainer.style.top = (rect.top + rect.height / 2) + 'px';
            tooltipContainer.style.opacity = '1';
            tooltipContainer.style.visibility = 'visible';
        });

        item.addEventListener('mouseleave', function() {
            tooltipContainer.style.opacity = '0';
            tooltipContainer.style.visibility = 'hidden';
        });
    });
}

/**
 * Переключение сайдбара
 */
window.toggleSidebar = function() {
    document.body.classList.toggle('sidebar-open');
};

/**
 * Отправка логов в Telegram
 */
window.sendLogsToTelegram = function() {
    const container = document.getElementById('log-container');
    if (!container || container.innerText.trim() === '') {
        alert('Логи пусты!');
        return;
    }

    const logText = container.innerText;
    const message = 'SCRawCheat Logs:\n' + logText;
    const telegramUrl = 'https://t.me/share/url?url=' + encodeURIComponent('SCRawCheat Logs') + '&text=' + encodeURIComponent(message);
    window.open(telegramUrl, '_blank');
};

/**
 * Обновление конфигурации UI
 */
window.refreshUIConfig = function() {
    return fetch('/api/settings/get')
        .then(function(res) { return res.json(); })
        .then(function(settings) {
            window.UI_CONFIG = {
                hoverEnabled: settings.switch_hover !== undefined ? settings.switch_hover : true,
                clickEnabled: settings.switch_click !== undefined ? settings.switch_click : true,
                hoverVol: (settings.volume_hover !== undefined ? settings.volume_hover : 35) / 100,
                clickVol: (settings.volume_click !== undefined ? settings.volume_click : 45) / 100,
                background: settings.background || 'bot'
            };
            return window.UI_CONFIG;
        })
        .catch(function(err) {
            console.error('Ошибка обновления UI_CONFIG:', err);
        });
};