import asyncio
import logging
from datetime import datetime, date
from zoneinfo import ZoneInfo

from aiogram import Bot

from bot.config import config
from bot.services import sheets_service

logger = logging.getLogger(__name__)
_TZ = ZoneInfo("Asia/Yekaterinburg")


async def _do_birthday_check(bot: Bot) -> None:
    try:
        birthdays = await asyncio.get_event_loop().run_in_executor(
            None, sheets_service.get_birthdays_today
        )
    except Exception as e:
        logger.error("Birthday check: ошибка чтения таблицы: %s", e, exc_info=True)
        return

    if not birthdays:
        return

    lines = ["🎂 Сегодня день рождения у клиентов:"]
    for b in birthdays:
        lines.append(f"• {b['name']} (д.р. {b['dob']})")
    msg = "\n".join(lines)

    for user_id in config.allowed_telegram_ids:
        try:
            await bot.send_message(user_id, msg)
        except Exception as e:
            logger.error("Birthday: не удалось отправить уведомление %s: %s", user_id, e)


async def birthday_worker(bot: Bot) -> None:
    """Фоновая задача: в 9:00 по Екатеринбургу проверяет дни рождения клиентов."""
    last_check_date: date | None = None
    while True:
        await asyncio.sleep(60)
        now = datetime.now(tz=_TZ)
        today = now.date()
        if now.hour >= 9 and last_check_date != today:
            last_check_date = today
            logger.info("Birthday: запускаю проверку дней рождения")
            await _do_birthday_check(bot)
