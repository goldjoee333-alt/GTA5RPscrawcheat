// static/js/fix_all_paths.js
(function() {
    console.log('🔧 FIX ALL PATHS - ЗАГРУЖЕН');
    
    // СПИСОК ВСЕХ КАРТИНОК В ПРОЕКТЕ
    const ALL_IMAGES = {
        'build': [
            'image1.png', 'image2.png', 'image3.png', 'image4.png'
        ],
        'cook': [
            'fire2.png', 'frukti.png', 'fruktisalat.png', 'knife2.png', 
            'myaso.png', 'ovoshi.png', 'startCooking.png', 'voda.png', 
            'voda2.png', 'whisk2.png'
        ],
        'cow': [
            '1.png', '2.png', '3.png', 'cow.png'
        ],
        'gym': [
            'gym_done.png', 'gymFault.png', 'gymStart.png', 'gymSuccess.png'
        ],
        'post': [
            'post.png'
        ],
        'shveika': [
            '1.png', '2.png', '3.png', '4.png', '5.png', '6.png', '7.png', '8.png',
            '9.png', '10.png', '11.png', '12.png', '13.png', '14.png', '15.png', '16.png',
            '17.png', '18.png', '19.png', '20.png', 'checkForShveika.png', 'stopShveika.png'
        ],
        'taxi': [
            'taxi.png', 'принять.png'
        ],
        'tokar': [
            'i3.png', 'stameskaTest.png'
        ]
    };

    // Функция для предзагрузки всех картинок
    function preloadAllImages() {
        console.log('🔄 Предзагрузка всех картинок...');
        
        for (const [category, files] of Object.entries(ALL_IMAGES)) {
            files.forEach(filename => {
                const img = new Image();
                const path = `/static/assets/${category}/${filename}`;
                img.onload = () => console.log(`✅ Загружена: ${path}`);
                img.onerror = () => console.log(`❌ Не загружена: ${path}`);
                img.src = path;
            });
        }
    }

    // Функция для исправления всех img тегов на странице
    function fixAllImages() {
        const images = document.querySelectorAll('img');
        console.log(`📸 Найдено изображений на странице: ${images.length}`);
        
        images.forEach(img => {
            const originalSrc = img.getAttribute('src') || img.src;
            if (!originalSrc) return;
            
            // Пропускаем уже правильные пути
            if (originalSrc.includes('/static/')) return;
            if (originalSrc.startsWith('http')) return;
            if (originalSrc.startsWith('data:')) return;
            
            // Извлекаем имя файла
            const fileName = originalSrc.split('/').pop();
            
            // Ищем категорию по имени файла
            let foundCategory = null;
            for (const [category, files] of Object.entries(ALL_IMAGES)) {
                if (files.includes(fileName)) {
                    foundCategory = category;
                    break;
                }
            }
            
            if (foundCategory) {
                const newSrc = `/static/assets/${foundCategory}/${fileName}`;
                console.log(`🔄 Исправляем: ${originalSrc} -> ${newSrc}`);
                img.src = newSrc;
                
                // Добавляем обработчик ошибки
                img.onerror = function() {
                    console.error(`❌ Ошибка загрузки: ${newSrc}`);
                    // Пробуем альтернативный путь
                    this.src = `/static/assets/${foundCategory}/${fileName}`;
                };
            } else {
                // Если категория не найдена, пробуем угадать по пути
                if (originalSrc.includes('build')) {
                    img.src = `/static/assets/build/${fileName}`;
                } else if (originalSrc.includes('cook')) {
                    img.src = `/static/assets/cook/${fileName}`;
                } else if (originalSrc.includes('cow')) {
                    img.src = `/static/assets/cow/${fileName}`;
                } else if (originalSrc.includes('gym')) {
                    img.src = `/static/assets/gym/${fileName}`;
                } else if (originalSrc.includes('post')) {
                    img.src = `/static/assets/post/${fileName}`;
                } else if (originalSrc.includes('shveika')) {
                    img.src = `/static/assets/shveika/${fileName}`;
                } else if (originalSrc.includes('taxi')) {
                    img.src = `/static/assets/taxi/${fileName}`;
                } else if (originalSrc.includes('tokar')) {
                    img.src = `/static/assets/tokar/${fileName}`;
                }
            }
        });
    }

    // Запускаем предзагрузку всех картинок
    preloadAllImages();
    
    // Исправляем пути на текущей странице
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', fixAllImages);
    } else {
        fixAllImages();
    }
    
    // Наблюдаем за изменениями в DOM
    const observer = new MutationObserver(fixAllImages);
    observer.observe(document.body, {
        childList: true,
        subtree: true
    });
    
    // Запускаем каждые 2 секунды (на всякий случай)
    setInterval(fixAllImages, 2000);
})();