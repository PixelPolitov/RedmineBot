#!/usr/bin/env python
from os import getenv
import configparser
import asyncio
import logging
import aiohttp
from aiohttp import web
from aiohttp.web_exceptions import HTTPClientError
from aiogram import Bot
from aiogram.types.input_file import BufferedInputFile
from aiogram.enums import ParseMode
from get_api_key import get_api_key_and_login_from_telegram
from message_handler import message_handler


logger = logging.getLogger(__name__)
LOG_FORMAT = '%s %b "%{Referer}i" "%{User-Agent}i"'

config = configparser.ConfigParser()
config.read('config.ini')
REDMINE_URL = config['Redmine']['url']
BOT_TOKEN = getenv("BOT_TOKEN")
REDMINE_ADMIN_API_KEY = getenv("REDMINE_ADMIN_API_KEY")
SECRET_TOKEN = getenv("SECRET_TOKEN")

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)


async def handle_webhook(request):
    token = request.rel_url.query.get('token', None)
    if token != SECRET_TOKEN:
        logger.error("Не верный секретный токен для сервера вебхуков")
        return web.Response(status=403, text="Forbidden")

    data = await request.json()

    # Извлечение логинов из recipients
    message, attachment_ids, attachment_names = message_handler(data)
    recipient_logins = [recipient['name']
                        for recipient in data['data']['recipients']]

    for login in recipient_logins:
        *_, chat_id_from_db = get_api_key_and_login_from_telegram(
            login, chat_id=None)
        if chat_id_from_db:  # срок хранения этого id в redis - сутки
            await bot.send_message(chat_id_from_db, message)
            for attach_id, file_name in zip(attachment_ids, attachment_names):
                bytes_data = await download_file_from_redmine(attach_id, REDMINE_ADMIN_API_KEY)
                input_file = BufferedInputFile(
                    file=bytes_data, filename=file_name)
                await bot.send_document(chat_id_from_db, document=input_file)

    return web.Response(text='Webhook received!')


async def download_file_from_redmine(attachment_id, api_key):
    url = f"{REDMINE_URL}/attachments/download/{attachment_id}"

    headers = {
        "X-Redmine-API-Key": api_key
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            if response.status != 200:
                logger.error(
                    f"Failed to download attachment. Status: %s {response.status}")
                raise HTTPClientError(
                    text=f"Failed to download attachment. Status: {response.status}")

            file_content = await response.read()
            return file_content

app = web.Application()
app.router.add_post("/v1/redmine", handle_webhook)


async def main():
    runner = web.AppRunner(app, access_log_format=LOG_FORMAT)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 5000)
    logger.info("WebHook server has started")
    await site.start()
    await asyncio.Event().wait()

# if __name__ == "__main__":
#     logger.info("WebHook server has started")
#     web.run_app(app, host='0.0.0.0', port=5000, access_log_format=LOG_FORMAT)
