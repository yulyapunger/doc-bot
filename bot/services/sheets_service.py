import json
import logging
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from google.oauth2.credentials import Credentials
from google.oauth2.service_account import Credentials as ServiceCredentials
from googleapiclient.discovery import build

from bot.config import config

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]

HEADER = [
    "Ф.И.О. (загранпаспорт)",   # A — individual
    "№ договора",               # B — merged
    "Телефон",                  # C — merged
    "Email",                    # D — merged
    "Дата полной оплаты",       # E — merged
    "№ загранпаспорта",         # F — individual
    "Дата окончания паспорта",  # G — individual
    "Дата рождения",            # H — individual
    "Возраст",                  # I — individual
    "Стоимость тура, руб.",     # J — merged
    "Оплачено, руб.",           # K — merged
    "Остаток к доплате, руб.",  # L — merged
]

# Колонки B, C, D, E, J, K, L (0-indexed: 1,2,3,4,9,10,11) — общие для договора
SHARED_COLS = [1, 2, 3, 4, 9, 10, 11]


def _text(value: str) -> str:
    """Принудительно задаёт текстовый тип ячейки (префикс ' скрыт в UI)."""
    if value and value[0] in ("+", "-", "=", "@"):
        return f"'{value}"
    return value


def _age(dob_str: str, contract_date_str: str) -> int | str:
    """Возраст на дату договора. Форматы DD.MM.YYYY."""
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            dob = datetime.strptime(dob_str.strip(), fmt)
            ref = datetime.strptime(contract_date_str.strip(), fmt)
            return ref.year - dob.year - ((ref.month, ref.day) < (dob.month, dob.day))
        except ValueError:
            continue
    return ""


def _get_service():
    creds_data = json.loads(config.google_credentials_json)
    if creds_data.get("type") == "service_account":
        creds = ServiceCredentials.from_service_account_info(creds_data, scopes=SCOPES)
    else:
        creds = Credentials.from_authorized_user_info(creds_data, SCOPES)
    return build("sheets", "v4", credentials=creds)


def _ensure_tab(service, spreadsheet_id: str, tab_name: str) -> int:
    """Returns sheet_id of the tab; creates it with header row if missing."""
    spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    for sheet in spreadsheet.get("sheets", []):
        props = sheet["properties"]
        if props["title"] == tab_name:
            sheet_id = props["sheetId"]
            existing = service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=f"'{tab_name}'!A1:A1",
            ).execute()
            if not existing.get("values"):
                _write_header(service, spreadsheet_id, tab_name)
            return sheet_id

    result = service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": [{"addSheet": {"properties": {"title": tab_name}}}]},
    ).execute()
    sheet_id = result["replies"][0]["addSheet"]["properties"]["sheetId"]
    _write_header(service, spreadsheet_id, tab_name)
    return sheet_id


def _write_header(service, spreadsheet_id: str, tab_name: str) -> None:
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"'{tab_name}'!A1",
        valueInputOption="RAW",
        body={"values": [HEADER]},
    ).execute()


def append_contract_rows(
    tab_name: str,
    tourists: list[dict],
    contract_number: str,
    contract_date: str,
    total_price: float,
    deposit: float,
    phone: str,
    email: str,
    payment_deadline: str,
    remaining: float | None,
) -> None:
    """
    Appends one row per tourist/employee to the tab named after the tour.
    Columns B–E, J–L are merged (shared for contract).
    Columns F–I (passport, valid until, dob, age) are individual per tourist.
    """
    spreadsheet_id = config.google_sheets_id
    if not spreadsheet_id or not config.google_credentials_json:
        logger.warning("Sheets: GOOGLE_SHEETS_ID или GOOGLE_CREDENTIALS_JSON не заданы, пропускаю")
        return
    if not tourists:
        logger.warning("Sheets: список туристов пуст, пропускаю")
        return

    logger.info("Sheets: записываю %d строк в вкладку '%s', spreadsheet_id=%s", len(tourists), tab_name, spreadsheet_id)
    service = _get_service()
    sheet_id = _ensure_tab(service, spreadsheet_id, tab_name)

    current = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=f"'{tab_name}'!A:A",
    ).execute()
    start_row_idx = len(current.get("values", []))  # 0-indexed

    total_val = int(total_price)
    deposit_val = int(deposit) if deposit else 0
    first_data_row = start_row_idx + 1  # 1-indexed

    rows = []
    for i, t in enumerate(tourists):
        name = f"{t.get('surname_latin', '')} {t.get('name_latin', '')}".strip()
        passport = t.get("passport_number", "")
        valid_until = t.get("valid_until", "")
        dob = t.get("date_of_birth", "")
        age = _age(dob, contract_date) if dob and contract_date else ""
        row_num = first_data_row + i
        remaining_formula = f"=J{row_num}-K{row_num}"
        if i == 0:
            # A     B                C               D               E                 F                 G            H    I     J           K             L
            rows.append([name, contract_number, _text(phone), _text(email), payment_deadline, _text(passport), valid_until, dob, age, total_val, deposit_val, remaining_formula])
        else:
            rows.append([name, "", "", "", "", _text(passport), valid_until, dob, age, "", "", remaining_formula])

    service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range=f"'{tab_name}'!A{start_row_idx + 1}",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": rows},
    ).execute()

    if len(tourists) > 1:
        requests = [
            {
                "mergeCells": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": start_row_idx,
                        "endRowIndex": start_row_idx + len(tourists),
                        "startColumnIndex": col,
                        "endColumnIndex": col + 1,
                    },
                    "mergeType": "MERGE_ALL",
                }
            }
            for col in SHARED_COLS
        ]
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": requests},
        ).execute()


# ── Клиентская база ────────────────────────────────────────────────────────────

TOURIST_DB_TAB = "Клиентская база"

TOURIST_DB_HEADER = [
    "Фамилия и имя (рус)",          # A  0
    "Фамилия и имя (англ)",         # B  1
    "Телефон",                       # C  2
    "Instagram",                     # D  3
    "TG",                            # E  4
    "Пол",                           # F  5
    "Дата рождения",                 # G  6
    "№ загранпаспорта",             # H  7
    "Срок действия",                 # I  8
    "Город проживания",              # J  9
    "Семейное положение",            # K  10
    "Статус",                        # L  11
    "Доход",                         # M  12
    "Платежеспособность",            # N  13
    "Ездил в тур",                   # O  14
    "Кол-во туров с Divopromo",     # P  15
    "Средний чек тура",              # Q  16
    "Страны куда ездил",             # R  17
    "Цель поездки",                  # S  18
    "Что для него важно?",           # T  19
    "Лояльность к бренду",          # U  20
    "Как часто готов ездить?",      # V  21
]

_TZ = ZoneInfo("Asia/Yekaterinburg")


def _is_cyrillic(s: str) -> bool:
    return bool(re.search("[а-яА-ЯёЁ]", s or ""))


def _ensure_client_db_tab(service, spreadsheet_id: str) -> None:
    spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    for sheet in spreadsheet.get("sheets", []):
        if sheet["properties"]["title"] == TOURIST_DB_TAB:
            existing = service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=f"'{TOURIST_DB_TAB}'!A1:A1",
            ).execute()
            if not existing.get("values"):
                _write_tourist_db_header(service, spreadsheet_id)
            return
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": [{"addSheet": {"properties": {"title": TOURIST_DB_TAB}}}]},
    ).execute()
    _write_tourist_db_header(service, spreadsheet_id)


def _write_tourist_db_header(service, spreadsheet_id: str) -> None:
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"'{TOURIST_DB_TAB}'!A1",
        valueInputOption="RAW",
        body={"values": [TOURIST_DB_HEADER]},
    ).execute()


def _cell(row: list, idx: int) -> str:
    return row[idx].strip() if len(row) > idx else ""


def _is_duplicate(row: list, name_latin: str, name_rf: str, passport: str) -> bool:
    existing_latin = _cell(row, 1).upper()
    existing_rf = _cell(row, 0).upper()
    existing_passport = _cell(row, 7)

    name_match = (
        (name_latin and existing_latin and name_latin.upper() == existing_latin)
        or (name_rf and existing_rf and name_rf.upper() == existing_rf)
    )
    if not name_match:
        return False

    if passport and existing_passport:
        return passport.upper().replace(" ", "") == existing_passport.upper().replace(" ", "")
    return True


def upsert_tourist_in_client_db(
    tab_name: str,
    tourists: list[dict],
    phone: str = "",
) -> None:
    """
    Дублирует туристов в вкладку 'Клиентская база'.
    Проверяет дубликаты по имени + паспорту. Если найден — обновляет пустые
    ячейки и добавляет тур в 'Ездил в тур'. Иначе — добавляет новую строку.
    """
    spreadsheet_id = config.google_sheets_id
    if not spreadsheet_id or not config.google_credentials_json:
        logger.warning("Sheets: GOOGLE_SHEETS_ID или GOOGLE_CREDENTIALS_JSON не заданы, пропускаю")
        return
    if not tourists:
        return

    service = _get_service()
    _ensure_client_db_tab(service, spreadsheet_id)

    response = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=f"'{TOURIST_DB_TAB}'!A:V",
    ).execute()
    existing_rows = response.get("values", [])
    data_rows = existing_rows[1:]  # skip header

    for i, tourist in enumerate(tourists):
        name_latin = f"{tourist.get('surname_latin', '')} {tourist.get('name_latin', '')}".strip()
        full_name = tourist.get("full_name", "")
        name_rf = full_name if _is_cyrillic(full_name) else ""
        t_phone = phone if i == 0 else ""
        gender = tourist.get("gender", "")
        dob = tourist.get("date_of_birth", "")
        passport = tourist.get("passport_number", "")
        valid_until = tourist.get("valid_until", "")

        dup_idx = None
        for j, row in enumerate(data_rows):
            if _is_duplicate(row, name_latin, name_rf, passport):
                dup_idx = j
                break

        if dup_idx is not None:
            row = data_rows[dup_idx]
            sheet_row = dup_idx + 2  # +1 header, +1 for 1-indexing

            updates = []

            def _set_if_empty(col_idx: int, value: str) -> None:
                if not value:
                    return
                if not _cell(row, col_idx):
                    updates.append((col_idx, value))

            _set_if_empty(0, name_rf)
            _set_if_empty(2, _text(t_phone))
            _set_if_empty(5, gender)
            _set_if_empty(6, dob)
            _set_if_empty(7, _text(passport))
            _set_if_empty(8, valid_until)

            existing_tours = _cell(row, 14)
            tour_list = [t.strip() for t in existing_tours.split(",") if t.strip()]
            if tab_name and tab_name not in tour_list:
                tour_list.append(tab_name)
                updates.append((14, ", ".join(tour_list)))

            if updates:
                batch_data = [
                    {
                        "range": f"'{TOURIST_DB_TAB}'!{chr(ord('A') + col)}{sheet_row}",
                        "values": [[val]],
                    }
                    for col, val in updates
                ]
                service.spreadsheets().values().batchUpdate(
                    spreadsheetId=spreadsheet_id,
                    body={"valueInputOption": "USER_ENTERED", "data": batch_data},
                ).execute()
                for col, val in updates:
                    while len(data_rows[dup_idx]) <= col:
                        data_rows[dup_idx].append("")
                    data_rows[dup_idx][col] = val
        else:
            new_row = [""] * 22
            new_row[0] = name_rf
            new_row[1] = name_latin
            new_row[2] = _text(t_phone)
            new_row[5] = gender
            new_row[6] = dob
            new_row[7] = _text(passport)
            new_row[8] = valid_until
            new_row[14] = tab_name

            service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range=f"'{TOURIST_DB_TAB}'!A1",
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body={"values": [new_row]},
            ).execute()
            data_rows.append(new_row)


def get_birthdays_today() -> list[dict]:
    """Возвращает список туристов у которых сегодня день рождения (день и месяц совпадают)."""
    spreadsheet_id = config.google_sheets_id
    if not spreadsheet_id or not config.google_credentials_json:
        return []
    try:
        service = _get_service()
        response = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"'{TOURIST_DB_TAB}'!A:G",
        ).execute()
        rows = response.get("values", [])
        if len(rows) < 2:
            return []

        today = datetime.now(tz=_TZ)
        results = []
        for row in rows[1:]:
            dob_str = _cell(row, 6)
            if not dob_str:
                continue
            for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"):
                try:
                    dob = datetime.strptime(dob_str.strip(), fmt)
                    if dob.day == today.day and dob.month == today.month:
                        name = _cell(row, 0) or _cell(row, 1)
                        results.append({"name": name, "dob": dob_str.strip()})
                    break
                except ValueError:
                    continue
        return results
    except Exception as e:
        logger.error("Sheets: get_birthdays_today error: %s", e, exc_info=True)
        return []
