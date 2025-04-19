import mysql.connector
import requests
import time
import os
from tqdm import tqdm
from dotenv import load_dotenv

# Загрузка переменных окружения из файла .env
load_dotenv()

# Конфигурация БД из переменных окружения
DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'database': os.getenv('DB_NAME'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'port': int(os.getenv('DB_PORT', 3306))
}

# API ключ и идентификатор папки Yandex.Cloud из переменных окружения
YANDEX_API_KEY = os.getenv('YANDEX_API_KEY')
YANDEX_FOLDER_ID = os.getenv('YANDEX_FOLDER_ID')

# Настройки приложения
BATCH_SIZE = int(os.getenv('BATCH_SIZE', 100))
DELAY_BETWEEN_REQUESTS = float(os.getenv('DELAY_BETWEEN_REQUESTS', 0.2))

# URL для Yandex Translate API
TRANSLATE_URL = "https://translate.api.cloud.yandex.net/translate/v2/translate"


def connect_to_db():
    """Подключение к базе данных MySQL"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        print("Успешное подключение к базе данных")
        return conn
    except mysql.connector.Error as err:
        print(f"Ошибка при подключении к базе данных: {err}")
        return None


def get_untranslated_tweets(conn, batch_size=100, offset=0):
    """Получение твитов из базы данных по пакетам"""
    cursor = conn.cursor(dictionary=True)

    # Запрос для получения твитов из good_tweet за текущий день
    query = """
            SELECT * \
            FROM `tweets` \
            WHERE  `created_at` >= NOW() - INTERVAL 24 HOUR \
                 LIMIT %s \
            OFFSET %s; \
            """

    cursor.execute(query, (batch_size, offset))
    tweets = cursor.fetchall()
    cursor.close()
    return tweets


def count_untranslated_tweets(conn):
    """Подсчёт общего количества твитов для перевода"""
    cursor = conn.cursor()

    # Запрос для подсчета твитов из good_tweet за текущий день
    query = """
            SELECT COUNT(*) \
            FROM `tweets` \
            WHERE  `created_at` >= NOW() - INTERVAL 24 HOUR \
            """

    cursor.execute(query)
    count = cursor.fetchone()[0]
    cursor.close()
    return count


def translate_text(text):
    """Перевод текста с английского на русский через Yandex API"""
    if not text:
        return ""

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Api-Key {YANDEX_API_KEY}"
    }

    data = {
        "folder_id": YANDEX_FOLDER_ID,
        "texts": [text],
        "sourceLanguageCode": "en",
        "targetLanguageCode": "ru"
    }

    try:
        response = requests.post(TRANSLATE_URL, json=data, headers=headers)
        response.raise_for_status()

        result = response.json()
        if 'translations' in result and result['translations']:
            return result['translations'][0]['text']
        return ""
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при обращении к API перевода: {e}")
        return ""


def update_tweet_translation(conn, tweet_id, translated_text):
    """Обновление поля tweet_text в базе данных и сохранение оригинального текста"""
    cursor = conn.cursor()

    # Сначала проверяем, есть ли уже сохраненный оригинальный текст
    query_check = """
                  SELECT tweet_text, original_tweet_text \
                  FROM tweets \
                  WHERE id = %s \
                  """
    cursor.execute(query_check, (tweet_id,))
    result = cursor.fetchone()

    if not result:
        cursor.close()
        return

    tweet_text, original_text = result

    # Создаем новое поле для хранения оригинального текста, если его еще нет
    try:
        cursor.execute("SHOW COLUMNS FROM tweets LIKE 'original_tweet_text'")
        column_exists = cursor.fetchone()
        if not column_exists:
            cursor.execute("ALTER TABLE tweets ADD COLUMN original_tweet_text TEXT")
            print("Создано новое поле 'original_tweet_text' для хранения оригинального текста")
    except mysql.connector.Error as err:
        print(f"Ошибка при проверке/создании колонки: {err}")

    # Обновляем запись: сохраняем оригинальный текст только если не был сохранен ранее
    if original_text is None:
        query_update = """
                       UPDATE tweets
                       SET original_tweet_text = %s,
                           tweet_text          = %s
                       WHERE id = %s \
                       """
        cursor.execute(query_update, (tweet_text, translated_text, tweet_id))
    else:
        # Если оригинальный текст уже сохранен, просто обновляем перевод
        query_update = """
                       UPDATE tweets
                       SET tweet_text = %s
                       WHERE id = %s \
                       """
        cursor.execute(query_update, (translated_text, tweet_id))

    cursor.close()


def main():
    # Проверка наличия необходимых переменных окружения
    required_vars = ['DB_HOST', 'DB_NAME', 'DB_USER', 'DB_PASSWORD', 'YANDEX_API_KEY', 'YANDEX_FOLDER_ID']
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        print(f"Ошибка: Следующие переменные окружения не найдены в файле .env: {', '.join(missing_vars)}")
        print("Пожалуйста, добавьте их в файл .env и попробуйте снова.")
        return

    # Подключение к базе данных
    conn = connect_to_db()
    if not conn:
        return

    try:
        # Посчитаем общее количество твитов для перевода для прогресс-бара
        total_tweets = count_untranslated_tweets(conn)
        print(f"Найдено {total_tweets} твитов для перевода")

        if total_tweets == 0:
            print("Нет твитов для обработки за сегодня.")
            return

        batch_size = BATCH_SIZE  # Размер пакета твитов из переменных окружения
        offset = 0
        processed_count = 0

        with tqdm(total=total_tweets, desc="Перевод твитов") as pbar:
            while processed_count < total_tweets:
                tweets = get_untranslated_tweets(conn, batch_size, offset)
                if not tweets:
                    break

                for tweet in tweets:
                    tweet_id = tweet['id']
                    tweet_text = tweet['tweet_text']

                    # Перевод текста
                    translated_text = translate_text(tweet_text)

                    # Обновление записи в БД
                    if translated_text:
                        update_tweet_translation(conn, tweet_id, translated_text)

                    # Небольшая задержка из переменных окружения
                    time.sleep(DELAY_BETWEEN_REQUESTS)
                    pbar.update(1)
                    processed_count += 1

                offset += batch_size

                # Сохраняем изменения каждые N твитов
                conn.commit()

        print(f"Перевод завершен. Переведено {processed_count} твитов.")

    except Exception as e:
        print(f"Произошла ошибка: {e}")

    finally:
        if conn and conn.is_connected():
            conn.close()
            print("Соединение с базой данных закрыто")


if __name__ == "__main__":
    main()