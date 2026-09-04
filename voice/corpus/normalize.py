#!/usr/bin/env python3
"""Привести корпус канала в порядок: убрать дубли и пересобрать .md из .json.

    python3 voice/corpus/normalize.py --check   # только проверить, ничего не писать
    python3 voice/corpus/normalize.py           # починить

Где лежит корпус, задаётся ключами: `--dir` (папка, по умолчанию папка скрипта),
`--json` и `--md` (имена файлов внутри неё, по умолчанию `channel.json` и
`channel.md`). Заголовок `.md` берётся из `voice/author.json` (поля
`channel` и `channel_title`) либо задаётся руками через `--title`.

Зачем это здесь. Корпус собирается из выгрузки канала и раньше правился руками,
из-за чего в нём оказывались посты дважды: рядом лежали версия из веб-версии
канала (HTML-сущности `&#33;`, просмотры строкой «1.53K») и версия из БД
(markdown-жирный, просмотры числом). Отпечаток голоса считается по этому файлу,
так что дубли смещали частоты, а заметить их без пересчёта было нечем.

Правило разрешения: при совпадении отметки времени остаётся запись из БД -
просмотры у неё число, а не строка.

`.md` - производный файл, он всегда собирается из `.json`. Функция `render()`
воспроизводит формат существующего корпуса байт в байт; `--check` это
подтверждает, поэтому пересборка не тащит за собой изменений разметки.
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent


def default_title(corpus_dir: Path) -> str:
    """Заголовок корпуса из `author.json` рядом с папкой корпуса (`voice/`)."""
    author_path = corpus_dir.parent / "author.json"
    if not author_path.exists():
        return "# Телеграм-канал"
    author = json.loads(author_path.read_text(encoding="utf-8"))
    title = "# Телеграм-канал"
    if author.get("channel"):
        title += f" @{author['channel']}"
    if author.get("channel_title"):
        title += f" ({author['channel_title']})"
    return title


def date_range(rows: list[dict]) -> str:
    """«(2022-10 — 2026-08)» по первой и последней записи; для пустого корпуса пусто."""
    if not rows:
        return ""
    months = sorted(r["date"][:7] for r in rows)
    return f"({months[0]} — {months[-1]})"


def load(json_path: Path) -> list[dict]:
    return json.loads(json_path.read_text(encoding="utf-8"))


def deduplicate(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Возвращает (что оставить, что убрать). Дубль - совпадение `date`."""
    counts = collections.Counter(r["date"] for r in rows)
    kept, dropped = [], []
    for r in rows:
        # У версии из веб-версии канала просмотры строкой («1.53K»),
        # у версии из БД - числом. Дублем считаем первую.
        if counts[r["date"]] > 1 and isinstance(r.get("views"), str):
            dropped.append(r)
        else:
            kept.append(r)
    return kept, dropped


def header(row: dict) -> str:
    views = row.get("views")
    date = row["date"][:10]
    return f"## {date} ({views} views)" if views not in (None, "", 0) else f"## {date}"


def render(rows: list[dict], title: str) -> str:
    out = f"{title}\n\nВсего постов: **{len(rows)}** {date_range(rows)}\n\n"
    for r in rows:
        out += f"{header(r)}\n\n{r['text'].strip()}\n\n---\n\n"
    return out


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--check", action="store_true", help="только проверить, не записывать")
    ap.add_argument("--dir", type=Path, default=SCRIPT_DIR, help="папка корпуса (по умолчанию папка скрипта)")
    ap.add_argument("--json", default="channel.json", help="имя .json внутри --dir")
    ap.add_argument("--md", default="channel.md", help="имя .md внутри --dir")
    ap.add_argument("--title", default=None, help="заголовок .md; по умолчанию из ../author.json")
    args = ap.parse_args()

    corpus_dir = args.dir.resolve()
    json_path = corpus_dir / args.json
    md_path = corpus_dir / args.md
    title = args.title if args.title is not None else default_title(corpus_dir)

    rows = load(json_path)
    kept, dropped = deduplicate(rows)
    md_matches = md_path.exists() and md_path.read_text(encoding="utf-8") == render(rows, title)

    print(f"записей в json: {len(rows)}, уникальных: {len(kept)}, дублей: {len(dropped)}")
    print(f"md собирается из json без расхождений: {'да' if md_matches else 'НЕТ'}")
    for r in dropped:
        print(f"  дубль: {r['date']} (views={r['views']!r})")

    if args.check:
        # Расходящийся .md - тоже повод для ненулевого кода: значит его правили
        # руками, и следующая пересборка эту правку потеряет.
        return 0 if (not dropped and md_matches) else 1

    if not dropped and md_matches:
        print("менять нечего")
        return 0

    json_path.write_text(json.dumps(kept, ensure_ascii=False, indent=1), encoding="utf-8")
    md_path.write_text(render(kept, title), encoding="utf-8")
    print(f"пересобрано: {len(kept)} постов в обоих файлах")
    print("не забудь пересчитать частоты в voice/fingerprint.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
