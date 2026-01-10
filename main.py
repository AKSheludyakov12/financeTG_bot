import re
import telebot
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import os

TOKEN = os.getenv("BOT_TOKEN")
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS")

bot = telebot.TeleBot("8505854707:AAE31hekBEsjcO0QlnfmW8HA_VQ8SMtjJ8U")

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]


creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)
print("Доступные таблицы:")
try:
    spreadsheets = client.list_spreadsheet_files()
    for s in spreadsheets:
        print(f"- {s['name']}")
except Exception as e:
    print("Нет доступа:", e)
    exit()

sheet = client.open("finance_analys").worksheet("unload_TG")


@bot.message_handler(content_types=["text"])
def handle_message(message):
    text = message.text.strip()

    if re.search(r"[а-яёА-ЯЁa-z]+\s*\d+", text):
        # РАЗДЕЛЯЕМ на текст и число
        parts = re.split(r"\s+", text, 1)
        product = parts[0]
        amount = int(parts[1])

        data = [text, product, amount, datetime.now().strftime("%d.%m.%Y")]
        sheet.append_row(data)
        bot.reply_to(message, f"✅ {product}: {amount}")
    else:
        bot.reply_to(message, "❌ Формат: кофе 500")


bot.polling(none_stop=True)
