"""
Одноразовый скрипт для получения OAuth-токена личного Google-аккаунта,
которым бот будет загружать договоры на Google Drive.

Использование:
    python gdrive_oauth_setup.py client_secret.json

1. В Google Cloud Console (тот же проект, где сервисный аккаунт):
   APIs & Services -> Credentials -> Create Credentials -> OAuth client ID
   -> Application type: Desktop app -> Create -> Download JSON.
   Сохраните файл как client_secret.json рядом с этим скриптом.
2. Если экран согласия (OAuth consent screen) ещё не настроен — настройте его
   (User type: External, добавьте свой email в Test users), иначе Google
   откажет в авторизации.
3. Запустите: python gdrive_oauth_setup.py client_secret.json
   Откроется браузер — войдите тем аккаунтом, на чьём Google Drive должны
   появляться договоры, разрешите доступ.
4. Скрипт выведет JSON — вставьте его целиком в переменную окружения
   GOOGLE_CREDENTIALS_JSON на Railway (заменив текущий ключ сервисного
   аккаунта).
5. GDRIVE_ROOT_FOLDER_ID должен указывать на папку на Google Drive ЭТОГО
   аккаунта (создайте папку и возьмите ID из её URL).
"""

import sys

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]


def main() -> None:
    if len(sys.argv) != 2:
        print("Использование: python gdrive_oauth_setup.py client_secret.json")
        sys.exit(1)

    client_secret_path = sys.argv[1]
    flow = InstalledAppFlow.from_client_secrets_file(client_secret_path, SCOPES)
    creds = flow.run_local_server(port=0)

    print("\nГотово! Вставьте эту строку в GOOGLE_CREDENTIALS_JSON на Railway:\n")
    print(creds.to_json())


if __name__ == "__main__":
    main()
