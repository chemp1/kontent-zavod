#!/usr/bin/env python3
"""Кандидаты в вотчлист: кого нашла разведка по поиску.

Считает по постам из поисковой выдачи (source="search"), поэтому это не оценка
аккаунта, а сигнал «этот автор попадает в топ по нашим темам». Медиану автора
по такой выборке считать нельзя — она завышена по построению.

Запуск: python3 candidates.py [--min-posts 1] [--lang ru]
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path

from features import engagement, language

HERE = Path(__file__).resolve().parent
POSTS_FILE = HERE / "data" / "posts.jsonl"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min-posts", type=int, default=1)
    parser.add_argument("--lang", help="фильтр по языку: ru или en")
    args = parser.parse_args()

    by_author: dict[str, list[dict]] = defaultdict(list)
    for line in POSTS_FILE.read_text().splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            # Файл могли читать в момент дозаписи: последняя строка бывает
            # обрезанной. Пропускаем, на следующем запуске она будет целой.
            continue
        if row.get("source") == "search":
            by_author[row["author"]].append(row)

    rows = []
    for author, posts in by_author.items():
        langs = [language(p.get("text") or "") for p in posts]
        lang = max(set(langs), key=langs.count)
        if args.lang and lang != args.lang:
            continue
        if len(posts) < args.min_posts:
            continue
        engagements = [engagement(p) for p in posts]
        rows.append(
            {
                "handle": author,
                "hits": len(posts),
                "max_engagement": max(engagements),
                "median_engagement": round(statistics.median(engagements)),
                "lang": lang,
                "sample": (posts[0].get("text") or "").split("\n")[0][:60],
            }
        )

    rows.sort(key=lambda r: (r["hits"], r["max_engagement"]), reverse=True)

    print(f"{'аккаунт':<24} {'попад':>5} {'макс':>7} {'медиана':>8} {'язык':>5}  пример")
    for row in rows:
        print(
            f"{row['handle']:<24} {row['hits']:>5} {row['max_engagement']:>7} "
            f"{row['median_engagement']:>8} {row['lang']:>5}  {row['sample']}"
        )
    print(f"\nвсего кандидатов: {len(rows)}")


if __name__ == "__main__":
    main()
