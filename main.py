#!/usr/bin/env python
from os import getenv
import sys
import redis
import logging
import configparser
import asyncio
from my_logger import setup_logger
import redmine_bot
import web_hooks
from get_api_key import (
    save_fernet_key,
    cipher_password,
    decrypt_password,
    is_password_encrypted
)

setup_logger()

logger = logging.getLogger(__name__)


async def main():
    # Запускаем обе асинхронные функции параллельно
    await asyncio.gather(
        redmine_bot.main(),
        web_hooks.main()
    )

if __name__ == "__main__":
    config = configparser.ConfigParser()
    config.read('config.ini')

    REDIS_HOST = config['Redis']['host']
    REDIS_PORT = int(config['Redis']['port'])
    REDIS_DB = int(config['Redis']['db'])
    REDIS_USER = config['Redis']['user']
    REDIS_PASS = getenv('REDIS_PASS')

    redis_conn = redis.StrictRedis(
        host=REDIS_HOST, port=REDIS_PORT, username=REDIS_USER, password=REDIS_PASS, db=REDIS_DB)
    try:
        if not redis_conn.get('encryption:key'):
            save_fernet_key()

        # Проверяем, сохранен ли уже зашифрованный пароль в конфиге, если нет - шифруем и сохраняем
        if not is_password_encrypted():
            cipher_password(config['Database']['password'])

        # При запуске приложения расшифровываем пароль
        decrypt_password(config['Database']['password'])
    except Exception as e:
        logger.error("Не удалось подключиться к Redis: %s", e)
        sys.exit(1)

    asyncio.run(main())
