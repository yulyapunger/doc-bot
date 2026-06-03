import io
import json

from google.oauth2.credentials import Credentials
from google.oauth2.service_account import Credentials as ServiceCredentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

from bot.config import config

SCOPES = ["https://www.googleapis.com/auth/drive"]


def _get_service():
    creds_json = config.google_credentials_json
    if not creds_json:
        raise RuntimeError("GOOGLE_CREDENTIALS_JSON не задан")

    creds_data = json.loads(creds_json)

    if creds_data.get("type") == "service_account":
        creds = ServiceCredentials.from_service_account_info(creds_data, scopes=SCOPES)
    else:
        # OAuth2 user credentials (token JSON)
        creds = Credentials.from_authorized_user_info(creds_data, SCOPES)

    return build("drive", "v3", credentials=creds)


def _get_or_create_folder(service, name: str, parent_id: str) -> str:
    """Возвращает ID папки (создаёт если не существует)."""
    query = (
        f"name='{name}' and mimeType='application/vnd.google-apps.folder' "
        f"and '{parent_id}' in parents and trashed=false"
    )
    results = service.files().list(q=query, fields="files(id)").execute()
    files = results.get("files", [])
    if files:
        return files[0]["id"]

    folder_metadata = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }
    folder = service.files().create(body=folder_metadata, fields="id").execute()
    return folder["id"]


def upload_contract(pdf_bytes: bytes, filename: str, tour_name: str) -> str:
    """
    Загружает PDF в папку tour_name на Google Drive.
    Возвращает file_id.
    """
    service = _get_service()
    root_folder_id = config.gdrive_root_folder_id

    tour_folder_id = _get_or_create_folder(service, tour_name, root_folder_id)

    file_metadata = {
        "name": f"{filename}.pdf",
        "parents": [tour_folder_id],
    }
    media = MediaIoBaseUpload(io.BytesIO(pdf_bytes), mimetype="application/pdf")
    file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id",
    ).execute()
    return file["id"]
