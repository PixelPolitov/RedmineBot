#!/usr/bin/env python
import sys
from os import getenv
import configparser
import logging
from typing import Tuple
import redis
from redis.exceptions import RedisError
import mysql.connector
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

config = configparser.ConfigParser()
config.read('config.ini')

REDIS_HOST = config['Redis']['host']
REDIS_PORT = int(config['Redis']['port'])
REDIS_DB = int(config['Redis']['db'])
REDIS_USER = config['Redis']['user']
REDIS_PASS = getenv('REDIS_PASS')
EXPIRE_TIME_SECONDS = int(config['Redis']['expire_time_seconds'])

DATABASE_CONFIG = {
    'host': config['Database']['host'],
    'user': config['Database']['user'],
    'database': config['Database']['database']
}

# id custom поля - TelegramLogin в Редмайн
telegramCustomId = int(config['Redmine']['custom_id'])

# Создание подключения к Redis
redis_conn = redis.StrictRedis(
    host=REDIS_HOST, port=REDIS_PORT, username=REDIS_USER, password=REDIS_PASS, db=REDIS_DB)


def save_fernet_key():
    """Генерация и сохранение ключа шифрования в Redis."""
    key = Fernet.generate_key()
    redis_conn.set('encryption:key', key)


def cipher_password(password):
    """Шифрование пароля и его сохранение в config.ini."""
    cipher_suite = Fernet(redis_conn.get('encryption:key'))
    encrypted_password = cipher_suite.encrypt(
        password.encode('utf-8')).decode('utf-8')
    config['Database']['password'] = encrypted_password
    with open('config.ini', 'w', encoding='utf-8') as configfile:
        config.write(configfile)


def decrypt_password(encrypted_password):
    """Расшифровка пароля для использования в приложении."""
    key = redis_conn.get('encryption:key')
    if not key:
        raise ValueError("Ключ шифрования не найден в Redis.")

    cipher_suite = Fernet(key)
    try:
        decrypted_password = cipher_suite.decrypt(
            encrypted_password.encode('utf-8')).decode('utf-8')
        DATABASE_CONFIG['password'] = decrypted_password
    except Exception:
        logger.error(
            "Ошибка при расшифровке пароля. Ключ шифрования не подходит для этого пароля. Запишите пароль в открытой форме и запустите бота.")
        sys.exit(1)


def is_password_encrypted():
    """Проверяем, является ли строка пароля зашифрованным токеном."""
    password = config['Database']['password']
    try:
        # Проверяем, что строка имеет длину, которая соответствует шифру Fernet
        return len(password) >= 44 and password.endswith('==')
    except (ValueError, TypeError):
        # Если длина не соответствует, значит это не зашифрованный пароль. ДА ТУПА...
        return False


def get_data_from_redis(telegram_username: str) -> Tuple[str, int, int]:
    try:
        api_key = redis_conn.get(f"{telegram_username}_key")
        id_from_db = redis_conn.get(f"{telegram_username}_id")
        chat_id_from_db = redis_conn.get(f"{telegram_username}_chat_id")

    except RedisError as e:
        raise e

    return (value.decode('utf-8') if value else None for value in (api_key, id_from_db, chat_id_from_db))


def set_data_to_redis(telegram_username: str, api_key: str, id_from_db: int, chat_id: int):
    redis_conn.set(f"{telegram_username}_key", api_key, ex=EXPIRE_TIME_SECONDS)
    redis_conn.set(f"{telegram_username}_id",
                   id_from_db, ex=EXPIRE_TIME_SECONDS)
    redis_conn.set(f"{telegram_username}_chat_id",
                   chat_id)


def get_data_from_db(telegram_username: str) -> Tuple[str, int]:
    cnx = mysql.connector.connect(**DATABASE_CONFIG)
    cursor = cnx.cursor()

    query = """
        SELECT t.value, u.id
        FROM tokens AS t
        JOIN users AS u ON t.user_id = u.id
        JOIN custom_values AS cv ON u.id = cv.customized_id
        WHERE cv.custom_field_id = %s
        AND cv.value = %s
        AND t.action = 'api';
    """
    cursor.execute(query, (telegramCustomId, telegram_username))
    result = cursor.fetchone()
    cursor.close()
    cnx.close()

    return result if result else (None, None)


def get_api_key_and_login_from_telegram(telegram_username: str, chat_id: int = None) -> Tuple[str, int, int]:
    try:
        api_key, id_from_db, chat_id_from_db = get_data_from_redis(
            telegram_username)

        if chat_id and (not chat_id_from_db or chat_id != chat_id_from_db):
            redis_conn.set(f"{telegram_username}_chat_id",
                           chat_id)

        if not api_key or not id_from_db:
            api_key, id_from_db = get_data_from_db(telegram_username)
            if api_key and id_from_db:
                set_data_to_redis(telegram_username, api_key,
                                  id_from_db, chat_id)

    except RedisError as e:
        logger.error(f"Ошибка Redis: %s {e}")

    return api_key, id_from_db, chat_id_from_db
