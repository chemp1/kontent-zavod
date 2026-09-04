#!/usr/bin/env python3
"""Проверка: дают ли цепочки постов выигрыш в вовлечении.

Цепочкой считаем посты одного автора, идущие подряд с разрывом до 20 минут:
так публикуют продолжение мысли, а не отдельный пост. Настоящей разметки
цепочек Threads наружу не отдаёт, поэтому это прокси, а не факт.

Главное в скрипте — сравнение ВНУТРИ автора. По всему корпусу цепочки выглядят
успешнее, но это эффект плодовитых авторов: они и постят пачками, и аккаунты
у них крупнее. Внутри автора эффект исчезает.
"""

from __future__ import annotations

import collections
import json
import statistics
from datetime import datetime
from pathlib import Path

from features import engagement

POSTS_FILE = Path(__file__).resolve().parent / "data" / "posts.jsonl"
GAP_SECONDS = 1200


def split_author(posts: list[dict]) -> tuple[list[int], list[int]]:
    posts.sort(key=lambda r: r["published_at"])
    times = [datetime.fromisoformat(r["published_at"]) for r in posts]
    chain, single = [], []
    for i, row in enumerate(posts):
        near = (i > 0 and (times[i] - times[i - 1]).total_seconds() <= GAP_SECONDS) or (
            i < len(posts) - 1
            and (times[i + 1] - times[i]).total_seconds() <= GAP_SECONDS
        )
        (chain if near else single).append(engagement(row))
    return chain, single


def main() -> None:
    by_author: dict[str, list[dict]] = collections.defaultdict(list)
    for line in POSTS_FILE.read_text().splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("source") == "profile":
            by_author[row["author"]].append(row)

    all_chain, all_single = [], []
    wins = losses = 0
    per_author = []

    for author, posts in by_author.items():
        chain, single = split_author(posts)
        all_chain += chain
        all_single += single
        if len(chain) >= 3 and len(single) >= 3:
            mc, ms = statistics.median(chain), statistics.median(single)
            per_author.append((author, mc, ms))
            wins += mc > ms
            losses += mc < ms

    print("по всему корпусу (так делать нельзя, но показательно):")
    print(f"  в цепочках {len(all_chain)} постов, медиана {statistics.median(all_chain):.0f}")
    print(f"  одиночных  {len(all_single)} постов, медиана {statistics.median(all_single):.0f}")
    print(f"\nвнутри авторов ({len(per_author)} с достаточным числом и тех и других):")
    print(f"  цепочки выигрывают у {wins}, проигрывают у {losses}")
    for author, mc, ms in sorted(per_author, key=lambda x: -(x[1] - x[2])):
        print(f"    @{author:<22} цепочка {mc:>6.0f}   одиночные {ms:>6.0f}")


if __name__ == "__main__":
    main()
