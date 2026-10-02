from flask import Flask, request, jsonify
import telebot
import gspread
import json
import os
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import re

app = Flask(__name__)

TOKEN = os.getenv("BOT_TOKEN")
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS")

# Google Sheets
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]
creds = ServiceAccountCredentials.from_json_keyfile_dict(
    json.loads(GOOGLE_CREDENTIALS), scope
)
client = gspread.authorize(creds)
sheet = client.open("finance_analys").worksheet("unload_TG")

bot = telebot.TeleBot(TOKEN)

# Хранилище состояний
user_states = {}

# Словарь месяцев для текстового формата на русском языке
MONTHS_RU = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля", 5: "мая", 6: "июня",
    7: "июля", 8: "августа", 9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"
}

MAIN_KEYBOARD = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
MAIN_KEYBOARD.add("Доход", "Расход")

INCOME_KEYBOARD = telebot.types.InlineKeyboardMarkup()
INCOME_KEYBOARD.add(
    telebot.types.InlineKeyboardButton("Зарплата", callback_data="income_salary")
)
INCOME_KEYBOARD.add(
    telebot.types.InlineKeyboardButton("Фриланс", callback_data="income_freelance")
)
INCOME_KEYBOARD.add(
    telebot.types.InlineKeyboardButton("Подарки", callback_data="income_gift")
)
INCOME_KEYBOARD.add(
    telebot.types.InlineKeyboardButton("Другое", callback_data="income_other")
)

EXPENSE_KEYBOARD = telebot.types.InlineKeyboardMarkup()
EXPENSE_KEYBOARD.add(
    telebot.types.InlineKeyboardButton("Покупки", callback_data="expense_shopping")
)
EXPENSE_KEYBOARD.add(
    telebot.types.InlineKeyboardButton("Платежи", callback_data="expense_payments")
)
EXPENSE_KEYBOARD.add(
    telebot.types.InlineKeyboardButton("Задолженности", callback_data="expense_debt")
)
EXPENSE_KEYBOARD.add(
    telebot.types.InlineKeyboardButton("Развлечения", callback_data="expense_fun")
)
EXPENSE_KEYBOARD.add(
    telebot.types.InlineKeyboardButton("Другое", callback_data="expense_other")
)
EXPENSE_KEYBOARD.add(
    telebot.types.InlineKeyboardButton("Транспорт", callback_data="expense_transfer")
)
EXPENSE_KEYBOARD.add(
    telebot.types.InlineKeyboardButton("Одежда/обувь", callback_data="expense_cloth")
)

@bot.message_handler(commands=["start"])
def start_handler(message):
    bot.send_message(message.chat.id, "Выберите тип:", reply_markup=MAIN_KEYBOARD)
    user_states[message.from_user.id] = {"step": "waiting_type"}


@bot.message_handler(func=lambda message: message.text == "Доход")
def income_type(message):
    bot.send_message(message.chat.id, "Категория дохода:", reply_markup=INCOME_KEYBOARD)
    user_states[message.from_user.id] = {"step": "waiting_category", "type": "income"}


@bot.message_handler(func=lambda message: message.text == "Расход")
def expense_type(message):
    bot.send_message(
        message.chat.id, "Категория расхода:", reply_markup=EXPENSE_KEYBOARD
    )
    user_states[message.from_user.id] = {"step": "waiting_category", "type": "expense"}


@bot.callback_query_handler(
    func=lambda call: call.data.startswith(("income_", "expense_"))
)
def process_category(call):
    user_id = call.from_user.id
    type_, category = call.data.split("_", 1)

    user_states[user_id] = {
        "step": "waiting_comment",
        "type": type_,
        "category": category,
    }

    bot.edit_message_text(
        f"✅ {type_.title()} - {category.title()}\n\n📝 Введите комментарий:",
        call.message.chat.id,
        call.message.message_id,
    )


@bot.message_handler(
    func=lambda message: message.from_user.id in user_states
    and user_states[message.from_user.id]["step"] == "waiting_comment"
)
def process_comment(message):
    user_id = message.from_user.id
    user_states[user_id]["comment"] = message.text
    user_states[user_id]["step"] = "waiting_amount"
    bot.send_message(message.chat.id, "💰 Введите сумму:")


@bot.message_handler(
    func=lambda message: message.from_user.id in user_states
    and user_states[message.from_user.id]["step"] == "waiting_amount"
)
def process_amount(message):
    user_id = message.from_user.id
    try:
        amount = float(message.text.replace(",", "."))
        data = user_states[user_id]

        now = datetime.now()
        current_month = MONTHS_RU[now.month]

        # Добавлена новая колонка с месяцем на 5-ю позицию (перед датой)
        record = [
            message.from_user.first_name or "Unknown",
            data["type"].title(),
            data["category"].title(),
            data["comment"],
            amount,
            current_month,
            now.strftime("%d.%m.%Y %H:%M"),
        ]
        sheet.append_row(record)

        bot.send_message(
            message.chat.id,
            f"✅ *Запись сохранена!*\n\n"
            f"👤 {record[0]}\n"
            f"📊 {record[1]}: {record[2]}\n"
            f"📝 {record[3]}\n"
            f"📅 Месяц: {record[5]}\n"
            f"💰 *{amount}₽*\n"
            f"📅 {record[-1]}",
            parse_mode="Markdown",
        )

        # Очищаем состояние для следующего круга
        del user_states[user_id]
        bot.send_message(message.chat.id, "➕ Что дальше?", reply_markup=MAIN_KEYBOARD)

    except ValueError:
        bot.send_message(
            message.chat.id, "❌ Введите корректную сумму (например: 67000)"
        )
    except Exception as e:
        if user_id in user_states:
            del user_states[user_id]
        bot.send_message(
            message.chat.id, "❌ Произошла ошибка при сохранении. Попробуйте заново.", reply_markup=MAIN_KEYBOARD
        )


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
    return "🚀 Finance Bot работает!"


if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=f"https://financetg-bot.onrender.com/{TOKEN}")
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)
