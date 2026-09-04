#!/usr/bin/env python3
"""Сводный отчёт: то, чего не видно внутри одной площадки.

Правило простое — сюда идёт только то, что нельзя посчитать на одной
площадке. Пересказ четырёх отчётов пятым документом никому не нужен.

    python3 summary.py 2026-08-23-gde-publikovatsya
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict

from analyze import SPLIT_KEY, add_lift, clean, load, split
from common.features import medians
from report import REPORTS, bars, dumbbell, kpi

SITES = [("habr", "Хабр"), ("dzen", "Дзен"), ("tenchat", "TenChat"),
         ("dtf", "DTF"), ("vc", "vc.ru")]

# Лента раздаёт, поиск накапливает — разные машины, разные правила.
FEED = {"dzen", "tenchat"}


def corpus() -> dict[str, dict]:
    out = {}
    for site, label in SITES:
        rows = clean(site, load(site))
        if len(rows) < 30:
            continue
        add_lift(site, rows)
        top, rest = split(rows, SPLIT_KEY[site])
        out[site] = {"label": label, "rows": rows, "top": top, "rest": rest,
                     "med_top": medians([r["_f"] for r in top]),
                     "med_rest": medians([r["_f"] for r in rest])}
    return out


def views_block(data: dict) -> dict:
    items = [{"label": d["label"],
              "value": round(statistics.median([r["views"] for r in d["rows"]])),
              "note": f"{len(d['rows'])} статей"}
             for d in data.values()]
    items.sort(key=lambda x: -x["value"])
    return bars(
        "Сколько собирает обычная статья",
        "Медиана просмотров по корпусу площадки. Корпуса собраны по-разному, "
        "поэтому это порядок величины, а не рейтинг площадок.",
        sum(len(d["rows"]) for d in data.values()), items)


def price_of_char_block(data: dict) -> dict:
    items = []
    for d in data.values():
        vals = [1000 * r["views"] / max(1, r["_f"]["chars"]) for r in d["rows"]]
        items.append({"label": d["label"], "value": round(statistics.median(vals)),
                      "note": f"медиана длины {round(statistics.median([r['_f']['chars'] for r in d['rows']]))} зн"})
    items.sort(key=lambda x: -x["value"])
    return bars(
        "Цена тысячи знаков",
        "Сколько просмотров приходится на тысячу знаков текста у медианной статьи. "
        "Где длинный текст окупается, а где его никто не просил.",
        sum(len(d["rows"]) for d in data.values()), items)


def feed_vs_search_block(data: dict) -> dict | None:
    groups: dict[str, list[dict]] = {"feed": [], "search": []}
    for site, d in data.items():
        groups["feed" if site in FEED else "search"].extend(d["top"])
    if not groups["feed"] or not groups["search"]:
        return None

    def stat(rows: list[dict], fn) -> float:
        return statistics.median([fn(r) for r in rows])

    a, b = groups["feed"], groups["search"]
    items = [
        {"label": "Возраст статьи, дней", "a": round(stat(a, lambda r: r["_age"])),
         "b": round(stat(b, lambda r: r["_age"]))},
        {"label": "Знаков", "a": round(stat(a, lambda r: r["_f"]["chars"])),
         "b": round(stat(b, lambda r: r["_f"]["chars"]))},
        {"label": "Подзаголовков", "a": round(stat(a, lambda r: r["_f"]["headers"])),
         "b": round(stat(b, lambda r: r["_f"]["headers"]))},
        {"label": "Доля моложе 90 дней, %",
         "a": round(100 * sum(1 for r in a if r["_age"] < 90) / len(a)),
         "b": round(100 * sum(1 for r in b if r["_age"] < 90) / len(b))},
    ]
    return dumbbell(
        "Лента против поиска",
        "Верхние четверти всех площадок, сложенные в две группы. Дзен и TenChat "
        "раздают алгоритмом, Хабр и DTF копят охват из поиска и обсуждения.",
        len(a) + len(b),
        {"a": f"лента: Дзен, TenChat ({len(a)})", "b": f"поиск: Хабр, DTF, vc ({len(b)})"},
        items)


def universal_block(data: dict) -> dict:
    """Один признак, четыре площадки: где он работает, а где нет."""
    items = []
    for d in data.values():
        top, rest = d["med_top"], d["med_rest"]
        if top["headers"] < 1 and rest["headers"] < 1:
            continue      # площадка без подзаголовков вовсе — сравнивать нечего
        ratio = top["headers"] / max(0.5, rest["headers"])
        items.append({"label": d["label"], "value": round(ratio, 2),
                      "note": f"{round(top['headers'])} против {round(rest['headers'])}"})
    items.sort(key=lambda x: -x["value"])
    return bars(
        "Во сколько раз у верхней четверти больше подзаголовков",
        "Единица — «столько же, сколько у остальных». Признак, который на vc был "
        "самым сильным, работает не везде.",
        sum(len(d["rows"]) for d in data.values()), items, unit="x")


def genre_block(data: dict, genres: tuple[str, ...] = ("кейс", "исповедь", "разбор", "гайд")) -> dict | None:
    items = []
    for site, d in data.items():
        by: dict[str, list[float]] = defaultdict(list)
        for r in d["rows"]:
            g = (r.get("_l") or {}).get("genre")
            if g in genres:
                by[g].append(r["_lift"])
        for g in genres:
            if len(by[g]) >= 6:
                items.append({"label": f"{d['label']}: {g}",
                              "value": round(statistics.median(by[g]), 1),
                              "note": f"{len(by[g])} статей"})
    if len(items) < 3:
        return None
    items.sort(key=lambda x: -x["value"])
    return bars(
        "Один жанр на разных площадках",
        "Медиана лифта к норме своего донора охвата. Единица — обычная статья.",
        sum(len(d["rows"]) for d in data.values()), items[:10], unit="x")


def first_person_block(data: dict) -> dict:
    items = []
    for d in data.values():
        items.append({"label": d["label"],
                      "value": round(d["med_top"]["t_first_person"]),
                      "note": f"у остальных {round(d['med_rest']['t_first_person'])}%"})
    items.sort(key=lambda x: -x["value"])
    return bars(
        "«Я» в заголовке у верхней четверти",
        "Доля заголовков от первого лица среди залетевших. В скобках — сколько "
        "у остальных на той же площадке.",
        sum(len(d["top"]) for d in data.values()), items, unit="%")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    args = ap.parse_args()
    data = corpus()

    total = sum(len(d["rows"]) for d in data.values())
    chars = sum(sum(r["_f"]["chars"] for r in d["rows"]) for d in data.values())
    meds = {s: statistics.median([r["views"] for r in d["rows"]]) for s, d in data.items()}
    spread = max(meds.values()) / max(1, min(meds.values()))

    blocks = [
        kpi([("Площадок", str(len(data)), "с корпусом от 30 статей"),
             ("Статей в замере", str(total), "за 12 месяцев"),
             ("Знаков прочитано", f"{chars // 1000} тыс.", "полные тексты"),
             ("Разрыв медиан", f"x{spread:.0f}", "между площадками")]),
        views_block(data),
        price_of_char_block(data),
        universal_block(data),
        first_person_block(data),
    ]
    fs = feed_vs_search_block(data)
    if fs:
        blocks.insert(4, fs)
    g = genre_block(data)
    if g:
        blocks.append(g)

    out = REPORTS / f"{args.slug}.data.json"
    out.write_text(json.dumps({"blocks": blocks}, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print(f"{out}: {len(blocks)} блоков")
    for site, d in data.items():
        print(f"  {d['label']:<9} {len(d['rows']):>4} статей, медиана "
              f"{statistics.median([r['views'] for r in d['rows']]):>8.0f} просм, "
              f"верх {len(d['top'])}")


if __name__ == "__main__":
    main()
