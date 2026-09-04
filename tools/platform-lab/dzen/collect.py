#!/usr/bin/env python3
"""Дзен: каналы, а через них — статьи с просмотрами.

Тематику на Дзене нельзя задать разделом: `dzen.ru/t/<тег>` отдаёт 404,
а `?category=` анонимной сессии ленту не меняет. Зато канал тематичен
по определению, и экспорт канала отдаёт просмотры, лайки и комментарии —
но только если передать `country_code`, `clid` и `lang` разом.

    python3 dzen/collect.py channels --calls 60   # разведка: кто тут пишет про ИИ и бизнес
    python3 dzen/collect.py cards                 # статьи каналов за 12 месяцев

Список каналов после разведки правится руками: `data/dzen/channels.json` —
файл под глаза, а не под алгоритм. Разведка предлагает, человек вычёркивает.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import normalize as nz
from common.fetch import get_json, pause
from common.store import DATA, append, cards_path, done_ids

PLATFORM = "dzen"
FEED = "https://dzen.ru/api/v3/launcher/more?country_code=ru&clid=300"
EXPORT = ("https://dzen.ru/api/v3/launcher/export"
          "?channel_name={}&country_code=ru&clid=300&lang=ru")
CHANNELS_FILE = DATA / "dzen" / "channels.json"

TOPICAL = {
    "ИИ": re.compile(r"нейросет|искусственн\w+ интеллект|\bии\b|\bai\b|gpt|chatgpt|"
                     r"машинн\w+ обучен|нейронк", re.I),
    "технологии": re.compile(r"технолог|гаджет|\bit\b|айти|програм|разработк|цифров|"
                             r"компьютер|софт|киберб", re.I),
    "бизнес": re.compile(r"бизнес|предприниматель|стартап|маркетинг|продаж|деньг|"
                         r"финанс|инвест|налог|карьер|управлен", re.I),
}

# Каналы-агрегаторы новостей: у них просмотры про раздачу, а не про текст.
MEDIA = re.compile(r"новост|газет|\bria\b|риа|тасс|известия|ведомост|коммерсант|"
                   r"lenta|рбк|\brbc\b|дзен\.новости", re.I)

YEAR_AGO = datetime.now(timezone.utc) - timedelta(days=365)


def classify(title: str, description: str) -> tuple[str | None, bool]:
    blob = f"{title} {description}"
    for topic, pat in TOPICAL.items():
        if pat.search(blob):
            return topic, bool(MEDIA.search(blob))
    return None, bool(MEDIA.search(blob))


def stage_channels(calls: int) -> None:
    """Лента используется не как источник статей, а как источник каналов."""
    found: dict[str, dict] = {}
    if CHANNELS_FILE.exists():
        found = {c["alias"]: c for c in json.loads(CHANNELS_FILE.read_text(encoding="utf-8"))}
    url = FEED
    for i in range(calls):
        data = get_json(url)
        items = (data or {}).get("items") or []
        if not items:
            print(f"  вызов {i + 1}: пусто, останавливаюсь")
            break
        for it in items:
            src = it.get("source") or {}
            alias = src.get("url")
            if not alias or alias in found:
                continue
            topic, is_media = classify(src.get("title") or "", src.get("description") or "")
            if not topic:
                continue
            found[alias] = {
                "alias": alias,
                "title": src.get("title"),
                "subscribers": src.get("subscribers"),
                "topic": topic,
                "kind": "media" if is_media else "person",
                "description": (src.get("description") or "")[:200],
            }
        nxt = (data or {}).get("more") or {}
        url = nxt.get("link") or FEED
        if (i + 1) % 10 == 0:
            print(f"  вызов {i + 1}: тематических каналов {len(found)}")
        pause(1.5, 3.0)

    CHANNELS_FILE.parent.mkdir(parents=True, exist_ok=True)
    rows = sorted(found.values(), key=lambda c: -(c.get("subscribers") or 0))
    CHANNELS_FILE.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    by_topic: dict[str, int] = {}
    for c in rows:
        by_topic[c["topic"]] = by_topic.get(c["topic"], 0) + 1
    print(f"каналов найдено {len(rows)}: {by_topic}. Файл — {CHANNELS_FILE}")


def to_card(it: dict, channel: dict) -> dict | None:
    if not it.get("publication_object_id") and not it.get("share_link"):
        return None
    social = it.get("socialInfo") or {}
    src = it.get("source") or {}
    ts = it.get("publication_date")
    try:
        published = datetime.fromtimestamp(int(ts), timezone.utc)
    except (TypeError, ValueError):
        return None
    link = (it.get("share_link") or "").split("?")[0]
    return nz.card(
        PLATFORM,
        id=link.rsplit("/", 1)[-1] or it.get("publication_object_id"),
        url=link,
        title=(it.get("title") or "").strip(),
        author=src.get("title") or channel["title"],
        author_kind=channel["kind"],
        published_at=published.isoformat(),
        views=it.get("views"),
        likes=social.get("likesCount"),
        comments=social.get("commentCount"),
        topic=channel["topic"],
        extra={
            "channel": channel["alias"],
            "subscribers": src.get("subscribers") or channel.get("subscribers"),
            "time_to_read_sec": it.get("timeToReadSeconds"),
            "item_type": it.get("item_type"),
        },
    )


def walk_channel(channel: dict, seen: set, max_pages: int) -> int:
    url = EXPORT.format(channel["alias"])
    added = 0
    for page in range(max_pages):
        data = get_json(url)
        items = [i for i in ((data or {}).get("items") or []) if i.get("item_type") == "native"]
        if not items:
            break
        oldest = None
        for it in items:
            card = to_card(it, channel)
            if not card or card["id"] in seen:
                continue
            published = datetime.fromisoformat(card["published_at"])
            oldest = published if oldest is None else min(oldest, published)
            if published < YEAR_AGO or not card["views"]:
                continue
            card["group"] = "pool"
            append(cards_path(PLATFORM), card)
            seen.add(card["id"])
            added += 1
        if oldest and oldest < YEAR_AGO:
            break
        nxt = ((data or {}).get("more") or {}).get("link")
        if not nxt:
            break
        url = nxt
        pause(1.5, 3.0)
    return added


def stage_cards(max_pages: int, limit: int) -> None:
    if not CHANNELS_FILE.exists():
        sys.exit("сначала разведка: python3 dzen/collect.py channels")
    # Список курируется руками: разведка тащит глянец и региональные новости,
    # а замер про ИИ, технологии и бизнес. Флаг keep ставится в channels.json.
    channels = [c for c in json.loads(CHANNELS_FILE.read_text(encoding="utf-8"))
                if c.get("keep")][:limit]
    seen = done_ids(cards_path(PLATFORM))
    for i, ch in enumerate(channels, 1):
        added = walk_channel(ch, seen, max_pages)
        print(f"  {i}/{len(channels)} {ch['alias']:<28} {ch['topic']:<12} +{added} (всего {len(seen)})")
    print(f"карточек: {len(seen)}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["channels", "cards"])
    ap.add_argument("--calls", type=int, default=60)
    ap.add_argument("--pages", type=int, default=18)
    ap.add_argument("--limit", type=int, default=60)
    args = ap.parse_args()
    if args.stage == "channels":
        stage_channels(args.calls)
    else:
        stage_cards(args.pages, args.limit)


if __name__ == "__main__":
    main()
