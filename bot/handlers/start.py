from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.config import config
from bot.handlers.contract_individual import STATE_RENDERERS as INDIVIDUAL_RENDERERS
from bot.handlers.contract_legal import STATE_RENDERERS as LEGAL_RENDERERS
from bot.keyboards.common import main_menu_kb

router = Router()

STATE_RENDERERS = {**INDIVIDUAL_RENDERERS, **LEGAL_RENDERERS}


def _is_allowed(telegram_id: int) -> bool:
    return telegram_id in config.allowed_telegram_ids


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    if not _is_allowed(message.from_user.id):
        await message.answer("Доступ запрещён.")
        return
    await state.clear()
    await message.answer(
        "Договорной бот ИП Распопов\n\nВыберите действие:",
        reply_markup=main_menu_kb(),
    )


@router.callback_query(lambda c: c.data == "cancel")
async def cancel_handler(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(
        "Действие отменено. Выберите действие:",
        reply_markup=main_menu_kb(),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "go_back")
async def go_back_handler(callback: CallbackQuery, state: FSMContext, session_factory: async_sessionmaker) -> None:
    data = await state.get_data()
    history = data.get("_history", [])
    if not history:
        await callback.answer("Это первый шаг", show_alert=True)
        return
    prev_state = history.pop()
    await state.update_data(_history=history)
    await state.set_state(prev_state)
    renderer = STATE_RENDERERS.get(prev_state)
    if renderer is None:
        await callback.answer("Невозможно вернуться", show_alert=True)
        return
    await callback.answer()
    await renderer(callback.message, state, session_factory)


@router.callback_query(lambda c: c.data == "main_menu")
async def main_menu_handler(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(
        "Выберите действие:",
        reply_markup=main_menu_kb(),
    )
    await callback.answer()
