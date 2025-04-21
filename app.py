import os
import logging
from flask import Flask, render_template, url_for, redirect, send_from_directory, request, jsonify
import MySQLdb
import MySQLdb.cursors
from flask_mysqldb import MySQL
from dotenv import load_dotenv

# Загрузка переменных окружения из .env файла
load_dotenv()

app = Flask(__name__)

# Настройка логирования
app.logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setLevel(logging.INFO)
app.logger.addHandler(handler)

# Конфигурация MySQL
app.config['MYSQL_HOST'] = os.getenv('DB_HOST')
app.config['MYSQL_USER'] = os.getenv('DB_USER')
app.config['MYSQL_PASSWORD'] = os.getenv('DB_PASSWORD')
app.config['MYSQL_DB'] = os.getenv('DB_NAME')
app.config['MYSQL_PORT'] = int(os.getenv('DB_PORT', 3306))
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

# Инициализация MySQL
mysql = MySQL(app)

# Настройка путей для медиафайлов
app.config['TWITTER_IMAGES_PATH'] = '/Users/evgeniyyanvarskiy/Downloads/'
app.logger.info(f"Базовый путь для изображений: {app.config['TWITTER_IMAGES_PATH']}")


# Настройка статических файлов
@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)


# Маршрут для обслуживания изображений Twitter
@app.route('/twitter_images/<path:filename>')
def serve_twitter_image(filename):
    # Убираем дублирование папки twitter_images в пути, если оно есть
    if filename.startswith('twitter_images/'):
        # Путь изображения уже содержит twitter_images в начале, не добавляем его снова
        clean_path = filename
    else:
        # Добавляем twitter_images/ в начало пути только если его там нет
        clean_path = f"twitter_images/{filename}"

    # Полный путь к файлу на диске
    full_path = os.path.join(app.config['TWITTER_IMAGES_PATH'], clean_path)

    app.logger.info(f"Запрошен файл: {filename}, полный путь: {full_path}")

    # Проверка наличия файла
    if os.path.exists(full_path) and os.path.isfile(full_path):
        directory = os.path.dirname(full_path)
        file_name = os.path.basename(full_path)
        # Добавляем заголовок кеширования, чтобы избежать проблем с 304
        response = send_from_directory(directory, file_name)
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    else:
        app.logger.error(f"Файл не найден: {full_path}")
        return f"Файл не найден: {filename}", 404


@app.route('/')
@app.route('/page/<int:page>')
def index(page=1):
    # Получаем параметры фильтрации
    selected_categories = request.args.getlist('category')
    author_filter = request.args.get('author', '')

    # Получаем параметры фильтрации по дате
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    # Получаем параметры фильтрации по метрикам
    likes_from = request.args.get('likes_from', '')
    likes_to = request.args.get('likes_to', '')
    retweets_from = request.args.get('retweets_from', '')
    retweets_to = request.args.get('retweets_to', '')
    replies_from = request.args.get('replies_from', '')
    replies_to = request.args.get('replies_to', '')

    # Получаем все категории для фильтров
    cur = mysql.connection.cursor()
    cur.execute("SELECT category_id, category_name FROM categories ORDER BY category_name")
    all_categories = cur.fetchall()

    # Получаем всех авторов для выпадающего списка с данными из tweets вместо good_tweet
    cur.execute("""
                SELECT u.username,
                       COUNT(t.id) as tweet_count
                FROM users u
                         JOIN
                     tweets t ON u.id = t.user_id
                GROUP BY u.username
                ORDER BY u.username ASC
                """)
    all_authors = cur.fetchall()

    # Количество твитов на странице
    per_page = 50
    offset = (page - 1) * per_page

    # Формируем базовый запрос с возможностью фильтрации, используя только таблицу tweets
    # Проверяем структуру таблицы tweets, чтобы узнать, есть ли определенные столбцы
    # Проверка столбца category_id
    cur.execute("""
                SELECT COLUMN_NAME
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'tweets'
                  AND COLUMN_NAME = 'category_id'
                """)
    has_category_id = cur.fetchone() is not None

    # Проверка столбца tweet_text
    cur.execute("""
                SELECT COLUMN_NAME
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'tweets'
                  AND COLUMN_NAME = 'tweet_text'
                """)
    has_tweet_text = cur.fetchone() is not None

    # Проверка столбца original_tweet_text
    cur.execute("""
                SELECT COLUMN_NAME
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'tweets'
                  AND COLUMN_NAME = 'original_tweet_text'
                """)
    has_original_tweet_text = cur.fetchone() is not None

    # Проверка столбцов good и bad
    cur.execute("""
                SELECT COLUMN_NAME
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'tweets'
                  AND COLUMN_NAME IN ('good', 'bad')
                """)
    voting_columns = cur.fetchall()
    has_voting = len(voting_columns) > 0

    # Создаем запрос в зависимости от наличия столбца category_id
    if has_category_id:
        query_base = """
        FROM 
            tweets t
        LEFT JOIN 
            categories c ON t.category_id = c.category_id
        LEFT JOIN 
            users u ON t.user_id = u.id
        """
    else:
        # Если столбца category_id нет, то не делаем JOIN с таблицей categories
        query_base = """
        FROM 
            tweets t
        LEFT JOIN 
            users u ON t.user_id = u.id
        """

    # Создаем список для условий WHERE и параметров
    where_conditions = []
    query_params = []

    # ===== НАЧАЛО ФИЛЬТРАЦИИ ПО ORIGINAL_TWEET_TEXT =====
    # Добавляем условие для фильтрации твитов, где original_tweet_text равен NULL
    # Чтобы вернуть все твиты, просто удалите или закомментируйте эту строку
    if has_original_tweet_text:
        where_conditions.append("t.original_tweet_text IS NOT NULL")
    # ===== КОНЕЦ ФИЛЬТРАЦИИ ПО ORIGINAL_TWEET_TEXT =====

    # Добавляем условие фильтрации по категориям, если они выбраны
    if selected_categories:
        where_conditions.append("t.category_id IN ({})".format(
            ','.join(['%s'] * len(selected_categories))
        ))
        query_params.extend(selected_categories)

    # Добавляем условие фильтрации по автору, если указан
    if author_filter:
        where_conditions.append("u.username = %s")
        query_params.append(author_filter)

    # Добавляем условие фильтрации по дате
    if date_from:
        where_conditions.append("t.inserted_at >= %s")
        query_params.append(date_from)

    if date_to:
        where_conditions.append("t.inserted_at <= %s")
        query_params.append(date_to)

    # Добавляем условия фильтрации по метрикам
    if likes_from:
        where_conditions.append("t.likes >= %s")
        query_params.append(int(likes_from))

    if likes_to:
        where_conditions.append("t.likes <= %s")
        query_params.append(int(likes_to))

    if retweets_from:
        where_conditions.append("t.retweets >= %s")
        query_params.append(int(retweets_from))

    if retweets_to:
        where_conditions.append("t.retweets <= %s")
        query_params.append(int(retweets_to))

    if replies_from:
        where_conditions.append("t.replies >= %s")
        query_params.append(int(replies_from))

    if replies_to:
        where_conditions.append("t.replies <= %s")
        query_params.append(int(replies_to))

    # Формируем финальное условие WHERE
    query_where = ""
    if where_conditions:
        query_where = "WHERE " + " AND ".join(where_conditions)

    # Получаем общее количество твитов
    count_query = "SELECT COUNT(*) as total " + query_base + " " + query_where

    cur.execute(count_query, query_params)
    total_tweets = cur.fetchone()['total']

    # Вычисляем общее количество страниц
    total_pages = max(1, (total_tweets + per_page - 1) // per_page)

    # Корректируем текущую страницу, если она вышла за пределы
    page = min(page, total_pages)

    # Получаем твиты для текущей страницы
    # Составляем базовую часть SELECT запроса
    select_base = """
        t.id as tweet_id_num, 
        t.tweet_id, 
        t.created_at, 
        t.likes, 
        t.retweets, 
        t.replies, 
        t.is_retweet, 
        t.original_author,
        t.url as tweet_url,
        t.user_id, 
        u.username, 
        u.name as user_name
    """

    # Добавляем tweet_text, если он есть
    if has_tweet_text:
        select_base += ", t.tweet_text"

    # Добавляем original_tweet_text, если он есть
    if has_original_tweet_text:
        select_base += ", t.original_tweet_text"

    # Добавляем category_id и category_name, если есть category_id
    if has_category_id:
        select_base += ", t.category_id, c.category_name"

    # Добавляем поля good и bad для голосования, если они есть
    if has_voting:
        select_base += ", t.good, t.bad"

    # Формируем итоговый запрос
    query = "SELECT " + select_base + " " + query_base + " " + query_where + """
    ORDER BY 
        t.created_at DESC
    LIMIT %s OFFSET %s
    """

    # Добавляем параметры для LIMIT и OFFSET
    query_params.extend([per_page, offset])

    # Выполняем запрос с параметрами фильтрации и пагинации
    cur.execute(query, query_params)
    tweets = cur.fetchall()

    # Для каждого твита получаем связанные изображения
    for tweet in tweets:
        # Проверяем идентификатор твита
        tweet_id = tweet.get('tweet_id_num')

        # Если нет идентификатора, пропускаем
        if not tweet_id:
            tweet['images'] = []
            continue

        # Запрос для получения изображений
        image_query = """
                      SELECT local_path, \
                             image_url, \
                             isChart
                      FROM images
                      WHERE tweet_id = %s LIMIT 5 \
                      """

        cur.execute(image_query, (tweet_id,))
        images = cur.fetchall()

        # Обрабатываем пути к изображениям
        for image in images:
            if image['local_path']:
                # Используем только локальный путь из базы данных
                image['file_path'] = image['local_path']
            else:
                image['file_path'] = None

        tweet['images'] = images

    cur.close()

    return render_template('index.html',
                           tweets=tweets,
                           current_page=page,
                           total_pages=total_pages,
                           total_tweets=total_tweets,
                           all_categories=all_categories,
                           selected_categories=selected_categories,
                           author_filter=author_filter,
                           all_authors=all_authors,
                           date_from=date_from,
                           date_to=date_to,
                           likes_from=likes_from,
                           likes_to=likes_to,
                           retweets_from=retweets_from,
                           retweets_to=retweets_to,
                           replies_from=replies_from,
                           replies_to=replies_to,
                           has_category_id=has_category_id,
                           has_tweet_text=has_tweet_text,
                           has_voting=has_voting,
                           has_original_tweet_text=has_original_tweet_text)


@app.route('/api/vote', methods=['POST'])
def vote():
    try:
        data = request.get_json()
        tweet_id = data.get('tweet_id')
        vote_type = data.get('vote_type')

        if not tweet_id or vote_type not in ['good', 'bad']:
            return jsonify({"success": False, "message": "Некорректные данные"}), 400

        cur = mysql.connection.cursor()

        # Проверяем существование колонок good и bad в таблице tweets
        try:
            if vote_type == 'good':
                cur.execute("UPDATE tweets SET good = TRUE WHERE id = %s", (tweet_id,))
            else:
                cur.execute("UPDATE tweets SET bad = TRUE WHERE id = %s", (tweet_id,))

            mysql.connection.commit()
            app.logger.info(f"Голосование успешно: {vote_type} для твита {tweet_id}")
            cur.close()

            return jsonify({"success": True, "message": f"Голос '{vote_type}' успешно учтен!"}), 200
        except MySQLdb.Error as sql_error:
            app.logger.error(f"SQL ошибка при голосовании: {str(sql_error)}")
            # Если колонок нет, добавляем их
            if "Unknown column" in str(sql_error):
                try:
                    cur.execute("ALTER TABLE tweets ADD COLUMN good BOOLEAN DEFAULT FALSE")
                    cur.execute("ALTER TABLE tweets ADD COLUMN bad BOOLEAN DEFAULT FALSE")
                    mysql.connection.commit()

                    # Пробуем снова после добавления колонок
                    if vote_type == 'good':
                        cur.execute("UPDATE tweets SET good = TRUE WHERE id = %s", (tweet_id,))
                    else:
                        cur.execute("UPDATE tweets SET bad = TRUE WHERE id = %s", (tweet_id,))

                    mysql.connection.commit()
                    app.logger.info(f"Колонки добавлены и голосование успешно: {vote_type} для твита {tweet_id}")
                    return jsonify({"success": True, "message": f"Голос '{vote_type}' успешно учтен!"}), 200
                except Exception as alter_error:
                    app.logger.error(f"Ошибка при добавлении колонок: {str(alter_error)}")
                    return jsonify(
                        {"success": False, "message": "Не удалось добавить необходимые колонки в базу данных"}), 500
            else:
                return jsonify({"success": False, "message": f"SQL ошибка: {str(sql_error)}"}), 500

    except Exception as e:
        app.logger.error(f"Ошибка при голосовании: {str(e)}")
        return jsonify({"success": False, "message": "Произошла ошибка при голосовании"}), 500

@app.route('/translated')
@app.route('/translated/page/<int:page>')
def translated_tweets(page=1):
    # Количество твитов на странице
    per_page = 50
    offset = (page - 1) * per_page

    # Создаем подключение к базе данных
    cur = mysql.connection.cursor()

    # Проверка наличия столбца original_tweet_text
    cur.execute("""
                SELECT COLUMN_NAME
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'tweets'
                  AND COLUMN_NAME = 'original_tweet_text'
                """)
    has_original_tweet_text = cur.fetchone() is not None

    # Если столбца original_tweet_text нет, вернем сообщение об ошибке
    if not has_original_tweet_text:
        return render_template('error.html', message="Столбец original_tweet_text не найден в таблице tweets"), 404

    # Проверка столбца category_id
    cur.execute("""
                SELECT COLUMN_NAME
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'tweets'
                  AND COLUMN_NAME = 'category_id'
                """)
    has_category_id = cur.fetchone() is not None

    # Проверка столбцов good и bad
    cur.execute("""
                SELECT COLUMN_NAME
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'tweets'
                  AND COLUMN_NAME IN ('good', 'bad')
                """)
    voting_columns = cur.fetchall()
    has_voting = len(voting_columns) > 0

    # Базовый запрос с обязательным условием для original_tweet_text
    # Изменено условие: теперь мы проверяем, что original_tweet_text не NULL 
    # и не пустая строка, но также разрешаем показать дополнительно пустые строки
    if has_category_id:
        query_base = """
        FROM 
            tweets t
        LEFT JOIN 
            categories c ON t.category_id = c.category_id
        LEFT JOIN 
            users u ON t.user_id = u.id
        WHERE 
            t.original_tweet_text IS NOT NULL
        """
    else:
        query_base = """
        FROM 
            tweets t
        LEFT JOIN 
            users u ON t.user_id = u.id
        WHERE 
            t.original_tweet_text IS NOT NULL
        """

    # Получаем общее количество твитов с переводом
    count_query = "SELECT COUNT(*) as total " + query_base
    cur.execute(count_query)
    total_tweets = cur.fetchone()['total']

    # Если твитов нет, показываем сообщение о пустом результате
    if total_tweets == 0:
        cur.close()
        return render_template('index.html', 
                              tweets=[],
                              current_page=1,
                              total_pages=1,
                              total_tweets=0,
                              has_category_id=has_category_id,
                              has_tweet_text=True,
                              has_voting=has_voting,
                              has_original_tweet_text=has_original_tweet_text,
                              page_title="Переведенные твиты",
                              message="Нет переведенных твитов. Поле original_tweet_text пусто для всех записей.")

    # Вычисляем общее количество страниц
    total_pages = max(1, (total_tweets + per_page - 1) // per_page)

    # Корректируем текущую страницу, если она вышла за пределы
    page = min(page, total_pages)

    # Составляем базовую часть SELECT запроса
    select_base = """
        t.id as tweet_id_num, 
        t.tweet_id, 
        t.created_at, 
        t.likes, 
        t.retweets, 
        t.replies, 
        t.is_retweet, 
        t.original_author,
        t.url as tweet_url,
        t.user_id, 
        u.username, 
        u.name as user_name
    """

    # Добавляем tweet_text и original_tweet_text
    select_base += ", t.tweet_text"

    # При выводе используем COALESCE чтобы показать original_tweet_text если он есть, иначе tweet_text
    select_base += ", t.original_tweet_text"

    # Добавляем category_id и category_name, если есть category_id
    if has_category_id:
        select_base += ", t.category_id, c.category_name"

    # Добавляем поля good и bad для голосования, если они есть
    if has_voting:
        select_base += ", t.good, t.bad"

    # Формируем итоговый запрос
    query = "SELECT " + select_base + " " + query_base + """
    ORDER BY 
        t.created_at DESC
    LIMIT %s OFFSET %s
    """

    # Выполняем запрос с параметрами для пагинации
    cur.execute(query, (per_page, offset))
    tweets = cur.fetchall()

    # Для каждого твита получаем связанные изображения
    for tweet in tweets:
        tweet_id = tweet.get('tweet_id_num')

        if not tweet_id:
            tweet['images'] = []
            continue

        # Запрос для получения изображений
        image_query = """
                      SELECT local_path, \
                             image_url, \
                             isChart
                      FROM images
                      WHERE tweet_id = %s LIMIT 5 \
                      """

        cur.execute(image_query, (tweet_id,))
        images = cur.fetchall()

        # Обрабатываем пути к изображениям
        for image in images:
            if image['local_path']:
                image['file_path'] = image['local_path']
            else:
                image['file_path'] = None

        tweet['images'] = images

    cur.close()

    return render_template('index.html',
                           tweets=tweets,
                           current_page=page,
                           total_pages=total_pages,
                           total_tweets=total_tweets,
                           has_category_id=has_category_id,
                           has_tweet_text=True,
                           has_voting=has_voting,
                           has_original_tweet_text=has_original_tweet_text,
                           page_title="Переведенные твиты")

if __name__ == '__main__':
    # Создаем папки для статических файлов если их нет
    os.makedirs('static/css', exist_ok=True)
    os.makedirs('static/js', exist_ok=True)

    app.run(debug=True)