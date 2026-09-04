#!/usr/bin/env python3
"""Готовит числа и блоки для отчёта в студию.

Пишет `<слаг>.data.json` рядом с отчётом: графики строятся из данных, а не
переносятся в текст руками. Прозу отчёта пишет человек — генератор отвечает
только за цифры, чтобы их нельзя было исказить при пересказе.

Блоки ставятся в текст отчёта маркером `[[block:N]]` на отдельной строке.

Запуск:
    python3 report.py 2026-08-19-threads-baza
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

from analyze import MIN_AGE_HOURS, latest_snapshot, load, summarize
from features import engagement, extract, reply_share

HERE = Path(__file__).resolve().parent


def _common_dir() -> Path:
    """Где лежит `common.py` мастерской: `tools/trend-watch/` или `tools/tools/trend-watch/` выше по дереву."""
    bases = [Path(os.environ["WORKSHOP_ROOT"]).expanduser()] if os.environ.get("WORKSHOP_ROOT") else []
    bases += list(HERE.parents)
    for base in bases:
        for rel in ("tools/trend-watch", "tools/tools/trend-watch"):
            if (base / rel / "common.py").exists():
                return base / rel
    raise SystemExit("не нашёл tools/trend-watch/common.py: инструмент запускается из клона репозитория")


sys.path.insert(0, str(_common_dir()))
from common import find_root  # noqa: E402

REPORTS_DIR = find_root() / "content" / "reports"

FEATURE_LABELS = {
    "ends_with_question": "Вопрос в конце",
    "has_number": "Есть цифры",
    "first_person": "От первого лица",
    "has_list": "Список",
    "has_link": "Ссылка",
}

HOOK_LABELS = {
    "question": "Вопрос",
    "number": "Цифра",
    "personal": "Личное",
    "statement": "Заявление",
}


def pct(value: float) -> int:
    return round(value * 100)


def build_blocks(rows: list[dict], result: dict) -> list[dict]:
    blocks: list[dict] = []
    t = result["totals"]
    features = {f["feature"]: f for f in result["features"]}
    n_top = result["features"][0]["n_top"] if result["features"] else 0
    n_rest = result["features"][0]["n_rest"] if result["features"] else 0

    mature = [r for r in rows if (r.get("age_hours") or 0) >= MIN_AGE_HOURS]

    # 0. Числа сами по себе: это не график, это плитки.
    blocks.append(
        {
            "type": "kpi",
            "items": [
                {"label": "Постов в базе", "value": f"{t['posts_total']:,}".replace(",", " ")},
                {"label": "Авторов", "value": str(t["authors"]),
                 "note": f"из них {t['authors_with_baseline']} с базовой линией"},
                {"label": "Сравнимых постов", "value": str(t["posts_comparable"]),
                 "note": f"старше {MIN_AGE_HOURS} часов, из лент авторов"},
                {"label": "Медианная длина", "value": f"{round(statistics.median([len(r['text']) for r in mature]))}",
                 "note": "знаков"},
            ],
        }
    )

    # 1. Разброс аккаунтов по медианному вовлечению.
    by_author: dict[str, list[int]] = defaultdict(list)
    for row in rows:
        if row.get("source") == "profile":
            by_author[row["author"]].append(engagement(row))
    medians = sorted(
        ((a, statistics.median(v)) for a, v in by_author.items() if len(v) >= 3),
        key=lambda x: x[1],
        reverse=True,
    )
    if medians:
        blocks.append(
            {
                "type": "bars",
                "title": "Обычный пост у разных авторов",
                "hint": "Медиана вовлечения по ленте автора. Разброс между аккаунтами в сотни раз — "
                "поэтому виральность считается относительно нормы автора, а не в лайках.",
                "sample": sum(len(v) for v in by_author.values()),
                "items": [{"label": f"@{a}", "value": round(m)} for a, m in medians[:14]],
            }
        )

    # 2. Признаки текста: лучшая четверть лент против остальных постов.
    items = []
    for key, label in FEATURE_LABELS.items():
        row = features.get(key)
        if row:
            items.append({"label": label, "a": pct(row["top_share"]), "b": pct(row["rest_share"])})
    if items:
        blocks.append(
            {
                "type": "dumbbell",
                "title": "Что отличает выстрелившие посты",
                "hint": "Доля постов с признаком. Разрыв меньше пары десятков процентов "
                "на такой выборке ничего не доказывает.",
                "sample": n_top + n_rest,
                "unit": "%",
                "legend": {"a": f"лучшая четверть ({n_top})", "b": f"остальные ({n_rest})"},
                "items": items,
            }
        )

    # 3. Чем начинается пост.
    hook_items = []
    for key, label in HOOK_LABELS.items():
        row = features.get(f"hook_type={key}")
        if row:
            hook_items.append({"label": label, "a": pct(row["top_share"]), "b": pct(row["rest_share"])})
    if hook_items:
        blocks.append(
            {
                "type": "dumbbell",
                "title": "Чем начинается первая строка",
                "hint": "Первая строка — единственное, что видно в ленте до раскрытия поста.",
                "sample": n_top + n_rest,
                "unit": "%",
                "legend": {"a": f"лучшая четверть ({n_top})", "b": f"остальные ({n_rest})"},
                "items": hook_items,
            }
        )

    # 4. Из чего складывается вовлечение.
    if mature:
        totals = Counter()
        for row in mature:
            for key in ("likes", "replies", "reposts", "quotes"):
                totals[key] += int(row.get(key) or 0)
        blocks.append(
            {
                "type": "stack",
                "title": "Из чего складывается вовлечение",
                "hint": "Доли по всему корпусу. Ответы важны отдельно: в Threads охват растёт "
                "с диалога, а просмотры чужих постов площадка не показывает.",
                "sample": len(mature),
                "items": [
                    {"label": name, "value": totals[key]}
                    for key, name in [
                        ("likes", "Лайки"),
                        ("replies", "Ответы"),
                        ("quotes", "Цитаты"),
                        ("reposts", "Репосты"),
                    ]
                ],
            }
        )

    return blocks


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("slug", help="слаг отчёта, например 2026-08-19-threads-baza")
    args = parser.parse_args()

    rows = latest_snapshot(load())
    if not rows:
        raise SystemExit("нет данных")

    result = summarize(rows)
    blocks = build_blocks(rows, result)

    out = REPORTS_DIR / f"{args.slug}.data.json"
    out.write_text(json.dumps({"blocks": blocks}, ensure_ascii=False, indent=1))

    t = result["totals"]
    print(f"постов: {t['posts_total']}, авторов: {t['authors']}, сравнимых: {t['posts_comparable']}")
    print(f"блоков: {len(blocks)} -> {out}")
    for i, block in enumerate(blocks):
        print(f"  [[block:{i}]] {block['type']}: {block.get('title', 'плитки')}")

    mature = [r for r in rows if (r.get("age_hours") or 0) >= MIN_AGE_HOURS]
    print(f"\nмедианная длина: {round(statistics.median([len(r['text']) for r in mature]))} знаков")
    print(f"медианная доля ответов: {pct(statistics.median([reply_share(r) for r in mature]))}%")
    print(f"хуки по корпусу: {dict(Counter(extract(r)['hook_type'] for r in mature))}")
    print(f"медиана длины в топе против остальных: "
          f"{features_median(result, 'length (медиана)')}")
    print("\nлучшая четверть лент:")
    for post in result["top"][:12]:
        head = (post["text"] or "").split("\n")[0][:58]
        print(f"  x{post['score']:<6} @{post['author']:<20} {post['engagement']:>6}  {head}")


def features_median(result: dict, name: str) -> str:
    for row in result["features"]:
        if row["feature"] == name:
            return f"{row['top_share']} против {row['rest_share']}"
    return "—"


if __name__ == "__main__":
    main()
