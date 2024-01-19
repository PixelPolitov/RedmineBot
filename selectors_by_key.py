#!/usr/bin/env python
import configparser
import json
import logging
from redminelib import Redmine
from get_api_key import get_api_key_and_login_from_telegram

logger = logging.getLogger(__name__)

config = configparser.ConfigParser()
config.read('config.ini')
REDMINE_URL = config['Redmine']['url']

with open('aliases.json', 'r', encoding='utf-8') as file:
    file_data = json.load(file)

KEY_ALIASES = file_data['selectors'][0]


async def get_data_by_key(login: str, key: str, limit: int = 165):
    api_key, user_id, _ = get_api_key_and_login_from_telegram(
        login)
    redmine = Redmine(REDMINE_URL, key=api_key)

    # Получаем членства пользователя
    memberships = redmine.user.get(user_id).memberships

    # Если у пользователя нет членства в каких-либо проектах
    if not memberships:
        logger.info(
            f"У пользователя %s {login} нет доступа ни к одному проекту.")
        return f"У пользователя {login} нет доступа ни к одному проекту."

    # Получаем все проекты, в которых пользователь является членом
    user_projects = [{"id": membership.project.id,
                      "name": membership.project.name} for membership in memberships]

    orig_key = KEY_ALIASES.get(key, key)

    map_func = {
        'status': redmine.issue_status.all,
        'trackers': redmine.tracker.all,
        'priorities': lambda: redmine.enumeration.filter(resource='issue_priorities'),
        'projects': lambda: user_projects,
        # Можно добавить другие ключи и функции, если это необходимо
    }

    func = map_func.get(orig_key)
    if not func:
        logger.error(f"Неизвестный ключ: %s {orig_key}")
        raise ValueError(f"Неизвестный ключ: {orig_key}")

    data = func()

    # Если лимит равен 1, вернем первый элемент данных
    if limit == 1:
        return data[0] if data else None

    return data
