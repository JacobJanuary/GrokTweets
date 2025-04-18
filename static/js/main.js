document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM fully loaded - initializing scripts');

    // Функция для динамической подгрузки изображений
    function loadImages() {
        console.log('Loading images...');
        const images = document.querySelectorAll('.image-container img');

        images.forEach((img, index) => {
            // Если изображение не загрузилось, заменяем на плейсхолдер
            img.addEventListener('error', function() {
                console.log(`Error loading image: ${this.src}`);
                this.src = 'https://via.placeholder.com/300x200?text=Image+Not+Available';
                this.parentElement.classList.add('image-error');
            });

            // Анимация появления после загрузки
            img.addEventListener('load', function() {
                console.log(`Image loaded successfully: ${this.src}`);
                this.style.opacity = '1';
                this.parentElement.classList.add('loaded');
            });
        });
    }

    // Инициализация загрузки изображений
    loadImages();

    // Обработка переключения активной категории
    const categoryCheckboxes = document.querySelectorAll('.category-checkbox input');
    categoryCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', function() {
            const parent = this.parentElement;
            parent.classList.toggle('active', this.checked);
        });
    });

    // Сжимаем/разворачиваем блоки фильтров для компактного отображения
    const filterTitles = document.querySelectorAll('.filter-title');
    filterTitles.forEach(title => {
        title.addEventListener('click', function() {
            const filterGroup = this.closest('.filter-group');
            filterGroup.classList.toggle('collapsed');
        });

        // Добавляем иконку для сворачивания/разворачивания
        const toggleIcon = document.createElement('i');
        toggleIcon.className = 'fas fa-chevron-down toggle-icon';
        title.appendChild(toggleIcon);
    });

    // ------------ ГОЛОСОВАНИЕ ------------

    // Функция для показа уведомлений
    function showNotification(message, type = 'success') {
        // Создаем элемент уведомления
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.textContent = message;

        // Добавляем уведомление на страницу
        const container = document.getElementById('notification-container');
        container.appendChild(notification);

        // Показываем уведомление с небольшой задержкой
        setTimeout(() => {
            notification.classList.add('show');
        }, 10);

        // Скрываем и удаляем уведомление через 3 секунды
        setTimeout(() => {
            notification.classList.remove('show');

            // Удаляем из DOM после завершения анимации
            setTimeout(() => {
                container.removeChild(notification);
            }, 300);
        }, 3000);
    }

    // Обработка нажатий на кнопки голосования
    const voteButtons = document.querySelectorAll('.vote-button');
    voteButtons.forEach(button => {
        button.addEventListener('click', function() {
            const tweetId = this.dataset.tweetId;
            const voteType = this.dataset.voteType;

            // Отключаем кнопку на время запроса
            this.disabled = true;

            // Отправляем запрос на голосование
            fetch('/api/vote', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    tweet_id: tweetId,
                    vote_type: voteType
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Отмечаем кнопку как нажатую
                    this.classList.add('voted');

                    // Отключаем другую кнопку в этой паре
                    const tweetFooter = this.closest('.tweet-footer');
                    const otherButtons = tweetFooter.querySelectorAll(`.vote-button:not([data-vote-type="${voteType}"])`);
                    otherButtons.forEach(btn => {
                        btn.disabled = true;
                        btn.style.opacity = '0.5';
                    });

                    // Показываем уведомление об успехе
                    showNotification(data.message, 'success');
                } else {
                    // Показываем уведомление об ошибке
                    showNotification(data.message, 'error');
                    this.disabled = false;
                }
            })
            .catch(error => {
                console.error('Ошибка при голосовании:', error);
                showNotification('Произошла ошибка при голосовании', 'error');
                this.disabled = false;
            });
        });
    });

    // Исправляем проблему с прозрачностью изображений при загрузке страницы
    setTimeout(function() {
        const loadedImages = document.querySelectorAll('.image-container img');
        loadedImages.forEach(img => {
            if (img.complete) {
                img.style.opacity = '1';
                img.parentElement.classList.add('loaded');
            }
        });
    }, 500);
});