#!/usr/bin/env python3
"""vc.ru: досчитываем охваты к корпусу, собранному в августе, — уже без браузера.

В старом замере vc охваты снимались браузером по одной странице на статью,
поэтому из 418 собранных статей их получили 132. Теперь выяснилось, что
`api.vc.ru/v2.1/content?id=` отдаёт `counters.total` — ровно то число,
что показано на странице. Значит корпус можно закрыть целиком за десять минут.

    python3 vc/refresh.py --src /path/to/articles.jsonl

На входе - JSONL старого замера (одна статья на строку: `id`, `url`, `title`,
`author`, `date`, `subsite`, `is_editorial`; скрипты того замера в репо не входят).
Пишет в общую схему tools/platform-lab, чтобы vc участвовал в сводном отчёте
наравне с остальными. Исходный файл не трогает.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import normalize as nz
from common.fetch import get_json, pause
from common.store import append, cards_path, done_ids, texts_path

PLATFORM = "vc"
CONTENT = "https://api.vc.ru/v2.1/content?id={}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", type=Path, required=True,
                    help="JSONL старого замера vc (articles.jsonl)")
    args = ap.parse_args()
    src: Path = args.src
    if not src.exists():
        sys.exit(f"нет исходного корпуса: {src}")
    seen = done_ids(cards_path(PLATFORM))
    rows = {}
    for line in src.open(encoding="utf-8"):
        r = json.loads(line)
        rows[r["id"]] = r          # последняя запись побеждает, как в старом замере
    todo = [r for r in rows.values() if str(r["id"]) not in seen]
    print(f"в корпусе {len(rows)} статей, добираю {len(todo)}")

    ok = 0
    for i, r in enumerate(todo, 1):
        data = get_json(CONTENT.format(r["id"]))
        result = (data or {}).get("result") or {}
        counters = result.get("counters") or {}
        views = counters.get("total")
        if not views:
            pause()
            continue
        body = nz.from_osnova_blocks(result.get("blocks") or [])
        author = (result.get("author") or {}).get("name") or r.get("author")
        card = nz.card(
            PLATFORM,
            id=r["id"],
            url=r.get("url") or f"https://vc.ru/{r['id']}",
            title=r.get("title") or result.get("title") or "",
            author=author,
            author_kind="media" if r.get("is_editorial") else "person",
            published_at=datetime.fromtimestamp(r.get("date") or 0, timezone.utc).isoformat(),
            views=views,
            likes=counters.get("reactions"),
            comments=counters.get("comments"),
            topic=r.get("subsite"),
            extra={"favorites": counters.get("favorites"), "hits": counters.get("hits"),
                   "subsite": r.get("subsite"), "source_feed": r.get("source_feed")},
        )
        card["group"] = "pool"
        append(cards_path(PLATFORM), card)
        if body["chars"]:
            append(texts_path(PLATFORM), {
                "platform": PLATFORM, "id": card["id"], "url": card["url"],
                "title": card["title"], "group": "pool", "lead": "", **body,
            })
        ok += 1
        if i % 25 == 0:
            print(f"  {i}/{len(todo)}: собрано {ok}")
        pause()
    print(f"готово: {ok} статей с охватами")


if __name__ == "__main__":
    main()
