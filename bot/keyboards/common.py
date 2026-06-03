from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


# ── Главное меню ───────────────────────────────────────────────────────────────

def main_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Физическое лицо", callback_data="new_contract:individual"))
    builder.row(InlineKeyboardButton(text="Юридическое лицо", callback_data="new_contract:legal"))
    builder.row(InlineKeyboardButton(text="Шаблоны туров", callback_data="tour_templates:menu"))
    return builder.as_markup()


# ── Универсальные кнопки ───────────────────────────────────────────────────────

def confirm_kb(ok_text: str = "Данные верные", edit_text: str = "Внести изменения") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=ok_text, callback_data="confirm:yes"),
        InlineKeyboardButton(text=edit_text, callback_data="confirm:edit"),
    )
    return builder.as_markup()


def yes_no_kb(yes_cb: str = "yn:yes", no_cb: str = "yn:no") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Да", callback_data=yes_cb),
        InlineKeyboardButton(text="Нет", callback_data=no_cb),
    )
    return builder.as_markup()


def cancel_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Отмена", callback_data="cancel"))
    return builder.as_markup()


def back_cancel_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Назад", callback_data="go_back"),
        InlineKeyboardButton(text="Отмена", callback_data="cancel"),
    )
    return builder.as_markup()


# ── Тип ввода ──────────────────────────────────────────────────────────────────

def input_type_kb(photo_cb: str, text_cb: str) -> InlineKeyboardMarkup:
    """Фото или ввести текстом."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Отправить фото", callback_data=photo_cb),
        InlineKeyboardButton(text="Ввести текстом", callback_data=text_cb),
    )
    return builder.as_markup()


# ── Тур ───────────────────────────────────────────────────────────────────────

def tour_choice_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Из сохранённых", callback_data="tour:saved"))
    builder.row(InlineKeyboardButton(text="Создать новый", callback_data="tour:new"))
    return builder.as_markup()


def templates_list_kb(templates: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for t in templates:
        builder.row(InlineKeyboardButton(text=t.name, callback_data=f"tour_sel:{t.id}"))
    builder.row(InlineKeyboardButton(text="Отмена", callback_data="cancel"))
    return builder.as_markup()


def room_type_kb() -> InlineKeyboardMarkup:
    types = ["Одноместный", "Двухместный", "Стандартный", "Блочный", "Люкс", "Другой"]
    builder = InlineKeyboardBuilder()
    for t in types:
        builder.button(text=t, callback_data=f"room_type:{t}")
    builder.adjust(2)
    return builder.as_markup()


def room_count_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="1 номер", callback_data="room_count:1"),
        InlineKeyboardButton(text="½ (двухместное)", callback_data="room_count:½"),
    )
    return builder.as_markup()


def meal_type_kb() -> InlineKeyboardMarkup:
    types = ["BB (завтраки)", "HB (полупансион)", "FB (полный пансион)", "AI (всё включено)", "RO (без питания)"]
    builder = InlineKeyboardBuilder()
    for t in types:
        builder.button(text=t, callback_data=f"meal:{t}")
    builder.adjust(2)
    return builder.as_markup()


def transfer_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Нет", callback_data="transfer:нет"))
    builder.row(InlineKeyboardButton(text="Индивидуальный", callback_data="transfer:индивидуальный"))
    builder.row(InlineKeyboardButton(text="Групповой", callback_data="transfer:групповой"))
    return builder.as_markup()


def insurance_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Включена", callback_data="insurance:yes"),
        InlineKeyboardButton(text="Не включена", callback_data="insurance:no"),
    )
    return builder.as_markup()


def save_template_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Сохранить как шаблон", callback_data="save_tmpl:yes"),
        InlineKeyboardButton(text="Не сохранять", callback_data="save_tmpl:no"),
    )
    return builder.as_markup()


# ── Дата/номер договора ────────────────────────────────────────────────────────

def date_kb(current_date: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=f"Оставить {current_date}", callback_data="date:keep"),
        InlineKeyboardButton(text="Изменить", callback_data="date:change"),
    )
    return builder.as_markup()


def number_kb(current_number: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=f"№ {current_number}", callback_data="number:keep"),
        InlineKeyboardButton(text="Изменить", callback_data="number:change"),
    )
    return builder.as_markup()


# ── После генерации ────────────────────────────────────────────────────────────

def after_generate_kb(show_docx: bool = True) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Отправить на Google Drive", callback_data="gdrive:upload"))
    builder.row(InlineKeyboardButton(text="Пропустить", callback_data="gdrive:skip"))
    if show_docx:
        builder.row(InlineKeyboardButton(text="Получить DOCX для редактирования", callback_data="get_docx"))
    return builder.as_markup()


# ── Шаблоны туров ──────────────────────────────────────────────────────────────

def templates_manage_kb(templates: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for t in templates:
        builder.row(InlineKeyboardButton(text=t.name, callback_data=f"tmpl_manage:{t.id}"))
    builder.row(InlineKeyboardButton(text="Создать новый шаблон", callback_data="tmpl_manage:new"))
    builder.row(InlineKeyboardButton(text="Назад", callback_data="tmpl_manage:back"))
    return builder.as_markup()


def template_actions_kb(template_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Редактировать", callback_data=f"tmpl_action:{template_id}:edit"))
    builder.row(InlineKeyboardButton(text="Удалить", callback_data=f"tmpl_action:{template_id}:delete"))
    builder.row(InlineKeyboardButton(text="Назад", callback_data="tmpl_action:back"))
    return builder.as_markup()


# ── Редактирование поля клиента ────────────────────────────────────────────────

def edit_individual_fields_kb() -> InlineKeyboardMarkup:
    fields = [
        ("ФИО", "full_name"),
        ("Серия паспорта", "series"),
        ("Номер паспорта", "number"),
        ("Кем выдан", "issued_by"),
        ("Дата выдачи", "issue_date"),
        ("Адрес регистрации", "registration_address"),
        ("Фамилия (лат.)", "surname_latin"),
        ("Имя (лат.)", "name_latin"),
        ("Номер загранпаспорта", "passport_number"),
        ("Дата рождения", "date_of_birth"),
        ("Срок действия загранпаспорта", "valid_until"),
        ("Телефон", "phone"),
        ("Email", "email"),
    ]
    builder = InlineKeyboardBuilder()
    for label, key in fields:
        builder.button(text=label, callback_data=f"edit_field:{key}")
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="Готово", callback_data="edit_field:done"))
    return builder.as_markup()


def edit_legal_fields_kb() -> InlineKeyboardMarkup:
    fields = [
        ("Наименование", "company_name"),
        ("Правовая форма", "legal_form"),
        ("Директор", "director_name"),
        ("ИНН", "inn"),
        ("КПП", "kpp"),
        ("ОГРН", "ogrn"),
        ("Юр. адрес", "legal_address"),
        ("Почт. адрес", "postal_address"),
        ("Телефон", "phone"),
        ("Email", "email"),
        ("Банк", "bank_name"),
        ("Р/с", "bank_account"),
        ("К/с", "correspondent_account"),
        ("БИК", "bik"),
    ]
    builder = InlineKeyboardBuilder()
    for label, key in fields:
        builder.button(text=label, callback_data=f"edit_field:{key}")
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="Готово", callback_data="edit_field:done"))
    return builder.as_markup()
