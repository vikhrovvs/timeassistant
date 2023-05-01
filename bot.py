import os
import time
from datetime import datetime

from aiogram import Bot, types
from aiogram.dispatcher import Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.utils import executor

from apscheduler.schedulers.asyncio import AsyncIOScheduler

import asyncio
import logging


from database_operations import create_necessary_tables_if_not_exist

log = logging.getLogger(__name__)

from aiogram.dispatcher.filters.state import State, StatesGroup

bot = Bot(token=os.environ['BOT_TOKEN'])
# bot = Bot(token="")
dp = Dispatcher(bot)


@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    # response = "Hi!\nI'm time assistant!\nUse /help to see my commands!"
    response = f"Hi! Your id: {message.from_user.id}"
    await message.answer(response)


class Event(StatesGroup):
    name = State()  # Will be represented in storage as 'Form:name'
    date = State()
    period = State()


@dp.message_handler(commands=["event"])
async def event(message: types.Message):
    await Event.name.set()
    await message.reply("Hi! Please, enter your event description")

#TODO: cancel


@dp.message_handler(state=Event.name)
async def process_name(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['name'] = message.text
    await Event.next()
    await message.reply("Please, enter an event date")


#todo: Incorrect date


@dp.message_handler(state=Event.date)
async def process_date(message: types.Message, state:FSMContext):
    await Event.next()
    await state.update_data(date=message.text)

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
    markup.add("Every day", "Every week", "Every 10s")
    markup.add("Once")

    await message.reply("How often do you need a reminder of this event?", reply_markup=markup)


#todo: Incorrect period


@dp.message_handler(state=Event.period)
async def process_period(message: types.message, state: FSMContext):
    async with state.proxy() as data:
        data['period'] = message.text

        markup = types.ReplyKeyboardRemove()
        pass



async def send_date_to_admin(bot, admin_id=344762653, additional_text=""):
    text = f"Current time: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
    await bot.send_message(chat_id=admin_id, text=text)


async def main():
    # executor.start_polling(dp, timeout=10)
    create_necessary_tables_if_not_exist()

    await send_date_to_admin(bot, additional_text="Starting bot!\n")
    #
    scheduler = AsyncIOScheduler()
    # scheduler.start()
    # scheduler.add_job(send_date_to_admin, "interval", seconds=10, args=(bot,))

    try:
        scheduler.start()
        scheduler.add_job(send_date_to_admin, "interval", seconds=10, args=(bot,), start_date=datetime.now())

        await dp.start_polling()
    finally:
        await dp.storage.close()
        await dp.storage.wait_closed()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("Bot stopped!")
