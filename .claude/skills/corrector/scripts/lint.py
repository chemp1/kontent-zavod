#!/usr/bin/env python3
"""Линтер черновика поста под голос конкретного автора.

Считает объективные маркеры текста и сравнивает их с нормой, снятой с корпуса
постов автора. Вердикта о качестве не выносит: показывает, где текст отклоняется
от того, как автор пишет сам.

Пороги живут в `thresholds.json` (его генерирует `calibrate.py` по корпусу).
Без файла работают встроенные `DEFAULTS` - они сняты с корпуса одного русскоязычного
телеграм-канала и годятся как стартовая точка, но это не ваш автор.

Использование:
    python3 lint.py draft.md
    python3 lint.py --thresholds voice/thresholds.json draft.md
    cat draft.md | python3 lint.py --json
    python3 lint.py --strict draft.md      # код 2, если есть блокеры (для хуков)

Порядок поиска порогов: --thresholds → $VOICE_THRESHOLDS → <корень>/voice/thresholds.json
→ <корень>/voice/thresholds.json → thresholds.json рядом со скриптом → DEFAULTS.
Корень - каталог, в котором лежит `.claude/skills/<скилл>/scripts`.
"""

import argparse
import json
import os
import re
import statistics
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Пороги по умолчанию. Структура один в один совпадает с thresholds.json.
# Доли (`share`) - справочные: их пишет calibrate, линтер вставляет в сообщения.
# `level: "off"` выключает проверку.
# ---------------------------------------------------------------------------
DEFAULTS = {
    "meta": {
        "corpus_label": "встроенная норма",
        "posts": 203,
        "generated": None,
        "warnings": [],
    },
    "buckets": {"short_below": 1000, "medium_below": 1500},
    "dash": {"max_per_post": 1, "level": "stop"},
    "dash_bullets": {"level": "stop"},
    "markdown": {"level": "stop"},
    "list_emoji": {"level": "stop"},
    "banned_phrases": {
        "level": "stop",
        "items": [
            "важно понимать", "стоит отметить", "ключевой вывод", "итог:", "вывод:",
            "резюме:", "spoiler:", "подведём итог", "подведем итог", "главное:",
            "дорогие подписчики", "уважаемые", "коллеги,",
        ],
    },
    "abstract_nouns": {
        "level": "warn",
        "items": [
            "трансформация подходов", "оптимизация процессов", "повышение эффективности",
            "синергия", "проактивн", "имплементац",
        ],
    },
    # Паттерны, которых у автора не бывает. Каждый - отдельная проверка.
    "never": {
        "Самомаркировка честности": {
            "pattern": r"(честный разбор|без воды|без прикрас|объективный разбор|это не очередной|скажу как есть)",
            "level": "stop",
        },
        "Псевдотерапевтический регистр": {
            "pattern": r"(и это нормально|вы не одиноки|это не слабость|позвольте себе|ты имеешь право)",
            "level": "stop",
        },
        "«Это не X. Это Y»": {
            "pattern": r"[Ээ]то не [^.!?]{2,40}\.\s*[Ээ]то\s",
            "level": "stop",
            "flags": "",
        },
        "Триада-отрицание": {
            "pattern": r"\b(без|ни)\s+\w+\.\s*(без|ни)\s+\w+\.\s*(просто|только|лишь)\b",
            "level": "stop",
        },
        "Хвост копипасты": {
            "pattern": r"utm_source=(chatgpt|openai|claude)",
            "level": "stop",
        },
    },
    # Обход простого «это/есть»: «является», «представляет собой».
    "copula": {
        "pattern": r"\b(является|являются|представляет собой|представляют собой|выступает в роли"
                   r"|служит основой|носит характер|знаменует собой)\b",
        "warn_at": 2, "share": 0.06,
    },
    # «Данный» вместо «этот». Мн. ч. исключено: «данные» = data.
    "dannyj": {"pattern": r"\bданн(ый|ая|ое|ого|ой|ом|ую|ым)\b", "warn_at": 1, "share": 0.03},
    # Математические знаки в прозе: «Скорость > идеальности».
    "math": {"pattern": r"(?<![\w/])[=><≥≤≠≈±⇒→](?![\w/=])|\bvs\b", "warn_at": 1},
    # Модальное хеджирование - обтекаемость модели, а не сомнение автора.
    "modal_hedges": {
        "pattern": r"\b(может стать|способен обеспеч|призван реш|позволяет добит|может послужить"
                   r"|способствует повышен|может оказаться полезн)\w*",
        "warn_at": 1,
    },
    # Канцелярские переходы между абзацами.
    "kants": {
        "items": ["таким образом", "более того", "тем не менее", "в заключение",
                  "стоит подчеркнуть", "в современном мире", "в эпоху", "нельзя не упомянуть"],
        "warn_at": 2, "share": 0.03,
    },
    # Слова-усилители: живут в разговорной речи, блокером не делаем.
    "amplifiers": {
        "pattern": r"\b(просто|действительно|буквально|по-настоящему|поистине|на самом деле)\b",
        "warn_at": 3, "share": 0.17,
    },
    # Номинализация: канцелярит по суффиксам, а не по списку знакомых слов.
    "nominalization": {
        "pattern": r"\b\w{4,}(ение|ения|ению|ением|ании|ание|ания|ация|ации|ацию|ировка|ировки"
                   r"|ость|ости|остью)\b",
        "max_per_1000": 43,
    },
    "ending": {"terminals": ".!?)»:…"},
    # Скобки-улыбки. Бакеты по длине поста: `below: null` - «и всё, что длиннее».
    "smileys": {
        "pattern": r"[а-яёa-z0-9!?»\"]\)+",
        "buckets": [
            {"below": 1000, "share_any": 0.65, "share_two": None, "missing": "warn", "single": "ok"},
            {"below": None, "share_any": 0.92, "share_two": None, "missing": "stop", "single": "warn"},
        ],
    },
    # Эпистемические хеджи - авторская неуверенность. Обязательность зависит от длины.
    "hedges": {
        "items": ["кажется", "как будто", "есть ощущение", "складывается ощущение",
                  "подозреваю", "не до конца понимаю", "не уверен", "наверное",
                  "по ощущениям", "мне кажется", "это всё не точно", "это все не точно",
                  "интуитивн", "может быть ошибочн", "пока не могу"],
        "buckets": [
            {"below": 1000, "share": 0.22, "missing": "ok"},
            {"below": 1500, "share": 0.34, "missing": "warn"},
            {"below": None, "share": 0.59, "missing": "stop"},
        ],
    },
    "connectors": {
        "items": ["в общем", "короче", "при этом", "плюс", "зато", "вообще", "реально", "типо"],
        "missing": "warn", "share": None,
    },
    "first_person": {
        "pattern": r"\b(я|мне|меня|мой|мои|мною|сам)\b",
        "buckets": [
            {"below": 1000, "share": 0.54, "missing": "warn"},
            {"below": None, "share": 0.86, "missing": "stop"},
        ],
    },
    "paragraph_spread": {"min": 2.5},
    "sentence_cv": {"min": 0.42, "median": 0.58},
    "dotted_lines": {"max_share": 0.75, "typical": 0.33},
    # Двоеточие и точка с запятой обрывают конструкцию: «вычитал не всё: X убрал,
    # а Y оставил» - обычное предложение, а не рамка «не X, а Y».
    "not_x_but_y": {"pattern": r"\bне\s+[^,.!?:;]{2,40},\s*а\s+", "warn_at": 2},
    "length": {"ok_min": 700, "ok_max": 2600, "norm_min": 950, "norm_max": 1750},
    "title": {"enabled": True, "max_words": 6},
    "emoji": {
        "pattern": "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F900-\U0001F9FF⬀-⯿]",
        "list_pattern": r"^\s*(?:[\U0001F300-\U0001FAFF⬀-⯿☀-➿]|\d️⃣)",
        "warn_at": 4,
    },
    "dash_bullet_pattern": r"^\s*—\s",
    "score": {"stop": 12, "warn": 4},
}

LEVELS = ("stop", "warn", "ok", "off")


# ---------------------------------------------------------------------------
# Загрузка порогов
# ---------------------------------------------------------------------------
def deep_merge(base, over):
    """Накладывает `over` на `base`: словари сливаются, остальное заменяется."""
    if not isinstance(base, dict) or not isinstance(over, dict):
        return over
    out = dict(base)
    for k, v in over.items():
        out[k] = deep_merge(base.get(k), v) if k in base else v
    return out


def default_threshold_paths():
    # <корень>/.claude/skills/<скилл>/scripts/lint.py → корень на четыре уровня выше папки скрипта
    here = Path(__file__).resolve()
    root = here.parents[4] if len(here.parents) > 4 else here.parent
    return [
        root / "posts" / "voice" / "thresholds.json",
        root / "voice" / "thresholds.json",
        here.parent / "thresholds.json",
    ]


def load_thresholds(path=None):
    """Возвращает (пороги, откуда взяты). Частичный файл допустим - остальное из DEFAULTS."""
    candidates = []
    if path:
        candidates.append(Path(path))
    if os.environ.get("VOICE_THRESHOLDS"):
        candidates.append(Path(os.environ["VOICE_THRESHOLDS"]))
    candidates.extend(default_threshold_paths())
    for p in candidates:
        if p.is_file():
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
            return deep_merge(DEFAULTS, data), str(p)
    return json.loads(json.dumps(DEFAULTS)), "DEFAULTS"


def compile_patterns(T):
    """Собирает регулярки из порогов один раз."""
    def rx(p, flags=re.I):
        return re.compile(p, flags)

    P = {
        "copula": rx(T["copula"]["pattern"]),
        "dannyj": rx(T["dannyj"]["pattern"]),
        "math": rx(T["math"]["pattern"]),
        "modal": rx(T["modal_hedges"]["pattern"]),
        "amplifiers": rx(T["amplifiers"]["pattern"]),
        "nominal": rx(T["nominalization"]["pattern"]),
        "smiley": rx(T["smileys"]["pattern"]),
        "first_person": rx(T["first_person"]["pattern"]),
        "not_x_but_y": rx(T["not_x_but_y"]["pattern"]),
        "emoji": rx(T["emoji"]["pattern"], 0),
        "list_emoji": rx(T["emoji"]["list_pattern"], re.M),
        "dash_bullet": rx(T["dash_bullet_pattern"], re.M),
        "never": {},
    }
    for label, spec in T["never"].items():
        flags = 0 if spec.get("flags") == "" else re.I
        P["never"][label] = rx(spec["pattern"], flags)
    return P


def strip_frontmatter(text):
    """Черновики в студии лежат с YAML-шапкой - она служебная, не часть поста."""
    return re.sub(r"\A---\n.*?\n---\n", "", text, flags=re.S)


def pick_bucket(buckets, chars):
    """Первый бакет, чья граница `below` больше длины; `below: null` ловит остальное."""
    for b in buckets:
        if b.get("below") is None or chars < b["below"]:
            return b
    return buckets[-1]


# ---------------------------------------------------------------------------
# Измерение: сырые числа по тексту. Их же использует calibrate.py по корпусу.
# ---------------------------------------------------------------------------
def measure(text, T, P):
    lines = [l for l in text.splitlines() if l.strip()]
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    words = len(text.split())
    chars = len(text)
    low = text.lower()

    body_md = "\n".join(lines[1:]) if len(lines) > 1 else ""
    body_md = re.sub(r"\[[^\]]+\]\([^)\s]+\)", "", body_md)

    m = {
        "chars": chars,
        "words": words,
        "lines": len(lines),
        "dash": text.count("—") + text.count("–"),
        "dash_em": text.count("—"),
        "dash_en": text.count("–"),
        "dash_bullets": len(P["dash_bullet"].findall(text)),
        "markdown": len(re.findall(r"\*\*|^#{1,6}\s|^\s*[*_]\s", body_md, re.M)),
        "list_emoji": len(P["list_emoji"].findall(text)),
        "banned": [p for p in T["banned_phrases"]["items"] if p in low],
        "abstract": [p for p in T["abstract_nouns"]["items"] if p in low],
        "never": {label: len(rx.findall(text)) for label, rx in P["never"].items()},
        "copula": len(P["copula"].findall(text)),
        "dannyj": len(P["dannyj"].findall(text)),
        "math": len(P["math"].findall(text)),
        "modal": len(P["modal"].findall(text)),
        "kants": [k for k in T["kants"]["items"] if k in low],
        "amplifiers": len(P["amplifiers"].findall(text)),
        "nominal_per_1000": (1000 * len(P["nominal"].findall(text)) / words) if words else 0.0,
        "smileys": len(P["smiley"].findall(text)),
        "hedges": [h for h in T["hedges"]["items"] if h in low],
        "connectors": [c for c in T["connectors"]["items"] if c in low],
        "first_person": bool(P["first_person"].search(low)),
        "not_x_but_y": len(P["not_x_but_y"].findall(low)),
        "emoji": len(P["emoji"].findall(text)),
        "last_line": lines[-1].rstrip() if lines else "",
        "last_char": (lines[-1].rstrip()[-1] if lines and lines[-1].rstrip() else ""),
        "para_lens": [len(p.split()) for p in paras],
        "para_spread": None,
        "sentence_cv": None,
        "dotted_share": None,
        "title": lines[0] if lines else "",
        "title_words": len(lines[0].split()) if lines else 0,
        "title_dotted": bool(lines and lines[0].rstrip().endswith(".")),
    }

    if len(paras) >= 3:
        lens = m["para_lens"]
        m["para_spread"] = max(lens) / max(1, min(lens))

    clean = re.sub(r"https?://\S+", "", text)
    sent_lens = [len(s.split()) for s in re.split(r"(?<=[.!?])\s+|\n+", clean)
                 if len(s.split()) >= 3]
    if len(sent_lens) >= 5:
        mean = statistics.mean(sent_lens)
        m["sentence_cv"] = statistics.stdev(sent_lens) / mean if mean else 0.0

    if lines:
        dotted = sum(1 for l in lines if l.rstrip().endswith("."))
        m["dotted_share"] = dotted / len(lines)
        m["dotted"] = dotted

    return m


# ---------------------------------------------------------------------------
# Проверки
# ---------------------------------------------------------------------------
class Check:
    def __init__(self, level, label, detail, fix=""):
        self.level = level  # "stop" | "warn" | "ok"
        self.label = label
        self.detail = detail
        self.fix = fix

    def as_dict(self):
        return {"level": self.level, "label": self.label, "detail": self.detail, "fix": self.fix}


def pct(x):
    return f"{round(100 * x)}%" if isinstance(x, (int, float)) else "?"


def analyze(text, T=None, P=None):
    T = T or json.loads(json.dumps(DEFAULTS))
    P = P or compile_patterns(T)
    m = measure(text, T, P)
    out = []
    chars, words = m["chars"], m["words"]
    B = T["buckets"]
    short = chars < B["short_below"]

    # --- жёсткие детекторы ---
    d = T["dash"]
    if d.get("level", "stop") != "off":
        if m["dash"] > d["max_per_post"]:
            detail = f"{m['dash_em']} шт." + (f" + en dash '–' {m['dash_en']} шт." if m["dash_en"] else "")
            out.append(Check(d["level"], "Длинное тире", detail,
                             f"Норма автора: 0-{d['max_per_post']} на пост. Заменить на дефис с пробелами ' - '."))
        else:
            out.append(Check("ok", "Длинное тире", f"{m['dash']} шт.", ""))

    lvl = T["dash_bullets"].get("level", "stop")
    if lvl != "off" and m["dash_bullets"]:
        out.append(Check(lvl, "Буллеты через тире", f"{m['dash_bullets']} шт.",
                         "У автора не встречаются. Заменить на '1. 2. 3.' или '- '."))

    # Жирный заголовок первой строкой и ссылки [текст](url) - норма черновика:
    # при копировании в телегу они превращаются в форматирование. Всё остальное - нет.
    lvl = T["markdown"].get("level", "stop")
    if lvl != "off" and m["markdown"]:
        out.append(Check(lvl, "Markdown-разметка", f"{m['markdown']} шт. (кроме заголовка и ссылок)",
                         "В корпусе отсутствует. Жирным - только заголовок."))

    lvl = T["list_emoji"].get("level", "stop")
    if lvl != "off" and m["list_emoji"]:
        out.append(Check(lvl, "Эмодзи как маркеры списка", f"{m['list_emoji']} шт.",
                         "В корпусе автора их нет. Убрать."))

    lvl = T["banned_phrases"].get("level", "stop")
    if lvl != "off" and m["banned"]:
        out.append(Check(lvl, "Служебные обороты", ", ".join(m["banned"]),
                         "Ноль вхождений в корпусе. Удалить."))

    lvl = T["abstract_nouns"].get("level", "warn")
    if lvl != "off" and m["abstract"]:
        out.append(Check(lvl, "Абстрактные существительные", ", ".join(m["abstract"]),
                         "Заменить на конкретный факт: цифру, сервис, имя, город."))

    # --- машинный русский ---
    for label, spec in T["never"].items():
        lvl = spec.get("level", "stop")
        n = m["never"].get(label, 0)
        if lvl != "off" and n:
            out.append(Check(lvl, label, f"{n} шт.",
                             "Ноль вхождений в корпусе автора. Переписать своими словами."))

    c = T["copula"]
    if m["copula"] >= c["warn_at"]:
        share = f" В корпусе это {pct(c['share'])} постов." if c.get("share") is not None else ""
        out.append(Check("warn", "Обход глагола «быть»", f"{m['copula']} шт. («является», «представляет собой»)",
                         f"Сказать прямо: «это», «у него», «работает как».{share}"))

    c = T["dannyj"]
    if m["dannyj"] >= c["warn_at"]:
        share = f"В корпусе {pct(c['share'])} постов. " if c.get("share") is not None else ""
        out.append(Check("warn", "«Данный» вместо «этот»", f"{m['dannyj']} шт.",
                         f"{share}Заменить на «этот» или убрать."))

    if m["math"] >= T["math"]["warn_at"]:
        out.append(Check("warn", "Матзнаки в прозе", f"{m['math']} шт.",
                         "«Скорость > идеальности» - машинная формула. Написать словами."))

    if m["modal"] >= T["modal_hedges"]["warn_at"]:
        out.append(Check("warn", "Модальное хеджирование",
                         f"{m['modal']} шт. («может стать», «способен обеспечить»)",
                         "Это не хеджи автора: он сомневается сам («кажется»), а не смягчает утверждение."))

    c = T["kants"]
    if len(m["kants"]) >= c["warn_at"]:
        share = f"В корпусе {pct(c['share'])} постов. " if c.get("share") is not None else ""
        out.append(Check("warn", "Канцелярские переходы", ", ".join(m["kants"]),
                         f"{share}Абзацы у автора стыкуются без служебных связок."))

    if m["amplifiers"] >= T["amplifiers"]["warn_at"]:
        out.append(Check("warn", "Слова-усилители", f"{m['amplifiers']} шт. («просто», «действительно»)",
                         "Тест на удаление: убрать слово. Смысл не изменился - это вода."))

    nom_max = T["nominalization"]["max_per_1000"]
    if words and m["nominal_per_1000"] > nom_max:
        out.append(Check("warn", "Номинализация",
                         f"{m['nominal_per_1000']:.0f} на 1000 слов (p90 автора - {nom_max})",
                         "Отглагольные существительные на -ение/-ация. Вернуть глаголы."))

    last = m["last_line"]
    if (T["ending"].get("level", "warn") != "off" and last
            and last[-1] not in T["ending"]["terminals"] and not last.startswith("http")):
        out.append(Check("warn", "Обрыв последней строки", f"«…{last[-40:]}»",
                         "Текст кончается на полуслове - похоже на упёршуюся в лимит генерацию."))

    # --- обязательные маркеры: требования зависят от длины поста ---
    sb = pick_bucket(T["smileys"]["buckets"], chars)
    sm = m["smileys"]
    if sm == 0:
        lvl = sb.get("missing", "warn")
        if lvl != "off":
            if lvl == "ok":
                out.append(Check("ok", "Скобки-улыбки", "нет ни одной (для такой длины норма)", ""))
            else:
                share = sb.get("share_any")
                fix = (f"Есть в {pct(share)} постов такой длины. Нужна хотя бы одна, лучше после самоиронии."
                       if share is not None else "Обычно хотя бы одна есть.")
                out.append(Check(lvl, "Скобки-улыбки", "нет ни одной", fix))
    elif sm == 1:
        lvl = sb.get("single", "ok")
        if lvl != "off":
            out.append(Check(lvl, "Скобки-улыбки", "одна",
                             "" if lvl == "ok" else "Обычно их несколько. Проверить, не суховат ли текст."))
    else:
        out.append(Check("ok", "Скобки-улыбки", f"{sm} шт.", ""))

    hb = pick_bucket(T["hedges"]["buckets"], chars)
    if not m["hedges"]:
        lvl = hb.get("missing", "warn")
        share = hb.get("share")
        if lvl == "ok":
            out.append(Check("ok", "Хеджи", "ни одного (для такой длины норма)", ""))
        elif lvl == "warn":
            out.append(Check("warn", "Хеджи", "ни одного",
                             f"В постах этой длины хедж есть у {pct(share)}. Добавить, если честно по материалу."
                             if share is not None else "Добавить, если честно по материалу."))
        elif lvl == "stop":
            out.append(Check("stop", "Хеджи", "ни одного",
                             f"В постах этой длины хедж есть у {pct(share)}. Без него текст читается как чужой."
                             if share is not None else "Без хеджа длинный текст читается как чужой."))
    else:
        out.append(Check("ok", "Хеджи", ", ".join(m["hedges"][:5]), ""))

    cn = T["connectors"]
    if not m["connectors"]:
        lvl = cn.get("missing", "warn")
        if lvl != "off":
            sample = ", ".join(f"'{c}'" for c in cn["items"][:3])
            out.append(Check(lvl, "Разговорные связки", "ни одной",
                             "" if lvl == "ok" else f"Обычно есть {sample} или похожая."))
    else:
        out.append(Check("ok", "Разговорные связки", ", ".join(m["connectors"]), ""))

    fb = pick_bucket(T["first_person"]["buckets"], chars)
    if not m["first_person"]:
        lvl = fb.get("missing", "warn")
        if lvl != "off" and lvl != "ok":
            share = fb.get("share")
            out.append(Check(lvl, "Личное присутствие", "нет местоимений первого лица",
                             f"В постах этой длины первое лицо есть у {pct(share)}. Заземлить на себя."
                             if share is not None else "Текст автора всегда заземлён на себя."))

    # --- ритм ---
    if m["para_spread"] is not None:
        if m["para_spread"] < T["paragraph_spread"]["min"]:
            out.append(Check("warn", "Ритм абзацев",
                             f"длины {m['para_lens']}, разброс {m['para_spread']:.1f}x",
                             "У автора разброс большой. Добавить абзац в одну строку."))
        else:
            out.append(Check("ok", "Ритм абзацев", f"разброс {m['para_spread']:.1f}x", ""))

    if m["sentence_cv"] is not None:
        sc = T["sentence_cv"]
        if m["sentence_cv"] < sc["min"]:
            med = f"медиана автора {sc['median']:.2f}, " if sc.get("median") is not None else ""
            out.append(Check("warn", "Ритм предложений",
                             f"разброс CV {m['sentence_cv']:.2f} ({med}тревога ниже {sc['min']:.2f})",
                             "Предложения одинаковой длины. Добавить очень короткое или длинный заход."))
        else:
            out.append(Check("ok", "Ритм предложений", f"CV {m['sentence_cv']:.2f}", ""))

    dl = T["dotted_lines"]
    if m["dotted_share"] is not None and m["dotted_share"] > dl["max_share"]:
        typ = f"У автора точку имеет около {pct(dl['typical'])} строк. " if dl.get("typical") is not None else ""
        out.append(Check("warn", "Финальная пунктуация",
                         f"{m['dotted']} из {m['lines']} строк с точкой", f"{typ}Расшатать."))

    if m["not_x_but_y"] >= T["not_x_but_y"]["warn_at"]:
        out.append(Check("warn", "Конструкция «не X, а Y»", f"{m['not_x_but_y']} шт.",
                         "Допустима одна на пост. Оставить самую содержательную."))

    # --- объём и оформление ---
    L = T["length"]
    note = f"норма {L['norm_min']}-{L['norm_max']}"
    lvl = "ok" if L["ok_min"] <= chars <= L["ok_max"] else "warn"
    out.append(Check(lvl, "Длина", f"{chars} знаков, {words} слов ({note})",
                     "Слишком длинный пост оправдан только анонсом или большим отчётом." if chars > L["ok_max"]
                     else ("Коротковато для содержательного поста, если это не мини-реплика."
                           if chars < L["ok_min"] else "")))

    tt = T["title"]
    if tt.get("enabled", True) and m["title"]:
        w = m["title_words"]
        if w > tt["max_words"] or m["title_dotted"]:
            out.append(Check("warn", "Заголовок", f"«{m['title'][:50]}» ({w} сл.)",
                             f"Обычно 1-{max(1, tt['max_words'] - 2)} слова, именная группа, без точки."))
        else:
            out.append(Check("ok", "Заголовок", f"«{m['title'][:50]}» ({w} сл.)", ""))

    if m["emoji"] >= T["emoji"]["warn_at"]:
        out.append(Check("warn", "Эмодзи", f"{m['emoji']} шт.",
                         "Обычно их почти нет, эмоция передаётся скобками."))

    return out


def score_of(checks, T):
    stops = sum(1 for c in checks if c.level == "stop")
    warns = sum(1 for c in checks if c.level == "warn")
    s = T["score"]
    return stops, warns, max(0, 100 - s["stop"] * stops - s["warn"] * warns)


# ---------------------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(description="Линтер черновика под голос автора.")
    ap.add_argument("file", nargs="?", help="черновик (без аргумента - stdin)")
    ap.add_argument("--thresholds", help="thresholds.json (иначе поиск по стандартным путям)")
    ap.add_argument("--strict", action="store_true", help="код 2, если есть блокеры")
    ap.add_argument("--json", action="store_true", help="машинный вывод")
    args = ap.parse_args(argv)

    if args.file:
        with open(args.file, encoding="utf-8") as f:
            text = f.read()
    else:
        text = sys.stdin.read()

    if not text.strip():
        print("пустой текст")
        return 1

    text = strip_frontmatter(text)
    T, source = load_thresholds(args.thresholds)
    checks = analyze(text, T)
    stops, warns, score = score_of(checks, T)

    if args.json:
        print(json.dumps({
            "thresholds": source, "score": score, "stops": stops, "warns": warns,
            "checks": [c.as_dict() for c in checks],
        }, ensure_ascii=False, indent=1))
        return 2 if (args.strict and stops) else 0

    icons = {"stop": "!!", "warn": " ~", "ok": " ok"}
    order = {"stop": 0, "warn": 1, "ok": 2}
    label = T["meta"].get("corpus_label") or "норма автора"

    print(f"\n=== ЛИНТЕР ПОСТА ({label}) ===\n")
    for c in sorted(checks, key=lambda c: order[c.level]):
        print(f"{icons[c.level]:>3}  {c.label}: {c.detail}")
        if c.fix:
            print(f"     -> {c.fix}")

    print(f"\nблокеров: {stops}, замечаний: {warns}  |  похоже на автора: {score}/100")
    if stops:
        print("Текст пока читается как написанный не автором. Править по списку выше.")
    elif warns:
        print("Голос узнаваем, есть что подтянуть.")
    else:
        print("Механических отклонений нет. Дальше судить содержательно по fingerprint.md.")
    if source == "DEFAULTS":
        print("\n(пороги встроенные, не вашего автора: снимите свои через calibrate.py)")

    print("\nМеханика - половина дела. Смысловой слоп линтер не видит, для него:")
    print("  1. Тест гороскопа: мог бы этот текст написать кто угодно про что угодно?")
    print("  2. Кухня процесса: это суть истории или отчёт о моей работе?")
    print("  3. Правило светофора: править только помеченное, чистые абзацы не трогать.")

    # --strict нужен для хуков и CI: без него код возврата всегда 0.
    if args.strict and stops:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())