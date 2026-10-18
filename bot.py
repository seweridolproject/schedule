import asyncio
import logging
import os
from datetime import date, timedelta

from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)

import db
import timetable

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

BTN_TODAY = "📅 Сегодня"
BTN_TOMORROW = "📆 Завтра"
BTN_WEEK = "🗓 Эта Неделя"
BTN_NEXT = "▶️ След. неделя"
BTN_REPL = "⚠️ Замены"
BTN_BELLS = "🔔 Звонки"

NO_DATE = "Этой даты нет на странице сайта (сайт показывает другую неделю)."

dp = Dispatcher()

def main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_TODAY), KeyboardButton(text=BTN_TOMORROW)],
            [KeyboardButton(text=BTN_WEEK), KeyboardButton(text=BTN_NEXT)],
            [KeyboardButton(text=BTN_REPL), KeyboardButton(text=BTN_BELLS)],
        ],
        resize_keyboard=True,
    )


async def load_week(message: Message, day: date = None):

    
    group_id = db.get_user_group(message.from_user.id)
    if group_id is None:
        await message.answer("Сначала выберите группу: /start")
        return None
    try:
        url = db.get_group_url(group_id)
        if day is not None:
            return await timetable.get_week_for(url, day)
        return await timetable.get_week(url)
    except Exception:
        logging.exception("Не удалось загрузить расписание")
        await message.answer("Не удалось загрузить расписание с сайта. Попробуйте позже.")
        return None


# ---------- Команды ----------

@dp.message(CommandStart())
async def cmd_start(message: Message):
    buttons = [
        [InlineKeyboardButton(text=g["name"], callback_data=f"group:{g['id']}")]
        for g in db.get_groups()
    ]
    await message.answer(
        "Привет! Выбери свою группу:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )


@dp.callback_query(F.data.startswith("group:"))
async def choose_group(callback: CallbackQuery):
    group_id = int(callback.data.split(":")[1])
    db.set_user_group(callback.from_user.id, group_id)
    await callback.message.answer(
        f"Группа выбрана: {db.get_group_name(group_id)} ✅",
        reply_markup=main_keyboard(),
    )
    await callback.answer()


@dp.message(Command("schedule"))
@dp.message(F.text == BTN_TODAY)
async def show_today(message: Message):
    data = await load_week(message)
    if data is not None:
        await message.answer(timetable.format_day(data, date.today()) or NO_DATE)


@dp.message(Command("tomorrow"))
@dp.message(F.text == BTN_TOMORROW)
async def show_tomorrow(message: Message):
    day = date.today() + timedelta(days=1)
    data = await load_week(message, day)
    if data is not None:
        await message.answer(timetable.format_day(data, day) or NO_DATE)


@dp.message(Command("week"))
@dp.message(F.text == BTN_WEEK)
async def show_week(message: Message):
    data = await load_week(message)
    if data is not None:
        await message.answer(timetable.format_week(data))


@dp.message(Command("next"))
@dp.message(F.text == BTN_NEXT)
async def show_next_week(message: Message):
    today = date.today()
    monday = today + timedelta(days=7 - today.weekday())  # ближайший будущий понедельник
    data = await load_week(message, monday)
    if data is None:
        return
    if monday not in data:
        await message.answer("Не удалось получить следующую неделю с сайта.")
        return
    await message.answer(timetable.format_week(data))


@dp.message(Command("replacements"))
@dp.message(F.text == BTN_REPL)
async def show_replacements(message: Message):
    data = await load_week(message)
    if data is not None:
        text = timetable.format_changes(data)
        await message.answer(text or "Замен и переносов на этой неделе нет ✅")


@dp.message(Command("bells"))
@dp.message(F.text == BTN_BELLS)
async def show_bells(message: Message):
    data = await load_week(message)
    if data is not None:
        text = timetable.format_bells(data)
        await message.answer("Время пар:\n\n" + text if text else "Нет данных о времени пар.")


# ---------- Запуск ----------

async def start_web_server():

    port = os.getenv("PORT")
    if not port:
        return

    async def health(request):
        return web.Response(text="Bot is running")

    app = web.Application()
    app.router.add_get("/", health)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(port)).start()


async def main():
    if not BOT_TOKEN:
        raise SystemExit("Не задан BOT_TOKEN. Получите токен у @BotFather.")
    logging.basicConfig(level=logging.INFO)
    db.init_db()
    await start_web_server()
    bot = Bot(token=BOT_TOKEN)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
