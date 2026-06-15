import logging

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

logger = logging.getLogger(__name__)


class ErrorHandlingMiddleware(BaseMiddleware):
    """Не даёт боту "зависать" молча: при необработанном исключении в хендлере
    сбрасывает FSM-состояние и сообщает пользователю, что нужно начать заново."""

    async def __call__(self, handler, event: TelegramObject, data: dict):
        try:
            return await handler(event, data)
        except Exception:
            logger.exception("Ошибка при обработке обновления")
            state = data.get("state")
            if state:
                await state.clear()
            target = event.message if isinstance(event, CallbackQuery) else event
            if isinstance(target, Message):
                try:
                    await target.answer(
                        "Произошла ошибка при обработке. Состояние сброшено — начните заново: /start"
                    )
                except Exception:
                    pass
