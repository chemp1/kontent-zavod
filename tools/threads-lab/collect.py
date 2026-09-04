#!/usr/bin/env python3
"""Сборщик постов Threads через залогиненный браузер на отдельной машине.

Читает публичные страницы настоящим Chrome, которым управляет CLI `browser`
по ssh (хост - в переменной окружения `BROWSER_SSH_HOST`), достаёт посты
с метриками и дописывает их в data/posts.jsonl.

Только чтение. Скрипт никогда не кликает, не лайкает и не публикует: единственные
действия в браузере это переход по адресу и прокрутка. Это живой браузер живого
человека, и аккаунт в нём - не личный аккаунт автора.

Запуск:
    python3 collect.py --account <handle> --scrolls 5
    python3 collect.py --search "вайб-кодинг"
    python3 collect.py --watchlist            # все аккаунты из data/accounts.json
"""

from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from textclean import clean_post_text

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
POSTS_FILE = DATA / "posts.jsonl"
ACCOUNTS_FILE = DATA / "accounts.json"
EXTRACT_JS = HERE / "extract.js"

#: ssh-алиас машины с залогиненным Chrome и CLI `browser`.
BROWSER_SSH_HOST = os.environ.get("BROWSER_SSH_HOST", "browser-host")
SESSION = "tlab"
REMOTE_DIR = "/tmp/tools/threads-lab"

# Пауза между действиями. Человек листает ленту неровно, поэтому и мы тоже:
# ровный интервал это первое, на что смотрят анти-бот эвристики.
PAUSE_MIN, PAUSE_MAX = 3.0, 8.0

# Статистика профиля: подписчики и «недавние просмотры». Просмотры отдельных
# постов Threads не показывает никому, кроме автора, поэтому агрегат по профилю
# это единственный доступный сигнал охвата по чужому аккаунту.
PROFILE_JS = r"""
(() => {
  // Разбираем построчно, а не одной регуляркой по всей странице: Threads
  // разделяет разряды узкими неразрывными пробелами, и жадный поиск по всему
  // тексту отхватывает от числа хвост ("5 724 432" превращается в "431").
  const lines = (document.body.innerText || '').split('\n').map((s) => s.trim());
  const pick = (needle) => {
    const line = lines.find((l) => l.toLowerCase().includes(needle));
    if (!line) return null;
    const m = line.match(/([0-9][0-9\s.,   ]*[KMКМ]?)/);
    return m ? m[1].trim() : null;
  };
  return JSON.stringify({
    followers: pick('подписчик') || pick('follower'),
    recent_views: pick('недавних просмотр'),
    title: document.title,
  });
})()
"""


def pause() -> None:
    time.sleep(random.uniform(PAUSE_MIN, PAUSE_MAX))


def ssh(cmd: str, timeout: int = 90) -> str:
    res = subprocess.run(
        ["ssh", BROWSER_SSH_HOST, cmd],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return res.stdout.strip()


def browser(args: str, timeout: int = 90) -> str:
    return ssh(f"timeout 60 browser --session {SESSION} {args}", timeout=timeout)


def push_js(name: str, source: str) -> str:
    """Кладём JS файлом на хост браузера: кириллица в двойных ssh-кавычках коверкается."""
    remote = f"{REMOTE_DIR}/{name}"
    subprocess.run(
        ["ssh", BROWSER_SSH_HOST, f"mkdir -p {REMOTE_DIR}; cat > {remote}"],
        input=source,
        text=True,
        check=True,
        capture_output=True,
    )
    return remote


def evaluate(remote_js: str) -> object | None:
    raw = browser(f'eval "$(cat {remote_js})"')
    if not raw:
        return None
    try:
        envelope = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not envelope.get("success"):
        print(f"  eval не прошёл: {envelope.get('error')}", file=sys.stderr)
        return None
    inner = envelope.get("result", {}).get("result")
    if not inner:
        return None
    try:
        return json.loads(inner)
    except json.JSONDecodeError:
        return None


def open_window() -> None:
    browser("window create", timeout=60)


def close_window() -> None:
    browser("window close", timeout=60)


def goto(url: str) -> None:
    browser(f"goto '{url}'", timeout=90)
    pause()


def scroll() -> None:
    browser("eval \"window.scrollBy(0, window.innerHeight * 2); 'ok'\"", timeout=60)
    pause()


def media_kind(post: dict) -> str:
    if post.get("has_video"):
        return "video"
    if post.get("is_carousel"):
        return "carousel"
    # Одна картинка это чаще всего аватар автора, а не медиа поста.
    if (post.get("img_count") or 0) > 1:
        return "photo"
    return "none"


def normalize(post: dict, collected_at: datetime, source: str) -> dict | None:
    dt_raw = post.get("datetime")
    if not dt_raw:
        return None
    try:
        published = datetime.fromisoformat(dt_raw.replace("Z", "+00:00"))
    except ValueError:
        return None

    text = clean_post_text(post.get("text") or "", published.isoformat())
    age_hours = (collected_at - published).total_seconds() / 3600

    return {
        "id": post["id"],
        "author": post["author"],
        "url": post["url"],
        # Откуда пост попал в базу. Выдача поиска смещена в сторону удачных
        # постов, поэтому медиану автора считаем только по source="profile",
        # иначе норма завышается и всё выглядит недовыстрелившим.
        "source": source,
        "published_at": published.isoformat(),
        "collected_at": collected_at.isoformat(),
        "age_hours": round(age_hours, 1),
        "text": text,
        "length": len(text),
        "likes": post.get("likes"),
        "replies": post.get("replies"),
        "reposts": post.get("reposts"),
        "quotes": post.get("quotes"),
        "media": media_kind(post),
    }


def collect_page(url: str, scrolls: int) -> list[dict]:
    """Открыть страницу, прокрутить и собрать посты, сливая по id."""
    remote_js = push_js("extract.js", EXTRACT_JS.read_text())
    goto(url)

    # Извлекаем не после каждой прокрутки, а раз в три: один вызов browser
    # стоит примерно 15 секунд сетевого круга до расширения на той машине, и лишние
    # вызовы дают куда больше задержки, чем сами паузы между действиями.
    # Threads держит в DOM достаточно постов, чтобы ничего не потерялось.
    found: dict[str, dict] = {}
    for i in range(scrolls + 1):
        if i % 3 == 0 or i == scrolls:
            batch = evaluate(remote_js)
            if isinstance(batch, list):
                for post in batch:
                    found[post["id"]] = post
            print(f"  прокрутка {i}/{scrolls}: всего {len(found)}")
        if i < scrolls:
            scroll()
    return list(found.values())


def profile_stats(handle: str) -> dict:
    remote_js = push_js("profile.js", PROFILE_JS)
    stats = evaluate(remote_js)
    return stats if isinstance(stats, dict) else {}


def append_posts(rows: list[dict]) -> int:
    DATA.mkdir(exist_ok=True)
    # Дубль это тот же пост в том же снапшоте. Тот же пост, собранный завтра,
    # дублем не считается: по нему видно, как метрики росли.
    existing = set()
    if POSTS_FILE.exists():
        for line in POSTS_FILE.read_text().splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            existing.add((row["id"], row["collected_at"][:10]))

    written = 0
    with POSTS_FILE.open("a") as fh:
        for row in rows:
            key = (row["id"], row["collected_at"][:10])
            if key in existing:
                continue
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            existing.add(key)
            written += 1
    return written


def run_targets(targets: list[tuple[str, str]], scrolls: int) -> None:
    collected_at = datetime.now(timezone.utc)
    open_window()
    total = 0
    try:
        for kind, value in targets:
            if kind == "account":
                url = f"https://www.threads.com/@{value}"
            else:
                url = f"https://www.threads.com/search?q={value}&filter=top"
            print(f"\n{kind}: {value}")

            source = "profile" if kind == "account" else "search"
            raw_posts = collect_page(url, scrolls)
            rows = [
                r for r in (normalize(p, collected_at, source) for p in raw_posts) if r
            ]
            written = append_posts(rows)
            total += written
            print(f"  собрано {len(rows)}, новых записей {written}")

            if kind == "account":
                stats = profile_stats(value)
                if stats:
                    print(f"  профиль: {stats.get('followers')} подписчиков, "
                          f"{stats.get('recent_views')} недавних просмотров")
    finally:
        close_window()
    print(f"\nИтого новых записей: {total} -> {POSTS_FILE}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account", action="append", help="аккаунт без @, можно повторять")
    parser.add_argument("--search", action="append", help="поисковый запрос, можно повторять")
    parser.add_argument("--watchlist", action="store_true", help="все из accounts.json")
    parser.add_argument("--scrolls", type=int, default=4, help="сколько раз прокрутить")
    args = parser.parse_args()

    targets: list[tuple[str, str]] = []
    for handle in args.account or []:
        targets.append(("account", handle))
    for query in args.search or []:
        targets.append(("search", query))
    if args.watchlist:
        if not ACCOUNTS_FILE.exists():
            sys.exit(f"нет {ACCOUNTS_FILE}")
        accounts = json.loads(ACCOUNTS_FILE.read_text())
        targets += [("account", a["handle"]) for a in accounts]

    if not targets:
        parser.error("нужен --account, --search или --watchlist")

    run_targets(targets, args.scrolls)


if __name__ == "__main__":
    main()
