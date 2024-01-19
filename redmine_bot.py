#!/usr/bin/env python
import re
from os import getenv
import logging
from typing import Optional
from aiogram import Bot, Dispatcher, F, Router, types, html
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.exceptions import TelegramNotFound, TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.methods import DeleteWebhook
from aiogram.types import (
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from custom_filters import DocumentFilter, LongTextFilter
from redmine_req import RedmineRequests
from redmine_api import create_task, add_comment_with_attachment
from selectors_by_key import get_data_by_key

logger = logging.getLogger(__name__)

# Простые кнопки для ответов
yes_no_kb = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="Да"),
            KeyboardButton(text="Нет"),
        ]
    ],
    resize_keyboard=True,
)

priority_kb = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="Срочно"),
            KeyboardButton(text="НЕМЕДЛЕННО")
        ]
    ],
    resize_keyboard=True,
)

BOT_TOKEN = getenv("BOT_TOKEN")

form_router = Router()
redmine_req = RedmineRequests()

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)


class Form(StatesGroup):
    task_number = State()
    show_task = State()
    operation = State()
    action = State()
    create_description = State()
    create_subject = State()
    create_priority = State()
    project_id = State()
    project_name = State()
    potential_description = State()
    priority_state = State()
    long_text = State()
    comment = State()
    username = State()
    message_id = State()
    selector_key = State()
    tracker_id = State()
    tracker_name = State()
    uploads = State()
    number_of_files = State()
    downloads = State()


@form_router.message(DocumentFilter())
async def process_files_from_message(message: Message, state: FSMContext = None) -> None:
    # Получите текущие загрузки из состояния
    data = await state.get_data()
    current_uploads = data.get('uploads', [])

    # Если сообщение содержит документ
    if message.document:
        file_info = {'file_id': message.document.file_id,
                     'filename': message.document.file_name}
        current_uploads.append(file_info)

    data = {
        'uploads': current_uploads,
        'number_of_files': len(current_uploads)
    }
    await state.update_data(**data)

    # Если у сообщения есть подпись и загрузки
    if message.reply_to_message and message.caption and current_uploads:
        await handle_replies(message, state)
    elif message.caption and current_uploads:
        await process_long_text(message, state)


async def process_download_files(state: FSMContext) -> None:
    data = await state.get_data()
    current_downloads = data.get('downloads', [])
    for file_info in data['uploads']:
        file_id = file_info['file_id']
        file = await bot.get_file(file_id)
        file_path = file.file_path
        file_stream = await bot.download_file(file_path)
        file_info = {'path': file_stream,
                     'filename': file_info['filename']}
        current_downloads.append(file_info)
    await state.update_data(downloads=current_downloads, uploads=[])


def get_keyboard(buttons_data: dict, buttons_order: Optional[list[list[str]]] = None) -> InlineKeyboardMarkup:

    keyboard = []

    if buttons_order:
        for row_order in buttons_order:
            row = []
            for button_text in row_order:
                callback_data = buttons_data.get(button_text)
                if callback_data:
                    btn = InlineKeyboardButton(
                        text=button_text, callback_data=callback_data)
                    row.append(btn)
            keyboard.append(row)
    else:
        for button_text, callback_data in buttons_data.items():
            btn = InlineKeyboardButton(
                text=button_text, callback_data=callback_data)
            keyboard.append([btn])

    markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    return markup


def get_reply_keyboard(buttons_data):
    # Создаем кнопки на основе номеров задач
    keyboard_buttons = []
    current_row = []
    for task_number in buttons_data:
        button = KeyboardButton(text=task_number)
        current_row.append(button)

        # Если в текущем ряду уже две кнопки, добавляем их в общий список и очищаем текущий ряд
        if len(current_row) == 2:
            keyboard_buttons.append(current_row)
            current_row = []

    # Добавляем оставшиеся кнопки, если таковые имеются
    if current_row:
        keyboard_buttons.append(current_row)

    keyboard = ReplyKeyboardMarkup(
        keyboard=keyboard_buttons, resize_keyboard=True, one_time_keyboard=True)
    return keyboard


async def remove_keyboard(query: types.CallbackQuery):
    await bot.edit_message_text(text=query.message.text, chat_id=query.message.chat.id, message_id=query.message.message_id)


async def delete_messages_until(message: Message, target_id: int, exclude_ids: set = None):
    current_id = message.message_id

    logger.info(
        f"Начало удаления сообщений до %s {target_id} исключая {exclude_ids}")

    # Удаление сообщений в обратном порядке, от более новых к старым.
    while current_id > target_id:
        if current_id in exclude_ids:
            current_id -= 1
            continue

        try:
            await bot.delete_message(chat_id=message.chat.id, message_id=current_id)
        except TelegramNotFound:
            # Логируем, но игнорируем ошибку "сообщение для удаления не найдено".
            logger.warning(
                f"Сообщение %s {current_id} не найдено для удаления.")
        except TelegramBadRequest as e:
            # Логируем неожиданные ошибки и продолжаем с другими сообщениями.
            logger.error(
                f"Ошибка при удалении сообщения %s {current_id}: {e}", exc_info=True)
        finally:
            # В любом случае, продолжаем с следующим ID.
            current_id -= 1


@form_router.message(LongTextFilter())
async def process_long_text(message: Message, state: FSMContext = None):
    data = await state.get_data()
    # Извлечение длинной подписи (если имеется)
    long_text = message.text or message.caption or ""

    buttons_data = {
        'Добавить в последнюю задачу': 'add_comment',
        'Выбрать задачу': 'show_top10',
        'Создать новую задачу': 'create_task_form',
        'Завершить текущий диалог': 'cancel',
    }
    keyboard = get_keyboard(buttons_data)

    response = redmine_req.show_top10_user_tasks(
        message.from_user.username or 'unknown', 1)

    number_of_files = data.get("number_of_files", 0)

    match = re.search(r">(\d+)</a>", response)
    if match:
        task_number = match.group(1)
    else:
        logger.error(f"No match found in: %s {response}")
        return

    data = {
        "long_text": long_text,
        "task_number": task_number,
        "username": message.from_user.username or 'unknown',
    }

    await state.update_data(**data)
    message_form = (f"Как поступить с Вашим комментарием?\nДобавить в последнюю задачу,\nвыбрать задачу из списка или создать новую?\n"
                    f"{html.bold('Вложенных файлов: ')}{number_of_files}\n--------\n"
                    f"Последняя задача:\n{response}")
    await message.answer(message_form, reply_markup=keyboard)


@form_router.callback_query()
async def handle_callback_query(query: types.CallbackQuery, state: FSMContext):
    code = query.data
    code_to_function_map = {
        "add_comment": command_add_comment,
        "show_top10": command_show_top10,
        "create_task": command_create_task,
        "create_task_form": command_create_task_form,
        "ask_priority": ask_priority,
        "cancel": cancel_handler,
        "project_selector": command_get_selectors,
        "tracker_selector": command_get_selectors
    }

    if code == "show_top10":
        await state.set_state(Form.task_number)

    if code in ["project_selector", "tracker_selector"]:
        for row in query.message.reply_markup.inline_keyboard:
            for button in row:
                if button.callback_data == code:
                    button_text = button.text
                    await state.update_data(selector_key=button_text)
                    break

    # Проверяем, есть ли функция для данного кода
    if code in code_to_function_map:
        await code_to_function_map[code](query.message, state)

    if code in ("ask_priority", "create_task", "project_selector", "tracker_selector"):
        await remove_keyboard(query)
    else:
        await bot.delete_message(chat_id=query.message.chat.id, message_id=query.message.message_id)

    priority_map = {
        "priority_6": "Срочно",
        "priority_7": "НЕМЕДЛЕННО"
    }

    if code in priority_map:
        await state.update_data(priority_state=priority_map[code])
        await process_priority_choice(query.message, state)


@form_router.message(lambda message: message.reply_to_message is not None)
async def handle_replies(message: Message, state: FSMContext):
    data = await state.get_data()
    username = message.from_user.username or 'unknown'
    # Получение текста сообщения, на которое был дан ответ
    replied_text = message.reply_to_message.text

    files = None
    if 'uploads' in data:
        await process_download_files(state)
        data = await state.get_data()
        files = data.get('downloads')

    # Используя регулярное выражение для извлечения номера задачи
    match = re.search(r"#(\d+)", replied_text)
    if match:
        issue_id = match.group(1)

        # Сохраняем комментарий
        comment = message.text or message.caption
        kwargs = {
            "login": username,
            'chat_id': message.chat.id,
            "task_number": issue_id,
            "comment": comment,
        }
        if files:
            kwargs['files'] = files

        # Вызов функции command_add_comment
        response = await add_comment_with_attachment(**kwargs)
        await message.answer(response)
        await state.clear()
    else:
        await message.answer("Не могу найти номер задачи... :(")


@form_router.message(Command("add_comment"))
async def command_add_comment(message: Message, state: FSMContext):
    data = await state.get_data()
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")

    async def create_response_and_clear(username, task_number, comment, files=None):
        kwargs = {
            'login': username,
            'chat_id': message.chat.id,
            'task_number': task_number,
            'comment': comment
        }
        if files:
            kwargs['files'] = files

        response = await add_comment_with_attachment(**kwargs)
        await state.clear()
        return response

    if 'long_text' in data:
        username = data.get(
            'username', message.from_user.username or 'unknown')
        files = None
        if 'uploads' in data:
            await process_download_files(state)
            data = await state.get_data()
            files = data.get('downloads')

        response = await create_response_and_clear(
            username, data['task_number'], data['long_text'], files)
        await message.answer(response)
        await state.clear()
        return

    stripped_text = message.text.replace('/add_comment', '').strip()
    if not stripped_text:
        await message.answer("Не верный формат сообщения\nФормат: /add_comment 110022 Комментарий к задаче..")
        return

    numbers = re.search(r'^/add_comment\s+(\d+)', message.text)
    post_num_text = re.search(r'\d+\s+(.+)', message.text)

    if numbers:
        task_number = int(numbers.group(1))

        if post_num_text:
            comment = post_num_text.group(1).strip()

            response = await create_response_and_clear(
                message.from_user.username or 'unknown', task_number, comment)
            await message.answer(response)
            await state.clear()
            return

        else:
            await message.answer("Вы не написали комментарий к задаче или использовали не верный формат\nФормат: /add_comment 110022 Комментарий к задаче.")
            await cancel_handler(message, state)
    else:
        await state.set_state(Form.task_number)
        await message.answer("Пожалуйста, укажите номер задачи.")

        data = {
            "operation": add_comment_with_attachment,
            "action": "Добавляю комментарий к задаче №",
            "comment": stripped_text
        }
        await state.update_data(**data)


@form_router.message(Command("show_task"))
@form_router.message(lambda message: re.match(r'^покажи задачу(\s\d+)?$', message.text, re.IGNORECASE))
async def command_show_task(message: Message, state: FSMContext):
    await state.update_data(operation=redmine_req.show_task, action="Показываю задачу")
    chat_id = message.chat.id
    # await state.update_data(action="Показываю задачу")
    username = message.from_user.username or 'unknown'

    match = re.search(r'\d+', message.text)
    if match:
        task_number = int(match.group())
        await state.update_data(task_number=task_number)
        response = redmine_req.show_task(username, task_number, chat_id)

        await message.answer(response)
        await state.clear()

    else:
        await state.set_state(Form.task_number)
        await message.answer("Пожалуйста, укажите номер задачи.")


@form_router.message(Form.task_number)
async def process_task_number(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    long_text = data.get('long_text')
    uploads = data.get('uploads')

    if message.text == '/cancel':
        await cancel_handler(message, state)
        return

    async def process_attachments() -> str:
        await process_download_files(state)
        updated_data = await state.get_data()
        return updated_data.get('downloads', '')

    if long_text:
        task_match = re.search(r'\d+', message.text)
        files = await process_attachments() if uploads else ''

        if task_match:
            task_number = int(task_match.group(0))
            response = await add_comment_with_attachment(
                message.from_user.username or 'unknown', message.chat.id, task_number, long_text, files
            )
            await message.answer(response, reply_markup=ReplyKeyboardRemove())
            await state.clear()
            return

    if message.text.isdigit():
        await state.update_data(task_number=message.text)
        await state.set_state(Form.show_task)
        await message.answer(
            f"Хорошо!\nЗадача №{html.quote(message.text)}?", reply_markup=yes_no_kb
        )
    else:
        await message.answer("Номер задачи должен быть из цифр", reply_markup=ReplyKeyboardRemove())


@form_router.message(Form.show_task, F.text.casefold() == "нет")
async def process_dont_show_task(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Нет, так нет...", reply_markup=ReplyKeyboardRemove())


@form_router.message(Form.show_task, F.text.casefold() == "да")
async def process_show_task(message: Message, state: FSMContext) -> None:
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    data = await state.get_data()
    username = message.from_user.username or 'unknown'
    chat_id = message.chat.id

    args = []
    args.append(username)
    args.append(data['task_number'])
    args.append(chat_id)

    if 'comment' in data:
        args.append(data['comment'])

    await message.reply(
        f"Отлично!\n{data['action']} {html.quote(data['task_number'])}",
        reply_markup=ReplyKeyboardRemove(),
    )

    response = data['operation'](*args)
    await message.answer(response)


@form_router.message(Command("create_task_form"))
async def command_create_task_form(message: Message, state: FSMContext):
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    data = await state.get_data()

    buttons_data = {
        'Проект': 'project_selector',
        'Трекер': 'tracker_selector',
        'Приоритет': 'ask_priority',
        'Создать задачу': 'create_task',
        'Отмена': 'cancel',
    }

    buttons_order = [
        ['Проект', 'Трекер', 'Приоритет'],
        ['Создать задачу'],
        ['Отмена']
    ]

    keyboard = get_keyboard(buttons_data, buttons_order)

    default_project = await get_data_by_key(
        data['username'], "projects", 1)
    project = data.get('project_name', default_project['name'])

    default_tracker = data.get('tracker_name', await get_data_by_key(
        data['username'], "trackers", 1))

    default_priority = data.get('priority_state', 'Обязательно')
    default_subject = data.get(
        'create_subject', "Будет задана при создании задачи")

    number_of_files = data.get("number_of_files", 0)

    if "uploads" in data:
        await process_download_files(state)

    message_form = (
        f"{html.bold('Создание новой задачи')}\n\n"
        f"{html.bold('Проект: ')}{project}\n"
        f"{html.bold('Трекер: ')}{default_tracker}\n"
        f"{html.bold('Приоритет: ')}{default_priority}\n"
        f"{html.bold('Тема: ')}{default_subject}\n"
        f"{html.bold('Описание: ')}{data['long_text']}\n"
        f"{html.bold('Вложенных файлов: ')}{number_of_files}\n"
    )
    message_bottom = (
        "--------\nНиже вы можете изменить параметры новой задачи")

    if 'message_id' and 'create_subject' in data:  # Проверка наличия ID сохраненного сообщения
        await bot.edit_message_text(message_form, chat_id=message.chat.id, message_id=data['message_id'])
    elif 'message_id' in data:
        await bot.edit_message_text(message_form+message_bottom, chat_id=message.chat.id, message_id=data['message_id'], reply_markup=keyboard)
    else:
        sent_message = await message.answer(message_form+message_bottom, reply_markup=keyboard)
        # Сохраняем ID сообщения в состоянии
        await state.update_data(message_id=sent_message.message_id)


@form_router.message(Command("create_task"))
async def command_create_task(message: Message, state: FSMContext):
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    data = await state.get_data()
    description = data.get('long_text', '')
    await state.set_state(Form.create_description)

    if description:
        await state.update_data(potential_description=description)
    else:
        await state.update_data(potential_description=message.text)

    await message.answer("Создать задачу с этим описанием?", reply_markup=yes_no_kb)


@form_router.message(Form.create_description)
async def process_description(message: Message, state: FSMContext) -> None:
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    data = await state.get_data()
    if message.text.lower() == "да":
        description = data.get('potential_description', '')
        await state.update_data(description=description)
        await state.set_state(Form.create_subject)
        await message.answer("Напишите тему для задачи:", reply_markup=ReplyKeyboardRemove())
    else:
        await state.clear()
        await message.answer("Нет так нет...", reply_markup=ReplyKeyboardRemove())


@form_router.message(Form.create_subject)
async def process_subject(message: Message, state: FSMContext) -> None:
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    await state.update_data(create_subject=message.text)
    data = await state.get_data()

    required_keys = ['create_subject', 'long_text']
    if all(key in data for key in required_keys):

        await command_create_task_form(message, state)
        kwargs = {
            'login': data.get('username', message.from_user.username or 'unknown'),
            'chat_id': message.chat.id,
            'subject': data.get('create_subject'),
            'description': data.get('long_text'),
            'priority': data.get('priority_state'),
            'project': int(data['project_id']) if 'project_id' in data else None,
            'tracker_id': int(data['tracker_id']) if 'tracker_id' in data else None,
            'downloads': data.get('downloads')
        }

        # Убираем None значения из kwargs
        kwargs = {k: v for k, v in kwargs.items() if v is not None}
        response = await create_task(**kwargs)

        bot_response = await message.answer(response, reply_markup=ReplyKeyboardRemove())
        await delete_messages_until(message, data['message_id'], exclude_ids=[bot_response.message_id])
        await state.clear()

    else:
        await state.set_state(Form.create_priority)
        await message.answer("Изменить приоритет перед созданием задачи?\nПо умолчанию 'Обязательно'", reply_markup=yes_no_kb)


@form_router.message(Form.create_priority)
async def ask_priority(message: Message, state: FSMContext) -> None:
    chat_id = message.chat.id
    await bot.send_chat_action(chat_id, action="typing")
    data = await state.get_data()
    await state.set_state(Form.priority_state)
    if 'long_text' in data:
        buttons_data = {
            'НЕМЕДЛЕННО': 'priority_7',
            'Срочно': 'priority_6',
            'Отмена': 'cancel',
        }
        keyboard = get_keyboard(buttons_data)
        await message.answer(text="Выберете приоритет:", reply_markup=keyboard)
        return

    if message.text.lower() == "да":
        await message.answer(text="Выберете приоритет:", reply_markup=priority_kb)
    else:
        username = message.from_user.username or 'unknown'
        response = await create_task(
            username, chat_id, data['create_subject'], data['description'])

        await message.answer(response, reply_markup=ReplyKeyboardRemove())
        await state.clear()


@form_router.message(Form.priority_state)
async def process_priority_choice(message: Message, state: FSMContext) -> None:
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    data = await state.get_data()

    if 'long_text' and 'priority_state' in data:
        await command_create_task_form(message, state)
        return

    await state.update_data(priority_state=message.text)
    data = await state.get_data()

    kwargs = {
        'login': data.get('username', message.from_user.username or 'unknown'),
        'chat_id': message.chat.id,
        'subject': data.get('create_subject'),
        'description': data.get('description'),
        'priority': data.get('priority_state'),
        'project': int(data['project_id']) if 'project_id' in data else None,
        'tracker_id': int(data['tracker_id']) if 'tracker_id' in data else None,
        'downloads': data.get('downloads')
    }

    # Убираем None значения из kwargs
    kwargs = {k: v for k, v in kwargs.items() if v is not None}

    response = await create_task(**kwargs)

    bot_response = await message.answer(response, reply_markup=ReplyKeyboardRemove())
    await delete_messages_until(message, data['message_id'], exclude_ids=[bot_response.message_id])
    await state.clear()


@form_router.message(Form.project_id)
async def process_project(message: Message, state: FSMContext) -> None:
    match = re.match(r'(.+?)\s*\|\s*ID:\s*(\d+)', message.text)
    name, id_number = match.groups()
    data = {
        "project_id": id_number,
        "project_name": name
    }

    await state.update_data(**data)
    await command_create_task_form(message, state)


@form_router.message(Form.tracker_id)
async def process_tracker(message: Message, state: FSMContext) -> None:
    match = re.match(r'(.+?)\s*\|\s*ID:\s*(\d+)', message.text)
    name, id_number = match.groups()
    data = {
        "tracker_id": id_number,
        "tracker_name": name
    }

    await state.update_data(**data)
    await command_create_task_form(message, state)


@form_router.message(Command("show_top10"))
@form_router.message(F.text.casefold() == "покажи открытые задачи")
async def command_show_top10(message: Message, state: FSMContext):
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    data = await state.get_data()
    if 'long_text' in data:
        response = redmine_req.show_top10_user_tasks(data['username'])
        pattern = r"Задача #<a href=\'.+?/(\d+)\'>.+?</a>:</i></b></u> (.+?)\s*(?=<|\n|$)"
        matches = re.findall(pattern, response)
        results = [' '.join(match) for match in matches]

        keyboard = get_reply_keyboard(results)

        await message.answer("Выберете задачу:", reply_markup=keyboard)

    else:
        response = redmine_req.show_top10_user_tasks(
            message.from_user.username or 'unknown')
        await message.answer(response)


@form_router.message(Command("selectors"))
async def command_get_selectors(message: Message, state: FSMContext):
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    data = await state.get_data()
    key = data['selector_key']
    if 'Проект' == key:
        await state.set_state(Form.project_id)
    if 'Трекер' == key:
        await state.set_state(Form.tracker_id)

    data = await get_data_by_key(data['username'], key)
    results = []

    if isinstance(data, str):
        return data
    else:
        for item in data:
            result = f"{item['name']} | ID: {item['id']}"
            results.append(result)

    keyboard = get_reply_keyboard(results)

    await message.answer(f"Выберете {key.lower()}:", reply_markup=keyboard)


@form_router.message(Command("count_my_tasks"))
@form_router.message(F.text.casefold() == "количество открытых задач")
async def command_count_my_tasks(message: Message):
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")

    username = message.from_user.username or 'unknown'
    response = redmine_req.number_of_open_tasks(username)
    await message.answer(response)


@form_router.message(CommandStart())
@form_router.message(F.text.casefold() == "помощь" or F.text.casefold() == "/help")
async def command_help_handler(message: Message) -> None:
    help_message = """
Вот список команд, с которыми я могу помочь:

🔍 ПРОСМОТР
- `/show_top10` — покажет 10 последних открытых задач.
- `/count_my_tasks` — узнать количество ваших активных задач.
- `/show_task <номер>` — детали задачи по номеру, например: `/show_task 110022`.

✏️ СОЗДАНИЕ
- `/create_task` — создание новой задачи, например `/create_task Описание для задачи...`
- `/add_comment <номер> <комментарий>` — добавление комментария к задаче, например: `/add_comment 110022 Отличная работа!`.

📝 Если введённый вами текст содержит более 5 слов, я предложу варианты действий с ним. Также вы можете отправить файл с короткой подписью, и я также предложу варианты действий.

💼 При загрузке нескольких файлов: пожалуйста, не добавляйте комментарий к группе файлов — я его не учту. Если хотите создать задачу с файлами, лучше отправьте комментарий отдельно после загрузки. Или загрузите несколько файлов, а последний — с нужной подписью, чтобы вызвать меню действий.
"""

    await message.answer(f"Привет, {message.from_user.full_name}!\n{help_message}", parse_mode='Markdown')


@form_router.message(Command("cancel"))
@form_router.message(F.text.casefold() == "отмена")
async def cancel_handler(message: Message, state: FSMContext) -> None:
    await state.clear()
    """
    Allow user to cancel any action
    """
    current_state = await state.get_state()
    if current_state is None:
        return

    logger.info("Cancelling state %r", current_state)
    await state.clear()
    await message.answer(
        "Cancelled.",
        reply_markup=ReplyKeyboardRemove(),
    )


async def main():
    dp = Dispatcher()
    dp.include_router(form_router)
    await bot(DeleteWebhook(drop_pending_updates=True))
    await dp.start_polling(bot)
