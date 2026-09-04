#!/usr/bin/env python3
"""Считает блоки для отчёта в студию: content/reports/<слаг>.data.json.

Формы всего четыре — kpi, bars, dumbbell, stack, — и это ограничение
из студии, а не лень: пятую форму заводят, когда появляется работа,
которую ни одна из четырёх не делает. Поле sample заполняется всегда:
без него любая разница на картинке выглядит убедительнее, чем она есть.

    python3 report.py habr 2026-08-23-habr-chto-chitayut
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter
from pathlib import Path

from analyze import PEER, SPLIT_KEY, add_lift, clean, load, split
from common.features import medians
from common.store import REPO

REPORTS: Path = REPO / "content" / "reports"

RU_GENRE = {"кейс": "Кейс", "гайд": "Гайд", "разбор": "Разбор", "мнение": "Мнение",
            "исповедь": "Исповедь", "подборка": "Подборка", "туториал": "Туториал",
            "обзор": "Обзор", "интервью": "Интервью",
            "новость_с_комментарием": "Новость с комментарием"}
RU_HOOK = {"история": "История", "цифра": "Цифра", "конфликт": "Конфликт",
           "вопрос": "Вопрос", "определение": "Определение",
           "анонс_итога": "Итог сразу", "обещание_пользы": "Обещание пользы"}
RU_SPEC = {"свои_цифры": "Свои цифры", "чужие_цифры": "Чужие цифры",
           "примеры_без_цифр": "Примеры без цифр", "общие_слова": "Общие слова"}


def kpi(items: list[tuple[str, str, str]]) -> dict:
    return {"type": "kpi", "items": [{"label": a, "value": b, "note": c} for a, b, c in items]}


def dumbbell(title: str, hint: str, sample: int, legend: dict, items: list[dict],
             unit: str = "") -> dict:
    return {"type": "dumbbell", "title": title, "hint": hint, "sample": sample,
            "unit": unit, "legend": legend, "items": items}


def bars(title: str, hint: str, sample: int, items: list[dict], unit: str = "") -> dict:
    return {"type": "bars", "title": title, "hint": hint, "sample": sample,
            "unit": unit, "items": items}


def stack(title: str, hint: str, sample: int, items: list[dict]) -> dict:
    return {"type": "stack", "title": title, "hint": hint, "sample": sample, "items": items}


def structure_block(top: list[dict], rest: list[dict]) -> dict:
    a, b = medians([r["_f"] for r in top]), medians([r["_f"] for r in rest])
    keys = [("Знаков", "chars"), ("Подзаголовков", "headers"), ("Пунктов списка", "list_items"),
            ("Картинок", "media"), ("Ритм абзацев, p90/p10", "para_p90_p10"),
            ("Ровных абзацев подряд", "max_run_even")]
    return dumbbell(
        "Чем верхняя четверть отличается от остальных",
        "Медианы. Ритм p90/p10 — во сколько раз длинный абзац длиннее короткого.",
        len(top) + len(rest),
        {"a": f"верхняя четверть ({len(top)})", "b": f"остальные ({len(rest)})"},
        [{"label": label, "a": round(a[key]), "b": round(b[key])} for label, key in keys],
    )


def title_block(top: list[dict], rest: list[dict]) -> dict:
    a, b = medians([r["_f"] for r in top]), medians([r["_f"] for r in rest])
    keys = [("Есть число", "t_num"), ("Двоеточие", "t_colon"),
            ("От первого лица", "t_first_person"), ("Моя история", "t_my_story"),
            ("Инструкция «как…»", "t_howto"), ("Отрицание", "t_neg"),
            ("Обращение к читателю", "t_you")]
    return dumbbell(
        "Что в заголовке",
        "Доля статей с признаком.",
        len(top) + len(rest),
        {"a": f"верхняя четверть ({len(top)})", "b": f"остальные ({len(rest)})"},
        [{"label": label, "a": round(a[key]), "b": round(b[key])} for label, key in keys],
        unit="%",
    )


def label_lift_block(rows: list[dict], field: str, ru: dict, title: str, hint: str,
                     min_n: int = 5, key: str = "_lift") -> dict | None:
    """Медиана лифта (или просмотров) по значению разметки."""
    groups: dict[str, list[float]] = {}
    for r in rows:
        val = (r.get("_l") or {}).get(field)
        if val:
            groups.setdefault(val, []).append(r[key])
    digits = 1 if key == "_lift" else 0
    items = [{"label": ru.get(k, k), "value": round(statistics.median(v), digits),
              "note": f"{len(v)} статей"}
             for k, v in groups.items() if len(v) >= min_n]
    if len(items) < 2:
        return None
    items.sort(key=lambda x: -x["value"])
    return bars(title, hint, sum(len(v) for v in groups.values()), items,
                unit="x" if key == "_lift" else "")


def peers_block(platform: str, rows: list[dict]) -> dict:
    """Норма разных доноров охвата: почему залёт считается относительно."""
    peer_of = PEER[platform]
    groups: dict[str, list[int]] = {}
    for r in rows:
        groups.setdefault(peer_of(r) or "—", []).append(r["views"])
    big = sorted(((k, v) for k, v in groups.items() if len(v) >= 5),
                 key=lambda kv: -statistics.median(kv[1]))[:8]
    return bars(
        "Обычная статья у разных доноров охвата",
        "Медиана просмотров. Разброс между ними и есть причина считать залёт "
        "относительно нормы, а не в абсолютных просмотрах.",
        len(rows),
        [{"label": (k or "—")[:45], "value": round(statistics.median(v)),
          "note": f"{len(v)} статей"} for k, v in big],
    )


def top_titles_block(top: list[dict]) -> dict:
    return bars(
        "Самые залетевшие",
        "Просмотры. Заголовки обрезаны до 45 знаков.",
        len(top),
        [{"label": r["title"][:45], "value": r["views"], "note": f"x{r['_lift']:.0f}"}
         for r in top[:8]],
    )


def speaker_stack(rows: list[dict]) -> dict | None:
    counts = Counter((r.get("_l") or {}).get("speaker") for r in rows
                     if (r.get("_l") or {}).get("speaker"))
    if len(counts) < 2:
        return None
    ru = {"частное_лицо": "Частное лицо", "лицо_от_компании": "Лицо от компании",
          "корпоративный_блог": "Корпоративный блог", "редакция": "Редакция",
          "аноним": "Аноним"}
    return stack(
        "Кто говорит в верхней четверти",
        "Размечено чтением: «лицо от компании» — человек пишет «я», но продаёт свою компанию.",
        sum(counts.values()),
        [{"label": ru.get(k, k), "value": v} for k, v in counts.most_common(6)],
    )


def subscribers_block(rows: list[dict]) -> dict | None:
    """Сколько даёт размер аудитории автора — до всякого текста."""
    known = [r for r in rows if (r.get("extra") or {}).get("subscribers")]
    if len(known) < 40:
        return None
    buckets = [("до 1 000", 0, 1000), ("1–5 тыс.", 1000, 5000),
               ("5–20 тыс.", 5000, 20000), ("больше 20 тыс.", 20000, 10 ** 9)]
    items = []
    for label, lo, hi in buckets:
        vals = [r["views"] for r in known
                if lo <= ((r.get("extra") or {}).get("subscribers") or 0) < hi]
        if len(vals) >= 10:
            items.append({"label": label, "value": round(statistics.median(vals)),
                          "note": f"{len(vals)} статей"})
    if len(items) < 2:
        return None
    return bars(
        "Что даёт размер аудитории автора",
        "Медиана просмотров по размеру подписной базы. Это фора, которая есть "
        "до того, как написана первая строка.",
        len(known), items)


def metrics_overlap_block(rows: list[dict], n: int) -> dict | None:
    """Хабр меряет успех тремя разными счётчиками, и они не совпадают."""
    def top_by(key) -> set:
        return {r["id"] for r in sorted(rows, key=key, reverse=True)[:n]}

    views = top_by(lambda r: r["views"] or 0)
    score = top_by(lambda r: (r.get("extra") or {}).get("score") or 0)
    fav = top_by(lambda r: (r.get("extra") or {}).get("favorites") or 0)
    if not any((r.get("extra") or {}).get("score") for r in rows):
        return None
    return bars(
        "Верх по просмотрам и верх по рейтингу — разные статьи",
        "Совпадение верхних четвертей, %. Плюсы меряют одобрение сообщества, "
        "просмотры — попадание в поиск и в ленты, закладки — пользу.",
        len(rows),
        [{"label": "Просмотры и рейтинг", "value": round(100 * len(views & score) / n),
          "note": f"{len(views & score)} из {n}"},
         {"label": "Рейтинг и закладки", "value": round(100 * len(score & fav) / n),
          "note": f"{len(score & fav)} из {n}"},
         {"label": "Просмотры и закладки", "value": round(100 * len(views & fav) / n),
          "note": f"{len(views & fav)} из {n}"}],
        unit="%",
    )


def build(platform: str) -> tuple[list[dict], dict]:
    rows = clean(platform, load(platform))
    add_lift(platform, rows)
    top, rest = split(rows, SPLIT_KEY[platform])
    views = [r["views"] for r in rows]
    labeled = [r for r in rows if r.get("_l")]

    blocks = [
        kpi([
            ("Статей в замере", str(len(rows)), "за 12 месяцев"),
            ("Медиана просмотров", f"{statistics.median(views):.0f}", "по корпусу"),
            ("Порог верхней четверти",
             f"{top[-1]['views']:,}".replace(",", " ") if SPLIT_KEY[platform] == "views"
             else f"x{top[-1]['_lift']:.1f}",
             "просмотров" if SPLIT_KEY[platform] == "views" else "к норме своего донора"),
            ("Максимум", f"{max(views):,}".replace(",", " "), "просмотров"),
        ]),
        peers_block(platform, rows),
    ]
    overlap = metrics_overlap_block(rows, len(top))
    if overlap:
        blocks.append(overlap)
    blocks += [
        structure_block(top, rest),
        title_block(top, rest),
        top_titles_block(top),
    ]
    key = SPLIT_KEY[platform]
    unit_hint = ("Медиана просмотров." if key == "views"
                 else "Медиана лифта к норме донора. Единица — обычная статья.")
    genre = label_lift_block(labeled, "genre", RU_GENRE,
                             "Сколько собирает статья разного жанра", unit_hint, key=key)
    if genre:
        blocks.append(genre)
    hook = label_lift_block(labeled, "lead_hook", RU_HOOK,
                            "Чем начинается залетевшая статья",
                            unit_hint + " Тип зачина размечен чтением.", key=key)
    if hook:
        blocks.append(hook)
    spec = label_lift_block(labeled, "specificity", RU_SPEC,
                            "Своя фактура против общих слов",
                            unit_hint + " Тип конкретики размечен чтением.", key=key)
    if spec:
        blocks.append(spec)
    subs = subscribers_block(rows)
    if subs:
        blocks.append(subs)
    sp = speaker_stack(top)
    if sp:
        blocks.append(sp)

    stats = {
        "rows": len(rows), "top": len(top), "rest": len(rest),
        "labeled": len(labeled),
        "median_views": statistics.median(views),
        "max_views": max(views),
        "threshold_lift": round(top[-1]["_lift"], 1),
        "med_top": medians([r["_f"] for r in top]),
        "med_rest": medians([r["_f"] for r in rest]),
        "top_titles": [(r["title"], r["views"], round(r["_lift"], 1)) for r in top[:15]],
    }
    return blocks, stats


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("platform")
    ap.add_argument("slug")
    args = ap.parse_args()
    blocks, stats = build(args.platform)
    out = REPORTS / f"{args.slug}.data.json"
    out.write_text(json.dumps({"blocks": blocks}, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print(f"{out}: {len(blocks)} блоков")
    print(json.dumps({k: v for k, v in stats.items()
                      if k not in ("med_top", "med_rest")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
