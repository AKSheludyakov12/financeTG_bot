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
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import CommandStart
import asyncio
import uvicorn

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


class Form(StatesGroup):
    waiting_category = State()
    waiting_comment = State()
    waiting_amount = State()


@dp.message(CommandStart())
async def start_handler(message, state: FSMContext):
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Доход"), KeyboardButton(text="Расход")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )

    await message.answer("Выберите тип:", reply_markup=keyboard)
    await state.set_state(Form.waiting_category)


@dp.message(F.text == "Доход")
async def income_type(message, state: FSMContext):
    inline_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Зарплата", callback_data="income_salary")],
            [InlineKeyboardButton(text="Фриланс", callback_data="income_freelance")],
            [InlineKeyboardButton(text="Подарки", callback_data="income_gift")],
            [InlineKeyboardButton(text="Другое", callback_data="income_other")],
        ]
    )
    await message.answer("Категория дохода:", reply_markup=inline_kb)
    await state.set_state(Form.waiting_category)


@dp.message(F.text == "Расход")
async def expense_type(message, state: FSMContext):
    inline_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Покупки", callback_data="expense_shopping")],
            [InlineKeyboardButton(text="Платежи", callback_data="expense_payments")],
            [InlineKeyboardButton(text="Задолженности", callback_data="expense_debt")],
            [InlineKeyboardButton(text="Развлечения", callback_data="expense_fun")],
            [InlineKeyboardButton(text="Другое", callback_data="expense_other")],
        ]
    )
    await message.answer("Категория расхода:", reply_markup=inline_kb)
    await state.set_state(Form.waiting_category)


@dp.callback_query(F.data.startswith(("income_", "expense_")))
async def process_category(callback, state: FSMContext):
    category_data = callback.data.split("_", 1)
    type_ = category_data[0]
    category = category_data[1]

    await state.update_data(type=type_, category=category)
    await callback.message.edit_text(
        f"✅ Выбрано: {type_.title()} - {category.title()}\n\n"
        f"📝 Введите комментарий:\n(например: 'Сигареты' или 'Зарплата январь')"
    )
    await state.set_state(Form.waiting_comment)
    await callback.answer()


@dp.message(Form.waiting_comment)
async def process_comment(message, state: FSMContext):
    await state.update_data(comment=message.text)
    await message.answer("💰 Введите сумму (число):")
    await state.set_state(Form.waiting_amount)


@dp.message(Form.waiting_amount)
async def process_amount(message, state: FSMContext):
    try:
        amount = float(message.text.replace(",", "."))
        data = await state.get_data()

        # Сохраняем в Google Sheets
        record = [
            message.from_user.first_name or "Unknown",
            data["type"].title(),
            data["category"].title(),
            data["comment"],
            amount,
            datetime.now().strftime("%d.%m.%Y %H:%M"),
        ]
        sheet.append_row(record)

        await message.answer(
            f"✅ *Запись сохранена!*\n\n"
            f"👤 {record[0]}\n"
            f"📊 {record[1]}: {record[2]}\n"
            f"📝 {record[3]}\n"
            f"💰 *{amount}₽*\n"
            f"📅 {record[-1]}",
            parse_mode="Markdown",
        )

    except ValueError:
        await message.answer("❌ Введите корректную сумму (например: 67000 или 245.50)")
        return

    await state.clear()
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Доход"), KeyboardButton(text="Расход")]],
        resize_keyboard=True,
    )
    await message.answer("➕ Что дальше?", reply_markup=keyboard)


@app.route(f"/{TOKEN}", methods=["POST"])
async def webhook():
    json_string = request.get_data().decode("utf-8")
    update = telebot.types.Update.de_json(json_string)

    # Обработка через aiogram
    if update:
        await dp.feed_update(bot, update.to_python())  # Конвертируем для aiogram

    return "OK"


@app.route("/")
def home():
    return "🚀 Finance Bot is running!"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
