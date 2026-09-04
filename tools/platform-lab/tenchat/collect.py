#!/usr/bin/env python3
"""TenChat: посты с метриками и полными текстами из SSR-пейлоада.

Публичного API нет, зато страница хештега отдаёт двадцать постов,
отсортированных по просмотрам за все годы, — и в `__NUXT_DATA__` лежит
всё сразу: текст маркдауном, viewCount, likeCount, комментарии, автор,
хештеги. Один запрос = двадцать залетевших постов с текстами.

    python3 tenchat/collect.py --rounds 2 --top-hashtags 40

Транслитерацию хештега угадывать нельзя (`/hashtag/нейросеть` → 500,
`/hashtag/neyroset` → 200): правильный ключ приходит в самих постах,
в поле hashtags[].nameTransliteration. Поэтому сбор идёт кругами:
посев → собрали хештеги из постов → второй круг по ним.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import normalize as nz
from common.fetch import get, pause
from common.store import append, cards_path, done_ids, texts_path

PLATFORM = "tenchat"
BASE = "https://tenchat.ru/hashtag/"

SEED = ["neyroset", "iskusstvennyyintellekt", "biznes", "predprinimatelstvo",
        "tehnologii", "it", "avtomatizaciya", "startap"]

# Тематический фильтр для второго круга: TenChat — деловая сеть, и без
# фильтра в выборку заедут «саморазвитие» и «нетворкинг» во всю ширину.
TOPICAL = re.compile(
    r"neyro|intellekt|ai\b|gpt|chatgpt|tehnolog|it\b|cifrov|avtomat|"
    r"biznes|predprinim|startap|prodazh|marketing|produkt|razrabotk|"
    r"programmir|dannye|analitik", re.I)

# Инфобизнес и SEO-помойка: на TenChat это заметная часть ленты.
SPAM = re.compile(
    r"^топ[- ]?\d+|пробив|официальный сайт|бесплатн\w* (курс|марафон|разбор)|"
    r"запишись на консультац|марафон желаний|мой наставник|"
    r"лучших ботов|скачать бесплатно", re.I)

TOPIC_BY_TAG = {"ИИ": r"neyro|intellekt|gpt|ai\b", "технологии": r"tehnolog|it\b|razrabotk|cifrov|dannye|programmir"}
YEAR_AGO = datetime.now(timezone.utc) - timedelta(days=365)


def payload(html: str) -> list | None:
    m = re.search(r'<script[^>]*id="__NUXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


def resolve(arr: list, idx, depth: int = 0):
    """Пейлоад Nuxt плоский: значения ссылаются друг на друга по индексам."""
    if depth > 6 or not isinstance(idx, int) or not (0 <= idx < len(arr)):
        return None
    v = arr[idx]
    if isinstance(v, dict):
        return {k: resolve(arr, i, depth + 1) for k, i in v.items()}
    if isinstance(v, list):
        if v and isinstance(v[0], str) and v[0] in ("Reactive", "Ref", "ShallowRef", "EmptyRef"):
            return resolve(arr, v[1], depth + 1) if len(v) > 1 else None
        return [resolve(arr, i, depth + 1) for i in v]
    return v


def posts_from(html: str) -> list[dict]:
    arr = payload(html)
    if not arr:
        return []
    out = []
    for i, v in enumerate(arr):
        if isinstance(v, dict) and "viewCount" in v and "text" in v:
            post = resolve(arr, i)
            if post and post.get("id"):
                out.append(post)
    return out


def topic_for(tags: list[str]) -> str:
    joined = " ".join(tags)
    for topic, pat in TOPIC_BY_TAG.items():
        if re.search(pat, joined, re.I):
            return topic
    return "бизнес"


def to_card(p: dict, tag: str) -> dict:
    user = p.get("user") or {}
    # Поля автора в пейлоаде называются name/surname/username, а не firstName.
    name = (user.get("username")
            or " ".join(x for x in [user.get("name"), user.get("surname")] if x))
    acc = (user.get("accountType") or "").upper()
    tags = [h.get("name") for h in (p.get("hashtags") or []) if isinstance(h, dict) and h.get("name")]
    return nz.card(
        PLATFORM,
        id=p["id"],
        url=f"https://tenchat.ru/media/{p['id']}-{p.get('titleTransliteration') or ''}".rstrip("-"),
        title=(p.get("title") or "").strip(),
        author=name,
        author_kind="company" if acc in ("COMPANY", "LEGAL_ENTITY") else "person",
        published_at=p.get("publishDate") or "",
        views=p.get("viewCount"),
        likes=p.get("likeCount"),
        comments=p.get("userCommentCount"),
        topic=topic_for(tags),
        extra={
            "shares": p.get("shareCount"),
            "hashtags": tags,
            "account_type": acc,
            "subscribers": user.get("subscriberCounter"),
            "position": user.get("positionName"),
            "company": user.get("companyName"),
            "feed_type": p.get("feedType"),
            "pictures": len(p.get("pictures") or []),
            "source_tag": tag,
        },
    )


def fresh_enough(card: dict) -> bool:
    """Топ хештега отсортирован по просмотрам за все годы, а нам нужен год.

    Отсюда же особенность площадки для отчёта: лучшие посты TenChat живут
    годами, и «за 12 месяцев» здесь — это срез, а не весь топ.
    """
    try:
        dt = datetime.fromisoformat(card["published_at"])
    except (ValueError, TypeError):
        return False
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt >= YEAR_AGO


def harvest(tag: str, seen: set, counter: Counter) -> int:
    html = get(BASE + tag)
    if not html:
        print(f"  #{tag}: не открылся")
        return 0
    added = 0
    for p in posts_from(html):
        pid = str(p["id"])
        for h in p.get("hashtags") or []:
            if isinstance(h, dict) and h.get("nameTransliteration"):
                counter[h["nameTransliteration"]] += h.get("postCount") or 1
        if pid in seen:
            continue
        card = to_card(p, tag)
        if not fresh_enough(card) or SPAM.search(card["title"] or ""):
            continue
        body = nz.from_markdown(p.get("text") or "")
        if body["chars"] < 900:      # площадка короче остальных, порог vc тут выкосит половину
            continue
        card["group"] = "top"
        append(cards_path(PLATFORM), card)
        append(texts_path(PLATFORM), {
            "platform": PLATFORM, "id": card["id"], "url": card["url"],
            "title": card["title"], "group": "top", "lead": "", **body,
        })
        seen.add(pid)
        added += 1
    print(f"  #{tag}: +{added} (всего {len(seen)})")
    return added


def save_post(p: dict, tag: str, group: str, seen: set) -> bool:
    pid = str(p.get("id") or "")
    if not pid or pid in seen:
        return False
    card = to_card(p, tag)
    if not fresh_enough(card) or SPAM.search(card["title"] or ""):
        return False
    body = nz.from_markdown(p.get("text") or "")
    if body["chars"] < 900:
        return False
    card["group"] = group
    append(cards_path(PLATFORM), card)
    append(texts_path(PLATFORM), {
        "platform": PLATFORM, "id": card["id"], "url": card["url"],
        "title": card["title"], "group": group, "lead": "", **body,
    })
    seen.add(pid)
    return True


def stage_neighbors(limit: int) -> None:
    """Контрольная группа: страница поста несёт соседние посты того же автора.

    Хештег отдаёт только топ-20 по просмотрам — то есть одних залетевших.
    Сравнивать их не с чем, пока рядом не лежат обычные посты тех же людей.
    """
    from common.store import read_jsonl
    cards = [c for c in read_jsonl(cards_path(PLATFORM)) if c.get("group") == "top"]
    cards.sort(key=lambda c: -(c.get("views") or 0))
    seen = done_ids(cards_path(PLATFORM))
    added = 0
    for i, c in enumerate(cards[:limit], 1):
        html = get(c["url"])
        if not html:
            continue
        for p in posts_from(html):
            if save_post(p, "neighbor", "control", seen):
                added += 1
        if i % 10 == 0:
            print(f"  {i}/{min(limit, len(cards))}: контрольных +{added} (всего {len(seen)})")
        pause()
    print(f"контрольная группа: +{added}, в файле {len(seen)}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", nargs="?", default="hashtags", choices=["hashtags", "neighbors"])
    ap.add_argument("--rounds", type=int, default=2)
    ap.add_argument("--top-hashtags", type=int, default=40)
    ap.add_argument("--limit", type=int, default=60)
    args = ap.parse_args()

    if args.stage == "neighbors":
        stage_neighbors(args.limit)
        return

    seen = done_ids(cards_path(PLATFORM))
    counter: Counter = Counter()
    done_tags: set[str] = set()
    queue = list(SEED)

    for rnd in range(args.rounds):
        print(f"круг {rnd + 1}: {len(queue)} хештегов")
        for tag in queue:
            if tag in done_tags:
                continue
            done_tags.add(tag)
            harvest(tag, seen, counter)
            pause()
        queue = [t for t, _ in counter.most_common()
                 if t not in done_tags and TOPICAL.search(t)][:args.top_hashtags]
        if not queue:
            break
    print(f"собрано постов: {len(seen)}, хештегов пройдено {len(done_tags)}")


if __name__ == "__main__":
    main()
