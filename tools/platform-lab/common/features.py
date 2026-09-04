#!/usr/bin/env python3
"""Признаки, которые считаются кодом, а не чтением.

Ядро взято дословно из старого замера vc — не потому что оно идеально,
а чтобы новые площадки были сравнимы с уже опубликованным замером vc.
Добавлено то, чего на vc не было и без чего эти четыре площадки не описать:
код (Хабр), ритм по квантилям (лонгриды длиннее, старый para_spread на них
вырождается), нормировки на длину (иначе «у верха больше подзаголовков»
окажется просто «верх длиннее»), концовка (продажа).
"""

from __future__ import annotations

import re
import statistics

NUM_TOKEN = re.compile(r"(?<![\w.,])\d[\d  ]*(?:[.,]\d+)?(?![\w])")
I_ME = re.compile(r"\b(я|мне|меня|мной|мо[йяёеи]\w*)\b", re.I)
WE = re.compile(r"\b(мы|нас|нам|нами|наш\w*)\b", re.I)
YOU = re.compile(r"\b(вы|вас|вам|вами|ваш\w*|ты|тебя|тебе|тво[йяие]\w*)\b", re.I)
LATIN = re.compile(r"\b[A-Za-z][A-Za-z0-9+.#_-]{1,}\b")

T_LIST = re.compile(r"^\s*\d+\s|\b\d+\s+(?:способ\w*|причин\w*|ошиб\w*|шаг\w*|правил\w*|"
                    r"урок\w*|инструмент\w*|совет\w*|мысл\w*|факт\w*|при[её]м\w*|вещ\w*)", re.I)
T_HOWTO = re.compile(r"^как\s+(?!я\b|мы\b|мне\b|нас\b|мо[йя]\b)", re.I)
T_MYSTORY = re.compile(r"^(как|почему)\s+(я|мы|мне|нас|мой|наш)\b|^(мой|моя|мои|наш\w*)\b|^я\b", re.I)
T_NEG = re.compile(r"\b(не|без|хватит|перестал\w*|никогда|нельзя|зря|провал\w*|ошиб\w*|"
                   r"уб(ил|ила)|потерял\w*)\b", re.I)
T_CONTRAST = re.compile(r"\bно\b|,\s*а\b|вместо|против|не совпада|оказал", re.I)
T_FIRST = re.compile(r"\b(я|мы|мой|наш|меня|нас|мои|моя)\b", re.I)
T_HOW = re.compile(r"^(как|почему|что|зачем|сколько)\b", re.I)

CTA = re.compile(r"подпис\w+|мой канал|телеграм|t\.me/|запис\w+ на|оставьте заявку|"
                 r"напишите мне|пишите в лич|консультац|ссылка в профиле", re.I)
BAIT = re.compile(r"а как у вас|что думаете|напишите в комментар|делитесь в комментар", re.I)

LEAD_STORY = re.compile(r"^\s*(в\s+20\d\d|\d+\s+(год\w*|мес\w*|недел\w*|дн\w*)\s+назад|"
                        r"однажды|как-то|когда[- ]то|вчера|на прошлой недел)", re.I)


def _q(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    k = max(0, min(len(ordered) - 1, int(round(p * (len(ordered) - 1)))))
    return ordered[k]


def _max_run_even(wl: list[int]) -> int:
    """Самая длинная цепочка соседних абзацев в пределах ±25% длины.

    Прямой детектор выровненного текста — того самого, который в регистре vc
    назван первым признаком сгенерированного.
    """
    best = run = 1
    for a, b in zip(wl, wl[1:]):
        if a and b and abs(a - b) <= 0.25 * max(a, b):
            run += 1
            best = max(best, run)
        else:
            run = 1
    return best if len(wl) > 1 else 0


def features(row: dict) -> dict:
    paras: list[str] = row.get("paras") or []
    headers: list[str] = row.get("headers") or []
    title: str = row.get("title") or ""
    body = " ".join(paras)
    chars = sum(len(p) for p in paras)
    wl = [len(p.split()) for p in paras] or [0]
    tail = body[-600:]
    lead = row.get("lead") or (paras[0] if paras else "")
    code_chars = row.get("code_chars") or 0
    total = chars + code_chars + 1

    f = {
        # объём и структура
        "chars": chars,
        "paras": len(paras),
        "headers": len(headers),
        "chars_per_header": chars / max(1, len(headers)),
        "list_items": row.get("list_items") or 0,
        "media": row.get("media") or 0,
        "quotes": row.get("quotes") or 0,
        "code_blocks": row.get("code_blocks") or 0,
        "code_share": 100 * code_chars / total,
        # ритм
        "para_median": statistics.median(wl),
        "para_spread": (max(wl) / max(1, min(wl))) if len(wl) > 1 else 1,
        "para_p90_p10": _q(wl, 0.9) / max(1.0, _q(wl, 0.1)),
        "short_para_share": 100 * sum(1 for w in wl if w <= 25) / len(wl),
        "long_para_share": 100 * sum(1 for w in wl if w >= 80) / len(wl),
        "max_run_even": _max_run_even(wl),
        # плотность
        "digits_per_1k": 1000 * len(re.findall(r"\d", body)) / max(1, chars),
        "numbers_per_1k": 1000 * len(NUM_TOKEN.findall(body)) / max(1, chars),
        "links_per_1k": 1000 * (row.get("links") or 0) / max(1, chars),
        "media_per_1k": 1000 * (row.get("media") or 0) / max(1, chars),
        "list_per_1k": 1000 * (row.get("list_items") or 0) / max(1, chars),
        "latin_per_1k": 1000 * len(LATIN.findall(body)) / max(1, chars),
        "i_per_1k": 1000 * len(I_ME.findall(body)) / max(1, chars),
        "we_per_1k": 1000 * len(WE.findall(body)) / max(1, chars),
        "you_per_1k": 1000 * len(YOU.findall(body)) / max(1, chars),
        # заголовок
        "t_words": len(title.split()),
        "t_chars": len(title),
        "t_num": bool(re.search(r"\d", title)),
        "t_colon": ":" in title,
        "t_how": bool(T_HOW.match(title)),
        "t_q": title.rstrip().endswith("?"),
        "t_first_person": bool(T_FIRST.search(title)),
        "t_contrast": bool(T_CONTRAST.search(title)),
        "t_list_number": bool(T_LIST.search(title)),
        "t_howto": bool(T_HOWTO.match(title)),
        "t_my_story": bool(T_MYSTORY.match(title)),
        "t_neg": bool(T_NEG.search(title)),
        "t_you": bool(YOU.search(title)),
        "heads_with_num": sum(1 for h in headers if re.search(r"\d", h)),
        # лид и концовка
        "lead_chars": len(lead),
        "lead_num": bool(NUM_TOKEN.search(lead[:200])),
        "lead_i": bool(I_ME.search(lead)),
        "lead_you": bool(YOU.search(lead)),
        "lead_q": "?" in lead[:200],
        "lead_story": bool(LEAD_STORY.match(lead)),
        "ends_with_cta": bool(CTA.search(tail)),
        "ends_with_bait": bool(BAIT.search(tail)),
    }
    return f


SHARE_KEYS = {k for k in (
    "t_num", "t_colon", "t_how", "t_q", "t_first_person", "t_contrast", "t_list_number",
    "t_howto", "t_my_story", "t_neg", "t_you", "lead_num", "lead_i", "lead_you",
    "lead_q", "lead_story", "ends_with_cta", "ends_with_bait")}


def medians(rows: list[dict]) -> dict:
    """Медиана для чисел, доля в процентах для флагов."""
    if not rows:
        return {}
    out = {}
    for key in rows[0]:
        values = [r[key] for r in rows]
        if key in SHARE_KEYS:
            out[key] = 100 * sum(1 for v in values if v) / len(values)
        else:
            out[key] = statistics.median(values)
    return out
