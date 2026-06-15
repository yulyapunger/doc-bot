import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bot.config import config
from bot.database.models import Base
from bot.handlers import contract_individual, contract_legal, start, tour_templates

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    engine = create_async_engine(config.database_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    bot = Bot(token=config.bot_token)
    await bot.set_my_commands([
        BotCommand(command="start", description="Главное меню"),
    ])
    dp = Dispatcher(storage=MemoryStorage())

    dp["session_factory"] = session_factory

    dp.include_router(start.router)
    dp.include_router(tour_templates.router)
    dp.include_router(contract_individual.router)
    dp.include_router(contract_legal.router)

    logger.info("Bot started")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
