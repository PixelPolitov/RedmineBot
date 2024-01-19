#!/usr/bin/env python
import json
import configparser
import logging
import requests
from get_api_key import get_api_key_and_login_from_telegram

logger = logging.getLogger(__name__)

config = configparser.ConfigParser()
config.read('config.ini')
REDMINE_URL = config['Redmine']['url']

# Словарь алиасов для ключей
with open('aliases.json', 'r', encoding='utf-8') as file:
    data = json.load(file)

KEY_ALIASES = data['requests'][0]


class RedmineRequests:
    def show_task(self, login: str, task_number: int, chat_id: int):
        api_key, user_id, _ = get_api_key_and_login_from_telegram(
            login, chat_id)

        if not user_id:
            logger.info(
                f"Пользователь с именем %s {login} не найден в Redmine.")
            return f'Пользователь с именем {login} не найден в Redmine.'

        url = f"{REDMINE_URL}/issues/{task_number}.json?include=journals"
        headers = {'X-Redmine-API-Key': api_key}

        try:
            http_response = requests.get(url, headers=headers, timeout=30)
        except Exception as e:
            logger.error(f"Ошибка при запросе к Redmine. Причина: %s {e}")
            return "Сервер Редмайн не доступен. Обратитесь к вашему админу."

        # пустой список для хранения ответов
        responses = []

        if http_response.status_code == 200:
            issue_data = http_response.json()['issue']
            keys = issue_data.keys()

            # Вывести информацию для каждого ключа
            for key in keys:
                if key in issue_data and key != "custom_fields":
                    value = issue_data[key]

                    if isinstance(value, dict) and 'name' in value:
                        value = value['name']

                    # Обработка комментариев
                    elif key == 'journals':
                        comments = []
                        for journal in value:
                            if 'notes' in journal and journal['notes']:
                                comment_author = journal['user'][
                                    'name'] if 'user' in journal and 'name' in journal['user'] else 'Неизвестный'
                                comments.append(
                                    f"{comment_author}: {journal['notes']}")
                        value = '\r\n'.join(comments)

                    russian_key = KEY_ALIASES.get(key, key)
                    if key == "id":
                        responses.append(
                            f"<u><b><i>{russian_key}:</i></b></u> <a href='{REDMINE_URL}/{task_number}'>{value}</a>")
                    else:
                        responses.append(
                            f"<u><b><i>{russian_key}:</i></b></u> {value}")

        else:
            logger.error(
                f"Ошибка при запросе к Redmine. Код состояния: %s {http_response.status_code}")
            return f"Ошибка при запросе к Redmine. Код состояния: {http_response.status_code}"

        final_response = '\r\n'.join(responses)

        return final_response

    def show_top10_user_tasks(self, login: str, num: int = 10):
        api_key, user_id, _ = get_api_key_and_login_from_telegram(
            login)

        if not user_id:
            logger.info(
                f"Пользователь с именем %s {login} не найден в Redmine.")
            return f"Пользователь с именем {login} не найден в Redmine."

        maxlimit = 10
        num = min(num, maxlimit)
        url = f"{REDMINE_URL}/issues.json?assigned_to_id={user_id}&status_id=1,2,3&limit={num}"
        headers = {'X-Redmine-API-Key': api_key}

        try:
            http_response = requests.get(url, headers=headers, timeout=30)
        except Exception as e:
            logger.error(f"Ошибка при запросе к Redmine. Причина: %s {e}")
            return "Сервер Редмайн не доступен. Обратитесь к вашему админу."

        tasks = []

        if http_response.status_code == 200:
            issues = http_response.json()['issues']
            if issues:
                for issue in issues:
                    issue_id = issue['id']
                    subject = issue['subject']
                    tasks.append(
                        f"<u><b><i>Задача #<a href='{REDMINE_URL}/{issue_id}'>{issue_id}</a>:</i></b></u> {subject}")

                return '\r\n'.join(tasks)
            else:
                logger.info(
                    f"На пользователя %s {user_id} нет открытых задач.")
                return f"На пользователя {user_id} нет открытых задач."

        else:
            logger.error(
                f"Ошибка при запросе к Redmine. Код состояния: %s {http_response.status_code}")
            return f'Ошибка при запросе к Redmine. Код состояния: {http_response.status_code}'

    def number_of_open_tasks(self, login: str):
        api_key, user_id, _ = get_api_key_and_login_from_telegram(
            login)

        if not user_id:
            logger.info(
                f"Пользователь с именем %s {login} не найден в Redmine.")
            return f'Пользователь с именем {login} не найден в Redmine.'

        url = f'{REDMINE_URL}/issues.json?assigned_to_id={user_id}&status_id=1,2,3&limit=100'
        headers = {'X-Redmine-API-Key': api_key}

        try:
            http_response = requests.get(url, headers=headers, timeout=30)
        except Exception as e:
            logger.error(f"Ошибка при запросе к Redmine. Причина: %s {e}")
            return "Сервер Редмайн не доступен. Обратитесь к вашему админу."

        if http_response.status_code == 200:
            total_issues = http_response.json().get(
                'total_count', 0)  # Получаем общее количество задач

            return f"У Вас {total_issues} открытых задач."
        else:
            logger.error(
                f"Ошибка при запросе к Redmine. Код состояния: %s {http_response.status_code}")
            return f"Ошибка при запросе к Redmine. Код состояния: {http_response.status_code}"
