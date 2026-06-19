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
    "Ф.И.О. (загранпаспорт)",
    "№ договора",
    "Стоимость тура, руб.",
    "Телефон",
    "Email",
    "Дата полной оплаты",
    "Остаток к доплате, руб.",
]

PRICE_COL_IDX = 2  # column C, 0-indexed


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
    names: list[str],
    contract_number: str,
    total_price: float,
    phone: str,
    email: str,
    payment_deadline: str,
    remaining: float | None,
) -> None:
    """
    Appends one row per tourist/employee to the tab named after the tour.
    Merges the price cell (column C) vertically if there are multiple people.
    """
    spreadsheet_id = config.google_sheets_id
    if not spreadsheet_id or not config.google_credentials_json:
        logger.warning("Sheets: GOOGLE_SHEETS_ID или GOOGLE_CREDENTIALS_JSON не заданы, пропускаю")
        return
    if not names:
        logger.warning("Sheets: список имён пуст, пропускаю")
        return

    logger.info("Sheets: записываю %d строк в вкладку '%s', spreadsheet_id=%s", len(names), tab_name, spreadsheet_id)
    service = _get_service()
    sheet_id = _ensure_tab(service, spreadsheet_id, tab_name)

    current = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=f"'{tab_name}'!A:A",
    ).execute()
    start_row_idx = len(current.get("values", []))  # 0-indexed, after existing rows

    total_str = f"{total_price:,.0f}".replace(",", " ")
    remaining_str = f"{remaining:,.0f}".replace(",", " ") if remaining is not None else ""

    rows = []
    for i, name in enumerate(names):
        if i == 0:
            rows.append([name, contract_number, total_str, phone, email, payment_deadline, remaining_str])
        else:
            rows.append([name, contract_number, "", phone, email, payment_deadline, remaining_str])

    service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range=f"'{tab_name}'!A{start_row_idx + 1}",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": rows},
    ).execute()

    if len(names) > 1:
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [{
                "mergeCells": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": start_row_idx,
                        "endRowIndex": start_row_idx + len(names),
                        "startColumnIndex": PRICE_COL_IDX,
                        "endColumnIndex": PRICE_COL_IDX + 1,
                    },
                    "mergeType": "MERGE_ALL",
                }
            }]},
        ).execute()
