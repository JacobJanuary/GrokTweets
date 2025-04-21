import MySQLdb
import MySQLdb.cursors
from dotenv import load_dotenv
import os
import datetime
import math

# Загрузка переменных окружения
load_dotenv()

# Загрузка параметров подключения к БД
DB_CONFIG = {
    'host': os.getenv("DB_HOST"),
    'db': os.getenv("DB_NAME"),
    'user': os.getenv("DB_USER"),
    'passwd': os.getenv("DB_PASSWORD"),
    'port': int(os.getenv("DB_PORT")),
    'cursorclass': MySQLdb.cursors.DictCursor
}

# Подключение к базе данных MySQL
try:
    conn = MySQLdb.connect(**DB_CONFIG)
    cursor = conn.cursor()
    
    # Выполнение запроса
    cursor.execute("SELECT `id`, `tweet_text`, `original_tweet_text`, `url` FROM `tweets` WHERE `bad`")
    all_tweets = cursor.fetchall()
    
    # Расчет количества файлов
    tweets_per_file = 500
    total_tweets = len(all_tweets)
    num_files = math.ceil(total_tweets / tweets_per_file)
    
    print(f"Найдено всего {total_tweets} 'плохих' твитов")
    print(f"Будет создано {num_files} файлов по {tweets_per_file} твитов в каждом")
    
    # Текущее время для имен файлов
    current_time = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    
    # Разбивка на файлы
    for file_index in range(num_files):
        start_idx = file_index * tweets_per_file
        end_idx = min((file_index + 1) * tweets_per_file, total_tweets)
        tweets_chunk = all_tweets[start_idx:end_idx]
        
        # Генерация имени файла с номером части
        filename = f"bad_tweets_{current_time}_part{file_index+1}.txt"
        
        # Запись результатов в файл
        with open(filename, 'w', encoding='utf-8') as file:
            for tweet in tweets_chunk:
                file.write(f"- {tweet['id']}\n")
                file.write(f"- {tweet['url']}\n")
                
                # Используем original_tweet_text если доступен, иначе tweet_text
                tweet_text = tweet['original_tweet_text'] if tweet['original_tweet_text'] else tweet['tweet_text']
                file.write(f"- {tweet_text}\n")
                
                file.write("\n" + "-" * 50 + "\n\n")  # разделитель между записями
        
        print(f"Создан файл {filename} с {len(tweets_chunk)} твитами")

except Exception as e:
    print(f"Ошибка: {str(e)}")

finally:
    # Закрытие подключения к базе данных
    if 'cursor' in locals() and cursor:
        cursor.close()
    if 'conn' in locals() and conn:
        conn.close()