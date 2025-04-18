#отсеивает мусор и разбивает по категориям. Около $0.01 за 10 твитов
import requests
import json
import os
import time
from datetime import datetime
from dotenv import load_dotenv
# Updated import to use the new prompt file
from new_prompt import TWITTER_ANALYSIS_PROMPT
import mysql.connector
from mysql.connector import Error

# Загрузка API ключа из переменных окружения
load_dotenv()
API_KEY = os.getenv("GROK_API_KEY")

# Загрузка параметров подключения к БД
DB_CONFIG = {
    'host': os.getenv("DB_HOST"),
    'database': os.getenv("DB_NAME"),
    'user': os.getenv("DB_USER"),
    'password': os.getenv("DB_PASSWORD"),
    'port': int(os.getenv("DB_PORT"))
}

# Эндпоинт API
API_URL = "https://api.x.ai/v1/chat/completions"

# Системный промт для задания контекста анализа
SYSTEM_PROMPT = """Ты аналитик, который интерпретирует посты и комментарии на X, предоставляя подробный и понятный анализ их содержания и контекста. Отвечай на русском языке. Анализируй пошагово, учитывая весь контекст."""


def get_db_connection():
    """
    Создает и возвращает соединение с базой данных
    """
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        if connection.is_connected():
            print("Успешное подключение к базе данных")
            return connection
    except Error as e:
        print(f"Ошибка при подключении к базе данных: {e}")
        return None


def call_grok_api_improved(url):
    """
    Вызов Grok API с оптимизированными параметрами на основе рекомендаций
    """
    if not API_KEY:
        print("Ошибка: API ключ не найден. Создайте файл .env с GROK_API_KEY=ваш_ключ")
        return None

    # Получаем текст твита из базы данных
    connection = get_db_connection()
    if not connection:
        return None

    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT tweet_text FROM tweets WHERE url = %s", (url,))
        result = cursor.fetchone()
        if not result:
            print(f"Твит с URL {url} не найден в базе данных")
            return None
        tweet_text = result['tweet_text']
    except Exception as e:
        print(f"Ошибка при получении текста твита: {e}")
        return None
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

    headers = {
        "Content-Type": "application/json",
        "x-api-key": API_KEY
    }

    # Формируем сообщения с системным промтом и пользовательским запросом
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": TWITTER_ANALYSIS_PROMPT.replace("[Insert tweet text here]", tweet_text)}
    ]

    data = {
        "model": "grok-3-latest",
        "messages": messages,
        "temperature": 0.0,
        "max_tokens": 4096000,
        "thinking": True
    }

    try:
        print("\nОтправка запроса в Grok API...")
        response = requests.post(API_URL, headers=headers, json=data)
        response.raise_for_status()

        result = response.json()

        if "thinking" in result and result["thinking"]:
            print("\n=== Процесс мышления Grok (Think) ===")
            print(result["thinking"])
            print("================================\n")

        content = result["choices"][0]["message"]["content"]

        # Выводим ответ в консоль для отладки
        print("\n=== Ответ от Grok API ===")
        print(content)
        print("========================\n")

        return content

    except requests.exceptions.RequestException as e:
        print(f"Ошибка при обращении к API: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"Код ошибки: {e.response.status_code}")
            print(f"Ответ сервера: {e.response.text}")
            if e.response.status_code == 401:
                print("Ошибка аутентификации (401): Убедитесь, что ваш API-ключ правильно настроен в файле .env")
        return None
    except (KeyError, IndexError) as e:
        print(f"Ошибка при обработке ответа: {e}")
        print(f"Полученный ответ: {response.text if 'response' in locals() else 'Нет данных'}")
        return None


def mark_tweet_as_checked(tweet_id):
    """
    Помечает твит как проверенный, устанавливая isChecked = true
    """
    connection = get_db_connection()
    if not connection:
        return False

    try:
        cursor = connection.cursor()
        update_query = "UPDATE tweets SET isChecked = TRUE WHERE id = %s"
        cursor.execute(update_query, (tweet_id,))
        connection.commit()
        print(f"Твит ID {tweet_id} помечен как проверенный")
        return True
    except Error as e:
        print(f"Ошибка при обновлении статуса твита: {e}")
        return False
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()


def create_tables():
    """
    Создает таблицы categories и good_tweet, если они не существуют
    """
    connection = get_db_connection()
    if not connection:
        return False

    try:
        cursor = connection.cursor()

        # Создаем таблицу categories
        create_categories_query = """
                                  CREATE TABLE IF NOT EXISTS categories \
                                  ( \
                                      category_id \
                                      INT \
                                      AUTO_INCREMENT \
                                      PRIMARY \
                                      KEY, \
                                      category_name \
                                      VARCHAR \
                                  ( \
                                      50 \
                                  ) NOT NULL UNIQUE
                                      ) \
                                  """
        cursor.execute(create_categories_query)

        # Вставляем предопределенные категории, если их нет
        insert_categories_query = """
                                  INSERT \
                                  IGNORE INTO categories (category_name) 
        VALUES ('news'), ('analysis'), ('forecast'), ('insight'), ('education'), ('other') \
                                  """
        cursor.execute(insert_categories_query)

        # Создаем таблицу good_tweet
        create_good_tweet_query = """
                                  CREATE TABLE IF NOT EXISTS good_tweet \
                                  ( \
                                      id \
                                      INT \
                                      AUTO_INCREMENT \
                                      PRIMARY \
                                      KEY, \
                                      tweet_id \
                                      VARCHAR \
                                  ( \
                                      255 \
                                  ) NOT NULL,
                                      user_id VARCHAR \
                                  ( \
                                      255 \
                                  ) NOT NULL,
                                      category_id INT,
                                      grok_text TEXT,
                                      url VARCHAR \
                                  ( \
                                      255 \
                                  ),
                                      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                      FOREIGN KEY \
                                  ( \
                                      category_id \
                                  ) REFERENCES categories \
                                  ( \
                                      category_id \
                                  )
                                      ) \
                                  """
        cursor.execute(create_good_tweet_query)

        # Проверяем наличие поля isChecked в таблице tweets
        check_field_query = """
                            SELECT COUNT(*)
                            FROM information_schema.COLUMNS
                            WHERE TABLE_SCHEMA = %s
                              AND TABLE_NAME = 'tweets'
                              AND COLUMN_NAME = 'isChecked' \
                            """
        cursor.execute(check_field_query, (DB_CONFIG['database'],))
        field_exists = cursor.fetchone()[0]

        # Если поля нет, добавляем его
        if not field_exists:
            add_field_query = """
                              ALTER TABLE tweets
                                  ADD COLUMN isChecked BOOLEAN DEFAULT FALSE \
                              """
            cursor.execute(add_field_query)
            print("Поле isChecked добавлено в таблицу tweets")

        connection.commit()
        print("Таблицы categories и good_tweet созданы или уже существуют")
        return True
    except Error as e:
        print(f"Ошибка при создании таблиц: {e}")
        return False
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()


def process_tweets():
    """
    Обрабатывает твиты из базы данных и сохраняет результаты в таблицу good_tweet
    Возвращает словарь со статистикой обработки
    """
    connection = get_db_connection()
    if not connection:
        return {
            "total_processed": 0,
            "worthy_tweets": 0,
            "rejected_tweets": 0,
            "categories": {}
        }

    # Инициализируем статистику
    stats = {
        "total_processed": 0,
        "worthy_tweets": 0,
        "rejected_tweets": 0,
        "categories": {}
    }

    try:
        cursor = connection.cursor(dictionary=True)

        # Получаем твиты, соответствующие критериям, включая только непроверенные (isChecked = FALSE или NULL)
        select_query = """
                       SELECT id, user_id, tweet_text, url, likes, retweets, replies
                       FROM tweets
                        WHERE LENGTH(tweet_text) > 25
                         AND (isChecked = FALSE OR isChecked IS NULL) 
                         AND DATE(`created_at`)= CURDATE()
                       """

        cursor.execute(select_query)
        tweets = cursor.fetchall()

        print(f"Найдено {len(tweets)} твитов для обработки")

        for tweet in tweets:
            print(f"\nОбработка твита: {tweet['url']}")
            stats["total_processed"] += 1

            # Получаем анализ от Grok
            grok_response = call_grok_api_improved(tweet['url'])

            # Отмечаем твит как проверенный независимо от результатов анализа
            mark_tweet_as_checked(tweet['id'])

            if grok_response:
                # Анализируем ответ от Grok (теперь он должен быть либо "NO", либо название категории)
                grok_response = grok_response.strip()

                # Проверяем, соответствует ли ответ ожидаемому формату
                valid_categories = ["news", "analysis", "forecast", "insight", "education", "other"]
                is_valid_response = (grok_response.upper() == "NO") or (grok_response.lower() in valid_categories)

                # Если ответ некорректен, не помечаем твит как проверенный и пропускаем его
                if not is_valid_response:
                    print(f"Неожиданный ответ от Grok API: {grok_response}")
                    print(f"Твит {tweet['id']} будет отправлен на повторную проверку")
                    # Отменяем пометку как проверенный (откатываем действие mark_tweet_as_checked)
                    update_query = "UPDATE tweets SET isChecked = FALSE WHERE id = %s"
                    cursor.execute(update_query, (tweet['id'],))
                    connection.commit()
                    continue

                # Если ответ "NO" - твит не прошел проверку качества
                if grok_response.upper() == "NO":
                    stats["rejected_tweets"] += 1
                    print("Твит не соответствует критериям ценности")
                else:
                    # Обрабатываем валидную категорию
                    category_name = grok_response.lower()

                    # Увеличиваем счетчик достойных твитов
                    stats["worthy_tweets"] += 1

                    # Обновляем статистику по категориям
                    if category_name in stats["categories"]:
                        stats["categories"][category_name] += 1
                    else:
                        stats["categories"][category_name] = 1

                    # Получаем category_id для категории
                    get_category_id_query = "SELECT category_id FROM categories WHERE category_name = %s"
                    cursor.execute(get_category_id_query, (category_name,))
                    category_result = cursor.fetchone()

                    if category_result:
                        category_id = category_result['category_id']
                        # Сохраняем результат в таблицу good_tweet, используя оригинальный текст твита для grok_text
                        insert_query = """
                                       INSERT INTO good_tweet (tweet_id, user_id, category_id, grok_text, url)
                                       VALUES (%s, %s, %s, %s, %s) \
                                       """
                        cursor.execute(insert_query,
                                       (tweet['id'], tweet['user_id'], category_id, tweet['tweet_text'], tweet['url']))
                        connection.commit()
                        print(f"Твит сохранен в good_tweet: {category_name}")
                    else:
                        print(f"Категория {category_name} не найдена в таблице categories")
            else:
                # Увеличиваем счетчик забракованных твитов
                stats["rejected_tweets"] += 1
                print(
                    f"Не удалось получить анализ от Grok API для твита {tweet['id']}, но твит помечен как проверенный")

            # Небольшая задержка между запросами
            time.sleep(1)

    except Error as e:
        print(f"Ошибка при обработке твитов: {e}")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

    return stats


def main():
    """
    Основная функция для запуска обработки твитов
    """
    print("=== Обработка твитов через Grok API ===")
    start_time = time.time()

    # Создаем таблицы
    if not create_tables():
        print("Не удалось создать таблицы")
        return

    # Запускаем обработку твитов и получаем статистику
    stats = process_tweets()

    # Вычисляем время работы
    execution_time = time.time() - start_time
    hours, remainder = divmod(execution_time, 3600)
    minutes, seconds = divmod(remainder, 60)
    time_str = ""
    if hours > 0:
        time_str += f"{int(hours)} ч "
    if minutes > 0:
        time_str += f"{int(minutes)} мин "
    time_str += f"{int(seconds)} сек"

    # Выводим статистику
    print("\n=== Статистика выполнения ===")
    print(f"Время работы: {time_str}")
    print(f"Всего обработано твитов: {stats['total_processed']}")
    print(f"Достойных твитов: {stats['worthy_tweets']}")
    print(f"Забракованных твитов: {stats['rejected_tweets']}")

    if stats["categories"]:
        print("\nРаспределение по категориям:")
        for category, count in stats["categories"].items():
            print(f"  - {category}: {count}")

    print("============================")
    print("Обработка завершена")


if __name__ == "__main__":
    main()