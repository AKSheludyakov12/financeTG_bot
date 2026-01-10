from flask import Flask, request
import telebot
import gspread
import json
import re
import os
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

app = Flask(__name__)

TOKEN = os.getenv("BOT_TOKEN")
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS")

bot = telebot.TeleBot(TOKEN)

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]
creds = ServiceAccountCredentials.from_json_keyfile_dict(
    json.loads(GOOGLE_CREDENTIALS), scope
)
client = gspread.authorize(creds)
sheet = client.open("finance_analys").worksheet("unload_TG")


@bot.message_handler(content_types=["text"])
def handle_message(message):
    text = message.text.strip()
    if re.search(r"[а-яёА-ЯЁa-z]+\s*\d+", text):
        parts = re.split(r"\s+", text, 1)
        product, amount = parts[0], parts[1]
        data = [text, product, amount, datetime.now().strftime("%d.%m.%Y")]
        sheet.append_row(data)
        bot.reply_to(message, f"✅ {product}: {amount}")
    else:
        bot.reply_to(message, "❌ Формат: кофе 500")


@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    if request.headers.get("content-type") == "application/json":
        json_string = request.get_data().decode("utf-8")
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ""
    return "OK!"


@app.route("/")
def home():
    return "Bot is running!"


if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=f"https://financetg-bot.onrender.com/{TOKEN}")
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
