#!/bin/bash

# Директория для lock-файла
LOCK_DIR="/var/lock"
LOCK_FILE="$LOCK_DIR/100news.lock"

# Путь к логам
LOG_FILE="/var/log/100news.log"

# Проверяем, существует ли lock-файл
if [ -e "$LOCK_FILE" ]; then
    # Проверяем, активен ли процесс
    PID=$(cat "$LOCK_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "$(date): Скрипт уже выполняется с PID $PID. Выход." >> "$LOG_FILE"
        exit 0
    else
        echo "$(date): Найден устаревший lock-файл. Удаляю." >> "$LOG_FILE"
        rm "$LOCK_FILE"
    fi
fi

# Создаем lock-файл
echo $$ > "$LOCK_FILE"

# Путь к вашему скрипту Python (измените на актуальный)
SCRIPT_PATH="/opt/100news/100news.py"

# Путь к интерпретатору Python в вашем окружении
PYTHON_PATH="/opt/100news/venv/bin/python"

# Запуск скрипта с выводом логов
echo "$(date): Запуск скрипта 100news.py" >> "$LOG_FILE"
$PYTHON_PATH $SCRIPT_PATH >> "$LOG_FILE" 2>&1
EXIT_CODE=$?

# Логгируем результат выполнения
if [ $EXIT_CODE -eq 0 ]; then
    echo "$(date): Скрипт успешно завершен" >> "$LOG_FILE"
else
    echo "$(date): Скрипт завершился с ошибкой. Код: $EXIT_CODE" >> "$LOG_FILE"
fi

# Удаляем lock-файл при завершении
rm "$LOCK_FILE"

exit $EXIT_CODE