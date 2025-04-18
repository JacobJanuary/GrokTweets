import MySQLdb
import MySQLdb.cursors
from openai import OpenAI
from dotenv import load_dotenv
import os
import datetime


# Функция для построения промта
def build_prompt(tweets_text):
    prompt = (
        "Carefully analyze the following list of tweets from the top 100 influencers. Each tweet may contain:\n"
        "- Important news\n"
        "- Exclusive insider information or rumors\n"
        "- Technical analysis of markets, charts, or assets\n"
        "- In-depth reviews or analysis of projects\n"
        "- Other significant insights or information relevant for market participants\n"
        "Each tweet includes a link to the original post.\n\n"
        "Your tasks:\n"
        "1. Identify and group together tweets that convey the same or similar news, insights, analyses, or reviews (even if phrased differently).\n"
        "2. Extract unique, key items — this includes major news, fresh insider information, technical analyses that have drawn notable public attention, and high-quality reviews or breakdowns of important projects and markets. Only include those confirmed by several independent tweets/sources or that have generated strong community engagement.\n"
        "3. Before including any story or news item in the summary, attempt to verify its actuality and credibility by searching for confirmation or coverage from reputable sources on the internet. If it cannot be confirmed, either omit it or clearly mark it as unverified in the summary.\n"
        "4. Ignore trivial, redundant, personal, promotional, meaningless, humorous, or fragmented tweets — do not include any that do not add real value for market analysis.\n"
        "5. For each main item, provide a concise one-line headline (in Russian), a brief summary or explanation (1–2 sentences max, in Russian if needed), and include links to the 1–3 most informative original tweets on the topic.\n"
        "6. The final summary should consist of no more than 5–10 main points (covering significant news, insights, technical analyses, and reviews). Group less important or secondary issues under a general 'Other' section. Omit tweets that do not contribute independently valuable information.\n"
        "7. The final summary should make the main events, stories, and analytical insights clear to someone who has not read the tweets.\n\n"
        "Strictly follow this structure for each point:\n"
        "— Number\n"
        "— Concise headline (in Russian)\n"
        "— (1–2 sentence explanation in Russian, if needed)\n"
        "— Link(s) to the best tweet(s) on this topic\n\n"
        "Always write the whole summary strictly in clear, succinct, business-like Russian (do not use English in the output). Focus on content important and useful for market participants and investors; avoid redundancy, repetition, or wording that does not add value.\n\n"
        f"Here is the list of tweets:\n\n{tweets_text}\n"
    )
    return prompt


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

# Извлечение 20 самых ранних твитов из базы данных, где checked не равно true (ASC сортировка по id)
cursor.execute(
    "SELECT `id`, `grok_text`, `url` FROM `good_tweet` WHERE `checked` IS NOT TRUE ORDER BY `id` ASC LIMIT 20")
tweets = cursor.fetchall()

# Сохраняем ID твитов для последующего обновления поля checked
tweet_ids = [tweet['id'] for tweet in tweets]

# Форматирование твитов в строку
tweets_text = ""
for i, tweet in enumerate(tweets, 1):
    tweets_text += f"--- Tweet {i} ---\nText: {tweet['grok_text']}\nURL: {tweet['url']}\n\n"

# Настройка клиента OpenAI для API Grok
client = OpenAI(
    api_key=API_KEY,
    base_url="https://api.x.ai/v1",
)

# Формирование запроса для Grok
messages = [
    {"role": "system",
     "content": "You are Grok, a chatbot created by xAI. Your task is to analyze tweets from top influencers and extract only high-impact information with maximum precision and clarity."},
    {"role": "user", "content": build_prompt(tweets_text)},
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
        update_query = "UPDATE `good_tweet` SET `checked` = TRUE WHERE `id` IN ({})".format(
            ', '.join(['%s'] * len(tweet_ids)))
        cursor.execute(update_query, tweet_ids)

    conn.commit()
    print(f"Ответ успешно сохранен в базе данных с timestamp: {current_time}")
    print(f"Помечено {len(tweet_ids)} твитов как проверенные (checked=true)")
except Exception as e:
    conn.rollback()
    print(f"Ошибка при сохранении в базу данных: {str(e)}")

# Вывод результата для проверки
print("Ответ Grok:")
print(response)

# Закрытие подключения к базе данных
cursor.close()
conn.close()