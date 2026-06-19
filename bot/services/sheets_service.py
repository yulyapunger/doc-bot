import json
import logging

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
    "Стоимость тура, руб.",     # I — merged
    "Оплачено, руб.",           # J — merged
    "Остаток к доплате, руб.",  # K — merged
]

# Колонки B, C, D, E, I, J, K (0-indexed: 1,2,3,4,8,9,10) — общие для договора
SHARED_COLS = [1, 2, 3, 4, 8, 9, 10]


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
    total_price: float,
    deposit: float,
    phone: str,
    email: str,
    payment_deadline: str,
    remaining: float | None,
) -> None:
    """
    Appends one row per tourist/employee to the tab named after the tour.
    Columns B–G are merged vertically (shared for contract).
    Columns H–J (passport number, valid until, dob) are individual per tourist.
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
    start_row_idx = len(current.get("values", []))  # 0-indexed, after existing rows

    total_val = int(total_price)
    deposit_val = int(deposit) if deposit else 0
    first_data_row = start_row_idx + 1  # 1-indexed row number of first tourist

    rows = []
    for i, t in enumerate(tourists):
        name = f"{t.get('surname_latin', '')} {t.get('name_latin', '')}".strip()
        passport = t.get("passport_number", "")
        valid_until = t.get("valid_until", "")
        dob = t.get("date_of_birth", "")
        row_num = first_data_row + i
        remaining_formula = f"=I{row_num}-J{row_num}"
        if i == 0:
            # A  B               C      D      E                 F        G            H    I          J            K
            rows.append([name, contract_number, phone, email, payment_deadline, passport, valid_until, dob, total_val, deposit_val, remaining_formula])
        else:
            rows.append([name, "", "", "", "", passport, valid_until, dob, "", "", remaining_formula])

    service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range=f"'{tab_name}'!A{start_row_idx + 1}",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": rows},
    ).execute()

    if len(tourists) > 1:
        # Merge columns B–G (indices 1–6) — all shared fields
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
