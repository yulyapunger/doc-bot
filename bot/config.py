import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    bot_token: str
    anthropic_api_key: str
    database_url: str
    allowed_telegram_ids: set[int]
    google_credentials_json: str
    gdrive_root_folder_id: str
    google_sheets_id: str

    @classmethod
    def from_env(cls) -> "Config":
        raw_ids = os.environ["ALLOWED_TELEGRAM_IDS"]
        allowed_ids = {int(x.strip()) for x in raw_ids.split(",") if x.strip()}
        return cls(
            bot_token=os.environ["TELEGRAM_BOT_TOKEN"],
            anthropic_api_key=os.environ["ANTHROPIC_API_KEY"],
            database_url=os.environ["DATABASE_URL"],
            allowed_telegram_ids=allowed_ids,
            google_credentials_json=os.getenv("GOOGLE_CREDENTIALS_JSON", ""),
            gdrive_root_folder_id=os.getenv("GDRIVE_ROOT_FOLDER_ID", ""),
            google_sheets_id=os.getenv("GOOGLE_SHEETS_ID", ""),
        )


config = Config.from_env()
