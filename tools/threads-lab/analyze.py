#!/usr/bin/env python3
"""Сводка по собранным постам: чем удачные посты авторов отличаются от их обычных.

Виральность считаем как превышение автором собственной нормы, а не абсолютные
лайки. Просмотры отдельных постов Threads показывает только их автору, поэтому
абсолютные числа несравнимы между аккаунтами разного размера: сто лайков у
блогера с тысячей подписчиков и у блогера с миллионом — разные события.

Запуск:
    python3 analyze.py                 # печатает сводку
    python3 analyze.py --json out.json # плюс машинный вывод для отчёта
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path

from features import engagement, extract, reply_share

HERE = Path(__file__).resolve().parent
POSTS_FILE = HERE / "data" / "posts.jsonl"

# Метрики поста растут первые сутки-двое. Если мешать свежие посты со старыми,
# свежие систематически выглядят провальными, и весь анализ съезжает.
MIN_AGE_HOURS = 72


def load() -> list[dict]:
    if not POSTS_FILE.exists():
        return []
    rows = []
    for line in POSTS_FILE.read_text().splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def latest_snapshot(rows: list[dict]) -> list[dict]:
    """Один пост — одна запись: берём самый свежий снапшот."""
    best: dict[str, dict] = {}
    for row in rows:
        cur = best.get(row["id"])
        if cur is None or row["collected_at"] > cur["collected_at"]:
            best[row["id"]] = row
    return list(best.values())


def author_baselines(rows: list[dict]) -> dict[str, float]:
    """Медиана вовлечения по автору — считаем только по его собственной ленте.

    Выдача поиска показывает удачные посты, поэтому норма, снятая по ней,
    завышена, и обычные посты того же автора выглядят провальными."""
    by_author: dict[str, list[int]] = defaultdict(list)
    for row in rows:
        if row.get("source") == "profile":
            by_author[row["author"]].append(engagement(row))
    return {
        author: statistics.median(values)
        for author, values in by_author.items()
        if len(values) >= 3
    }


# Сколько постов нужно от автора, чтобы «выстрелил относительно себя» вообще
# имело смысл. На трёх постах верхняя треть — это один пост, то есть шум.
MIN_POSTS_PER_AUTHOR = 6

# Какая доля ленты автора считается его удачными постами.
TOP_SHARE = 0.25


def summarize(rows: list[dict]) -> dict:
    mature = [r for r in rows if (r.get("age_hours") or 0) >= MIN_AGE_HOURS]
    baselines = author_baselines(mature)

    # Сравниваем только внутри лент авторов. Посты из поиска попали в выборку
    # потому, что уже выстрелили: если смешать их с лентами, верхняя группа
    # окажется набита ими по построению, и «признаками виральности» окажутся
    # признаки попадания в поисковый топ.
    by_author: dict[str, list[dict]] = defaultdict(list)
    for row in mature:
        if row.get("source") == "profile":
            by_author[row["author"]].append(row)

    top: list[dict] = []
    rest: list[dict] = []
    used_authors = 0

    for author, posts in by_author.items():
        if len(posts) < MIN_POSTS_PER_AUTHOR:
            continue
        used_authors += 1
        base = baselines.get(author)

        scored = sorted(
            (
                {
                    **row,
                    **extract(row),
                    "engagement": engagement(row),
                    "reply_share": round(reply_share(row), 3),
                    # Отношение к медиане автора показываем в списке, но группы
                    # по нему не режем: у автора с медианой 4 любой средний пост
                    # даёт «x80», и верхняя группа набивается такими артефактами
                    # вместо действительно выделяющихся постов.
                    "score": round(engagement(row) / base, 1) if base else None,
                }
                for row in posts
            ),
            key=lambda p: p["engagement"],
            reverse=True,
        )
        cut = max(1, round(len(scored) * TOP_SHARE))
        top.extend(scored[:cut])
        rest.extend(scored[cut:])

    top.sort(key=lambda p: p["score"] or 0, reverse=True)

    return {
        "totals": {
            "posts_total": len(rows),
            "posts_mature": len(mature),
            "posts_comparable": len(top) + len(rest),
            "authors": len({r["author"] for r in rows}),
            "authors_with_baseline": used_authors,
        },
        "features": compare(top, rest),
        "top": top[:15],
    }


BOOL_FEATURES = ["ends_with_question", "has_number", "first_person", "has_list", "has_link"]


def compare(top: list[dict], rest: list[dict]) -> list[dict]:
    """Доля признака в лучшей четверти лент против остальных постов."""
    out = []
    if not top or not rest:
        return out

    for name in BOOL_FEATURES:
        share_top = sum(1 for p in top if p[name]) / len(top)
        share_rest = sum(1 for p in rest if p[name]) / len(rest)
        out.append(
            {
                "feature": name,
                "top_share": round(share_top, 3),
                "rest_share": round(share_rest, 3),
                "lift": round(share_top / share_rest, 2) if share_rest else None,
                "n_top": len(top),
                "n_rest": len(rest),
            }
        )

    for name in ["hook_type", "media"]:
        values = {p[name] for p in top} | {p[name] for p in rest}
        for value in sorted(values):
            share_top = sum(1 for p in top if p[name] == value) / len(top)
            share_rest = sum(1 for p in rest if p[name] == value) / len(rest)
            out.append(
                {
                    "feature": f"{name}={value}",
                    "top_share": round(share_top, 3),
                    "rest_share": round(share_rest, 3),
                    "lift": round(share_top / share_rest, 2) if share_rest else None,
                    "n_top": len(top),
                    "n_rest": len(rest),
                }
            )

    for name in ["length", "hook_len", "reply_share"]:
        out.append(
            {
                "feature": f"{name} (медиана)",
                "top_share": round(statistics.median([p[name] for p in top]), 2),
                "rest_share": round(statistics.median([p[name] for p in rest]), 2),
                "lift": None,
                "n_top": len(top),
                "n_rest": len(rest),
            }
        )
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", help="куда записать машинный вывод")
    args = parser.parse_args()

    rows = latest_snapshot(load())
    if not rows:
        print(f"нет данных: {POSTS_FILE}")
        return

    result = summarize(rows)
    t = result["totals"]
    print(f"постов всего: {t['posts_total']}, старше {MIN_AGE_HOURS}ч: {t['posts_mature']}")
    print(f"авторов: {t['authors']}, из них с базовой линией: {t['authors_with_baseline']}")
    print(f"сравнимых постов (есть норма автора): {t['posts_comparable']}\n")

    if not result["features"]:
        print("для сравнения нужно больше постов с лент авторов")
    else:
        print(f"{'признак':<28} {'топ':>8} {'осталь':>8} {'лифт':>6}")
        for row in result["features"]:
            lift = f"{row['lift']}x" if row["lift"] else "—"
            print(f"{row['feature']:<28} {row['top_share']:>8} {row['rest_share']:>8} {lift:>6}")

    print("\nлучшая четверть лент:")
    for post in result["top"][:10]:
        head = (post["text"] or "").split("\n")[0][:70]
        print(f"  x{post['score']:<6} @{post['author']:<20} {head}")

    if args.json:
        Path(args.json).write_text(json.dumps(result, ensure_ascii=False, indent=1))
        print(f"\nмашинный вывод: {args.json}")


if __name__ == "__main__":
    main()
