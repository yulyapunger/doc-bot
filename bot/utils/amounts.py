import re


def parse_amount(text: str) -> float:
    text = text.strip().replace(" ", "").replace("\xa0", "")
    # "200.000" или "1.200.000" — точка как разделитель тысяч
    if re.match(r'^\d{1,3}(\.\d{3})+$', text):
        text = text.replace(".", "")
    else:
        text = text.replace(",", ".")
    return float(text)
