#!/usr/bin/env python3
"""Блоки для отчёта по нише «Claude Code и вайб-кодинг» на Хабре.

Отличие от report.py: тот меряет площадку целиком, этот — одну тему внутри
неё. Вопрос другой: не «что тут заходит», а «что уже занято и где дыра».

    python3 habr/niche_report.py 2026-08-23-habr-nisha-vaib-kodinga
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.store import DATA, TEXTS, load_by_id, read_jsonl
from habr.topic import is_relevant
from report import REPORTS, bars, kpi, stack

RU_SUBJECT = {
    "вайб_кодинг_практика": "Практика вайб-кодинга",
    "claude_code": "Claude Code",
    "другой_инструмент": "Другой инструмент",
    "рынок_и_профессия": "Рынок и профессия",
    "агенты_архитектура": "Агенты и протоколы",
    "сравнение_инструментов": "Сравнение инструментов",
    "железо_и_доступ": "Железо и доступ",
    "прочее": "Прочее",
    "обучение": "Обучение",
}
RU_DEPTH = {"поверхностно": "Поверхностно", "рабочий_уровень": "Рабочий уровень",
            "глубоко": "Глубоко"}
RU_PROOF = {"свой_опыт_с_цифрами": "Свой опыт с цифрами", "свой_опыт_без_цифр": "Свой опыт без цифр",
            "чужие_данные": "Чужие данные", "документация": "Пересказ документации",
            "рассуждение": "Рассуждение"}


def load() -> tuple[list[dict], list[tuple[dict, dict]]]:
    cards = load_by_id(DATA / "habr-topic" / "cards.jsonl")
    niche = [c for c in cards.values() if (c.get("views") or 0) > 0 and is_relevant(c)]
    labels = {str(r["id"]): r
              for p in sorted((TEXTS / "habr-topic" / "labels").glob("batch-*.jsonl"))
              for r in read_jsonl(p)}
    pairs = [(cards[i], l) for i, l in labels.items() if i in cards]
    return niche, pairs


def quarters_block(niche: list[dict]) -> dict:
    q: Counter = Counter()
    for c in niche:
        y, m = int(c["published_at"][:4]), int(c["published_at"][5:7])
        q[f"{y} Q{(m - 1) // 3 + 1}"] += 1
    items = [{"label": k, "value": v, "note": ""} for k, v in sorted(q.items())]
    items[-1]["note"] = "квартал не закончился"
    return bars(
        "Сколько статей в нише выходит по кварталам",
        "Все статьи про Claude Code, вайб-кодинг и агентов в разработке с января 2025.",
        len(niche), items)


def clusters_block(pairs: list[tuple[dict, dict]]) -> dict:
    counts = Counter(l.get("subject") for _, l in pairs)
    return bars(
        "Чем занята верхняя сотня",
        "Сколько статей из ста приходится на каждую делянку. Размечено чтением полных текстов.",
        len(pairs),
        [{"label": RU_SUBJECT.get(k, k), "value": v, "note": ""} for k, v in counts.most_common()])


def depth_block(pairs: list[tuple[dict, dict]]) -> dict:
    d = defaultdict(list)
    for c, l in pairs:
        d[l.get("depth")].append((c.get("extra") or {}).get("score") or 0)
    order = ["глубоко", "рабочий_уровень", "поверхностно"]
    return bars(
        "Что Хабр плюсует: медиана рейтинга по глубине",
        "Просмотры у трёх групп почти одинаковые (60, 48 и 51 тысяча). Рейтинг — нет.",
        len(pairs),
        [{"label": RU_DEPTH[k], "value": round(statistics.median(d[k])),
          "note": f"{len(d[k])} статей"} for k in order if d.get(k)])


def proof_block(pairs: list[tuple[dict, dict]]) -> dict:
    d = defaultdict(list)
    for c, l in pairs:
        d[l.get("proof")].append((c.get("extra") or {}).get("score") or 0)
    items = [{"label": RU_PROOF.get(k, k), "value": round(statistics.median(v)),
              "note": f"{len(v)} статей"} for k, v in d.items() if len(v) >= 5]
    items.sort(key=lambda x: -x["value"])
    return bars(
        "Медиана рейтинга по тому, чем автор доказывает",
        "Позиция собирает плюсы, пересказ документации — нет.",
        len(pairs), items)


def authors_block(niche: list[dict], pairs: list[tuple[dict, dict]]) -> dict:
    top = [c for c, _ in pairs]
    counts = Counter("Корпоративный блог" if c["author_kind"] == "company" else "Частный автор"
                     for c in top)
    return stack(
        "Кто пишет верхнюю сотню",
        "Флаг корпоративности приходит из API площадки, не размечался.",
        len(top),
        [{"label": k, "value": v} for k, v in counts.most_common()])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    args = ap.parse_args()
    niche, pairs = load()
    top = sorted((c for c, _ in pairs), key=lambda c: -(c["views"] or 0))
    by_views = {c["id"] for c in top[:25]}
    by_score = {c["id"] for c in sorted(top, key=lambda c: -((c.get("extra") or {}).get("score") or 0))[:25]}

    blocks = [
        kpi([
            ("Статей в нише", str(len(niche)), "с января 2025"),
            ("Порог верхней сотни", f"{top[-1]['views'] // 1000} тыс.", "просмотров"),
            ("Медиана сотни", f"{statistics.median([c['views'] for c in top]) / 1000:.0f} тыс.",
             f"против {statistics.median([c['views'] for c in niche]) / 1000:.1f} тыс. по нише"),
            ("Топ по просмотрам ∩ топ по рейтингу", f"{len(by_views & by_score)} из 25",
             "два разных успеха"),
        ]),
        quarters_block(niche),
        clusters_block(pairs),
        depth_block(pairs),
        proof_block(pairs),
        authors_block(niche, pairs),
    ]
    out = REPORTS / f"{args.slug}.data.json"
    out.write_text(json.dumps({"blocks": blocks}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{out}: {len(blocks)} блоков; ниша {len(niche)}, размечено {len(pairs)}")


if __name__ == "__main__":
    main()
