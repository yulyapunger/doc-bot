import asyncio
from datetime import date

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.config import config
from bot.database import crud
from bot.keyboards.common import (
    add_back_row,
    after_generate_kb,
    back_cancel_kb,
    cancel_kb,
    confirm_kb,
    date_kb,
    edit_legal_fields_kb,
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
from bot.utils import navigation as nav
from bot.utils.album import collect_album_photos

router = Router()


class LegalContract(StatesGroup):
    # Карточка компании
    company_card = State()
    confirm_company = State()
    edit_field_select = State()
    edit_field_value = State()
    # Сотрудники
    employee_more = State()
    employee_passport = State()
    # Тур (аналогично физлицу)
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
    # Договор
    contract_date = State()
    contract_number_init = State()
    contract_number = State()
    # Готово
    after_generate = State()


# ── Вход ──────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "new_contract:legal")
async def start_legal(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.from_user.id not in config.allowed_telegram_ids:
        return
    await state.clear()
    await state.update_data(employees=[])
    await state.set_state(LegalContract.company_card)
    await callback.message.edit_text(
        "Договор юридического лица\n\n"
        "Шаг 1/8: Пришлите фото карточки компании или введите реквизиты текстом:\n"
        "Наименование\nПравовая форма\nДиректор\nИНН\nКПП\nОГРН\n"
        "Юр.адрес\nПочт.адрес\nТелефон\nEmail\nБанк\nР/с\nК/с\nБИК",
        reply_markup=cancel_kb(),
    )
    await callback.answer()


# ── Карточка компании ──────────────────────────────────────────────────────────

@router.message(LegalContract.company_card, F.photo)
async def company_card_photo(message: Message, state: FSMContext, bot: Bot) -> None:
    pages = await collect_album_photos(message, state, bot)
    if pages is None:
        return
    await message.answer("Читаю карточку компании...")
    try:
        company = await claude_service.extract_company_card(pages[0])
    except Exception as e:
        await message.answer(f"Не удалось прочитать карточку: {e}\nВведите данные текстом.")
        return
    await state.update_data(company=company)
    await _show_company_summary(message, state)


@router.message(LegalContract.company_card, F.document)
async def company_card_document(message: Message, state: FSMContext, bot: Bot) -> None:
    mime = (message.document.mime_type or "").lower()
    supported = ("image/jpeg", "image/jpg", "image/png", "image/webp", "application/pdf")
    if mime not in supported:
        await message.answer("Поддерживаются файлы JPEG, PNG и PDF.")
        return
    await message.answer("Читаю карточку компании...")
    file = await bot.get_file(message.document.file_id)
    raw = await bot.download_file(file.file_path)
    img_bytes = raw.read()
    if mime == "application/pdf":
        card_input = claude_service.pdf_to_jpegs(img_bytes)
        media_type = "image/jpeg"
    else:
        card_input = img_bytes
        media_type = "image/png" if mime == "image/png" else "image/jpeg"
    try:
        company = await claude_service.extract_company_card(card_input, media_type=media_type)
    except Exception as e:
        await message.answer(f"Не удалось прочитать карточку: {e}\nВведите данные текстом.")
        return
    await state.update_data(company=company)
    await _show_company_summary(message, state)


@router.message(LegalContract.company_card, F.text)
async def company_card_text(message: Message, state: FSMContext) -> None:
    try:
        company = await claude_service.extract_company_card(None, text=message.text)
    except Exception:
        lines = [l.strip() for l in message.text.strip().splitlines() if l.strip()]
        if len(lines) < 14:
            await message.answer("Нужно 14 строк. Пришлите фото или заполните все поля.")
            return
        company = {
            "company_name": lines[0],
            "legal_form": lines[1],
            "director_name": lines[2],
            "inn": lines[3],
            "kpp": lines[4],
            "ogrn": lines[5],
            "legal_address": lines[6],
            "postal_address": lines[7],
            "phone": lines[8],
            "email": lines[9],
            "bank_name": lines[10],
            "bank_account": lines[11],
            "correspondent_account": lines[12],
            "bik": lines[13],
        }
    await state.update_data(company=company)
    await _show_company_summary(message, state)


async def _show_company_summary(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    c = data["company"]
    text = (
        "Шаг 2/8: Проверьте данные компании:\n\n"
        f"Наименование: {c.get('company_name')}\n"
        f"Правовая форма: {c.get('legal_form')}\n"
        f"Директор: {c.get('director_name')}\n"
        f"ИНН: {c.get('inn')}\n"
        f"КПП: {c.get('kpp')}\n"
        f"ОГРН: {c.get('ogrn')}\n"
        f"Юр. адрес: {c.get('legal_address')}\n"
        f"Почт. адрес: {c.get('postal_address')}\n"
        f"Телефон: {c.get('phone')}\n"
        f"Email: {c.get('email')}\n"
        f"Банк: {c.get('bank_name')}\n"
        f"Р/с: {c.get('bank_account')}\n"
        f"К/с: {c.get('correspondent_account')}\n"
        f"БИК: {c.get('bik')}"
    )
    await nav.advance(state, LegalContract.confirm_company)
    await message.answer(text, reply_markup=add_back_row(confirm_kb()))


@router.callback_query(F.data == "confirm:yes", LegalContract.confirm_company)
async def company_confirmed(callback: CallbackQuery, state: FSMContext) -> None:
    await _ask_employees(callback.message, state)
    await callback.answer()


@router.callback_query(F.data == "confirm:edit", LegalContract.confirm_company)
async def company_edit(callback: CallbackQuery, state: FSMContext) -> None:
    await nav.advance(state, LegalContract.edit_field_select)
    await callback.message.edit_text("Выберите поле:", reply_markup=add_back_row(edit_legal_fields_kb()))
    await callback.answer()


@router.callback_query(F.data.startswith("edit_field:"), LegalContract.edit_field_select)
async def select_edit_field(callback: CallbackQuery, state: FSMContext) -> None:
    field = callback.data.split(":", 1)[1]
    if field == "done":
        await _show_company_summary_from_cb(callback, state)
        return
    await state.update_data(_edit_field=field)
    await nav.advance(state, LegalContract.edit_field_value)
    await callback.message.edit_text(f"Введите новое значение для '{field}':", reply_markup=back_cancel_kb())
    await callback.answer()


@router.message(LegalContract.edit_field_value, F.text)
async def save_edit_field(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    field = data.get("_edit_field")
    company = data["company"]
    company[field] = message.text.strip()
    await state.update_data(company=company)
    await state.set_state(LegalContract.edit_field_select)
    await message.answer("Сохранено. Выберите ещё поле или 'Готово':", reply_markup=add_back_row(edit_legal_fields_kb()))


async def _show_company_summary_from_cb(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    c = data["company"]
    text = (
        "Данные компании:\n\n"
        f"{c.get('company_name')} ({c.get('legal_form')})\n"
        f"Директор: {c.get('director_name')}\n"
        f"ИНН: {c.get('inn')} / КПП: {c.get('kpp')} / ОГРН: {c.get('ogrn')}\n"
        f"Адрес: {c.get('legal_address')}\n"
        f"Телефон: {c.get('phone')} / Email: {c.get('email')}"
    )
    await state.set_state(LegalContract.confirm_company)
    await callback.message.edit_text(text, reply_markup=add_back_row(confirm_kb()))
    await callback.answer()


# ── Сотрудники ──────────────────────────────────────────────────────────────────

async def _ask_employees(message: Message, state: FSMContext) -> None:
    await nav.advance(state, LegalContract.employee_more)
    await message.answer(
        "Шаг 3/8: Добавьте приезжающих лиц (сотрудников).\n"
        "Пришлите фото загранпаспорта или введите текстом:\n"
        "Фамилия латиницей\nИмя латиницей\nДата рождения\nНомер паспорта\nДата выдачи\nСрок действия",
        reply_markup=add_back_row(yes_no_kb("emp:add", "emp:done")),
    )


@router.callback_query(F.data == "emp:add", LegalContract.employee_more)
async def employee_add(callback: CallbackQuery, state: FSMContext) -> None:
    await nav.advance(state, LegalContract.employee_passport)
    await callback.message.edit_text(
        "Пришлите фото загранпаспорта сотрудника или введите данные:\n"
        "Фамилия (лат.)\nИмя (лат.)\nДата рождения (ДД.ММ.ГГГГ)\nНомер паспорта\nДата выдачи (ДД.ММ.ГГГГ)\nСрок действия (ДД.ММ.ГГГГ)",
        reply_markup=back_cancel_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "emp:done", LegalContract.employee_more)
async def employees_done(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    if not data.get("employees"):
        await callback.answer("Добавьте хотя бы одного сотрудника", show_alert=True)
        return
    await _ask_tour_legal(callback.message, state)
    await callback.answer()


@router.message(LegalContract.employee_passport, F.photo)
async def employee_photo(message: Message, state: FSMContext, bot: Bot) -> None:
    pages = await collect_album_photos(message, state, bot)
    if pages is None:
        return
    await message.answer("Читаю загранпаспорт...")
    try:
        passport = await claude_service.extract_foreign_passport(pages[0])
    except Exception as e:
        await message.answer(f"Ошибка: {e}\nВведите данные текстом.")
        return
    await _save_employee(message, state, passport)


@router.message(LegalContract.employee_passport, F.document)
async def employee_document(message: Message, state: FSMContext, bot: Bot) -> None:
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
    await _save_employee(message, state, passport)


@router.message(LegalContract.employee_passport, F.text)
async def employee_text(message: Message, state: FSMContext) -> None:
    lines = [l.strip() for l in message.text.strip().splitlines() if l.strip()]
    if len(lines) < 6:
        await message.answer("Нужно 6 строк: Фамилия / Имя / Дата рожд. / Номер / Дата выдачи / Срок действия")
        return
    passport = {
        "surname_latin": lines[0],
        "name_latin": lines[1],
        "date_of_birth": lines[2],
        "passport_number": lines[3],
        "issue_date": lines[4],
        "valid_until": lines[5],
    }
    await _save_employee(message, state, passport)


async def _save_employee(message: Message, state: FSMContext, passport: dict) -> None:
    data = await state.get_data()
    employees = data.get("employees", [])
    employees.append(passport)
    await state.update_data(employees=employees)
    await state.set_state(LegalContract.employee_more)
    await message.answer(
        f"Сотрудник добавлен: {passport.get('surname_latin')} {passport.get('name_latin')}\n"
        f"Всего: {len(employees)}\n\nДобавить ещё?",
        reply_markup=add_back_row(yes_no_kb("emp:add", "emp:done")),
    )


# ── Тур (аналогично физлицу) ───────────────────────────────────────────────────

async def _ask_tour_legal(message: Message, state: FSMContext) -> None:
    await nav.advance(state, LegalContract.tour_choice)
    await message.answer("Шаг 4/8: Выбор тура:", reply_markup=add_back_row(tour_choice_kb()))


@router.callback_query(F.data == "tour:saved", LegalContract.tour_choice)
async def tour_from_saved(callback: CallbackQuery, state: FSMContext, session_factory: async_sessionmaker) -> None:
    async with session_factory() as session:
        templates = await crud.get_all_templates(session)
    if not templates:
        await callback.message.edit_text("Шаблонов нет.", reply_markup=add_back_row(tour_choice_kb()))
        await callback.answer()
        return
    await nav.advance(state, LegalContract.tour_select_saved)
    await callback.message.edit_text("Выберите тур:", reply_markup=add_back_row(templates_list_kb(templates)))
    await callback.answer()


@router.callback_query(F.data.startswith("tour_sel:"), LegalContract.tour_select_saved)
async def tour_selected(callback: CallbackQuery, state: FSMContext, session_factory: async_sessionmaker) -> None:
    template_id = int(callback.data.split(":")[1])
    async with session_factory() as session:
        template = await crud.get_template(session, template_id)
    if not template:
        await callback.answer("Не найден")
        return
    await state.update_data(
        tour_template_id=template.id,
        country=template.country,
        city=template.city or "",
        hotel=template.hotel,
        check_in_date=template.check_in_date or "",
        check_out_date=template.check_out_date or "",
        nights=template.nights or 0,
        room_type=template.room_type or "",
        room_count=template.room_count or "1",
        meal_type=template.meal_type or "",
        transfer=template.transfer,
        insurance=template.insurance,
        additional_conditions=template.additional_conditions or "",
        payment_deadline=template.payment_deadline or "",
    )
    await _ask_finances_legal(callback.message, state)
    await callback.answer()


@router.callback_query(F.data == "tour:new", LegalContract.tour_choice)
async def tour_new(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(tour_template_id=None)
    await nav.advance(state, LegalContract.tour_country)
    await callback.message.edit_text("Страна:", reply_markup=back_cancel_kb())
    await callback.answer()


@router.message(LegalContract.tour_country, F.text)
async def tour_country(message: Message, state: FSMContext) -> None:
    await state.update_data(country=message.text.strip())
    await nav.advance(state, LegalContract.tour_city)
    await message.answer("Город (или '-'):", reply_markup=back_cancel_kb())


@router.message(LegalContract.tour_city, F.text)
async def tour_city(message: Message, state: FSMContext) -> None:
    val = message.text.strip()
    await state.update_data(city="" if val == "-" else val)
    await nav.advance(state, LegalContract.tour_hotel)
    await message.answer("Отель:", reply_markup=back_cancel_kb())


@router.message(LegalContract.tour_hotel, F.text)
async def tour_hotel(message: Message, state: FSMContext) -> None:
    await state.update_data(hotel=message.text.strip())
    await nav.advance(state, LegalContract.tour_checkin)
    await message.answer("Дата заезда (ДД.ММ.ГГГГ):", reply_markup=back_cancel_kb())


@router.message(LegalContract.tour_checkin, F.text)
async def tour_checkin(message: Message, state: FSMContext) -> None:
    await state.update_data(check_in_date=message.text.strip())
    await nav.advance(state, LegalContract.tour_checkout)
    await message.answer("Дата выезда (ДД.ММ.ГГГГ):", reply_markup=back_cancel_kb())


@router.message(LegalContract.tour_checkout, F.text)
async def tour_checkout(message: Message, state: FSMContext) -> None:
    await state.update_data(check_out_date=message.text.strip())
    await nav.advance(state, LegalContract.tour_nights)
    await message.answer("Количество ночей:", reply_markup=back_cancel_kb())


@router.message(LegalContract.tour_nights, F.text)
async def tour_nights(message: Message, state: FSMContext) -> None:
    try:
        await state.update_data(nights=int(message.text.strip()))
    except ValueError:
        await message.answer("Введите число:")
        return
    await nav.advance(state, LegalContract.tour_room_type)
    await message.answer("Тип номера:", reply_markup=add_back_row(room_type_kb()))


@router.callback_query(F.data.startswith("room_type:"), LegalContract.tour_room_type)
async def tour_room_type(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(room_type=callback.data.split(":", 1)[1])
    await nav.advance(state, LegalContract.tour_room_count)
    await callback.message.edit_text("Кол-во номеров:", reply_markup=add_back_row(room_count_kb()))
    await callback.answer()


@router.callback_query(F.data.startswith("room_count:"), LegalContract.tour_room_count)
async def tour_room_count(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(room_count=callback.data.split(":", 1)[1])
    await nav.advance(state, LegalContract.tour_meal)
    await callback.message.edit_text("Питание:", reply_markup=add_back_row(meal_type_kb()))
    await callback.answer()


@router.callback_query(F.data.startswith("meal:"), LegalContract.tour_meal)
async def tour_meal(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(meal_type=callback.data.split(":", 1)[1])
    await nav.advance(state, LegalContract.tour_transfer)
    await callback.message.edit_text("Трансфер:", reply_markup=add_back_row(transfer_kb()))
    await callback.answer()


@router.callback_query(F.data.startswith("transfer:"), LegalContract.tour_transfer)
async def tour_transfer(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(transfer=callback.data.split(":", 1)[1])
    await nav.advance(state, LegalContract.tour_insurance)
    await callback.message.edit_text("Страховка:", reply_markup=add_back_row(insurance_kb()))
    await callback.answer()


@router.callback_query(F.data.startswith("insurance:"), LegalContract.tour_insurance)
async def tour_insurance(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(insurance=callback.data.split(":", 1)[1] == "yes")
    await nav.advance(state, LegalContract.tour_additional)
    await callback.message.edit_text("Дополнительные условия (или '-'):", reply_markup=back_cancel_kb())
    await callback.answer()


@router.message(LegalContract.tour_additional, F.text)
async def tour_additional(message: Message, state: FSMContext) -> None:
    val = message.text.strip()
    await state.update_data(additional_conditions="" if val == "-" else val)
    await nav.advance(state, LegalContract.tour_payment_deadline)
    await message.answer("Дата полной оплаты (ДД.ММ.ГГГГ):", reply_markup=back_cancel_kb())


@router.message(LegalContract.tour_payment_deadline, F.text)
async def tour_payment_deadline_handler(message: Message, state: FSMContext) -> None:
    await state.update_data(payment_deadline=message.text.strip())
    await nav.advance(state, LegalContract.tour_save_template)
    await message.answer("Сохранить тур как шаблон?", reply_markup=add_back_row(save_template_kb()))


@router.callback_query(F.data.startswith("save_tmpl:"), LegalContract.tour_save_template)
async def tour_save_template(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.data == "save_tmpl:yes":
        await nav.advance(state, LegalContract.tour_template_name)
        await callback.message.edit_text("Введите название шаблона:", reply_markup=back_cancel_kb())
    else:
        await _ask_finances_legal(callback.message, state)
    await callback.answer()


@router.message(LegalContract.tour_template_name, F.text)
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
    await _ask_finances_legal(message, state)


# ── Финансы (юрлицо: полная оплата в течение 3 банковских дней) ───────────────

async def _ask_finances_legal(message: Message, state: FSMContext) -> None:
    await nav.advance(state, LegalContract.finance_total)
    await message.answer(
        "Шаг 5/8: Итоговая сумма по договору (руб.):\n"
        "(Оплата производится в течение 3 банковских дней)",
        reply_markup=back_cancel_kb(),
    )


@router.message(LegalContract.finance_total, F.text)
async def finance_total(message: Message, state: FSMContext) -> None:
    try:
        total = float(message.text.strip().replace(" ", "").replace(",", "."))
    except ValueError:
        await message.answer("Введите число:")
        return
    await state.update_data(total_price=total)
    await _ask_contract_date_legal(message, state)


# ── Дата и номер договора ──────────────────────────────────────────────────────

async def _ask_contract_date_legal(message: Message, state: FSMContext) -> None:
    today = date.today().strftime("%d.%m.%Y")
    await state.update_data(contract_date=today)
    await nav.advance(state, LegalContract.contract_date)
    await message.answer("Шаг 6/8: Дата договора:", reply_markup=add_back_row(date_kb(today)))


@router.callback_query(F.data == "date:keep", LegalContract.contract_date)
async def date_keep(callback: CallbackQuery, state: FSMContext, session_factory: async_sessionmaker) -> None:
    await _ask_contract_number_legal(callback.message, state, session_factory)
    await callback.answer()


@router.callback_query(F.data == "date:change", LegalContract.contract_date)
async def date_change(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.message.edit_text("Введите дату договора (ДД.ММ.ГГГГ):", reply_markup=back_cancel_kb())
    await callback.answer()


@router.message(LegalContract.contract_date, F.text)
async def date_manual(message: Message, state: FSMContext, session_factory: async_sessionmaker) -> None:
    await state.update_data(contract_date=message.text.strip())
    await _ask_contract_number_legal(message, state, session_factory)


async def _ask_contract_number_legal(
    message: Message, state: FSMContext, session_factory: async_sessionmaker
) -> None:
    async with session_factory() as session:
        initialized = await crud.counter_initialized(session, "legal")

    if not initialized:
        await nav.advance(state, LegalContract.contract_number_init)
        await message.answer(
            "Шаг 7/8: Первый договор юрлица.\nС какого номера начать нумерацию?",
            reply_markup=back_cancel_kb(),
        )
        return

    async with session_factory() as session:
        number = await crud.get_next_number(session, "legal")
    formatted = f"{number}/кор"
    await state.update_data(contract_number=formatted, _suggested_number=formatted)
    await nav.advance(state, LegalContract.contract_number)
    await message.answer("Шаг 7/8: Номер договора:", reply_markup=add_back_row(number_kb(formatted)))


@router.message(LegalContract.contract_number_init, F.text)
async def contract_number_init(
    message: Message, state: FSMContext, session_factory: async_sessionmaker
) -> None:
    try:
        start = int(message.text.strip())
    except ValueError:
        await message.answer("Введите целое число:")
        return
    async with session_factory() as session:
        await crud.init_counter(session, "legal", start)
    formatted = f"{start}/кор"
    await state.update_data(contract_number=formatted, _suggested_number=formatted)
    await nav.advance(state, LegalContract.contract_number)
    await message.answer(f"Номер договора № {formatted}:", reply_markup=add_back_row(number_kb(formatted)))


@router.callback_query(F.data == "number:keep", LegalContract.contract_number)
async def number_keep(
    callback: CallbackQuery, state: FSMContext, session_factory: async_sessionmaker
) -> None:
    await _generate_legal_contract(callback.message, state, session_factory, callback.from_user.id)
    await callback.answer()


@router.callback_query(F.data == "number:change", LegalContract.contract_number)
async def number_change(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.message.edit_text("Введите номер договора (например: 45/кор):", reply_markup=back_cancel_kb())
    await callback.answer()


@router.message(LegalContract.contract_number, F.text)
async def number_manual(
    message: Message, state: FSMContext, session_factory: async_sessionmaker
) -> None:
    await state.update_data(contract_number=message.text.strip())
    await _generate_legal_contract(message, state, session_factory, message.from_user.id)


# ── Генерация договора ─────────────────────────────────────────────────────────

async def _generate_legal_contract(
    message: Message,
    state: FSMContext,
    session_factory: async_sessionmaker,
    telegram_id: int,
) -> None:
    await message.answer("Генерирую договор...")
    data = await state.get_data()
    c = data["company"]
    number = data["contract_number"]

    try:
        pdf_bytes, docx_bytes = await asyncio.to_thread(document_service.generate_legal_contract, data)
    except Exception as e:
        await message.answer(f"Ошибка генерации: {e}")
        return

    if number == data.get("_suggested_number"):
        async with session_factory() as session:
            await crud.increment_counter(session, "legal")

    async with session_factory() as session:
        contract = await crud.save_contract(session, {
            "number": number,
            "contract_date": data.get("contract_date", ""),
            "client_name": c.get("company_name", ""),
            "contract_type": "legal",
            "tour_template_id": data.get("tour_template_id"),
            "manager_telegram_id": telegram_id,
        })

    filename = document_service.format_legal_filename(number, c.get("company_name", ""))
    await state.update_data(
        _contract_id=contract.id,
        _pdf_bytes=pdf_bytes,
        _docx_bytes=docx_bytes,
        _filename=filename,
        _tour_name=f"{data.get('country', '')} {data.get('check_in_date', '')[:4] if data.get('check_in_date') else ''}".strip(),
    )

    await message.answer_document(
        BufferedInputFile(pdf_bytes, filename=f"{filename}.pdf"),
        caption=f"Договор № {number} готов.",
        reply_markup=after_generate_kb(),
    )
    await state.set_state(LegalContract.after_generate)


# ── После генерации ────────────────────────────────────────────────────────────

@router.callback_query(F.data == "gdrive:upload", LegalContract.after_generate)
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
        await callback.message.answer("Загружено.")
    except Exception as e:
        await callback.message.answer(f"Ошибка: {e}")
    await state.clear()
    await callback.answer()


@router.callback_query(F.data == "gdrive:skip", LegalContract.after_generate)
async def gdrive_skip(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.message.edit_reply_markup()
    await state.clear()
    from bot.keyboards.common import main_menu_kb
    await callback.message.answer("Готово. Выберите действие:", reply_markup=main_menu_kb())
    await callback.answer()


@router.callback_query(F.data == "get_docx", LegalContract.after_generate)
async def get_docx(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    filename = data.get("_filename", "contract")
    await callback.message.answer_document(
        BufferedInputFile(data["_docx_bytes"], filename=f"{filename}.docx"),
    )
    await callback.answer()


# ── Рендереры для кнопки "Назад" ───────────────────────────────────────────────

def _prompt(text, kb_factory=back_cancel_kb):
    """Фабрика рендереров для простых текстовых шагов."""
    async def _render(message: Message, state: FSMContext, session_factory: async_sessionmaker = None) -> None:
        if callable(text):
            data = await state.get_data()
            value = text(data)
        else:
            value = text
        await message.answer(value, reply_markup=kb_factory())
    return _render


async def _render_confirm_company(message: Message, state: FSMContext, session_factory: async_sessionmaker = None) -> None:
    data = await state.get_data()
    c = data["company"]
    text = (
        "Шаг 2/8: Проверьте данные компании:\n\n"
        f"Наименование: {c.get('company_name')}\n"
        f"Правовая форма: {c.get('legal_form')}\n"
        f"Директор: {c.get('director_name')}\n"
        f"ИНН: {c.get('inn')}\n"
        f"КПП: {c.get('kpp')}\n"
        f"ОГРН: {c.get('ogrn')}\n"
        f"Юр. адрес: {c.get('legal_address')}\n"
        f"Почт. адрес: {c.get('postal_address')}\n"
        f"Телефон: {c.get('phone')}\n"
        f"Email: {c.get('email')}\n"
        f"Банк: {c.get('bank_name')}\n"
        f"Р/с: {c.get('bank_account')}\n"
        f"К/с: {c.get('correspondent_account')}\n"
        f"БИК: {c.get('bik')}"
    )
    await message.answer(text, reply_markup=add_back_row(confirm_kb()))


async def _render_employee_more(message: Message, state: FSMContext, session_factory: async_sessionmaker = None) -> None:
    data = await state.get_data()
    employees = data.get("employees", [])
    await message.answer(
        f"Сотрудников в списке: {len(employees)}\n\nДобавить ещё?",
        reply_markup=add_back_row(yes_no_kb("emp:add", "emp:done")),
    )


async def _render_tour_select_saved(message: Message, state: FSMContext, session_factory: async_sessionmaker = None) -> None:
    async with session_factory() as session:
        templates = await crud.get_all_templates(session)
    await message.answer("Выберите тур:", reply_markup=add_back_row(templates_list_kb(templates)))


async def _render_contract_date(message: Message, state: FSMContext, session_factory: async_sessionmaker = None) -> None:
    data = await state.get_data()
    current = data.get("contract_date") or date.today().strftime("%d.%m.%Y")
    await message.answer("Шаг 6/8: Дата договора:", reply_markup=add_back_row(date_kb(current)))


async def _render_contract_number(message: Message, state: FSMContext, session_factory: async_sessionmaker = None) -> None:
    data = await state.get_data()
    number = data.get("contract_number") or data.get("_suggested_number", "")
    await message.answer("Шаг 7/8: Номер договора:", reply_markup=add_back_row(number_kb(number)))


STATE_RENDERERS = {
    LegalContract.confirm_company.state: _render_confirm_company,
    LegalContract.edit_field_select.state: _prompt(
        "Выберите поле:", lambda: add_back_row(edit_legal_fields_kb())
    ),
    LegalContract.edit_field_value.state: _prompt(
        lambda d: f"Введите новое значение для '{d.get('_edit_field')}':"
    ),
    LegalContract.employee_more.state: _render_employee_more,
    LegalContract.employee_passport.state: _prompt(
        "Пришлите фото загранпаспорта сотрудника или введите данные:\n"
        "Фамилия (лат.)\nИмя (лат.)\nДата рождения (ДД.ММ.ГГГГ)\nНомер паспорта\nДата выдачи (ДД.ММ.ГГГГ)\nСрок действия (ДД.ММ.ГГГГ)"
    ),
    LegalContract.tour_choice.state: _prompt(
        "Шаг 4/8: Выбор тура:", lambda: add_back_row(tour_choice_kb())
    ),
    LegalContract.tour_select_saved.state: _render_tour_select_saved,
    LegalContract.tour_country.state: _prompt("Страна:"),
    LegalContract.tour_city.state: _prompt("Город (или '-'):"),
    LegalContract.tour_hotel.state: _prompt("Отель:"),
    LegalContract.tour_checkin.state: _prompt("Дата заезда (ДД.ММ.ГГГГ):"),
    LegalContract.tour_checkout.state: _prompt("Дата выезда (ДД.ММ.ГГГГ):"),
    LegalContract.tour_nights.state: _prompt("Количество ночей:"),
    LegalContract.tour_room_type.state: _prompt(
        "Тип номера:", lambda: add_back_row(room_type_kb())
    ),
    LegalContract.tour_room_count.state: _prompt(
        "Кол-во номеров:", lambda: add_back_row(room_count_kb())
    ),
    LegalContract.tour_meal.state: _prompt(
        "Питание:", lambda: add_back_row(meal_type_kb())
    ),
    LegalContract.tour_transfer.state: _prompt(
        "Трансфер:", lambda: add_back_row(transfer_kb())
    ),
    LegalContract.tour_insurance.state: _prompt(
        "Страховка:", lambda: add_back_row(insurance_kb())
    ),
    LegalContract.tour_additional.state: _prompt("Дополнительные условия (или '-'):"),
    LegalContract.tour_payment_deadline.state: _prompt("Дата полной оплаты (ДД.ММ.ГГГГ):"),
    LegalContract.tour_save_template.state: _prompt(
        "Сохранить тур как шаблон?", lambda: add_back_row(save_template_kb())
    ),
    LegalContract.tour_template_name.state: _prompt("Введите название шаблона:"),
    LegalContract.finance_total.state: _prompt(
        "Шаг 5/8: Итоговая сумма по договору (руб.):\n"
        "(Оплата производится в течение 3 банковских дней)"
    ),
    LegalContract.contract_date.state: _render_contract_date,
    LegalContract.contract_number_init.state: _prompt(
        "Шаг 7/8: Первый договор юрлица.\nС какого номера начать нумерацию?"
    ),
    LegalContract.contract_number.state: _render_contract_number,
}
