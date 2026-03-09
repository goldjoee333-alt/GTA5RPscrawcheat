/**
 * drag.js - Перетаскивание окна и управление окном
 * SCRawCheat
 */

(function() {
    if (window.__dragInitialized) {
        return;
    }
    window.__dragInitialized = true;

    let isDragging = false;
    let dragStartX = 0;
    let dragStartY = 0;
    let initialWindowX = 0;
    let initialWindowY = 0;
    const dragRegion = document.querySelector('.titlebar-drag-region');

    /**
     * Сворачивание окна
     */
    window.minimizeWindow = function() {
        console.log('Minimize window called');
        if (window.pywebview && window.pywebview.api && window.pywebview.api.minimize) {
            try {
                window.pywebview.api.minimize();
            } catch (err) {
                console.error('Error minimizing window:', err);
            }
        } else {
            console.log('Minimize window (browser mode)');
        }
    };

    /**
     * Закрытие окна
     */
    window.closeWindow = function() {
        console.log('Close window called');
        if (window.pywebview && window.pywebview.api && window.pywebview.api.close) {
            try {
                window.pywebview.api.close();
            } catch (err) {
                console.error('Error closing window:', err);
            }
        } else {
            console.log('Close window (browser mode)');
            if (window.close) {
                window.close();
            }
        }
    };

    /**
     * Начало перетаскивания
     */
    const handleMouseDown = async function(e) {
        if (e.button !== 0) return;

        isDragging = true;
        dragStartX = e.screenX;
        dragStartY = e.screenY;

        if (window.pywebview && window.pywebview.api && window.pywebview.api.get_position) {
            try {
                const pos = await window.pywebview.api.get_position();
                // ИСПРАВЛЕНО: убраны точки и добавлены проверки
                initialWindowX = (pos && pos.x) ? pos.x : (window.screenX || 0);
                initialWindowY = (pos && pos.y) ? pos.y : (window.screenY || 0);
            } catch (err) {
                console.error('Error getting position:', err);
                initialWindowX = window.screenX || 0;
                initialWindowY = window.screenY || 0;
            }
        } else {
            initialWindowX = window.screenX || 0;
            initialWindowY = window.screenY || 0;
        }

        e.preventDefault();
    };

    /**
     * Процесс перетаскивания
     */
    const handleMouseMove = function(e) {
        if (!isDragging) return;

        const deltaX = e.screenX - dragStartX;
        const deltaY = e.screenY - dragStartY;

        const newX = initialWindowX + deltaX;
        const newY = initialWindowY + deltaY;

        if (window.pywebview && window.pywebview.api && window.pywebview.api.move) {
            try {
                window.pywebview.api.move(newX, newY);
            } catch (err) {
                console.error('Error moving window:', err);
            }
        }
    };

    /**
     * Завершение перетаскивания
     */
    const handleMouseUp = function() {
        isDragging = false;
    };

    // Добавляем обработчики событий
    if (dragRegion) {
        dragRegion.addEventListener('mousedown', handleMouseDown);
        document.addEventListener('mousemove', handleMouseMove);
        document.addEventListener('mouseup', handleMouseUp);
        document.addEventListener('mouseleave', handleMouseUp);
    }
})();