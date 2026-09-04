#!/usr/bin/env python3
"""Сводка по площадке: чем верхняя четверть отличается от остальных.

Главное отличие от старого замера vc — «залёт» считается не в абсолютных просмотрах,
а относительно нормы своего донора охвата: канала на Дзене, автора
в TenChat, хаба на Хабре, раздела на DTF. Абсолютный топ Дзена это топ
подписчиков, а не топ текста, и сравнивать по нему бессмысленно.

    python3 analyze.py habr
    python3 analyze.py --all
"""

from __future__ import annotations

import argparse
import re
import statistics
from datetime import datetime, timezone

from common.features import SHARE_KEYS, features, medians
from common.store import cards_path, load_by_id, read_jsonl, texts_path

PLATFORMS = ["habr", "dzen", "tenchat", "dtf", "vc"]

# Донор охвата: относительно чего считается норма.
PEER = {
    "habr": lambda c: (c.get("extra") or {}).get("hubs", [None])[0] or c.get("topic"),
    "dzen": lambda c: (c.get("extra") or {}).get("channel"),
    "tenchat": lambda c: c.get("author"),
    "dtf": lambda c: (c.get("extra") or {}).get("subsite"),
    "vc": lambda c: (c.get("extra") or {}).get("subsite"),
}

# По чему резать верхнюю четверть. Везде — лифт к норме своего донора, кроме
# Дзена: там каналов в корпусе мало, у половины меньше десятка статей, и лифт
# вытаскивает наверх выбросы мелких каналов вместо того, что площадка реально
# раздаёт. Оба разбиения посчитаны, расхождение вынесено в отчёт.
SPLIT_KEY = {"habr": "_lift", "dtf": "_lift", "tenchat": "_lift",
             "vc": "_lift", "dzen": "views"}

SPAM = re.compile(r"\bмфо\b|займ|кредитн|букмекер|казино|ставк[аи] на спорт|промокод|"
                  r"накрутк|обменник|обмен валют|как оплатить|подписк[уи] \w+ из россии|"
                  r"^топ[- ]?\d+|пробив|бесплатн\w* (курс|марафон)|звезды в тг", re.I)

MIN_CHARS = {"habr": 1500, "dzen": 1500, "dtf": 1500, "tenchat": 900, "vc": 1500}
# Свежая статья ещё не добрала охват — но «свежая» на разных площадках разное.
# Дзен и TenChat раздают алгоритмом за первые дни, Хабр и DTF копят месяцами
# из поиска и обсуждения. Один порог на всех выкосил бы половину ленточных
# площадок и ничего не дал бы поисковым.
MIN_AGE = {"habr": 30, "dtf": 30, "dzen": 14, "tenchat": 14, "vc": 14}


def load_labels(platform: str) -> dict[str, dict]:
    """Разметка чтением: жанр, кто говорит, зачин, конкретика."""
    from common.store import TEXTS
    out: dict[str, dict] = {}
    folder = TEXTS / platform / "labels"
    if not folder.exists():
        return out
    for path in sorted(folder.glob("batch-*.jsonl")):
        for row in read_jsonl(path):
            if row.get("id"):
                out[str(row["id"])] = row
    return out


def load(platform: str) -> list[dict]:
    cards = load_by_id(cards_path(platform))
    labels = load_labels(platform)
    rows = []
    for t in read_jsonl(texts_path(platform)):
        card = cards.get(t["id"])
        if not card:
            continue
        row = {**card, **t}
        row["_f"] = features(t | {"title": card["title"]})
        row["_l"] = labels.get(str(t["id"]), {})
        rows.append(row)
    return rows


def age_days(row: dict) -> float:
    try:
        dt = datetime.fromisoformat(row["published_at"])
    except (ValueError, TypeError):
        return 0.0
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - dt).total_seconds() / 86400


def kept_channels() -> set[str]:
    import json
    from common.store import DATA
    path = DATA / "dzen" / "channels.json"
    if not path.exists():
        return set()
    return {c["alias"] for c in json.loads(path.read_text(encoding="utf-8")) if c.get("keep")}


def clean(platform: str, rows: list[dict]) -> list[dict]:
    """Отсев до сравнения: корпоративные блоги, SEO, короткое, свежее.

    Дзен — исключение по типу автора: тематических каналов там мало и почти
    все они принадлежат медиа или компаниям. Личных блогеров про ИИ и бизнес
    на площадке единицы, поэтому в корпус идут все кураторские каналы,
    а разница между ними снимается лифтом к норме своего канала.
    """
    keep = kept_channels() if platform == "dzen" else set()
    out = []
    for r in rows:
        if platform == "dzen":
            if (r.get("extra") or {}).get("channel") not in keep:
                continue
        elif r.get("author_kind") != "person":
            continue
        if SPAM.search(r.get("title") or ""):
            continue
        if r["_f"]["chars"] < MIN_CHARS[platform]:
            continue
        if not r.get("views"):
            continue
        r["_age"] = age_days(r)
        if r["_age"] < MIN_AGE[platform]:
            continue
        out.append(r)
    return out


def add_lift(platform: str, rows: list[dict]) -> None:
    """Норма считается по донору охвата, а если он мал — по площадке."""
    peer_of = PEER[platform]
    groups: dict[str, list[int]] = {}
    for r in rows:
        groups.setdefault(peer_of(r) or "—", []).append(r["views"])
    site_median = statistics.median([r["views"] for r in rows]) if rows else 1
    for r in rows:
        peer = peer_of(r) or "—"
        vals = groups.get(peer, [])
        base = statistics.median(vals) if len(vals) >= 5 else site_median
        r["_peer"] = peer
        r["_lift"] = r["views"] / max(1, base)


def split(rows: list[dict], key: str = "_lift") -> tuple[list[dict], list[dict]]:
    ordered = sorted(rows, key=lambda r: -r[key])
    n = max(3, len(ordered) // 4)
    return ordered[:n], ordered[n:]


def show(label: str, rows: list[dict]) -> dict:
    med = medians([r["_f"] for r in rows])
    if not med:
        print(f"\n=== {label}: пусто ===")
        return {}
    print(f"\n=== {label} ({len(rows)} статей) ===")
    print(f"  знаков {med['chars']:.0f}, абзацев {med['paras']:.0f}, "
          f"медиана абзаца {med['para_median']:.0f} слов, ритм p90/p10 {med['para_p90_p10']:.0f}x, "
          f"ровных подряд {med['max_run_even']:.0f}")
    print(f"  подзаголовков {med['headers']:.0f} (знаков на подзаголовок {med['chars_per_header']:.0f}), "
          f"списка {med['list_items']:.0f}, картинок {med['media']:.0f}, цитат {med['quotes']:.0f}, "
          f"код {med['code_share']:.0f}%")
    print(f"  цифр/1k {med['numbers_per_1k']:.1f}, ссылок/1k {med['links_per_1k']:.1f}, "
          f"«я»/1k {med['i_per_1k']:.1f}, «мы»/1k {med['we_per_1k']:.1f}, «вы»/1k {med['you_per_1k']:.1f}")
    print(f"  заголовок: {med['t_words']:.0f} слов; число {med['t_num']:.0f}%, "
          f"двоеточие {med['t_colon']:.0f}%, от первого лица {med['t_first_person']:.0f}%, "
          f"моя история {med['t_my_story']:.0f}%, инструкция {med['t_howto']:.0f}%, "
          f"отрицание {med['t_neg']:.0f}%, обращение к читателю {med['t_you']:.0f}%")
    print(f"  лид: с цифрой {med['lead_num']:.0f}%, от «я» {med['lead_i']:.0f}%, "
          f"со сцены {med['lead_story']:.0f}%; концовка с продажей {med['ends_with_cta']:.0f}%")
    return med


def report(platform: str) -> dict:
    rows = clean(platform, load(platform))
    if not rows:
        print(f"\n### {platform}: данных нет")
        return {}
    add_lift(platform, rows)
    top, rest = split(rows, SPLIT_KEY[platform])
    peers = {r["_peer"] for r in rows}
    print(f"\n\n### {platform.upper()} — {len(rows)} статей, доноров охвата {len(peers)}")
    print(f"  медиана просмотров {statistics.median([r['views'] for r in rows]):.0f}, "
          f"максимум {max(r['views'] for r in rows)}")
    if SPLIT_KEY[platform] == "views":
        print(f"  порог верхней четверти: {top[-1]['views']} просмотров "
              f"(разбиение по абсолютному охвату)")
    else:
        print(f"  порог верхней четверти: лифт {top[-1]['_lift']:.1f}x к норме своего донора")
    print(f"  медиана возраста {statistics.median([r['_age'] for r in rows]):.0f} дней")
    med_top, med_rest = show("верхняя четверть", top), show("остальные", rest)
    print("\n  самые залетевшие:")
    for r in top[:10]:
        print(f"   {r['views']:>8} просм  x{r['_lift']:>5.1f}  {r['title'][:66]}")
    return {"platform": platform, "rows": rows, "top": top, "rest": rest,
            "med_top": med_top, "med_rest": med_rest}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("platform", nargs="?", choices=PLATFORMS)
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()
    targets = PLATFORMS if args.all or not args.platform else [args.platform]
    for p in targets:
        report(p)


if __name__ == "__main__":
    main()
