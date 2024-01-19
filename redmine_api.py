#!/usr/bin/env python
import configparser
import logging
from redminelib import Redmine
from redminelib.exceptions import ValidationError
from get_api_key import get_api_key_and_login_from_telegram

logger = logging.getLogger(__name__)

config = configparser.ConfigParser()
config.read('config.ini')
REDMINE_URL = config['Redmine']['url']

PRIO_MAPPING = {
    "Обязательно": 4,
    "Срочно": 6,
    "НЕМЕДЛЕННО": 7
}


async def create_task(login: str, chat_id: int, subject: str, description: str, priority: str = "Обязательно", project: int = None, tracker_id: int = None, downloads=None):
    try:
        api_key, user_id, _ = get_api_key_and_login_from_telegram(
            login, chat_id)

        if not user_id:
            logger.info(
                f"Пользователь с именем %s {login} не найден в Redmine.")
            return f"Пользователь с именем {login} не найден в Redmine."

        try:
            redmine = Redmine(REDMINE_URL, key=api_key)
        except Exception as e:
            logger.error(f"Ошибка при запросе к Redmine. Причина: %s {e}")
            return "Сервер Редмайн не доступен. Обратитесь к вашему админу."

        # Получаем членства пользователя
        memberships = redmine.user.get(user_id).memberships

        # Если у пользователя нет членства в каких-либо проектах
        if not memberships:
            logger.info(
                f"У пользователя %s {login} нет доступа ни к одному проекту.")
            return f"У пользователя {login} нет доступа ни к одному проекту."

        prio_id = PRIO_MAPPING.get(priority)

        # Выбираем первый проект, в который входит пользователь
        if not project:
            chosen_project = memberships[0].project
            chosen_project_name = chosen_project.name
            project = chosen_project.id
        else:
            chosen_project_name = redmine.project.get(project).name

        issue = redmine.issue.new()
        issue.project_id = project
        issue.subject = subject
        issue.description = description
        issue.priority_id = prio_id
        issue.tracker_id = tracker_id
        # Если предоставлены файлы, добавляем их как вложения
        if downloads:
            # print(downloads)
            issue.uploads = downloads
        issue.save()

        if hasattr(issue, 'id'):
            issue_url = f"{REDMINE_URL}/issues/{issue.id}"
            message = f'Задача <a href="{issue_url}">[{chosen_project_name} - #{issue.id}] {issue.subject}</a> создана!'
            # print(message)
            return message
        else:
            logger.error("Ошибка при создании задачи.")
            return "Ошибка при создании задачи."
    except ValidationError as e:
        logger.error(f"Произошла ошибка при создании задачи: %s {e}")
        return str(e)


async def add_comment_with_attachment(login: str, chat_id: int, task_number: int, comment: str, files=None):
    try:
        api_key, user_id, _ = get_api_key_and_login_from_telegram(
            login, chat_id)

        if not user_id:
            logger.info(
                f"Пользователь с именем %s {login} не найден в Redmine.")
            return f"Пользователь с именем {login} не найден в Redmine."

        try:
            redmine = Redmine(REDMINE_URL, key=api_key)
        except Exception as e:
            logger.error(f"Ошибка при запросе к Redmine. Причина: %s {e}")
            return "Сервер Редмайн не доступен. Обратитесь к вашему админу."

        # Проверяем существование задачи
        issue = redmine.issue.get(task_number)
        if not issue:
            logger.info(f"Задача с номером %s {task_number} не найдена.")
            return f"Задача с номером {task_number} не найдена."

        # Добавляем комментарий с прикрепленными файлами
        issue.notes = comment
        if files:
            issue.uploads = files
        issue.save()

        return f"Комментарий к задаче #{task_number} добавлен."

    except ValidationError as e:
        logger.error(f"Произошла ошибка при добавлении комментария: %s {e}")
        return str(e)
