from flask import Flask, request
import gspread
import json
import os
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Message,
    CallbackQuery,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import asyncio

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

bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


# FSM состояния
class Form(StatesGroup):
    waiting_category = State()
    waiting_comment = State()
    waiting_amount = State()


@dp.message(commands=["start"])
async def start_handler(message: Message, state: FSMContext):
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    keyboard.add(KeyboardButton("Доход"), KeyboardButton("Расход"))
    await message.answer("Выберите тип:", reply_markup=keyboard)
    await state.set_state(Form.waiting_category)


@dp.message(F.text == "Доход")
async def income_category(message: Message, state: FSMContext):
    inline_kb = InlineKeyboardMarkup(row_width=2)
    inline_kb.add(InlineKeyboardButton("Зарплата", callback_data="income_salary"))
    inline_kb.add(InlineKeyboardButton("Фриланс", callback_data="income_freelance"))
    inline_kb.add(InlineKeyboardButton("Подарки", callback_data="income_gift"))
    inline_kb.add(InlineKeyboardButton("Другое", callback_data="income_other"))
    await message.answer("Категория дохода:", reply_markup=inline_kb)
    await state.set_state(Form.waiting_category)


@dp.message(F.text == "Расход")
async def expense_category(message: Message, state: FSMContext):
    inline_kb = InlineKeyboardMarkup(row_width=2)
    inline_kb.add(InlineKeyboardButton("Покупки", callback_data="expense_shopping"))
    inline_kb.add(InlineKeyboardButton("Платежи", callback_data="expense_payments"))
    inline_kb.add(InlineKeyboardButton("Задолженности", callback_data="expense_debt"))
    inline_kb.add(InlineKeyboardButton("Развлечения", callback_data="expense_fun"))
    inline_kb.add(InlineKeyboardButton("Другое", callback_data="expense_other"))
    await message.answer("Категория расхода:", reply_markup=inline_kb)
    await state.set_state(Form.waiting_category)


@dp.callback_query(F.data.startswith(("income_", "expense_")))
async def process_category(callback: CallbackQuery, state: FSMContext):
    category = callback.data.split("_", 1)[1]
    await state.update_data(category=category, type=callback.data.split("_")[0])
    await callback.message.edit_text(
        f"Выбрано: {callback.data.replace('_', ' ').title()}\n\n"
        f"Введите комментарий (например, 'Сигареты' или 'Зарплата январь'):"
    )
    await state.set_state(Form.waiting_comment)
    await callback.answer()


@dp.message(Form.waiting_comment)
async def process_comment(message: Message, state: FSMContext):
    await state.update_data(comment=message.text)
    await message.answer("Введите сумму (число):")
    await state.set_state(Form.waiting_amount)


@dp.message(Form.waiting_amount)
async def process_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text)
        data = await state.get_data()

        # Сохраняем в Google Sheets
        record = [
            message.from_user.id,
            data["type"].title(),
            data["category"],
            data["comment"],
            amount,
            datetime.now().strftime("%d.%m.%Y %H:%M"),
        ]
        sheet.append_row(record)

        await message.answer(
            f"✅ Запись добавлена!\n"
            f"Тип: {data['type'].title()}\n"
            f"Категория: {data['category']}\n"
            f"Комментарий: {data['comment']}\n"
            f"Сумма: {amount}₽\n"
            f"Дата: {record[-1]}"
        )
    except ValueError:
        await message.answer("❌ Неверная сумма. Введите число.")
        return

    await state.clear()
    # Возвращаем в главное меню
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    keyboard.add(KeyboardButton("Доход"), KeyboardButton("Расход"))
    await message.answer("Что дальше?", reply_markup=keyboard)
    await state.set_state(Form.waiting_category)


@app.route(f"/{TOKEN}", methods=["POST"])
async def webhook():
    update = telebot.types.Update.de_json(request.get_data().decode("utf-8"))
    # Используем aiogram для обработки
    await dp.feed_update(bot, update)
    return "OK"


@app.route("/")
def home():
    return "Bot is running!"


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
