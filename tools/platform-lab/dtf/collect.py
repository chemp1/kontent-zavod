#!/usr/bin/env python3
"""DTF: карточки и полные тексты одним проходом через API Osnova.

Тот же движок, что у vc.ru, и с ним выяснилось важное: браузерный проход
за охватами, который делали в старом замере vc, не нужен. `counters.total` из API —
ровно то число, что показано на странице (проверено на статье 2263883:
API 815, браузер 815). Поэтому здесь один проход: поиск отдаёт и блоки,
и счётчики сразу.

    python3 dtf/collect.py search              # тематические запросы
    python3 dtf/collect.py baseline --weeks 52 # фон: обычные посты за год

Поиск даёт «залетевшие» (он ранжирует по релевантности и охвату),
фон — контрольную группу. Без фона отчёт сравнивал бы хит с хитом.
"""

from __future__ import annotations

import argparse
import sys
import time
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import normalize as nz
from common.fetch import get_json, pause
from common.store import append, cards_path, done_ids, texts_path

PLATFORM = "dtf"
SEARCH = "https://api.dtf.ru/v2.5/search"
TIMELINE = "https://api.dtf.ru/v2.5/timeline"

# ИИ, технологии, бизнес — в огранке площадки. DTF про игры, и это
# не дефект выборки, а свойство места: тут пишут про технологии
# для игровой аудитории. В отчёте это придётся назвать прямо.
QUERIES = [
    ("нейросети", "ИИ"), ("искусственный интеллект", "ИИ"), ("ChatGPT", "ИИ"),
    ("нейросеть для работы", "ИИ"), ("LLM", "ИИ"), ("ИИ-агенты", "ИИ"),
    ("вайб-кодинг", "технологии"), ("программирование", "технологии"),
    ("разработка игр", "технологии"), ("инди-разработка", "технологии"),
    ("движок", "технологии"), ("гайд по разработке", "технологии"),
    ("стартап", "бизнес"), ("монетизация", "бизнес"), ("маркетинг игр", "бизнес"),
    ("своя студия", "бизнес"), ("как я зарабатываю", "бизнес"), ("бизнес с нуля", "бизнес"),
]

YEAR_AGO = datetime.now(timezone.utc) - timedelta(days=365)


def to_card(e: dict, topic: str, feed: str) -> dict:
    c = e.get("counters") or {}
    author = e.get("author") or {}
    subsite = e.get("subsite") or {}
    kind = "media" if e.get("isEditorial") else "person"
    if (subsite.get("type") or 0) == 2 and not e.get("isEditorial"):
        kind = "company"
    return nz.card(
        PLATFORM,
        id=e["id"],
        url=e.get("url") or f"https://dtf.ru/{e['id']}",
        title=(e.get("title") or "").strip(),
        author=author.get("name"),
        author_kind=kind,
        published_at=datetime.fromtimestamp(e.get("date") or 0, timezone.utc).isoformat(),
        views=c.get("total"),
        likes=c.get("reactions"),
        comments=c.get("comments"),
        topic=topic,
        extra={
            "counters_views": c.get("views"),
            "hits": c.get("hits"),
            "favorites": c.get("favorites"),
            "subsite": subsite.get("name"),
            "subsite_id": e.get("subsiteId"),
            "is_editorial": e.get("isEditorial"),
            "is_news": e.get("isNews"),
            "author_id": author.get("id"),
            "source_feed": feed,
        },
    )


def keep(e: dict) -> bool:
    ts = e.get("date") or 0
    if datetime.fromtimestamp(ts, timezone.utc) < YEAR_AGO:
        return False
    if e.get("isNews"):
        return False
    return bool(e.get("blocks"))


def save(e: dict, topic: str, feed: str, group: str, seen: set) -> bool:
    # В выдаче поиска рядом со статьями приезжают карточки подсайтов
    # и репосты без тела — у них нет id, и это не ошибка.
    if not e.get("id") or str(e["id"]) in seen or not keep(e):
        return False
    body = nz.from_osnova_blocks(e.get("blocks") or [])
    if body["chars"] < 1500:
        return False
    card = to_card(e, topic, feed)
    card["group"] = group
    append(cards_path(PLATFORM), card)
    append(texts_path(PLATFORM), {
        "platform": PLATFORM, "id": card["id"], "url": card["url"],
        "title": card["title"], "group": group, "lead": "", **body,
    })
    seen.add(card["id"])
    return True


def stage_search(pages: int) -> None:
    seen = done_ids(cards_path(PLATFORM))
    for query, topic in QUERIES:
        added = 0
        for page in range(1, pages + 1):
            url = f"{SEARCH}?query={urllib.parse.quote(query)}&lastId={page}"
            data = get_json(url)
            items = ((data or {}).get("result") or {}).get("contents") or []
            if not items:
                break
            for it in items:
                # Поиск заворачивает статью в конверт, лента — тоже,
                # но не всегда: разворачиваем и там, и там.
                e = it.get("data") if isinstance(it, dict) and "data" in it else it
                if save(e or {}, topic, f"search:{query}", "top", seen):
                    added += 1
            pause()
        print(f"  «{query}»: +{added} (всего {len(seen)})")


def stage_baseline(weeks: int, per_week: int) -> None:
    """Фон: обычные посты за тот же год.

    Курсор timeline это обычный unix-таймстемп, поэтому в архив можно
    прыгать в любую неделю. Берём по две точки в неделю — так выборка
    не липнет к сезону.
    """
    seen = done_ids(cards_path(PLATFORM))
    now = int(time.time())
    added = 0
    for w in range(weeks):
        for k in range(per_week):
            ts = now - w * 7 * 86400 - k * 3 * 86400
            url = (f"{TIMELINE}?allSite=true&markdown=false&sorting=date"
                   f"&lastId=99999999&lastSortingValue={ts}")
            data = get_json(url)
            items = ((data or {}).get("result") or {}).get("items") or []
            for it in items:
                e = it.get("data") or {}
                if e and save(e, "фон", "baseline", "control", seen):
                    added += 1
            pause()
        if w % 5 == 0:
            print(f"  неделя -{w}: всего {len(seen)} (+{added})")
    print(f"фон собран: +{added}, в файле {len(seen)}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["search", "baseline"])
    ap.add_argument("--pages", type=int, default=8)
    ap.add_argument("--weeks", type=int, default=52)
    ap.add_argument("--per-week", type=int, default=2)
    args = ap.parse_args()
    if args.stage == "search":
        stage_search(args.pages)
    else:
        stage_baseline(args.weeks, args.per_week)


if __name__ == "__main__":
    main()
