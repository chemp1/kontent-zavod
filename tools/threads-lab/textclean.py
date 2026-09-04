#!/usr/bin/env python3
"""Чистка текста поста от служебных строк интерфейса.

Карточка поста в Threads отдаёт innerText вперемешку с обвязкой: тег темы,
дата, счётчик слайдов карусели, кнопка «Перевести», числа метрик снизу. Всё это
нужно снять, иначе длина поста и первая строка (главные признаки в анализе)
будут считаться по интерфейсу, а не по тексту автора.

Функция идемпотентна: её можно применить к уже очищенному тексту повторно.
"""

from __future__ import annotations

import re
from datetime import datetime

# Threads разделяет разряды узкими неразрывными пробелами, поэтому обычного
# \s в классе недостаточно: нужен явный перечень.
SPACES = "     "
NUM_LINE = re.compile(rf"^\d[\d{SPACES}.,]*\s*[KMКМ]?$")
DATE_LINE = re.compile(r"^\d{2}\.\d{2}\.\d{4}$")
# У постов свежее недели Threads показывает не дату, а «6 ч.» / «2 дн.» / «35 мин.».
# Без этого шапка у свежих постов не срезается, и тег темы уезжает в текст.
RELATIVE_LINE = re.compile(
    r"^\d+\s*(?:сек|с|мин|ч|дн|д|нед|мес|г)\.?$|^\d+\s*[smhdw]$",
    re.IGNORECASE,
)
SLIDE_SEP = re.compile(r"^/$")

UI_LINES = {
    "Перевести",
    "Translate",
    "Подписаться",
    "Ещё",
    "Показать перевод",
}


def clean_post_text(raw: str, published_at: str | None = None) -> str:
    if not raw:
        return ""

    lines = [ln.rstrip() for ln in raw.split("\n")]

    # 1. Шапка карточки: ник автора, тег темы, дата. Отрезаем всё по дату
    # включительно — она всегда последняя строка шапки. Ищем только в начале,
    # чтобы не срезать дату, упомянутую в самом тексте.
    date_str = None
    if published_at:
        try:
            date_str = datetime.fromisoformat(published_at).strftime("%d.%m.%Y")
        except ValueError:
            date_str = None

    head_limit = min(4, len(lines))
    cut = -1
    for i in range(head_limit):
        line = lines[i].strip().replace(" ", " ")
        is_date = DATE_LINE.match(line) and (date_str is None or line == date_str)
        if is_date or RELATIVE_LINE.match(line):
            cut = i
    if cut >= 0:
        lines = lines[cut + 1 :]

    # 2. Счётчик слайдов карусели: три строки подряд вида "1", "/", "2".
    # Снимаем до чистки хвоста: иначе хвостовые числа съедят у счётчика
    # последнюю строку, шаблон перестанет совпадать, и "1 /" останется в тексте.
    cleaned: list[str] = []
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        is_slide = (
            i + 2 < len(lines)
            and NUM_LINE.match(stripped)
            and SLIDE_SEP.match(lines[i + 1].strip())
            and NUM_LINE.match(lines[i + 2].strip())
        )
        if is_slide:
            i += 3
            continue
        if stripped in UI_LINES:
            i += 1
            continue
        cleaned.append(lines[i])
        i += 1

    # 3. Хвост: блок чисел-метрик под кнопками, а также обрубок счётчика
    # карусели ("1", "/"), если его последнюю строку срезали раньше.
    while cleaned:
        last = cleaned[-1].strip()
        if last and not NUM_LINE.match(last) and not SLIDE_SEP.match(last):
            break
        cleaned.pop()

    return "\n".join(cleaned).strip()
