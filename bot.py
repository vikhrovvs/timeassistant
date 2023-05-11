import asyncio
import os
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

import aiogram.utils.markdown as md
import apscheduler.jobstores.base
from aiogram import Bot, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ParseMode, CallbackQuery
from aiogram_calendar import simple_cal_callback, SimpleCalendar
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from database_operations import create_necessary_tables_if_not_exist, save_event, set_inactive, load_all_events
from user_event import UserEvent
from utils import get_logger, DEFAULT_TZ


log = get_logger()

bot = Bot(token=os.environ['BOT_TOKEN'])
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

scheduler = AsyncIOScheduler()


@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    response = "Hi!\nI'm time assistant!\nUse /event to create an event.\n" \
               "Use /cancel to stop event creation at any time\n\n" \
               "The only available timezone yet is UTC+3 (Europe/Moscow)"
    await message.answer(response)


class Event(StatesGroup):
    name = State()  # Will be represented in storage as 'Form:name'
    date = State()
    time = State()
    period = State()


@dp.message_handler(commands=["event"])
async def event(message: types.Message):
    await Event.name.set()
    await message.answer("Please, enter your event description")


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
                                                      "Please, write seperated as HH MM or HH MM SS")
        await state.update_data(temp_message=message)


@dp.message_handler(state=Event.time)
async def process_time(message: types.Message, state: FSMContext):
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
        del data['temp_message']
    await Event.next()

    await message.answer(
        f'You selected {selected_time.strftime("%H:%M:%S")}'
    )

    markup = types.InlineKeyboardMarkup()
    button_1w = types.InlineKeyboardButton('Every week', callback_data='select_period|' + 'Every week')
    button_1d = types.InlineKeyboardButton('Every day', callback_data='select_period|' + 'Every day')
    button_1h = types.InlineKeyboardButton('Every hour', callback_data='select_period|' + 'Every hour')
    button_10s = types.InlineKeyboardButton('Every 10s', callback_data='select_period|' + 'Every 10s')
    markup.row(button_1w, button_1d)
    markup.row(button_1h, button_10s)

    await message.answer(
        "How often do you need a reminder of this event?", reply_markup=markup
    )


@dp.callback_query_handler(lambda c: c.data.startswith('select_period'), state=Event.period)
# @dp.message_handler(state=Event.period)
# async def process_period(message: types.message, state: FSMContext):
async def process_period(callback_query: types.CallbackQuery, state: FSMContext):
    await bot.answer_callback_query(callback_query.id)
    await callback_query.message.delete_reply_markup()
    cmd, period = callback_query.data.split('|')
    async with state.proxy() as data:
        data['period'] = period
        start_date = datetime.combine(data['date'], data['time'], tzinfo=DEFAULT_TZ)
        user_event = UserEvent(event_id=str(uuid.uuid4()),
                               user_id=callback_query.from_user.id,
                               name=data['name'],
                               date=start_date,
                               period=data['period']
                               )

        save_event(user_event)
        await initialize_event(user_event)

        markup = types.InlineKeyboardMarkup()
        button = types.InlineKeyboardButton('Cancel event', callback_data='cancel_job|' + user_event.event_id)
        markup.add(button)

        await bot.send_message(
            callback_query.from_user.id,
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

    await state.finish()


async def initialize_event(user_event: UserEvent):
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

    scheduler.add_job(send_event_to_user, "interval", args=(user_event,),
                      start_date=user_event.date, id=user_event.event_id,
                      **interval)


async def cancel_event(event_id: str) -> str:
    try:
        scheduler.remove_job(event_id)
        set_inactive(event_id)
        message_text = 'Event cancelled successfully'
    except apscheduler.jobstores.base.JobLookupError:
        message_text = 'Oops! Event is already inactive'
    return message_text


@dp.callback_query_handler(lambda c: c.data.startswith('cancel_job'))
async def process_job_cancel(callback_query: types.CallbackQuery):
    # await callback_query.message.delete_reply_markup()
    cmd, event_id = callback_query.data.split('|')
    message_text = await cancel_event(event_id)
    markup = types.InlineKeyboardMarkup()
    button = types.InlineKeyboardButton('Resume event (not implemented yet)', callback_data='resume_job|' + event_id)
    markup.add(button)
    await callback_query.message.edit_reply_markup(markup)
    await bot.answer_callback_query(callback_query.id, text=message_text)

    # await callback_query.answer(text=message_text)
    # await bot.send_message(chat_id=callback_query.from_user.id, text=message_text)


async def send_date_to_admin(admin_id=344762653, additional_text=""):
    log.info(f"sending date to admin at {datetime.now()}")
    text = f"{additional_text}Current time: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
    await bot.send_message(chat_id=admin_id, text=text)


async def send_event_to_user(user_event: UserEvent):
    markup = types.InlineKeyboardMarkup()
    button = types.InlineKeyboardButton('Cancel event', callback_data='cancel_job|' + user_event.event_id)
    markup.add(button)
    await bot.send_message(chat_id=user_event.user_id, text=user_event.name, reply_markup=markup)


async def respawn_all_events():
    events = load_all_events()
    for event in events:
        await initialize_event(event)


async def main():
    log.info(f"Starting bot; it is now {datetime.now()}")
    create_necessary_tables_if_not_exist()
    await send_date_to_admin(additional_text="Starting bot!\n")

    try:
        scheduler.start()
        # scheduler.add_job(send_date_to_admin, "interval", minutes=10, args=(344762653, "started 10m ago"),
        #                   start_date=datetime.now() - timedelta(minutes=5))
        await respawn_all_events()

        await dp.start_polling()
    finally:
        await dp.storage.close()
        await dp.storage.wait_closed()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("Bot stopped!")
