from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.config import config
from bot.database import crud
from bot.keyboards.common import (
    cancel_kb,
    insurance_kb,
    main_menu_kb,
    meal_type_kb,
    room_count_kb,
    room_type_kb,
    template_actions_kb,
    templates_manage_kb,
    transfer_kb,
    yes_no_kb,
)

router = Router()

TEMPLATE_FIELDS_ORDER = [
    ("country", "Введите страну:"),
    ("city", "Введите город (или отправьте '-' если нет):"),
    ("hotel", "Введите отель:"),
    ("check_in_date", "Дата заезда (ДД.ММ.ГГГГ):"),
    ("check_out_date", "Дата выезда (ДД.ММ.ГГГГ):"),
    ("nights", "Количество ночей:"),
    ("payment_deadline", "Дата полной оплаты (ДД.ММ.ГГГГ):"),
    ("additional_conditions", "Дополнительные условия (или '-' если нет):"),
]


class TourTemplateStates(StatesGroup):
    name = State()
    country = State()
    city = State()
    hotel = State()
    check_in_date = State()
    check_out_date = State()
    nights = State()
    room_type = State()
    room_count = State()
    meal_type = State()
    transfer = State()
    insurance = State()
    additional_conditions = State()
    payment_deadline = State()


@router.callback_query(F.data == "tour_templates:menu")
async def templates_menu(callback: CallbackQuery, session_factory: async_sessionmaker) -> None:
    if callback.from_user.id not in config.allowed_telegram_ids:
        return
    async with session_factory() as session:
        templates = await crud.get_all_templates(session)
    if templates:
        await callback.message.edit_text(
            "Шаблоны туров:",
            reply_markup=templates_manage_kb(templates),
        )
    else:
        await callback.message.edit_text(
            "Шаблоны туров пока не созданы.",
            reply_markup=templates_manage_kb([]),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("tmpl_manage:"))
async def template_manage_action(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: async_sessionmaker,
) -> None:
    action = callback.data.split(":")[1]
    if action == "back":
        from bot.keyboards.common import main_menu_kb
        await callback.message.edit_text("Выберите действие:", reply_markup=main_menu_kb())
        await callback.answer()
        return
    if action == "new":
        await state.set_state(TourTemplateStates.name)
        await state.update_data(editing_id=None)
        await callback.message.edit_text(
            "Введите название шаблона (например: ОАЭ 2026):",
            reply_markup=cancel_kb(),
        )
        await callback.answer()
        return
    # action = template id
    template_id = int(action)
    async with session_factory() as session:
        template = await crud.get_template(session, template_id)
    if not template:
        await callback.answer("Шаблон не найден")
        return
    text = _format_template(template)
    await callback.message.edit_text(
        text,
        reply_markup=template_actions_kb(template_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("tmpl_action:"))
async def template_action(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: async_sessionmaker,
) -> None:
    parts = callback.data.split(":")
    if parts[1] == "back":
        async with session_factory() as session:
            templates = await crud.get_all_templates(session)
        await callback.message.edit_text("Шаблоны туров:", reply_markup=templates_manage_kb(templates))
        await callback.answer()
        return

    template_id, action = int(parts[1]), parts[2]

    if action == "delete":
        async with session_factory() as session:
            await crud.delete_template(session, template_id)
        async with session_factory() as session:
            templates = await crud.get_all_templates(session)
        await callback.message.edit_text(
            "Шаблон удалён. Шаблоны туров:",
            reply_markup=templates_manage_kb(templates),
        )
        await callback.answer()
        return

    if action == "edit":
        async with session_factory() as session:
            template = await crud.get_template(session, template_id)
        await state.set_state(TourTemplateStates.name)
        await state.update_data(editing_id=template_id)
        await callback.message.edit_text(
            f"Текущее название: {template.name}\nВведите новое (или отправьте то же):",
            reply_markup=cancel_kb(),
        )
        await callback.answer()


# ── Ввод полей шаблона ─────────────────────────────────────────────────────────

@router.message(TourTemplateStates.name)
async def tmpl_name(message: Message, state: FSMContext) -> None:
    await state.update_data(name=message.text.strip())
    await state.set_state(TourTemplateStates.country)
    await message.answer("Страна:")


@router.message(TourTemplateStates.country)
async def tmpl_country(message: Message, state: FSMContext) -> None:
    await state.update_data(country=message.text.strip())
    await state.set_state(TourTemplateStates.city)
    await message.answer("Город (или '-' если нет):")


@router.message(TourTemplateStates.city)
async def tmpl_city(message: Message, state: FSMContext) -> None:
    val = message.text.strip()
    await state.update_data(city=None if val == "-" else val)
    await state.set_state(TourTemplateStates.hotel)
    await message.answer("Отель:")


@router.message(TourTemplateStates.hotel)
async def tmpl_hotel(message: Message, state: FSMContext) -> None:
    await state.update_data(hotel=message.text.strip())
    await state.set_state(TourTemplateStates.check_in_date)
    await message.answer("Дата заезда (ДД.ММ.ГГГГ):")


@router.message(TourTemplateStates.check_in_date)
async def tmpl_checkin(message: Message, state: FSMContext) -> None:
    await state.update_data(check_in_date=message.text.strip())
    await state.set_state(TourTemplateStates.check_out_date)
    await message.answer("Дата выезда (ДД.ММ.ГГГГ):")


@router.message(TourTemplateStates.check_out_date)
async def tmpl_checkout(message: Message, state: FSMContext) -> None:
    await state.update_data(check_out_date=message.text.strip())
    await state.set_state(TourTemplateStates.nights)
    await message.answer("Количество ночей:")


@router.message(TourTemplateStates.nights)
async def tmpl_nights(message: Message, state: FSMContext) -> None:
    try:
        nights = int(message.text.strip())
    except ValueError:
        await message.answer("Введите число:")
        return
    await state.update_data(nights=nights)
    await state.set_state(TourTemplateStates.room_type)
    await message.answer("Тип номера:", reply_markup=room_type_kb())


@router.callback_query(F.data.startswith("room_type:"), TourTemplateStates.room_type)
async def tmpl_room_type(callback: CallbackQuery, state: FSMContext) -> None:
    val = callback.data.split(":", 1)[1]
    await state.update_data(room_type=val)
    await state.set_state(TourTemplateStates.room_count)
    await callback.message.edit_text("Количество номеров:", reply_markup=room_count_kb())
    await callback.answer()


@router.callback_query(F.data.startswith("room_count:"), TourTemplateStates.room_count)
async def tmpl_room_count(callback: CallbackQuery, state: FSMContext) -> None:
    val = callback.data.split(":", 1)[1]
    await state.update_data(room_count=val)
    await state.set_state(TourTemplateStates.meal_type)
    await callback.message.edit_text("Питание:", reply_markup=meal_type_kb())
    await callback.answer()


@router.callback_query(F.data.startswith("meal:"), TourTemplateStates.meal_type)
async def tmpl_meal(callback: CallbackQuery, state: FSMContext) -> None:
    val = callback.data.split(":", 1)[1]
    await state.update_data(meal_type=val)
    await state.set_state(TourTemplateStates.transfer)
    await callback.message.edit_text("Трансфер:", reply_markup=transfer_kb())
    await callback.answer()


@router.callback_query(F.data.startswith("transfer:"), TourTemplateStates.transfer)
async def tmpl_transfer(callback: CallbackQuery, state: FSMContext) -> None:
    val = callback.data.split(":", 1)[1]
    await state.update_data(transfer=val)
    await state.set_state(TourTemplateStates.insurance)
    await callback.message.edit_text("Страховка:", reply_markup=insurance_kb())
    await callback.answer()


@router.callback_query(F.data.startswith("insurance:"), TourTemplateStates.insurance)
async def tmpl_insurance(callback: CallbackQuery, state: FSMContext) -> None:
    val = callback.data.split(":", 1)[1] == "yes"
    await state.update_data(insurance=val)
    await state.set_state(TourTemplateStates.additional_conditions)
    await callback.message.edit_text("Дополнительные условия (или '-' если нет):")
    await callback.answer()


@router.message(TourTemplateStates.additional_conditions)
async def tmpl_additional(message: Message, state: FSMContext) -> None:
    val = message.text.strip()
    await state.update_data(additional_conditions=None if val == "-" else val)
    await state.set_state(TourTemplateStates.payment_deadline)
    await message.answer("Дата полной оплаты (ДД.ММ.ГГГГ):")


@router.message(TourTemplateStates.payment_deadline)
async def tmpl_payment_deadline(
    message: Message,
    state: FSMContext,
    session_factory: async_sessionmaker,
) -> None:
    await state.update_data(payment_deadline=message.text.strip())
    data = await state.get_data()
    editing_id = data.pop("editing_id", None)

    async with session_factory() as session:
        if editing_id:
            await crud.update_template(session, editing_id, data)
            text = "Шаблон обновлён."
        else:
            await crud.create_template(session, data, message.from_user.id)
            text = "Шаблон сохранён."
        templates = await crud.get_all_templates(session)

    await state.clear()
    await message.answer(text, reply_markup=templates_manage_kb(templates))


# ── Вспомогательные ────────────────────────────────────────────────────────────

def _format_template(t) -> str:
    insurance_str = "включена" if t.insurance else "нет"
    lines = [
        f"Шаблон: {t.name}",
        f"Страна: {t.country}" + (f", {t.city}" if t.city else ""),
        f"Отель: {t.hotel}",
        f"Заезд: {t.check_in_date} — {t.check_out_date} ({t.nights} н.)",
        f"Номер: {t.room_type}, {t.room_count}",
        f"Питание: {t.meal_type}",
        f"Трансфер: {t.transfer}",
        f"Страховка: {insurance_str}",
    ]
    if t.additional_conditions:
        lines.append(f"Доп. условия: {t.additional_conditions}")
    if t.payment_deadline:
        lines.append(f"Дата оплаты: {t.payment_deadline}")
    return "\n".join(lines)
