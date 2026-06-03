"""
Конвертирует оранжевые поля в DOCX-шаблонах в {{PLACEHOLDER}} маркеры.
Запускать один раз: python3 convert_templates.py
"""
import zipfile, shutil
from lxml import etree

NS  = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
XML_SPACE = '{http://www.w3.org/XML/1998/namespace}space'
W   = lambda tag: f'{{{NS}}}{tag}'

def is_orange(run):
    rpr = run.find(W('rPr'))
    if rpr is not None:
        shd = rpr.find(W('shd'))
        if shd is not None and (shd.get(W('fill'), '')).lower() == 'ff9900':
            return True
    return False

def get_text(run):
    t = run.find(W('t'))
    return t.text or '' if t is not None else ''

def set_text(run, text):
    t = run.find(W('t'))
    if t is None:
        t = etree.SubElement(run, W('t'))
    t.text = text
    if text and (' ' in text):
        t.set(XML_SPACE, 'preserve')
    elif XML_SPACE in t.attrib:
        del t.attrib[XML_SPACE]

def remove_shading(run):
    rpr = run.find(W('rPr'))
    if rpr is not None:
        shd = rpr.find(W('shd'))
        if shd is not None:
            rpr.remove(shd)

def collect_groups(root):
    groups = []
    for para in root.iter(W('p')):
        cur = []
        for run in para.iter(W('r')):
            if is_orange(run) and get_text(run).strip():
                cur.append(run)
            else:
                if cur:
                    groups.append(cur)
                    cur = []
        if cur:
            groups.append(cur)
    return groups

def convert(src, dst, placeholders):
    with zipfile.ZipFile(src, 'r') as z:
        names = z.namelist()
        contents = {n: z.read(n) for n in names}

    xml  = contents['word/document.xml']
    root = etree.fromstring(xml)
    groups = collect_groups(root)

    print(f"\n{'='*60}\n{dst}   ({len(groups)} групп, {len(placeholders)} плейсхолдеров)\n{'='*60}")
    for i, group in enumerate(groups):
        combined = ''.join(get_text(r) for r in group)
        ph = placeholders[i] if i < len(placeholders) else None
        if ph is None:
            # просто снять заливку, текст оставить
            for run in group:
                remove_shading(run)
            print(f"  {i+1:2d}. {combined!r:55s} → (снят цвет, текст сохранён)")
        else:
            set_text(group[0], '{{' + ph + '}}')
            remove_shading(group[0])
            for run in group[1:]:
                set_text(run, '')
                remove_shading(run)
            print(f"  {i+1:2d}. {combined!r:55s} → {{{{{ph}}}}}")

    # Снять оранжевый фон с любых оставшихся runs (пробелы/форматирование)
    for run in root.iter(W('r')):
        if is_orange(run):
            remove_shading(run)

    contents['word/document.xml'] = etree.tostring(
        root, xml_declaration=True, encoding='UTF-8', standalone=True
    )
    with zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED) as z:
        for n, data in contents.items():
            z.writestr(n, data)
    print(f"  → Сохранён: {dst}")


# ── Физлицо: 53 группы ────────────────────────────────────────────────────────
INDIVIDUAL = [
    "CONTRACT_NUMBER_FULL",         #  1: '№ 127 '
    "CONTRACT_DATE",                #  2: '«17» ноября 2024 г.'
    "CLIENT_FULL_NAME",             #  3: 'Колотов Николай Андреевич'
    "CANCELLATION_FEE_1",           #  4: '50%'
    "CANCELLATION_DAYS_1",          #  5: '30'
    "CANCELLATION_DAYS_2",          #  6: '30'
    "CLIENT_FULL_NAME",             #  7: повтор
    "PASSPORT_SERIES_NUMBER",       #  8: '1111 № 111111111'
    "PASSPORT_ISSUED_BY",           #  9: 'Отделением УФМС...'
    "PASSPORT_ISSUE_DATE",          # 10: '11.11.2011'
    "REGISTRATION_ADDRESS",         # 11: 'Адрес'
    "CLIENT_PHONE",                 # 12: '811111111111'
    "CLIENT_EMAIL",                 # 13: '11111111@mail.ru'
    "CONTRACT_NUMBER_SHORT",        # 14: '126'
    "CONTRACT_DATE_PART",           # 15: '17» ноября 2024 г.'
    "TOURIST_1_NAME",               # 16: 'KOLOTOV NIKOLAI'
    "TOURIST_1_GENDER",             # 17: 'М'
    "TOURIST_1_DOB",                # 18: '11.11.1995'
    "TOURIST_1_PASSPORT",           # 19: '11 11111111'
    "TOURIST_2_NAME",               # 20: 'VTOROI UCHASTNIK'
    "TOURIST_2_GENDER",             # 21: 'Ж'
    "TOURIST_2_DOB",                # 22: '11.11.1995'
    "TOURIST_2_PASSPORT",           # 23: '11  11111111'
    "COUNTRY_CITY",                 # 24
    "HOTEL",                        # 25
    "CHECK_IN_DATE",                # 26
    "CHECK_OUT_DATE",               # 27
    "NIGHTS",                       # 28
    "ROOM_TYPE",                    # 29
    "ROOM_COUNT",                   # 30
    "MEAL_TYPE",                    # 31
    "TRANSFER",                     # 32
    "INSURANCE",                    # 33
    "ADD_COND_1",                   # 34
    "ADD_COND_2",                   # 35
    "ADD_COND_3",                   # 36
    "ADD_COND_4",                   # 37
    "ADD_COND_5",                   # 38
    "ADD_COND_6",                   # 39
    "ADD_COND_7",                   # 40
    "ADD_COND_8",                   # 41
    "TOTAL_PRICE_RUB",              # 42: '142000 руб. 00 коп.'
    "TOTAL_PRICE_WORDS",            # 43: 'сто сорок две тысячи рублей'
    "DEPOSIT_RUB",                  # 44: '42000 руб. 00 коп.'
    "DEPOSIT_WORDS",                # 45: 'сорок две тысячи рублей'
    "DEPOSIT_DATE",                 # 46: '«17» ноября 2024г.'
    "PAYMENT_DEADLINE",             # 47: '1.12.24'
    "REMAINING_RUB",                # 48: '100000 руб. 00 коп.'
    "REMAINING_WORDS",              # 49: 'сто тысяч рублей'
    "CLIENT_FULL_NAME",             # 50: повтор (подпись)
    "CLIENT_FULL_NAME",             # 51: повтор (согласие)
    "PASSPORT_SERIES_NUMBER_LONG",  # 52: 'Паспорт: серия...'
    "PASSPORT_ISSUED_BY_AND_DATE",  # 53: 'Отделением... «15» января 2016 г.'
]

# ── Юрлицо: 65 групп ──────────────────────────────────────────────────────────
LEGAL = [
    "CONTRACT_NUMBER",              #  1: '70'
    "CONTRACT_DATE",                #  2: ' «05» мая 2025 г.'
    "COMPANY_LEGAL_FORM",           #  3: 'ООО'
    "COMPANY_SHORT_NAME_DISPLAY",   #  4: '«МСМ»'
    "DIRECTOR_TITLE_AND_NAME",      #  5: 'Генерального директора  Костоусова...'
    "BASIS_DOCUMENT",               #  6: 'действующего на основании Устава'
    "COMPANY_FULL_NAME",            #  7: 'ООО «Торговый Дом Батиссур»'
    "LEGAL_ADDRESS",                #  8
    "POSTAL_ADDRESS",               #  9
    "COMPANY_PHONE",                # 10
    "INN_KPP",                      # 11: '6658554263 / 665801001'
    "OGRN",                         # 12
    "BANK_ACCOUNT",                 # 13
    "BANK_NAME",                    # 14
    "CORRESPONDENT_ACCOUNT",        # 15
    "BIK",                          # 16
    "DIRECTOR_TITLE_SHORT",         # 17: 'Генеральный директор  '
    "DIRECTOR_SHORT_NAME",          # 18: 'Костоусов М.А.'
    "CONTRACT_NUMBER",              # 19: '131' (повтор в приложении)
    "CONTRACT_DATE",                # 20: '«06» мая 2025  г' (повтор)
    "EMPLOYEE_1_NAME",              # 21
    "EMPLOYEE_1_DOB",               # 22
    "EMPLOYEE_1_PASSPORT",          # 23
    "EMPLOYEE_1_ISSUE_DATE",        # 24
    "EMPLOYEE_1_VALID_UNTIL",       # 25
    "EMPLOYEE_2_NAME",              # 26
    "EMPLOYEE_2_DOB",               # 27
    "EMPLOYEE_2_PASSPORT",          # 28
    "EMPLOYEE_2_ISSUE_DATE",        # 29
    "EMPLOYEE_2_VALID_UNTIL",       # 30
    "COUNTRY_CITY",                 # 31
    "HOTEL",                        # 32
    "CHECK_IN_DATE",                # 33
    "CHECK_OUT_DATE",               # 34
    "NIGHTS",                       # 35
    "ROOM_TYPE",                    # 36
    "ROOM_COUNT",                   # 37
    "INSURANCE",                    # 38
    None,                           # 39: '-' (снять цвет, текст '-' оставить)
    "ADD_COND_1",                   # 40
    "ADD_COND_2",                   # 41: '- Трансферы...' (дефис слит с текстом)
    None,                           # 42: '-'
    "ADD_COND_3",                   # 43
    None,                           # 44: '-'
    "ADD_COND_4",                   # 45
    None,                           # 46: '-'
    "ADD_COND_5",                   # 47
    None,                           # 48: '-'
    "ADD_COND_6",                   # 49
    None,                           # 50: '-'
    "ADD_COND_7",                   # 51
    None,                           # 52: '-'
    "ADD_COND_8",                   # 53
    None,                           # 54: '-'
    "ADD_COND_9",                   # 55
    None,                           # 56: '-'
    "ADD_COND_10",                  # 57
    "ADD_COND_11",                  # 58: '- Помощь...' (дефис слит)
    "TOTAL_PRICE_RUB",              # 59: '2 711 450  руб.'
    "COMPANY_FULL_NAME",            # 60: повтор
    "LEGAL_ADDRESS",                # 61: повтор
    "INN_KPP_DISPLAY",              # 62: 'ИНН/КПП ...'
    "OGRN",                         # 63: повтор
    "DIRECTOR_TITLE_SHORT",         # 64: повтор
    "DIRECTOR_SHORT_NAME",          # 65: повтор
]


if __name__ == '__main__':
    convert(
        'templates/contract_individual.docx',
        'templates/contract_individual.docx',
        INDIVIDUAL,
    )
    convert(
        'templates/contract_legal.docx',
        'templates/contract_legal.docx',
        LEGAL,
    )
    print("\n✓ Шаблоны готовы.")
