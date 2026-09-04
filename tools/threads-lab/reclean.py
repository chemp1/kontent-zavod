#!/usr/bin/env python3
"""Перечистка текстов в уже собранном корпусе.

Нужна, когда правила чистки уточнились: пересобирать данные из Threads ради
этого нельзя (лишние заходы в чужой браузер), а текст в файле уже лежит.
Чистка идемпотентна, так что запускать можно сколько угодно раз.

Запуск:
    python3 reclean.py --dry-run   # показать, что изменится
    python3 reclean.py             # переписать data/posts.jsonl
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from textclean import clean_post_text

HERE = Path(__file__).resolve().parent
POSTS_FILE = HERE / "data" / "posts.jsonl"


def collector_running() -> bool:
    """Идёт ли сейчас сбор.

    Перечистка читает файл целиком и переписывает его. Если в этот момент
    сборщик допишет строку, она потеряется: наша запись затрёт файл версией
    без неё. Потеря тихая, поэтому проверяем заранее.
    """
    res = subprocess.run(
        ["pgrep", "-f", "^python3 .*collect\\.py"], capture_output=True, text=True
    )
    return res.returncode == 0


def drop_quoted(rows: list[dict]) -> tuple[list[dict], int]:
    """Убрать цитируемые посты, унаследовавшие метрики цитирующего.

    Когда пост цитирует другой пост, в карточке лежат две ссылки на посты, но
    панель действий и её числа общие. Старая версия извлекателя записывала обе
    ссылки, и цитируемый пост попадал в базу с чужими метриками — то есть
    выглядел выстрелившим, ничего для этого не сделав.

    Опознаём по паре признаков: совпадают автор, все четыре метрики и дата
    снятия, а текст одной записи содержит начало текста другой (карточка
    цитирующего включает в себя карточку цитируемого). Оставляем цитирующего.
    """
    groups: dict[tuple, list[dict]] = {}
    for row in rows:
        key = (
            row["author"],
            row.get("likes"),
            row.get("replies"),
            row.get("reposts"),
            row.get("quotes"),
            row["collected_at"][:10],
        )
        groups.setdefault(key, []).append(row)

    drop: set[int] = set()
    for members in groups.values():
        if len(members) < 2:
            continue
        for parent in members:
            for child in members:
                if parent is child:
                    continue
                head = (child.get("text") or "")[:30].strip()
                if head and head in (parent.get("text") or ""):
                    drop.add(id(child))

    kept = [r for r in rows if id(r) not in drop]
    return kept, len(rows) - len(kept)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true", help="переписать даже при идущем сборе")
    args = parser.parse_args()

    if not args.dry_run and not args.force and collector_running():
        raise SystemExit(
            "сейчас идёт сбор — дождитесь его окончания, иначе свежие записи "
            "потеряются при перезаписи файла (или --force, если уверены)"
        )

    rows, changed = [], 0
    for line in POSTS_FILE.read_text().splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        before = row.get("text") or ""
        after = clean_post_text(before, row.get("published_at"))
        if after != before:
            changed += 1
            if args.dry_run and changed <= 5:
                print(f"--- {row['id']} @{row['author']}")
                print(f"было:  {before[:120]!r}")
                print(f"стало: {after[:120]!r}\n")
            row["text"] = after
            row["length"] = len(after)
        rows.append(row)

    rows, dropped = drop_quoted(rows)
    print(f"записей: {len(rows) + dropped}, тексты изменятся: {changed}, "
          f"цитируемых на удаление: {dropped}")
    if args.dry_run:
        return

    POSTS_FILE.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    )
    print(f"переписано: {POSTS_FILE}")


if __name__ == "__main__":
    main()
