import asyncio
import re
from datetime import date

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.config import config
from bot.database import crud
from bot.keyboards.common import (
    after_generate_kb,
    cancel_kb,
    confirm_kb,
    date_kb,
    edit_individual_fields_kb,
    insurance_kb,
    meal_type_kb,
    number_kb,
    room_count_kb,
    room_type_kb,
    save_template_kb,
    templates_list_kb,
    tour_choice_kb,
    transfer_kb,
    yes_no_kb,
)
from bot.services import claude_service, document_service, gdrive_service
from bot.utils.album import collect_album_photos

router = Router()


class IndividualContract(StatesGroup):
    # Паспорт РФ
    ru_passport = State()
    # Загранпаспорт
    foreign_passport = State()
    # Контакты
    phone = State()
    email = State()
    # Проверка данных клиента
    confirm_client = State()
    edit_field_select = State()
    edit_field_value = State()
    # Туристы
    tourist_more = State()
    tourist_foreign = State()
    tourist_confirm = State()
    # Тур
    tour_choice = State()
    tour_select_saved = State()
    tour_country = State()
    tour_city = State()
    tour_hotel = State()
    tour_checkin = State()
    tour_checkout = State()
    tour_nights = State()
    tour_room_type = State()
    tour_room_count = State()
    tour_meal = State()
    tour_transfer = State()
    tour_insurance = State()
    tour_additional = State()
    tour_payment_deadline = State()
    tour_save_template = State()
    tour_template_name = State()
    # Финансы
    finance_total = State()
    finance_deposit = State()
    finance_payment_deadline = State()
    # Договор
    contract_date = State()
    contract_number_init = State()
    contract_number = State()
    # Готово
    after_generate = State()


# ── Вход ──────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "new_contract:individual")
async def start_individual(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.from_user.id not in config.allowed_telegram_ids:
        return
    await state.clear()
    await state.update_data(tourists=[])
    await state.set_state(IndividualContract.ru_passport)
    await callback.message.edit_text(
        "Договор физического лица\n\n"
        "Шаг 1/10: Пришлите фото паспорта РФ (основной разворот + прописка) "
        "или введите данные текстом в формате:\n"
        "ФИО\nСерия Номер\nКем выдан\nДата выдачи\nАдрес регистрации",
        reply_markup=cancel_kb(),
    )
    await callback.answer()


# ── Паспорт РФ ─────────────────────────────────────────────────────────────────

@router.message(IndividualContract.ru_passport, F.photo)
async def ru_passport_photo(message: Message, state: FSMContext, bot: Bot) -> None:
    pages = await collect_album_photos(message, state, bot)
    if pages is None:
        return
    await message.answer("Читаю паспорт...")
    try:
        passport = await claude_service.extract_ru_passport(pages)
    except Exception as e:
        await message.answer(f"Не удалось прочитать паспорт: {e}\nПопробуйте ещё раз или введите данные текстом.")
        return
    await state.update_data(ru_passport=passport)
    await _ask_foreign_passport(message, state)


@router.message(IndividualContract.ru_passport, F.document)
async def ru_passport_document(message: Message, state: FSMContext, bot: Bot) -> None:
    mime = (message.document.mime_type or "").lower()
    supported = ("image/jpeg", "image/jpg", "image/png", "image/webp", "application/pdf")
    if mime not in supported:
        await message.answer("Поддерживаются файлы JPEG, PNG и PDF.")
        return
    await message.answer("Читаю паспорт...")
    file = await bot.get_file(message.document.file_id)
    raw = await bot.download_file(file.file_path)
    img_bytes = raw.read()
    if mime == "application/pdf":
        pages = claude_service.pdf_to_jpegs(img_bytes)
        passport_input = pages
        media_type = "image/jpeg"
    else:
        passport_input = img_bytes
        media_type = "image/png" if mime == "image/png" else "image/jpeg"
    try:
        passport = await claude_service.extract_ru_passport(passport_input, media_type=media_type)
    except Exception as e:
        await message.answer(f"Не удалось прочитать паспорт: {e}\nВведите данные текстом.")
        return
    await state.update_data(ru_passport=passport)
    await _ask_foreign_passport(message, state)


@router.message(IndividualContract.ru_passport, F.text)
async def ru_passport_text(message: Message, state: FSMContext) -> None:
    lines = [l.strip() for l in message.text.strip().splitlines() if l.strip()]
    if len(lines) < 5:
        await message.answer(
            "Формат:\nФИО\nСерия Номер\nКем выдан\nДата выдачи\nАдрес регистрации"
        )
        return
    series_number = lines[1].split()
    passport = {
        "full_name": lines[0],
        "series": series_number[0] if series_number else "",
        "number": series_number[1] if len(series_number) > 1 else "",
        "issued_by": lines[2],
        "issue_date": lines[3],
        "registration_address": lines[4],
    }
    await state.update_data(ru_passport=passport)
    await _ask_foreign_passport(message, state)


async def _ask_foreign_passport(message: Message, state: FSMContext) -> None:
    await state.set_state(IndividualContract.foreign_passport)
    await message.answer(
        "Шаг 2/10: Пришлите фото загранпаспорта или введите данные текстом:\n"
        "Фамилия латиницей\nИмя латиницей\nНомер паспорта\nДата рождения (ДД.ММ.ГГГГ)\nСрок действия (ДД.ММ.ГГГГ)",
        reply_markup=cancel_kb(),
    )


# ── Загранпаспорт ──────────────────────────────────────────────────────────────

@router.message(IndividualContract.foreign_passport, F.photo)
async def foreign_passport_photo(message: Message, state: FSMContext, bot: Bot) -> None:
    pages = await collect_album_photos(message, state, bot)
    if pages is None:
        return
    await message.answer("Читаю загранпаспорт...")
    try:
        passport = await claude_service.extract_foreign_passport(pages[0])
    except Exception as e:
        await message.answer(f"Не удалось прочитать загранпаспорт: {e}\nВведите данные текстом.")
        return
    await state.update_data(foreign_passport=passport)
    await _ask_phone(message, state)


@router.message(IndividualContract.foreign_passport, F.document)
async def foreign_passport_document(message: Message, state: FSMContext, bot: Bot) -> None:
    mime = (message.document.mime_type or "").lower()
    supported = ("image/jpeg", "image/jpg", "image/png", "image/webp", "application/pdf")
    if mime not in supported:
        await message.answer("Поддерживаются файлы JPEG, PNG и PDF.")
        return
    await message.answer("Читаю загранпаспорт...")
    file = await bot.get_file(message.document.file_id)
    raw = await bot.download_file(file.file_path)
    img_bytes = raw.read()
    if mime == "application/pdf":
        img_bytes = claude_service.pdf_to_jpeg(img_bytes)
        media_type = "image/jpeg"
    else:
        media_type = "image/png" if mime == "image/png" else "image/jpeg"
    try:
        passport = await claude_service.extract_foreign_passport(img_bytes, media_type=media_type)
    except Exception as e:
        await message.answer(f"Не удалось прочитать загранпаспорт: {e}\nВведите данные текстом.")
        return
    await state.update_data(foreign_passport=passport)
    await _ask_phone(message, state)


@router.message(IndividualContract.foreign_passport, F.text)
async def foreign_passport_text(message: Message, state: FSMContext) -> None:
    lines = [l.strip() for l in message.text.strip().splitlines() if l.strip()]
    if len(lines) < 5:
        await message.answer(
            "Формат:\nФамилия латиницей\nИмя латиницей\nНомер\nДата рождения\nСрок действия"
        )
        return
    passport = {
        "surname_latin": lines[0],
        "name_latin": lines[1],
        "passport_number": lines[2],
        "date_of_birth": lines[3],
        "valid_until": lines[4],
    }
    await state.update_data(foreign_passport=passport)
    await _ask_phone(message, state)


async def _ask_phone(message: Message, state: FSMContext) -> None:
    await state.set_state(IndividualContract.phone)
    await message.answer("Шаг 3/10: Телефон клиента:", reply_markup=cancel_kb())


# ── Контакты ───────────────────────────────────────────────────────────────────

@router.message(IndividualContract.phone, F.text)
async def collect_phone(message: Message, state: FSMContext) -> None:
    await state.update_data(phone=message.text.strip())
    await state.set_state(IndividualContract.email)
    await message.answer("Email клиента:", reply_markup=cancel_kb())


@router.message(IndividualContract.email, F.text)
async def collect_email(message: Message, state: FSMContext) -> None:
    await state.update_data(email=message.text.strip())
    await _show_client_summary(message, state)


# ── Подтверждение данных клиента ───────────────────────────────────────────────

async def _show_client_summary(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    ru = data["ru_passport"]
    fg = data["foreign_passport"]
    text = (
        "Шаг 4/10: Проверьте данные клиента:\n\n"
        f"ФИО: {ru.get('full_name')}\n"
        f"Паспорт РФ: {ru.get('series')} {ru.get('number')}\n"
        f"Кем выдан: {ru.get('issued_by')}\n"
        f"Дата выдачи: {ru.get('issue_date')}\n"
        f"Адрес: {ru.get('registration_address')}\n\n"
        f"Загранпаспорт: {fg.get('surname_latin')} {fg.get('name_latin')}\n"
        f"Номер: {fg.get('passport_number')}\n"
        f"Дата рождения: {fg.get('date_of_birth')}\n"
        f"Действителен до: {fg.get('valid_until')}\n\n"
        f"Телефон: {data.get('phone')}\n"
        f"Email: {data.get('email')}"
    )
    await state.set_state(IndividualContract.confirm_client)
    await message.answer(text, reply_markup=confirm_kb())


@router.callback_query(F.data == "confirm:yes", IndividualContract.confirm_client)
async def client_confirmed(callback: CallbackQuery, state: FSMContext) -> None:
    await _ask_tourists(callback.message, state)
    await callback.answer()


@router.callback_query(F.data == "confirm:edit", IndividualContract.confirm_client)
async def client_edit(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(IndividualContract.edit_field_select)
    await callback.message.edit_text(
        "Выберите поле для исправления:",
        reply_markup=edit_individual_fields_kb(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("edit_field:"), IndividualContract.edit_field_select)
async def select_edit_field(callback: CallbackQuery, state: FSMContext) -> None:
    field = callback.data.split(":", 1)[1]
    if field == "done":
        await _show_client_summary_from_cb(callback, state)
        return
    await state.update_data(_edit_field=field)
    await state.set_state(IndividualContract.edit_field_value)
    await callback.message.edit_text(f"Введите новое значение для поля '{field}':")
    await callback.answer()


@router.message(IndividualContract.edit_field_value, F.text)
async def save_edit_field(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    field = data.get("_edit_field")
    ru_fields = {"full_name", "series", "number", "issued_by", "issue_date", "registration_address"}
    fg_fields = {"surname_latin", "name_latin", "passport_number", "date_of_birth", "valid_until"}
    contact_fields = {"phone", "email"}

    if field in ru_fields:
        ru = data["ru_passport"]
        ru[field] = message.text.strip()
        await state.update_data(ru_passport=ru)
    elif field in fg_fields:
        fg = data["foreign_passport"]
        fg[field] = message.text.strip()
        await state.update_data(foreign_passport=fg)
    elif field in contact_fields:
        await state.update_data(**{field: message.text.strip()})

    await state.set_state(IndividualContract.edit_field_select)
    await message.answer("Сохранено. Выберите ещё поле или нажмите 'Готово':", reply_markup=edit_individual_fields_kb())


async def _show_client_summary_from_cb(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    ru = data["ru_passport"]
    fg = data["foreign_passport"]
    text = (
        "Данные клиента:\n\n"
        f"ФИО: {ru.get('full_name')}\n"
        f"Паспорт РФ: {ru.get('series')} {ru.get('number')}\n"
        f"Кем выдан: {ru.get('issued_by')}\n"
        f"Дата выдачи: {ru.get('issue_date')}\n"
        f"Адрес: {ru.get('registration_address')}\n\n"
        f"Загранпаспорт: {fg.get('surname_latin')} {fg.get('name_latin')}\n"
        f"Номер: {fg.get('passport_number')}\n"
        f"Дата рождения: {fg.get('date_of_birth')}\n"
        f"Действителен до: {fg.get('valid_until')}\n\n"
        f"Телефон: {data.get('phone')}\n"
        f"Email: {data.get('email')}"
    )
    await state.set_state(IndividualContract.confirm_client)
    await callback.message.edit_text(text, reply_markup=confirm_kb())
    await callback.answer()


# ── Туристы ────────────────────────────────────────────────────────────────────

async def _ask_tourists(message: Message, state: FSMContext) -> None:
    """Заказчик уже включён в туристов первым."""
    data = await state.get_data()
    ru = data["ru_passport"]
    fg = data["foreign_passport"]
    main_tourist = {
        "full_name": ru.get("full_name"),
        "surname_latin": fg.get("surname_latin"),
        "name_latin": fg.get("name_latin"),
        "gender": fg.get("gender", ""),
        "passport_number": fg.get("passport_number"),
        "date_of_birth": fg.get("date_of_birth"),
        "valid_until": fg.get("valid_until"),
    }
    await state.update_data(tourists=[main_tourist])
    await state.set_state(IndividualContract.tourist_more)
    await message.answer(
        f"Шаг 5/10: Заказчик ({ru.get('full_name')}) включён в список туристов.\n\n"
        "Добавить ещё туриста?",
        reply_markup=yes_no_kb("tourist:add", "tourist:done"),
    )


@router.callback_query(F.data == "tourist:done", IndividualContract.tourist_more)
async def tourists_done(callback: CallbackQuery, state: FSMContext) -> None:
    await _ask_tour(callback.message, state)
    await callback.answer()


@router.callback_query(F.data == "tourist:add", IndividualContract.tourist_more)
async def tourist_add(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    if len(data.get("tourists", [])) >= 10:
        await callback.answer("Максимум 10 туристов")
        return
    await state.set_state(IndividualContract.tourist_foreign)
    await callback.message.edit_text(
        "Пришлите фото загранпаспорта туриста или введите данные текстом:\n"
        "Фамилия латиницей\nИмя латиницей\nНомер паспорта\nДата рождения\nСрок действия",
        reply_markup=cancel_kb(),
    )
    await callback.answer()


@router.message(IndividualContract.tourist_foreign, F.photo)
async def tourist_foreign_photo(message: Message, state: FSMContext, bot: Bot) -> None:
    pages = await collect_album_photos(message, state, bot)
    if pages is None:
        return
    await message.answer("Читаю загранпаспорт...")
    try:
        passport = await claude_service.extract_foreign_passport(pages[0])
    except Exception as e:
        await message.answer(f"Ошибка: {e}\nВведите данные текстом.")
        return
    await _save_tourist(message, state, passport)


@router.message(IndividualContract.tourist_foreign, F.document)
async def tourist_foreign_document(message: Message, state: FSMContext, bot: Bot) -> None:
    mime = (message.document.mime_type or "").lower()
    supported = ("image/jpeg", "image/jpg", "image/png", "image/webp", "application/pdf")
    if mime not in supported:
        await message.answer("Поддерживаются файлы JPEG, PNG и PDF.")
        return
    await message.answer("Читаю загранпаспорт...")
    file = await bot.get_file(message.document.file_id)
    raw = await bot.download_file(file.file_path)
    img_bytes = raw.read()
    if mime == "application/pdf":
        img_bytes = claude_service.pdf_to_jpeg(img_bytes)
        media_type = "image/jpeg"
    else:
        media_type = "image/png" if mime == "image/png" else "image/jpeg"
    try:
        passport = await claude_service.extract_foreign_passport(img_bytes, media_type=media_type)
    except Exception as e:
        await message.answer(f"Ошибка: {e}\nВведите данные текстом.")
        return
    await _save_tourist(message, state, passport)


@router.message(IndividualContract.tourist_foreign, F.text)
async def tourist_foreign_text(message: Message, state: FSMContext) -> None:
    lines = [l.strip() for l in message.text.strip().splitlines() if l.strip()]
    if len(lines) < 5:
        await message.answer("Нужно 5 строк: Фамилия / Имя / Номер / Дата рождения / Срок действия")
        return
    passport = {
        "surname_latin": lines[0],
        "name_latin": lines[1],
        "passport_number": lines[2],
        "date_of_birth": lines[3],
        "valid_until": lines[4],
        "full_name": f"{lines[0]} {lines[1]}",
    }
    await _save_tourist(message, state, passport)


async def _save_tourist(message: Message, state: FSMContext, passport: dict) -> None:
    data = await state.get_data()
    tourists = data.get("tourists", [])
    tourists.append(passport)
    await state.update_data(tourists=tourists)
    await state.set_state(IndividualContract.tourist_more)
    await message.answer(
        f"Турист добавлен: {passport.get('surname_latin')} {passport.get('name_latin')}\n"
        f"Итого туристов: {len(tourists)}\n\nДобавить ещё?",
        reply_markup=yes_no_kb("tourist:add", "tourist:done"),
    )


# ── Тур ────────────────────────────────────────────────────────────────────────

async def _ask_tour(message: Message, state: FSMContext) -> None:
    await state.set_state(IndividualContract.tour_choice)
    await message.answer("Шаг 6/10: Выбор тура:", reply_markup=tour_choice_kb())


@router.callback_query(F.data == "tour:saved", IndividualContract.tour_choice)
async def tour_from_saved(callback: CallbackQuery, state: FSMContext, session_factory: async_sessionmaker) -> None:
    async with session_factory() as session:
        templates = await crud.get_all_templates(session)
    if not templates:
        await callback.message.edit_text("Шаблонов нет. Создайте новый тур:", reply_markup=tour_choice_kb())
        await callback.answer()
        return
    await state.set_state(IndividualContract.tour_select_saved)
    await callback.message.edit_text("Выберите тур:", reply_markup=templates_list_kb(templates))
    await callback.answer()


@router.callback_query(F.data.startswith("tour_sel:"), IndividualContract.tour_select_saved)
async def tour_selected(callback: CallbackQuery, state: FSMContext, session_factory: async_sessionmaker) -> None:
    template_id = int(callback.data.split(":")[1])
    async with session_factory() as session:
        template = await crud.get_template(session, template_id)
    if not template:
        await callback.answer("Шаблон не найден")
        return
    tour_data = {
        "tour_template_id": template.id,
        "country": template.country,
        "city": template.city or "",
        "hotel": template.hotel,
        "check_in_date": template.check_in_date or "",
        "check_out_date": template.check_out_date or "",
        "nights": template.nights or 0,
        "room_type": template.room_type or "",
        "room_count": template.room_count or "1",
        "meal_type": template.meal_type or "",
        "transfer": template.transfer,
        "insurance": template.insurance,
        "additional_conditions": template.additional_conditions or "",
        "payment_deadline": template.payment_deadline or "",
    }
    await state.update_data(**tour_data)
    await _ask_finances(callback.message, state)
    await callback.answer()


@router.callback_query(F.data == "tour:new", IndividualContract.tour_choice)
async def tour_new(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(tour_template_id=None)
    await state.set_state(IndividualContract.tour_country)
    await callback.message.edit_text("Страна:", reply_markup=cancel_kb())
    await callback.answer()


@router.message(IndividualContract.tour_country, F.text)
async def tour_country(message: Message, state: FSMContext) -> None:
    await state.update_data(country=message.text.strip())
    await state.set_state(IndividualContract.tour_city)
    await message.answer("Город (или '-'):", reply_markup=cancel_kb())


@router.message(IndividualContract.tour_city, F.text)
async def tour_city(message: Message, state: FSMContext) -> None:
    val = message.text.strip()
    await state.update_data(city="" if val == "-" else val)
    await state.set_state(IndividualContract.tour_hotel)
    await message.answer("Отель:")


@router.message(IndividualContract.tour_hotel, F.text)
async def tour_hotel(message: Message, state: FSMContext) -> None:
    await state.update_data(hotel=message.text.strip())
    await state.set_state(IndividualContract.tour_checkin)
    await message.answer("Дата заезда (ДД.ММ.ГГГГ):")


@router.message(IndividualContract.tour_checkin, F.text)
async def tour_checkin(message: Message, state: FSMContext) -> None:
    await state.update_data(check_in_date=message.text.strip())
    await state.set_state(IndividualContract.tour_checkout)
    await message.answer("Дата выезда (ДД.ММ.ГГГГ):")


@router.message(IndividualContract.tour_checkout, F.text)
async def tour_checkout(message: Message, state: FSMContext) -> None:
    await state.update_data(check_out_date=message.text.strip())
    await state.set_state(IndividualContract.tour_nights)
    await message.answer("Количество ночей:")


@router.message(IndividualContract.tour_nights, F.text)
async def tour_nights(message: Message, state: FSMContext) -> None:
    try:
        await state.update_data(nights=int(message.text.strip()))
    except ValueError:
        await message.answer("Введите число:")
        return
    await state.set_state(IndividualContract.tour_room_type)
    await message.answer("Тип номера:", reply_markup=room_type_kb())


@router.callback_query(F.data.startswith("room_type:"), IndividualContract.tour_room_type)
async def tour_room_type(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(room_type=callback.data.split(":", 1)[1])
    await state.set_state(IndividualContract.tour_room_count)
    await callback.message.edit_text("Кол-во номеров:", reply_markup=room_count_kb())
    await callback.answer()


@router.callback_query(F.data.startswith("room_count:"), IndividualContract.tour_room_count)
async def tour_room_count(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(room_count=callback.data.split(":", 1)[1])
    await state.set_state(IndividualContract.tour_meal)
    await callback.message.edit_text("Питание:", reply_markup=meal_type_kb())
    await callback.answer()


@router.callback_query(F.data.startswith("meal:"), IndividualContract.tour_meal)
async def tour_meal(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(meal_type=callback.data.split(":", 1)[1])
    await state.set_state(IndividualContract.tour_transfer)
    await callback.message.edit_text("Трансфер:", reply_markup=transfer_kb())
    await callback.answer()


@router.callback_query(F.data.startswith("transfer:"), IndividualContract.tour_transfer)
async def tour_transfer(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(transfer=callback.data.split(":", 1)[1])
    await state.set_state(IndividualContract.tour_insurance)
    await callback.message.edit_text("Страховка:", reply_markup=insurance_kb())
    await callback.answer()


@router.callback_query(F.data.startswith("insurance:"), IndividualContract.tour_insurance)
async def tour_insurance(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(insurance=callback.data.split(":", 1)[1] == "yes")
    await state.set_state(IndividualContract.tour_additional)
    await callback.message.edit_text("Дополнительные условия (или '-'):")
    await callback.answer()


@router.message(IndividualContract.tour_additional, F.text)
async def tour_additional(message: Message, state: FSMContext) -> None:
    val = message.text.strip()
    await state.update_data(additional_conditions="" if val == "-" else val)
    await state.set_state(IndividualContract.tour_payment_deadline)
    await message.answer("Дата полной оплаты (ДД.ММ.ГГГГ):")


@router.message(IndividualContract.tour_payment_deadline, F.text)
async def tour_payment_deadline_handler(message: Message, state: FSMContext) -> None:
    await state.update_data(payment_deadline=message.text.strip())
    await state.set_state(IndividualContract.tour_save_template)
    await message.answer("Сохранить этот тур как шаблон?", reply_markup=save_template_kb())


@router.callback_query(F.data.startswith("save_tmpl:"), IndividualContract.tour_save_template)
async def tour_save_template(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.data == "save_tmpl:yes":
        await state.set_state(IndividualContract.tour_template_name)
        await callback.message.edit_text("Введите название шаблона (например: ОАЭ 2026):")
    else:
        await _ask_finances(callback.message, state)
    await callback.answer()


@router.message(IndividualContract.tour_template_name, F.text)
async def tour_template_name_handler(
    message: Message, state: FSMContext, session_factory: async_sessionmaker
) -> None:
    data = await state.get_data()
    template_data = {
        "name": message.text.strip(),
        "country": data.get("country", ""),
        "city": data.get("city"),
        "hotel": data.get("hotel", ""),
        "check_in_date": data.get("check_in_date"),
        "check_out_date": data.get("check_out_date"),
        "nights": data.get("nights"),
        "room_type": data.get("room_type"),
        "room_count": data.get("room_count"),
        "meal_type": data.get("meal_type"),
        "transfer": data.get("transfer", "нет"),
        "insurance": data.get("insurance", False),
        "additional_conditions": data.get("additional_conditions"),
        "payment_deadline": data.get("payment_deadline"),
    }
    async with session_factory() as session:
        template = await crud.create_template(session, template_data, message.from_user.id)
    await state.update_data(tour_template_id=template.id)
    await message.answer(f"Шаблон '{template.name}' сохранён.")
    await _ask_finances(message, state)


# ── Финансы ────────────────────────────────────────────────────────────────────

async def _ask_finances(message: Message, state: FSMContext) -> None:
    await state.set_state(IndividualContract.finance_total)
    await message.answer("Шаг 7/10: Общая стоимость тура (руб.):", reply_markup=cancel_kb())


def _parse_amount(text: str) -> float:
    text = text.strip().replace(" ", "").replace("\xa0", "")
    # "200.000" или "1.200.000" — точка как разделитель тысяч
    if re.match(r'^\d{1,3}(\.\d{3})+$', text):
        text = text.replace(".", "")
    else:
        text = text.replace(",", ".")
    return float(text)


@router.message(IndividualContract.finance_total, F.text)
async def finance_total(message: Message, state: FSMContext) -> None:
    try:
        total = _parse_amount(message.text)
    except ValueError:
        await message.answer("Введите число (например: 150000 или 200.000):")
        return
    await state.update_data(total_price=total)
    await state.set_state(IndividualContract.finance_deposit)
    await message.answer("Задаток (руб.):")


@router.message(IndividualContract.finance_deposit, F.text)
async def finance_deposit(message: Message, state: FSMContext) -> None:
    try:
        deposit = _parse_amount(message.text)
    except ValueError:
        await message.answer("Введите число:")
        return
    data = await state.get_data()
    total = data["total_price"]
    remaining = total - deposit
    await state.update_data(deposit=deposit, remaining=remaining)
    await state.set_state(IndividualContract.finance_payment_deadline)
    await message.answer(f"Доплата: {remaining:,.0f} руб.\nДата полной оплаты (ДД.ММ.ГГГГ):")


@router.message(IndividualContract.finance_payment_deadline, F.text)
async def finance_payment_deadline(message: Message, state: FSMContext) -> None:
    await state.update_data(finance_payment_deadline=message.text.strip())
    await _ask_contract_date(message, state)


# ── Дата и номер договора ──────────────────────────────────────────────────────

async def _ask_contract_date(message: Message, state: FSMContext) -> None:
    today = date.today().strftime("%d.%m.%Y")
    await state.update_data(contract_date=today)
    await state.set_state(IndividualContract.contract_date)
    await message.answer(
        f"Шаг 8/10: Дата договора:",
        reply_markup=date_kb(today),
    )


@router.callback_query(F.data == "date:keep", IndividualContract.contract_date)
async def date_keep(callback: CallbackQuery, state: FSMContext, session_factory: async_sessionmaker) -> None:
    await _ask_contract_number(callback.message, state, session_factory)
    await callback.answer()


@router.callback_query(F.data == "date:change", IndividualContract.contract_date)
async def date_change(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.message.edit_text("Введите дату договора (ДД.ММ.ГГГГ):")
    await callback.answer()


@router.message(IndividualContract.contract_date, F.text)
async def date_manual(message: Message, state: FSMContext, session_factory: async_sessionmaker) -> None:
    await state.update_data(contract_date=message.text.strip())
    await _ask_contract_number(message, state, session_factory)


async def _ask_contract_number(
    message: Message, state: FSMContext, session_factory: async_sessionmaker
) -> None:
    async with session_factory() as session:
        initialized = await crud.counter_initialized(session, "individual")

    if not initialized:
        await state.set_state(IndividualContract.contract_number_init)
        await message.answer(
            "Шаг 9/10: Первый договор физлица.\nС какого номера начать нумерацию?",
            reply_markup=cancel_kb(),
        )
        return

    async with session_factory() as session:
        number = await crud.get_next_number(session, "individual")

    await state.update_data(contract_number=str(number), _suggested_number=str(number))
    await state.set_state(IndividualContract.contract_number)
    await message.answer(
        f"Шаг 9/10: Номер договора:",
        reply_markup=number_kb(str(number)),
    )


@router.message(IndividualContract.contract_number_init, F.text)
async def contract_number_init(
    message: Message, state: FSMContext, session_factory: async_sessionmaker
) -> None:
    try:
        start = int(message.text.strip())
    except ValueError:
        await message.answer("Введите целое число:")
        return
    async with session_factory() as session:
        await crud.init_counter(session, "individual", start)
    await state.update_data(contract_number=str(start), _suggested_number=str(start))
    await state.set_state(IndividualContract.contract_number)
    await message.answer(
        f"Номер договора № {start}:",
        reply_markup=number_kb(str(start)),
    )


@router.callback_query(F.data == "number:keep", IndividualContract.contract_number)
async def number_keep(
    callback: CallbackQuery, state: FSMContext, session_factory: async_sessionmaker
) -> None:
    await _generate_contract(callback.message, state, session_factory, callback.from_user.id)
    await callback.answer()


@router.callback_query(F.data == "number:change", IndividualContract.contract_number)
async def number_change(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.message.edit_text("Введите номер договора:")
    await callback.answer()


@router.message(IndividualContract.contract_number, F.text)
async def number_manual(
    message: Message, state: FSMContext, session_factory: async_sessionmaker
) -> None:
    await state.update_data(contract_number=message.text.strip())
    await _generate_contract(message, state, session_factory, message.from_user.id)


# ── Генерация договора ─────────────────────────────────────────────────────────

async def _generate_contract(
    message: Message,
    state: FSMContext,
    session_factory: async_sessionmaker,
    telegram_id: int,
) -> None:
    await message.answer("Генерирую договор...")
    data = await state.get_data()
    number = data["contract_number"]
    ru = data["ru_passport"]

    try:
        pdf_bytes, docx_bytes = await asyncio.to_thread(document_service.generate_individual_contract, data)
    except Exception as e:
        await message.answer(f"Ошибка генерации документа: {e}")
        return

    if number == data.get("_suggested_number"):
        async with session_factory() as session:
            await crud.increment_counter(session, "individual")

    async with session_factory() as session:
        contract = await crud.save_contract(session, {
            "number": number,
            "contract_date": data.get("contract_date", ""),
            "client_name": ru.get("full_name", ""),
            "contract_type": "individual",
            "tour_template_id": data.get("tour_template_id"),
            "manager_telegram_id": telegram_id,
        })

    filename = document_service.format_individual_filename(number, ru.get("full_name", ""))
    await state.update_data(
        _contract_id=contract.id,
        _pdf_bytes=pdf_bytes,
        _docx_bytes=docx_bytes,
        _filename=filename,
        _tour_name=f"{data.get('country', '')} {data.get('check_in_date', '')[:4] if data.get('check_in_date') else ''}".strip(),
    )

    gdrive_ok = bool(config.google_credentials_json and config.gdrive_root_folder_id)
    await message.answer_document(
        BufferedInputFile(pdf_bytes, filename=f"{filename}.pdf"),
        caption=f"Договор № {number} готов.",
        reply_markup=after_generate_kb(gdrive_configured=gdrive_ok),
    )
    await state.set_state(IndividualContract.after_generate)


# ── После генерации ────────────────────────────────────────────────────────────

@router.callback_query(F.data == "gdrive:upload", IndividualContract.after_generate)
async def gdrive_upload(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: async_sessionmaker,
) -> None:
    data = await state.get_data()
    await callback.message.edit_reply_markup()
    await callback.message.answer("Загружаю на Google Drive...")
    try:
        file_id = gdrive_service.upload_contract(
            data["_pdf_bytes"],
            data["_filename"],
            data.get("_tour_name", "Прочие"),
        )
        async with session_factory() as session:
            await crud.update_gdrive_id(session, data["_contract_id"], file_id)
        await callback.message.answer("Файл загружен на Google Drive.")
    except Exception as e:
        await callback.message.answer(f"Ошибка загрузки: {e}")
    await state.clear()
    await callback.answer()


@router.callback_query(F.data == "gdrive:skip", IndividualContract.after_generate)
async def gdrive_skip(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.message.edit_reply_markup()
    await state.clear()
    from bot.keyboards.common import main_menu_kb
    await callback.message.answer("Готово. Выберите действие:", reply_markup=main_menu_kb())
    await callback.answer()


@router.callback_query(F.data == "get_docx", IndividualContract.after_generate)
async def get_docx(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    filename = data.get("_filename", "contract")
    await callback.message.answer_document(
        BufferedInputFile(data["_docx_bytes"], filename=f"{filename}.docx"),
        caption="DOCX для ручного редактирования",
    )
    await callback.answer()
