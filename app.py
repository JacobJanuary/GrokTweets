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
app.config['TWITTER_IMAGES_PATH'] = '/Users/evgeniyyanvarskiy/PycharmProjects/twitter/'
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

    # Получаем всех авторов для выпадающего списка
    cur.execute("""
    SELECT 
        u.username, COUNT(gt.id) as tweet_count 
    FROM 
        users u 
    JOIN 
        good_tweet gt ON u.id = gt.user_id 
    GROUP BY 
        u.username 
    ORDER BY 
        u.username ASC
    """)
    all_authors = cur.fetchall()

    # Количество твитов на странице
    per_page = 50
    offset = (page - 1) * per_page

    # Формируем базовый запрос с возможностью фильтрации
    query_base = """
    FROM 
        good_tweet gt
    LEFT JOIN 
        categories c ON gt.category_id = c.category_id
    LEFT JOIN 
        users u ON gt.user_id = u.id
    LEFT JOIN 
        tweets t ON gt.tweet_id = t.id
    """

    # Создаем список для условий WHERE и параметров
    where_conditions = []
    query_params = []

    # Добавляем условие фильтрации по категориям, если они выбраны
    if selected_categories:
        where_conditions.append("gt.category_id IN ({})".format(
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
    query = """
    SELECT 
        gt.id, 
        gt.grok_text, 
        gt.url as tweet_url, 
        gt.category_id,
        c.category_name,
        gt.user_id, 
        u.username, 
        u.name as user_name,
        t.id as tweet_id_num, 
        t.tweet_id, 
        t.created_at, 
        t.likes, 
        t.retweets, 
        t.replies, 
        t.is_retweet, 
        t.original_author,
        t.tweet_text
    """ + query_base + " " + query_where + """
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
        # Проверяем все возможные идентификаторы
        tweet_identifiers = []

        # Добавляем доступные идентификаторы для поиска
        if tweet.get('tweet_id_num'):
            tweet_identifiers.append(tweet['tweet_id_num'])
        if tweet.get('tweet_id'):
            tweet_identifiers.append(tweet['tweet_id'])
        if tweet.get('id'):
            tweet_identifiers.append(tweet['id'])

        # Если нет идентификаторов, пропускаем
        if not tweet_identifiers:
            tweet['images'] = []
            continue

        # Формируем условие IN для поиска по всем идентификаторам
        placeholders = ','.join(['%s'] * len(tweet_identifiers))

        image_query = f"""
        SELECT 
            local_path, 
            image_url, 
            isChart
        FROM 
            images
        WHERE 
            tweet_id IN ({placeholders})
        LIMIT 5
        """

        cur.execute(image_query, tweet_identifiers)
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
                           replies_to=replies_to)


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


if __name__ == '__main__':
    # Создаем папки для статических файлов если их нет
    os.makedirs('static/css', exist_ok=True)
    os.makedirs('static/js', exist_ok=True)

    app.run(debug=True)