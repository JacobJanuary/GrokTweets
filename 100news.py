import MySQLdb
import MySQLdb.cursors
from openai import OpenAI
from dotenv import load_dotenv
import os
import datetime
import requests
import re
import time


# Функция для форматирования текста для Telegram
def format_for_telegram(text):
    """
    Форматирует текст новостей для лучшего отображения в Telegram
    используя HTML разметку и эмодзи.
    """
    if not text:
        return text

    # Заменяем любое Markdown-форматирование на HTML
    # Заменяем ** на <b> тег для жирного текста
    text = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', text)
    # Заменяем * на <i> тег для курсива
    text = re.sub(r'\*([^*]+)\*', r'<i>\1</i>', text)
    # Заменяем ` на <code> тег для кода
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)

    # Словарь эмодзи по типам новостей и контексту
    emojis = {
        # Общие категории
        "проверенные новости": "📢",
        "непроверенные новости": "❓",
        "инсайды, аналитика": "🔍",
        "технический анализ": "📊",
        "торговые идеи": "💰",
        "прогнозы": "🔮",
        "обучение": "📚",

        # Контекстные эмодзи
        "рост": "📈",
        "падение": "📉",
        "биткоин": "₿",
        "btc": "₿",
        "bitcoin": "₿",
        "ethereum": "Ξ",
        "eth": "Ξ",
        "партнерство": "🤝",
        "запуск": "🚀",
        "листинг": "📋",
        "регулирование": "⚖️",
        "взлом": "🔓",
        "безопасность": "🔒",
        "закон": "📜",
        "суд": "⚖️",
        "предупреждение": "⚠️",
        "опасность": "🚨",
        "инвестиции": "💵",
        "доход": "💸",
        "кошелек": "👛",
        "новая функция": "✨",
        "обновление": "🔄",
        "успех": "✅",
        "провал": "❌",
        "внимание": "👀",
        "важно": "‼️",
        "инновации": "💡",
        "платежи": "💳",
        "nft": "🖼️",
        "defi": "🏦",
        "майнинг": "⛏️",
        "staking": "🥩",
        "комиссия": "💲",
        "халвинг": "✂️",
        "токен": "🪙",
        "ликвидность": "💧",
        "волатильность": "🎢"
    }

    # Форматируем заголовки и секции
    # Основные секции (делаем их жирными)
    for section in ["Проверенные новости", "Непроверенные новости", "Инсайды, аналитика",
                    "Технический анализ, торговые идеи, прогнозы", "Обучение"]:
        if section in text:
            # Получаем подходящий эмодзи для секции
            section_emoji = ""
            for key, emoji in emojis.items():
                if key.lower() in section.lower():
                    section_emoji = emoji
                    break

            if not section_emoji and "технический" in section.lower():
                section_emoji = emojis["технический анализ"]

            # Заменяем секцию на форматированную версию
            formatted_section = f"\n<b>{section_emoji} {section}</b>\n"
            text = text.replace(f"- {section}:", formatted_section)
            text = text.replace(f"{section}:", formatted_section)

    # Обрабатываем структуру: превращаем каждый заголовок новости в жирный текст
    lines = text.split('\n')
    in_section = False
    for i in range(len(lines)):
        line = lines[i].strip()

        # Пропускаем пустые строки
        if not line:
            continue

        # Если это главный заголовок секции
        if line.startswith("<b>"):
            in_section = True
            continue

        # Если мы в секции и строка начинается с "- "
        if in_section and line.startswith("- "):
            # Убираем "- " и делаем текст жирным
            headline = line[2:].strip()

            # Добавляем контекстные эмодзи
            headline_emoji = ""
            for keyword, emoji in emojis.items():
                # Проверяем наличие ключевых слов в заголовке (независимо от регистра)
                if keyword.lower() in headline.lower():
                    headline_emoji += emoji + " "

            # Добавляем эмодзи в заголовок и форматируем жирным
            lines[i] = f"<b>{headline_emoji}{headline}</b>"

        # Форматируем ссылки: ищем URL в тексте и форматируем их
        if "http" in line:
            # Ищем URL с помощью регулярного выражения
            url_pattern = r'https?://[^\s]+'
            urls = re.findall(url_pattern, line)

            for url in urls:
                # Если URL не находится в конце строки, не форматируем его
                if line.strip().endswith(url):
                    # Получаем текст до URL
                    text_before_url = line[:line.rfind(url)].strip()
                    # Заменяем строку на текст и ссылку
                    lines[i] = f"{text_before_url}\n{url}"

    # Собираем текст обратно
    formatted_text = '\n'.join(lines)

    return formatted_text


# Функция для построения промта
def build_prompt(tweets_text, covered_news):
    prompt = """
    You receive a list of tweets from crypto industry experts.
    Each tweet is given as a pair: url, tweet_text.

    You also receive a list of news headlines that have already been covered today.

    Your task is to analyze the tweets, filter, summarize, and present only original, meaningful, market-relevant messages in Russian. Strictly follow these criteria:

    FILTERING:
    - DO NOT include any tweet if its content (the event, news, or main idea) matches or duplicates any news already covered today from the provided list.
    - EXCLUDE any tweet that:
        - Contains advertising, referral, or promotional material; calls to retweet, like, follow, join chats, giveaways, airdrops, quick profit promises, NFT/token launches, or similar.
        - Lacks concrete information — only expresses emotions, memes, greetings, thanks, off-topic chatter or reactions such as "to the moon!", "HODL", "soon", "big news coming", etc.
        - Is just a link, or a very brief clickbait/repetitive promotional comment, personal conversation, meme, or generic reaction (user mentions, gifs, inside jokes).
        - Is just a news headline, clickbait, or rhetorical question about a potential event/result without facts, clear analysis or new information (e.g., "Is Bitcoin about to rally?", "XRP through the roof?", "Will Ethereum collapse soon?", etc.).
        - Is only a repost or rephrasing of a media headline without meaningful details, specific facts, analysis, or context.
        - Does not deliver meaningful content: no new data, analysis, fact, forecast, educational or market-related value.
        - Duplicates the meaning of other tweets (merge similar news/events into a single entry).

    Include a tweet only if it contains at least ONE of the following:
    - Actual, market-moving news: launches, listings, hacks, partnerships, bans or permissions, regulatory decisions, major reports or lawsuits, policy changes, official investigations, etc.
    - Authoritative opinions or forecasts with specifics (well-reasoned, with data or context — not just "bullish!").
    - Market or fundamental analysis: stats, fund flows, trend analysis, institutional activity, liquidation levels, etc.
    - Technical analysis with explanation: levels, indicators, patterns, market signals — only if accompanied by reasoning (not just "BTC up!").
    - Important insider information confirmed by combining data or trustworthy sources.
    - Valuable educational content about crypto markets, tools, or strategies (guides, explanations, step-by-step instructions).

    OUTPUT STRUCTURE:
    (Output ONLY the sections that have at least one tweet for them. Do NOT show, mention, or write anything about empty sections.
    All section titles, headlines, and summaries must be in Russian only.)

    - Проверенные новости:
        - Заголовок (3-7 слов на русском языке)
        - Краткое раскрытие (1-2 коротких предложения на русском языке, не повторяют заголовок, после текста просто ссылку на оригинальный твит)
    - Непроверенные новости:
        - Заголовок (на русском)
        - Краткое описание сути и почему информация не подтверждена (на русском, после текста просто ссылку)
    - Инсайды, аналитика:
        - Заголовок (на русском)
        - Краткая суть аналитики или инсайда (на русском, после текста просто ссылку)
    - Технический анализ, торговые идеи, прогнозы:
        - Заголовок (на русском)
        - Краткое пояснение ситуации (на русском, после текста просто ссылку)
    - Обучение:
        - Заголовок (на русском)
        - Краткое описание обучающего материала (на русском, после текста просто ссылку)

    Additional requirements:
    - Headlines and summaries must not repeat (merge similar topics, combine into one summary per news item).
    - Each item must be unique and concise, with no duplication across sections.
    - Remove all "noise" — only add events, insights, analysis, education, or trade ideas with genuine value for the market.
    - The digest must be brief, clear, and practical for traders or investors.

    The entire output must be in Russian language only, including ALL headlines, section titles and summaries.
    Do NOT add any words like "Source" or anything before the link; just put the link after summary text.  
    Output only the digest in the specified structure and nothing else.

    Here is the list of tweets to analyze (each row: url, tweet_text):

    {tweets}

    Here is the list of already covered news headlines for today (do NOT include any stories related to these):

    {covered_news}
    """
    final_prompt = prompt.format(tweets=tweets_text, covered_news=covered_news)
    return final_prompt


# Функция для отправки сообщения в Telegram канал
def send_to_telegram(message, disable_preview=False):
    try:
        # Загрузка Telegram Bot API токена и идентификатора канала из переменных окружения
        telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        telegram_channel_id = os.getenv("TELEGRAM_CHANNEL_ID")

        # Проверка наличия переменных окружения
        if not telegram_bot_token or not telegram_channel_id:
            print("Ошибка: TELEGRAM_BOT_TOKEN или TELEGRAM_CHANNEL_ID не настроены в .env файле")
            return False

        # URL для Telegram Bot API
        telegram_api_url = f"https://api.telegram.org/bot{telegram_bot_token}/sendMessage"

        # Проверка на длину сообщения
        # Telegram имеет ограничение ~4096 символов на сообщение
        max_length = 4000  # Берем с запасом

        # Если сообщение слишком длинное, разбиваем его на части
        if len(message) > max_length:
            parts = []
            # Находим основной заголовок новостей, который будет только в первой части
            header_match = re.search(r'<b>🔥 Криптоновости [^<]+</b>', message)
            header = header_match.group(0) if header_match else ""

            # Убираем заголовок из текста для разбиения
            content = message.replace(header, "", 1) if header else message

            # Определяем точки разделения по секциям
            sections = re.split(r'(<b>[\W\w]+?</b>\n)', content)

            # Инициализируем первую часть с заголовком
            current_part = header + "\n\n" if header else ""

            for section in sections:
                # Если добавление новой секции превысит лимит
                if len(current_part) + len(section) > max_length:
                    # Добавляем текущую часть в список и начинаем новую
                    parts.append(current_part)
                    current_part = section
                else:
                    # Если нет, просто добавляем раздел к текущей части
                    current_part += section

            # Добавляем последнюю часть
            if current_part:
                parts.append(current_part)

            # Отправляем каждую часть отдельно
            success = True
            for i, part in enumerate(parts):
                # К первой части добавляем номер, если частей больше одной
                message_header = ""
                if len(parts) > 1:
                    message_header = f"<b>Часть {i + 1}/{len(parts)}</b>\n\n"

                # Данные для отправки
                data = {
                    "chat_id": telegram_channel_id,
                    "text": message_header + part,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": disable_preview
                }

                # Отправка запроса к Telegram API
                response = requests.post(telegram_api_url, data=data)

                # Проверка статуса ответа
                if response.status_code != 200:
                    print(f"Ошибка при отправке части {i + 1}/{len(parts)} в Telegram: {response.text}")
                    success = False

                # Небольшая задержка между отправками частей (если нужно)
                if i < len(parts) - 1:
                    time.sleep(1)

            if success:
                print(f"Сообщение успешно отправлено в Telegram канал ({len(parts)} частей)")

            return success
        else:
            # Если сообщение не превышает лимит, отправляем как обычно
            data = {
                "chat_id": telegram_channel_id,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": disable_preview
            }

            # Отправка запроса к Telegram API
            response = requests.post(telegram_api_url, data=data)

            # Проверка статуса ответа
            if response.status_code == 200:
                print("Сообщение успешно отправлено в Telegram канал")
                return True
            else:
                print(f"Ошибка при отправке в Telegram: {response.text}")
                return False

    except Exception as e:
        print(f"Ошибка при отправке в Telegram: {str(e)}")
        return False


# Загрузка переменных окружения
load_dotenv()

# Загрузка API ключа
API_KEY = os.getenv("GROK_API_KEY")

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
conn = MySQLdb.connect(**DB_CONFIG)
cursor = conn.cursor()

# Получение предыдущих сводок новостей за последние 24 часа
one_day_ago = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
cursor.execute("SELECT `text_news` FROM `grok_news` WHERE `news_time` >= %s ORDER BY `news_time` DESC", (one_day_ago,))
previous_news = cursor.fetchall()

# Формирование строки с предыдущими сводками
previous_summaries = ""
for i, news in enumerate(previous_news, 1):
    previous_summaries += f"=== Previous Summary {i} ===\n{news['text_news']}\n\n"

# Извлечение 20 самых ранних твитов из базы данных, где checked не равно true (ASC сортировка по id)
cursor.execute(
    """
    SELECT `id`, `tweet_text`, `url`
    FROM `tweets`
    WHERE `isChecked` IS NOT TRUE
      AND LENGTH(`tweet_text`) >= 25
      AND `created_at` >= NOW() - INTERVAL 24 HOUR
    ORDER BY `tweets`.`id` DESC
        LIMIT 20;
    """)
tweets = cursor.fetchall()

# Проверяем, если запрос вернул менее 20 записей, то завершаем скрипт
if len(tweets) < 20:
    print(f"Получено только {len(tweets)} твитов, что меньше требуемых 20. Скрипт завершается.")
    cursor.close()
    conn.close()
    exit(0)

# Сохраняем ID твитов для последующего обновления поля checked
tweet_ids = [tweet['id'] for tweet in tweets]

# Форматирование твитов в строку
tweets_text = ""

print("\n=== ТВИТЫ ДЛЯ ПРОМПТА ===\n")

for i, tweet in enumerate(tweets, 1):

    # Формируем строку для промпта
    tweets_text += f"--- Tweet {i} ---\nText: {tweet['tweet_text']}\nURL: {tweet['url']}\n\n"

print("\n=== КОНЕЦ СПИСКА ТВИТОВ ===\n")

# Настройка клиента OpenAI для API Grok
client = OpenAI(
    api_key=API_KEY,
    base_url="https://api.x.ai/v1",
)

# Формирование запроса для Grok
messages = [
    {"role": "system", "content": "You are an expert crypto market analyst specializing in filtering and summarizing critical news, insights, and trading signals. Your task is to carefully analyze tweets from top influencers and produce only concise, high-impact, market-relevant information with perfect clarity and accuracy, in Russian."},
    {"role": "user", "content": build_prompt(tweets_text, previous_summaries)},
]

# Отправка запроса к API Grok с температурой 0
completion = client.chat.completions.create(
    model="grok-3-latest",
    messages=messages,
    temperature=0
)

# Получение ответа от Grok
response = completion.choices[0].message.content

# Получение текущей даты и времени
current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

# Вставка ответа в таблицу grok_news
try:
    # Вставляем ответ Grok в таблицу grok_news
    insert_query = "INSERT INTO `grok_news` (`text_news`, `news_time`) VALUES (%s, %s)"
    cursor.execute(insert_query, (response, current_time))

    # Обновляем поле checked=true для всех твитов, которые отправили в Grok
    if tweet_ids:
        update_query = "UPDATE `tweets` SET `isChecked` = TRUE WHERE `id` IN ({})".format(
            ', '.join(['%s'] * len(tweet_ids)))
        cursor.execute(update_query, tweet_ids)

    conn.commit()
    print(f"Ответ успешно сохранен в базе данных с timestamp: {current_time}")
    print(f"Помечено {len(tweet_ids)} твитов как проверенные (checked=true)")

    # Отправляем новости в Telegram канал
    if response and len(response.strip()) > 0:
        # Форматируем дату для сообщения
        formatted_date = datetime.datetime.now().strftime('%d.%m.%Y %H:%M')
        # Форматируем текст для Telegram с эмодзи и разметкой
        formatted_response = format_for_telegram(response)
        # Добавляем дату к началу сообщения
        telegram_message = f"<b>🔥 Криптоновости {formatted_date}</b>\n\n{formatted_response}"
        # Отправляем сообщение в Telegram
        send_to_telegram(telegram_message)
    else:
        print("Ответ от Grok пуст, сообщение в Telegram не отправлено")

except Exception as e:
    conn.rollback()
    print(f"Ошибка при сохранении в базу данных: {str(e)}")

# Вывод результата для проверки
print("Ответ Grok:")
print(response)

# Закрытие подключения к базе данных
cursor.close()
conn.close()