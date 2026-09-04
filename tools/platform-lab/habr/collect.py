#!/usr/bin/env python3
"""Хабр: карточки статей и полные тексты через открытый API.

Авторизация не нужна, счётчики отдаются прямо в карточке — на Хабре видно
и просмотры, и рейтинг, и закладки. Это единственная из четырёх площадок,
где для полного текста тоже хватает API.

    python3 habr/collect.py list              # карточки по срезам
    python3 habr/collect.py texts --limit 260 # полные тексты отобранных

Срезы — хабы (тематика) и потоки (крупные разделы). Верхние страницы дают
кандидатов в «залетевшие», глубокие — контрольную группу тех же хабов
за тот же год: сравнивать статью с самой собой нельзя, нужна вторая группа.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import normalize as nz
from common.fetch import get_json, pause
from common.store import append, cards_path, done_ids, load_by_id, texts_path

API = "https://habr.com/kek/v2/articles/"
PLATFORM = "habr"

# Тематики автора: ИИ, технологии, бизнес. На Хабре бизнес живёт не в хабах,
# а в потоках management и marketing — проверено, flow=develop при этом 404.
SLICES = [
    ("hub", "artificial_intelligence", "ИИ"),
    ("hub", "machine_learning", "ИИ"),
    ("hub", "natural_language_processing", "ИИ"),
    ("hub", "itcompanies", "бизнес"),
    ("hub", "career", "карьера"),
    ("hub", "programming", "технологии"),
    ("flow", "management", "бизнес"),
    ("flow", "marketing", "бизнес"),
]

DEEP_PAGES = (25, 60, 110)   # контрольная группа: те же хабы, тот же год, не топ


def url_for(kind: str, alias: str, page: int) -> str:
    return (f"{API}?{kind}={alias}&sort=rating&period=yearly"
            f"&page={page}&perPage=20&fl=ru&hl=ru")


def to_card(ref: dict, topic: str) -> dict:
    st = ref.get("statistics") or {}
    author = (ref.get("author") or {}).get("alias")
    hubs = [h.get("alias") for h in (ref.get("hubs") or [])]
    return nz.card(
        PLATFORM,
        id=ref["id"],
        url=f"https://habr.com/ru/articles/{ref['id']}/",
        title=nz.strip_tags(ref.get("titleHtml") or "").strip(),
        author=author,
        author_kind="company" if ref.get("isCorporative") else "person",
        published_at=ref.get("timePublished") or "",
        views=st.get("readingCount"),
        likes=st.get("votesCountPlus"),
        comments=st.get("commentsCount"),
        topic=topic,
        extra={
            "score": st.get("score"),
            "votes_plus": st.get("votesCountPlus"),
            "votes_minus": st.get("votesCountMinus"),
            "favorites": st.get("favoritesCount"),
            "reach": st.get("reach"),
            "readers": st.get("readers"),
            "reading_time": ref.get("readingTime"),
            "complexity": ref.get("complexity"),
            "post_type": ref.get("postType"),
            "hubs": hubs,
            "tags": [t.get("titleHtml") for t in (ref.get("tags") or [])],
        },
    )


def stage_list(pages: int) -> None:
    out = cards_path(PLATFORM)
    seen = done_ids(out)
    added = 0
    for kind, alias, topic in SLICES:
        wanted = list(range(1, pages + 1)) + list(DEEP_PAGES)
        for page in wanted:
            data = get_json(url_for(kind, alias, page))
            refs = (data or {}).get("publicationRefs") or {}
            if not refs:
                print(f"  {kind}={alias} стр. {page}: пусто")
                pause()
                continue
            new = 0
            for ref in refs.values():
                if str(ref["id"]) in seen:
                    continue
                card = to_card(ref, topic)
                card["source_page"] = page
                card["source_slice"] = f"{kind}={alias}"
                append(out, card)
                seen.add(card["id"])
                new += 1
                added += 1
            print(f"  {kind}={alias} стр. {page}: +{new} (всего {len(seen)})")
            pause()
    print(f"карточек добавлено {added}, в файле {len(seen)}")


def within_year(card: dict) -> bool:
    try:
        dt = datetime.fromisoformat(card["published_at"].replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return False
    return dt >= datetime.now(timezone.utc) - timedelta(days=365)


def select(cards: list[dict], top_n: int, control_n: int) -> list[dict]:
    """Сотня залетевших и контрольная группа из того же корпуса.

    Корпоративные блоги отсекаем до отбора: это аналог редакции на vc,
    их раздают подписчикам хаба, и сравнивать личную статью с ними
    так же бессмысленно, как блогерскую статью с редакционной.
    """
    pool = [c for c in cards if c["author_kind"] == "person" and within_year(c)
            and (c.get("views") or 0) > 0]
    pool.sort(key=lambda c: -(c["views"] or 0))
    top = pool[:top_n]
    rest = pool[top_n:]
    step = max(1, len(rest) // control_n) if rest else 1
    control = rest[::step][:control_n]
    for c in top:
        c["group"] = "top"
    for c in control:
        c["group"] = "control"
    return top + control


def stage_texts(top_n: int, control_n: int) -> None:
    cards = list(load_by_id(cards_path(PLATFORM)).values())
    chosen = select(cards, top_n, control_n)
    out = texts_path(PLATFORM)
    done = done_ids(out)
    todo = [c for c in chosen if c["id"] not in done]
    print(f"отобрано {len(chosen)} (топ {top_n} + контроль {control_n}), "
          f"уже есть {len(chosen) - len(todo)}, качаю {len(todo)}")
    for i, c in enumerate(todo, 1):
        data = get_json(f"https://habr.com/kek/v2/articles/{c['id']}/?fl=ru&hl=ru")
        if not data or not data.get("textHtml"):
            print(f"  {i}/{len(todo)} id={c['id']}: текста нет")
            pause()
            continue
        body = nz.from_html(data["textHtml"])
        lead = nz.strip_tags((data.get("leadData") or {}).get("textHtml") or "")
        append(out, {
            "platform": PLATFORM, "id": c["id"], "url": c["url"], "title": c["title"],
            "group": c["group"], "lead": re.sub(r"\s+", " ", lead).strip(), **body,
        })
        print(f"  {i}/{len(todo)} {c['views']:>7} просм  {body['chars']:>6} зн  "
              f"{c['title'][:60]}")
        pause()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["list", "texts"])
    ap.add_argument("--pages", type=int, default=6, help="верхних страниц на срез")
    ap.add_argument("--top", type=int, default=100)
    ap.add_argument("--control", type=int, default=100)
    args = ap.parse_args()
    if args.stage == "list":
        stage_list(args.pages)
    else:
        stage_texts(args.top, args.control)


if __name__ == "__main__":
    main()
