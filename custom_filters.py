#!/usr/bin/env python
from aiogram.filters import Filter
from aiogram.types import Message
from aiogram.fsm.context import FSMContext


class DocumentFilter(Filter):
    async def __call__(self, message: Message) -> bool:
        return bool(message.document or message.media_group_id)


class LongTextFilter(Filter):
    async def __call__(self, message: Message, state: FSMContext) -> bool:
        if not message.text or message.caption:
            return False
        data = await state.get_data()
        text_length = len((message.text or "").split())
        caption_length = len((message.caption or "").split())
        return (text_length > 5 or caption_length > 5) and "long_text" not in data
