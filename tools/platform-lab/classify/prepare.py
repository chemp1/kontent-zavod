#!/usr/bin/env python3
"""Нарезает корпус на батчи полных текстов — их читает модель.

Регексом берётся структура: длина, ритм, подзаголовки, цифры. Не берётся
то, ради чего всё затевалось: жанр, кто говорит, чем начинается, есть ли
своя фактура или общие слова, выполняет ли текст обещание заголовка.
Это читается, а не считается.

    python3 classify/prepare.py habr --size 8

Кладёт батчи в .data/tools/platform-lab/<площадка>/batches/batch-NN.md —
в git они не едут, это чужие тексты целиком.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.store import TEXTS, cards_path, load_by_id, read_jsonl, texts_path

MAX_CHARS = 14000      # длинные лонгриды режем: хвост статьи жанр не меняет


def batch_dir(platform: str) -> Path:
    return TEXTS / platform / "batches"


def render(row: dict, card: dict) -> str:
    body = "\n\n".join(row.get("paras") or [])
    if len(body) > MAX_CHARS:
        body = body[:MAX_CHARS] + "\n\n[…текст обрезан…]"
    heads = " | ".join((row.get("headers") or [])[:20])
    return (
        f"\n\n===== СТАТЬЯ id={row['id']} =====\n"
        f"ПЛОЩАДКА: {row['platform']}\n"
        f"ЗАГОЛОВОК: {row['title']}\n"
        f"АВТОР: {card.get('author')} ({card.get('author_kind')})\n"
        f"ПРОСМОТРОВ: {card.get('views')}\n"
        f"ПОДЗАГОЛОВКИ: {heads or '—'}\n"
        f"СТАТИСТИКА: {row.get('chars')} знаков, {len(row.get('paras') or [])} абзацев, "
        f"{row.get('list_items')} пунктов списка, {row.get('media')} картинок, "
        f"{row.get('code_blocks')} блоков кода\n"
        f"--- ТЕКСТ ---\n{body}\n"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("platform")
    ap.add_argument("--size", type=int, default=8)
    ap.add_argument("--cap-rest", type=int, default=0,
                    help="сколько статей взять из «остальных»: контроль должен быть "
                         "сопоставим с верхом, а не забивать разметку объёмом")
    args = ap.parse_args()

    # Размечаем не всё собранное, а ровно тот корпус, на котором считается
    # отчёт: верхняя четверть по лифту и остальные. Размечать отсеянное
    # SEO и корпоративные блоги — платить за то, что в выводы не войдёт.
    from analyze import add_lift, clean, load, split

    rows_full = clean(args.platform, load(args.platform))
    add_lift(args.platform, rows_full)
    top, rest = split(rows_full)
    for r in top:
        r["_group"] = "top"
    for r in rest:
        r["_group"] = "rest"
    if args.cap_rest and len(rest) > args.cap_rest:
        step = len(rest) / args.cap_rest
        rest = [rest[int(i * step)] for i in range(args.cap_rest)]
    rows = sorted(top + rest, key=lambda r: -r["_lift"])
    cards = load_by_id(cards_path(args.platform))

    out = batch_dir(args.platform)
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("batch-*.md"):
        old.unlink()

    index = []
    for i in range(0, len(rows), args.size):
        chunk = rows[i:i + args.size]
        name = f"batch-{i // args.size:02d}.md"
        (out / name).write_text("".join(render(r, cards[r["id"]]) for r in chunk),
                                encoding="utf-8")
        for r in chunk:
            index.append({"id": r["id"], "batch": name, "group": r["_group"],
                          "lift": round(r["_lift"], 2), "views": r["views"]})
    (out / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1),
                                    encoding="utf-8")
    n = (len(rows) + args.size - 1) // args.size
    print(f"{args.platform}: {len(rows)} статей ({len(top)} верх / {len(rest)} остальные) "
          f"→ {n} батчей по {args.size} в {out}")


if __name__ == "__main__":
    main()
