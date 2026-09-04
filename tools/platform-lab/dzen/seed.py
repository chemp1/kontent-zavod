#!/usr/bin/env python3
"""Посев каналов Дзена: проверяем список кандидатов и добавляем живых.

Разведка через анонимную ленту даёт в основном глянец, региональные новости
и эзотерику: наша тематика там редкая гостья. Поэтому вторым источником идёт
явный список — бренды, медиа и блогеры, которые по-хорошему должны быть
на Дзене. Алиас угадать нельзя, поэтому каждый проверяется запросом:
живой канал отдаёт статьи, мёртвый — пустой список.

    python3 dzen/seed.py

Результат дописывается в data/dzen/channels.json — тот же файл, что
пополняет разведка. Дальше его правит человек.
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.fetch import get_json, pause
from common.store import DATA

EXPORT = ("https://dzen.ru/api/v3/launcher/export"
          "?channel_name={}&country_code=ru&clid=300&lang=ru")
CHANNELS_FILE = DATA / "dzen" / "channels.json"

CANDIDATES = {
    "ИИ": ["nplus1", "proglib", "tproger", "skillbox", "netology", "yandex", "sber",
           "sberdevices", "sberbusiness", "gigachat", "cloudru", "seonews", "aiaiai",
           "neuralnetworks", "neuro", "ai-news", "mlmastery", "datasciencer",
           "nastyaai", "aitutor", "promptmaster", "neurohelper", "aiforbusiness"],
    "технологии": ["hi-tech.mail.ru", "gadgetpage", "overclockers.ru", "protech",
                   "ferra.ru", "cnews", "3dnews", "ixbt", "trashbox", "androidinsider",
                   "iguides", "rozetked", "keddr", "digger", "itc.ua", "selectel",
                   "timeweb", "beeline", "megafon", "mts", "kaspersky", "habr"],
    "бизнес": ["incrussia.ru", "monocle.ru", "forbes.ru", "rb.ru", "secretmag",
               "delovoymir", "bitrix24", "megaplan", "kontur", "moedelo", "tinkoffjournal",
               "investfuture", "bankiru", "frankmedia", "fintolk", "igorfaynman",
               "bessonov_invest", "vzoprodengi", "biznesmolodost", "predprinimatel",
               "franchise", "opora", "mybusiness", "gk-nalogi", "buhgalteria"],
}


def check(alias: str) -> dict | None:
    data = get_json(EXPORT.format(alias))
    items = [i for i in ((data or {}).get("items") or []) if i.get("item_type") == "native"]
    if not items:
        return None
    src = items[0].get("source") or {}
    views = [i["views"] for i in items if i.get("views")]
    return {
        "alias": alias,
        "title": src.get("title"),
        "subscribers": src.get("subscribers"),
        "description": (src.get("description") or "")[:200],
        "median_views": statistics.median(views) if views else None,
        "sample_items": len(items),
    }


def main() -> None:
    existing = {}
    if CHANNELS_FILE.exists():
        existing = {c["alias"]: c for c in json.loads(CHANNELS_FILE.read_text(encoding="utf-8"))}

    added = 0
    for topic, aliases in CANDIDATES.items():
        for alias in aliases:
            if alias in existing:
                continue
            info = check(alias)
            pause()
            if not info:
                continue
            info["topic"] = topic
            # Крупные бренды и редакции — отдельная лига, как редакция на vc:
            # их раздают, а не читают по выбору. В отчёт они не идут,
            # но нужны как фон «сколько собирает раздача».
            info["kind"] = "company" if (info["subscribers"] or 0) > 50000 else "person"
            existing[alias] = info
            added += 1
            print(f"  ✓ {alias:<20} {topic:<12} {str(info['subscribers']):>8} подп  "
                  f"медиана {str(info['median_views']):>7}  {(info['title'] or '')[:30]}")

    rows = sorted(existing.values(), key=lambda c: -(c.get("subscribers") or 0))
    CHANNELS_FILE.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"добавлено {added}, всего каналов {len(rows)}")


if __name__ == "__main__":
    main()
