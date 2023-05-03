import os
import time
from datetime import datetime
from dataclasses import dataclass

from aiogram import Bot, types
from aiogram.dispatcher import Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text
from aiogram.utils import executor
import aiogram.utils.markdown as md
from aiogram.types import ParseMode, CallbackQuery
from aiogram.contrib.fsm_storage.memory import MemoryStorage

from aiogram_calendar import simple_cal_callback, SimpleCalendar, dialog_cal_callback, DialogCalendar
from aiogram_timepicker.panel import FullTimePicker, full_timep_callback

from apscheduler.schedulers.asyncio import AsyncIOScheduler

import asyncio
import logging

from database_operations import create_necessary_tables_if_not_exist

log = logging.getLogger(__name__)

from aiogram.dispatcher.filters.state import State, StatesGroup

bot = Bot(token=os.environ['BOT_TOKEN'])
# bot = Bot(token="")
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

scheduler = AsyncIOScheduler()


@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    # response = "Hi!\nI'm time assistant!\nUse /help to see my commands!"
    response = f"Hi! Your id: {message.from_user.id}"
    await message.answer(response)


class Event(StatesGroup):
    name = State()  # Will be represented in storage as 'Form:name'
    date = State()
    time = State()
    period = State()


@dataclass
class UserEvent:
    event_id: int
    user_id: int
    name: str
    date: datetime
    period: str


@dp.message_handler(commands=["event"])
async def event(message: types.Message):
    await Event.name.set()
    await message.answer("Hi! Please, enter your event description")


@dp.message_handler(state='*', commands='cancel')
@dp.message_handler(Text(equals='cancel', ignore_case=True), state='*')
async def cancel_handler(message: types.Message, state: FSMContext):
    """
    Allow user to cancel any action
    """
    current_state = await state.get_state()
    if current_state is None:
        return

    # logging.info('Cancelling state %r', current_state)
    await state.finish()
    await message.answer('Event creation cancelled', reply_markup=types.ReplyKeyboardRemove())


@dp.message_handler(state=Event.name)
async def process_name(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['name'] = message.text
    await Event.next()
    await message.answer("Please, enter an event date", reply_markup=await SimpleCalendar().start_calendar())


@dp.callback_query_handler(simple_cal_callback.filter(), state=Event.date)
async def process_simple_calendar(callback_query: CallbackQuery, callback_data: dict, state: FSMContext):
    selected, date = await SimpleCalendar().process_selection(callback_query, callback_data)
    if selected:
        await Event.next()
        await state.update_data(date=date)
        await callback_query.message.answer(
            f'You selected {date.strftime("%d/%m/%Y")}'
        )

        message = await callback_query.message.answer("What is the time of your event?\n"
                                                      "Please select or write space separated",
                                                      reply_markup=await FullTimePicker().start_picker())
        await state.update_data(temp_message=message)


@dp.message_handler(state=Event.time)
async def process_name(message: types.Message, state: FSMContext):
    selected_time = None
    for fmt in ("%H %M %S", "%H %M", "%H:%M:%S", "%H:%M", "%H.%M.%S", "%H.%M", "%H,%M,%S", "%H,%M"):
        try:
            selected_time = datetime.strptime(message.text, fmt).time()
            break
        except ValueError:
            pass

    if not selected_time:
        await message.answer('Incorrect time format! Please, try again')
        return

    async with state.proxy() as data:
        data['time'] = selected_time
        await data['temp_message'].delete_reply_markup()
        del data['temp_message']
    await Event.next()

    await message.answer(
        f'You selected {selected_time.strftime("%H:%M:%S")}'
    )

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
    markup.add("Every day", "Every week")
    markup.add("Every hour", "Every 10s")

    await message.reply(
        "How often do you need a reminder of this event?", reply_markup=markup
    )


@dp.callback_query_handler(full_timep_callback.filter(), state=Event.time)
async def process_name(callback_query: CallbackQuery, callback_data: dict, state: FSMContext):
    r = await FullTimePicker().process_selection(callback_query, callback_data)
    selected, selected_time = r.selected, r.time
    if selected:
        await Event.next()
        await state.update_data(time=selected_time)
        await callback_query.message.answer(
            f'You selected {selected_time.strftime("%H:%M:%S")}'
        )
        # await callback_query.message.answer(
        #     f"debug: {state.proxy().keys()}"
        # )
        await callback_query.message.delete_reply_markup()

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
        markup.add("Every day", "Every week")
        markup.add("Every hour", "Every 10s")

        await callback_query.message.reply(
            "How often do you need a reminder of this event?", reply_markup=markup
        )


@dp.message_handler(state=Event.period)
async def process_period(message: types.message, state: FSMContext):
    async with state.proxy() as data:
        data['period'] = message.text

        markup = types.ReplyKeyboardRemove()

        user_event = UserEvent(event_id=-1,
                               user_id=message.chat.id,
                               name=data['name'],
                               date=datetime.combine(data['date'], data['time']),
                               period=data['period']
                               )

        await bot.send_message(
            message.chat.id,
            md.text(
                md.text("Event created!"),
                md.text("Event description: ", md.bold(data['name'])),
                md.text("Date&time: ", user_event.date),
                # md.text("Date: ", md.code(data['date'])),
                # md.text("Time: ", md.code(data['time'])),
                md.text("Period: ", data['period']),
                sep='\n',
            ),
            reply_markup=markup,
            parse_mode=ParseMode.MARKDOWN,
        )

    if user_event.period == "Every week":
        interval = {"weeks": 1}
    elif user_event.period == "Every day":
        interval = {"days": 1}
    elif user_event.period == "Every hour":
        interval = {"hours": 1}
    elif user_event.period == "Every 10s":
        interval = {"seconds": 10}
    else:
        interval = {"days": 1}

    scheduler.add_job(send_event_to_user, "interval", args=(user_event,), start_date=user_event.date, **interval)
    await state.finish()


async def send_date_to_admin(admin_id=344762653, additional_text=""):
    text = f"{additional_text}Current time: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
    await bot.send_message(chat_id=admin_id, text=text)


async def send_event_to_user(user_event: UserEvent):
    # TODO: check BD if cancelled
    await bot.send_message(chat_id=user_event.user_id, text=user_event.name)


async def main():
    # executor.start_polling(dp, timeout=10)
    create_necessary_tables_if_not_exist()

    await send_date_to_admin(additional_text="Starting bot!\n")
    #
    # scheduler.start()
    # scheduler.add_job(send_date_to_admin, "interval", seconds=10, args=(bot,))

    try:
        scheduler.start()
        # scheduler.add_job(send_date_to_admin, "interval", seconds=10, args=(bot,), start_date=datetime.now())

        await dp.start_polling()
    finally:
        await dp.storage.close()
        await dp.storage.wait_closed()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("Bot stopped!")
