#!/usr/bin/env python3
"""Тематический срез Хабра: что там уже написано про Claude Code и вайб-кодинг.

Отличие от habr/collect.py: тот берёт хабы целиком и меряет площадку,
этот берёт поиск по теме и меряет нишу — что в ней уже занято.

    python3 habr/topic.py list           # карточки по запросам
    python3 habr/topic.py texts --top 100

Поиск Хабра живёт на том же API: ?query=<строка>&order=relevance,
до 1000 результатов на запрос. Написания собираем все: «claude code»
и «клод код» дают разные выдачи.
"""

from __future__ import annotations

import argparse
import re
import sys
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import normalize as nz
from common.fetch import get_json, pause
from common.store import DATA, TEXTS, append, done_ids, load_by_id, read_jsonl

PLATFORM = "habr-topic"
SEARCH = "https://habr.com/kek/v2/articles/"

QUERIES = [
    ("claude code", "claude code"),
    ("клод код", "claude code"),
    ("anthropic claude", "claude code"),
    ("вайб-кодинг", "вайб-кодинг"),
    ("вайбкодинг", "вайб-кодинг"),
    ("vibe coding", "вайб-кодинг"),
    ("вайб кодинг", "вайб-кодинг"),
    ("ai агент разработка", "агенты в разработке"),
    ("cursor ide", "соседи"),
    ("codex cli", "соседи"),
    ("agentic coding", "агенты в разработке"),
]

# Тема родилась в 2025-м: термин vibe coding — февраль 2025, Claude Code — весна 2025.
SINCE = datetime(2025, 1, 1, tzinfo=timezone.utc)

CARDS = DATA / PLATFORM / "cards.jsonl"
TEXTS_FILE = TEXTS / PLATFORM / "texts.jsonl"


def url_for(query: str, page: int) -> str:
    return (f"{SEARCH}?query={urllib.parse.quote(query)}&order=relevance"
            f"&page={page}&perPage=50&fl=ru&hl=ru")


def clean_title(html: str) -> str:
    return re.sub(r"\s+", " ", nz.strip_tags(html or "")).strip()


def to_card(ref: dict, topic: str, query: str) -> dict | None:
    published = ref.get("timePublished") or ""
    try:
        dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt < SINCE:
        return None
    st = ref.get("statistics") or {}
    author = (ref.get("author") or {}).get("alias")
    return nz.card(
        PLATFORM,
        id=ref["id"],
        url=f"https://habr.com/ru/articles/{ref['id']}/",
        title=clean_title(ref.get("titleHtml")),
        author=author,
        author_kind="company" if ref.get("isCorporative") else "person",
        published_at=dt.isoformat(),
        views=st.get("readingCount"),
        likes=st.get("votesCountPlus"),
        comments=st.get("commentsCount"),
        topic=topic,
        extra={
            "score": st.get("score"),
            "votes_minus": st.get("votesCountMinus"),
            "favorites": st.get("favoritesCount"),
            "reading_time": ref.get("readingTime"),
            "complexity": ref.get("complexity"),
            "post_type": ref.get("postType"),
            "hubs": [h.get("alias") for h in (ref.get("hubs") or [])],
            "tags": [t.get("titleHtml") for t in (ref.get("tags") or [])],
            "query": query,
        },
    )


def stage_list(pages: int) -> None:
    seen = done_ids(CARDS)
    for query, topic in QUERIES:
        added = 0
        for page in range(1, pages + 1):
            data = get_json(url_for(query, page))
            refs = (data or {}).get("publicationRefs") or {}
            if not refs:
                break
            for ref in refs.values():
                if str(ref["id"]) in seen:
                    continue
                card = to_card(ref, topic, query)
                if not card:
                    continue
                append(CARDS, card)
                seen.add(card["id"])
                added += 1
            pause()
        print(f"  «{query}»: +{added} (всего {len(seen)})")
    print(f"карточек: {len(seen)}")


# Поиск по релевантности приносит и соседей: «Лучшие нейросети 2025»,
# «Вторая жизнь старого смартфона». Фильтр по заголовку и тегам оставляет
# только те статьи, где тема действительно заявлена.
RELEVANT = re.compile(
    r"claude|клод|вайб|vibe|cursor|курсор|codex|копилот|copilot|"
    r"агент\w*\s+(код|разработ|программ)|(код|разработ|программ)\w*\s+агент|"
    r"ai[- ]агент|ии[- ]агент|llm.{0,20}(код|разработ)|(код|разработ).{0,20}llm|"
    r"нейросет\w+.{0,20}(код|программ|разработ)|(код|программ|разработ)\w*.{0,20}нейросет",
    re.I)


def is_relevant(card: dict) -> bool:
    blob = " ".join([card.get("title") or "",
                     " ".join((card.get("extra") or {}).get("tags") or []),
                     " ".join((card.get("extra") or {}).get("hubs") or [])])
    return bool(RELEVANT.search(blob))


def top_by_views(limit: int) -> list[dict]:
    cards = [c for c in load_by_id(CARDS).values()
             if (c.get("views") or 0) > 0 and is_relevant(c)]
    cards.sort(key=lambda c: -(c["views"] or 0))
    return cards[:limit]


def stage_texts(limit: int) -> None:
    todo = [c for c in top_by_views(limit) if c["id"] not in done_ids(TEXTS_FILE)]
    print(f"качаю тексты: {len(todo)}")
    for i, c in enumerate(todo, 1):
        data = get_json(f"https://habr.com/kek/v2/articles/{c['id']}/?fl=ru&hl=ru")
        if not data or not data.get("textHtml"):
            pause()
            continue
        body = nz.from_html(data["textHtml"])
        lead = nz.strip_tags((data.get("leadData") or {}).get("textHtml") or "")
        append(TEXTS_FILE, {
            "platform": PLATFORM, "id": c["id"], "url": c["url"], "title": c["title"],
            "group": "top", "lead": re.sub(r"\s+", " ", lead).strip(), **body,
        })
        print(f"  {i}/{len(todo)} {c['views']:>7} просм  {body['chars']:>6} зн  {c['title'][:56]}")
        pause()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["list", "texts"])
    ap.add_argument("--pages", type=int, default=6)
    ap.add_argument("--top", type=int, default=100)
    args = ap.parse_args()
    if args.stage == "list":
        stage_list(args.pages)
    else:
        stage_texts(args.top)


if __name__ == "__main__":
    main()
