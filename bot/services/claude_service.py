import base64
import json
import re

import anthropic
import fitz  # PyMuPDF

from bot.config import config

_client = anthropic.AsyncAnthropic(api_key=config.anthropic_api_key)

MODEL = "claude-sonnet-4-6"


def pdf_to_jpeg(pdf_bytes: bytes) -> bytes:
    """Конвертирует первую страницу PDF в JPEG для передачи в Claude."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[0]
    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
    return pix.tobytes("jpeg")


def _image_content(image_bytes: bytes, media_type: str = "image/jpeg") -> dict:
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": media_type,
            "data": base64.standard_b64encode(image_bytes).decode(),
        },
    }


def _parse_json(text: str) -> dict:
    """Извлекает JSON из ответа модели."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"JSON не найден в ответе: {text[:200]}")
    return json.loads(match.group())


async def extract_ru_passport(image_bytes: bytes, media_type: str = "image/jpeg") -> dict:
    """
    Возвращает:
      full_name, series, number, issued_by, issue_date, registration_address
    """
    response = await _client.messages.create(
        model=MODEL,
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": [
                    _image_content(image_bytes, media_type),
                    {
                        "type": "text",
                        "text": (
                            "Извлеки данные из российского паспорта. "
                            "Верни ТОЛЬКО JSON без пояснений:\n"
                            '{"full_name": "Фамилия Имя Отчество", '
                            '"series": "0000", '
                            '"number": "000000", '
                            '"issued_by": "...", '
                            '"issue_date": "ДД.ММ.ГГГГ", '
                            '"registration_address": "..."}'
                        ),
                    },
                ],
            }
        ],
    )
    return _parse_json(response.content[0].text)


async def extract_foreign_passport(image_bytes: bytes, media_type: str = "image/jpeg") -> dict:
    """
    Возвращает:
      surname_latin, name_latin, gender, passport_number, date_of_birth, valid_until
    """
    response = await _client.messages.create(
        model=MODEL,
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": [
                    _image_content(image_bytes, media_type),
                    {
                        "type": "text",
                        "text": (
                            "Извлеки данные из заграничного паспорта. "
                            "Пол определи по полю SEX/MRZ строке или визуально: М для мужчины, Ж для женщины. "
                            "Верни ТОЛЬКО JSON без пояснений:\n"
                            '{"surname_latin": "SURNAME", '
                            '"name_latin": "FIRSTNAME", '
                            '"gender": "М или Ж", '
                            '"passport_number": "...", '
                            '"date_of_birth": "ДД.ММ.ГГГГ", '
                            '"valid_until": "ДД.ММ.ГГГГ"}'
                        ),
                    },
                ],
            }
        ],
    )
    return _parse_json(response.content[0].text)


async def extract_company_card(image_bytes: bytes | None, text: str | None = None) -> dict:
    """
    Принимает фото карточки компании или текст.
    Возвращает:
      company_name, legal_form, director_name, inn, kpp, ogrn,
      legal_address, postal_address, phone, email, bank_name,
      bank_account, correspondent_account, bik
    """
    content: list[dict] = []
    if image_bytes:
        content.append(_image_content(image_bytes))

    prompt = (
        "Извлеки реквизиты организации. "
        "Верни ТОЛЬКО JSON без пояснений:\n"
        '{"company_name": "ООО ...", '
        '"legal_form": "ООО/ОАО/ЗАО/...", '
        '"director_name": "Фамилия И.О.", '
        '"inn": "...", '
        '"kpp": "...", '
        '"ogrn": "...", '
        '"legal_address": "...", '
        '"postal_address": "...", '
        '"phone": "...", '
        '"email": "...", '
        '"bank_name": "...", '
        '"bank_account": "...", '
        '"correspondent_account": "...", '
        '"bik": "..."}'
    )
    if text:
        prompt = f"Текст карточки компании:\n{text}\n\n{prompt}"

    content.append({"type": "text", "text": prompt})

    response = await _client.messages.create(
        model=MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": content}],
    )
    return _parse_json(response.content[0].text)
