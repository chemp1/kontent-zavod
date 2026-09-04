#!/usr/bin/env python3
"""Разметка постов признаками, которые можно повторить в своём тексте.

Признаки намеренно механические: длина, тип первой строки, вопрос в конце,
наличие цифр. Всё, что требует понимания смысла («сильный тезис», «интересно»),
сюда не берём — такую разметку нельзя воспроизвести одинаково на тысяче постов,
а значит и выводы по ней будут о разметчике, а не о постах.
"""

from __future__ import annotations

import re

EMOJI = re.compile(
    "[\U0001f300-\U0001faff\U00002600-\U000027bf\U0001f1e6-\U0001f1ff]",
    flags=re.UNICODE,
)
CYRILLIC = re.compile(r"[а-яёА-ЯЁ]")
LATIN = re.compile(r"[a-zA-Z]")
FIRST_PERSON = re.compile(r"\b(я|мне|меня|мой|моя|мои|моё|у меня)\b", re.IGNORECASE)
LIST_MARKER = re.compile(r"^\s*(?:[-•*—]|\d+[.)])\s+", re.MULTILINE)
URL = re.compile(r"https?://|\b\w+\.(?:com|ru|ai|io|net|org)\b")


def first_line(text: str) -> str:
    for line in text.split("\n"):
        if line.strip():
            return line.strip()
    return ""


def hook_type(line: str) -> str:
    """Чем цепляет первая строка — единственное, что видно в ленте до раскрытия."""
    if not line:
        return "none"
    # Вопрос где угодно в строке, а не только в конце: «Сколько людей открыли
    # инструмент через неделю? Не знаю» читается как вопросительный зачин,
    # хотя строка заканчивается точкой.
    if "?" in line:
        return "question"
    if re.search(r"\d", line):
        return "number"
    if re.search(r"\b(я|мне|меня|мой)\b", line, re.IGNORECASE):
        return "personal"
    return "statement"


def language(text: str) -> str:
    cyr = len(CYRILLIC.findall(text))
    lat = len(LATIN.findall(text))
    if cyr == 0 and lat == 0:
        return "unknown"
    return "ru" if cyr >= lat else "en"


def ends_with_question(text: str) -> bool:
    stripped = text.rstrip()
    if not stripped:
        return False
    # Смотрим последнюю содержательную строку, а не последний символ: у постов
    # часто висит хвостом ссылка или подпись.
    for line in reversed(stripped.split("\n")):
        if line.strip():
            return line.strip().endswith("?")
    return False


def extract(post: dict) -> dict:
    text = post.get("text") or ""
    head = first_line(text)

    return {
        "length": len(text),
        "lines": len([ln for ln in text.split("\n") if ln.strip()]),
        "hook_len": len(head),
        "hook_type": hook_type(head),
        "ends_with_question": ends_with_question(text),
        "has_number": bool(re.search(r"\d", text)),
        "first_person": bool(FIRST_PERSON.search(text)),
        "has_list": bool(LIST_MARKER.search(text)),
        "emoji_count": len(EMOJI.findall(text)),
        "has_link": bool(URL.search(text)),
        "lang": language(text),
        "media": post.get("media", "none"),
    }


def engagement(post: dict) -> int:
    return sum(int(post.get(k) or 0) for k in ("likes", "replies", "reposts", "quotes"))


def reply_share(post: dict) -> float:
    total = engagement(post)
    if total == 0:
        return 0.0
    return int(post.get("replies") or 0) / total
