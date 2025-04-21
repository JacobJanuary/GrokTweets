import requests
import os
from dotenv import load_dotenv

load_dotenv()


def test_telegram():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHANNEL_ID")

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": "Тестовое сообщение. Настройка завершена успешно!"
    }

    response = requests.post(url, data=data)
    print(response.json())


test_telegram()