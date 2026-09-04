#!/usr/bin/env python3
"""Тексты статей Дзена — через живой Chrome на отдельной машине.

Единственное место во всём замере, где нужен браузер: метрики Дзен отдаёт
в JSON (`publicationStatistics` прямо в разметке), а тело статьи рендерит
клиентом — в HTML его нет, там ноль абзацев.

    python3 dzen/fetch_text.py --limit 220

Браузером управляет CLI `browser` по ssh; хост - в переменной окружения
`BROWSER_SSH_HOST`. Правила чужого браузера те же, что в tools/threads-lab: только
goto и eval, своё окно, закрыть за собой, один прогон в день, личный аккаунт
автора не используется.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import normalize as nz
from common.store import append, cards_path, done_ids, load_by_id, texts_path

#: ssh-алиас машины с залогиненным Chrome и CLI `browser`.
BROWSER_SSH_HOST = os.environ.get("BROWSER_SSH_HOST", "browser-host")
SESSION = "dzenlab"
REMOTE_DIR = "/tmp/tools/platform-lab"
PAUSE_MIN, PAUSE_MAX = 3.0, 7.0

# Тело статьи в Дзене живёт в article[itemprop] / .article-render; рекомендации
# и комментарии лежат рядом в такой же разметке, поэтому берём именно контейнер
# статьи, а не всё подряд, иначе к тексту приклеятся десять чужих заголовков.
EXTRACT_JS = r"""
(() => {
  const root =
    document.querySelector('[itemprop="articleBody"]') ||
    document.querySelector('.article-render') ||
    document.querySelector('article');
  if (!root) return JSON.stringify({ error: 'нет контейнера статьи' });
  const stats = (() => {
    const m = document.documentElement.innerHTML.match(
      /"publicationStatistics":\{"views":(\d+),"viewsTillEnd":(\d+)/);
    return m ? { views: +m[1], views_till_end: +m[2] } : {};
  })();
  const paras = [];
  const headers = [];
  let list_items = 0, media = 0, quotes = 0, links = 0;
  root.querySelectorAll('p, h1, h2, h3, h4, li, img, figure, blockquote, a').forEach((el) => {
    const tag = el.tagName.toLowerCase();
    const text = (el.innerText || '').trim();
    if (tag === 'p' && text.length > 1) paras.push(text);
    else if (/^h[1-4]$/.test(tag) && text) headers.push(text);
    else if (tag === 'li') list_items += 1;
    else if (tag === 'img' || tag === 'figure') media += 1;
    else if (tag === 'blockquote') quotes += 1;
    else if (tag === 'a') links += 1;
  });
  return JSON.stringify({ paras, headers, list_items, media, quotes, links, ...stats });
})()
"""


def pause() -> None:
    time.sleep(random.uniform(PAUSE_MIN, PAUSE_MAX))


def ssh(cmd: str, timeout: int = 120) -> str:
    try:
        res = subprocess.run(["ssh", BROWSER_SSH_HOST, cmd], capture_output=True,
                             text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return ""
    return res.stdout.strip()


def browser(args: str, timeout: int = 120) -> str:
    return ssh(f"timeout 90 browser --session {SESSION} {args}", timeout=timeout)


def push_js(name: str, source: str) -> str:
    """JS уезжает файлом: кириллица в двойных ssh-кавычках коверкается."""
    remote = f"{REMOTE_DIR}/{name}"
    subprocess.run(["ssh", BROWSER_SSH_HOST, f"mkdir -p {REMOTE_DIR}; cat > {remote}"],
                   input=source, text=True, check=True, capture_output=True)
    return remote


def evaluate(remote_js: str) -> dict | None:
    raw = browser(f'eval "$(cat {remote_js})"')
    if not raw:
        return None
    try:
        envelope = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not envelope.get("success"):
        return None
    inner = (envelope.get("result") or {}).get("result")
    if isinstance(inner, str):
        try:
            return json.loads(inner)
        except json.JSONDecodeError:
            return None
    return inner if isinstance(inner, dict) else None


def pick(limit: int) -> list[dict]:
    """Что качаем: верх по лифту и контроль из тех же каналов."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from analyze import add_lift, clean, load, split

    rows = clean("dzen", load("dzen")) if texts_path("dzen").exists() else []
    # Пока текстов мало, лифт считать не на чем: режем прямо по карточкам.
    if len(rows) >= limit:
        add_lift("dzen", rows)
        top, rest = split(rows)
        return (top + rest)[:limit]

    # Берём по каждому каналу его собственные верх и низ, а не общий топ:
    # иначе весь корпус соберётся из двух самых крупных каналов, и замер
    # опишет не тексты, а размер аудитории.
    from collections import defaultdict

    from analyze import kept_channels
    keep = kept_channels()
    by_channel: dict[str, list[dict]] = defaultdict(list)
    for c in load_by_id(cards_path("dzen")).values():
        ch = (c.get("extra") or {}).get("channel")
        if c.get("views") and ch in keep:
            by_channel[ch].append(c)

    per = max(4, limit // max(1, len(by_channel)))
    out: list[dict] = []
    for ch, cards in by_channel.items():
        cards.sort(key=lambda c: -(c["views"] or 0))
        half = max(2, per // 2)
        top = cards[:half]
        rest = cards[half:]
        step = max(1, len(rest) // max(1, half))
        out += top + rest[::step][:half]
    return out[:limit]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=220)
    args = ap.parse_args()

    todo = [c for c in pick(args.limit) if c["id"] not in done_ids(texts_path("dzen"))]
    print(f"к обходу {len(todo)} статей")
    remote = push_js("dzen_text.js", EXTRACT_JS)
    browser("window create")
    ok = 0
    try:
        for i, c in enumerate(todo, 1):
            browser(f"goto '{c['url']}'")
            pause()
            data = evaluate(remote)
            if not data or data.get("error") or not data.get("paras"):
                print(f"  {i}/{len(todo)} пусто: {c['url']}")
                continue
            body = {
                "paras": [p for p in data["paras"] if len(p) > 1],
                "headers": data.get("headers") or [],
                "list_items": data.get("list_items") or 0,
                "media": data.get("media") or 0,
                "quotes": data.get("quotes") or 0,
                "code_blocks": 0, "code_chars": 0,
                "links": data.get("links") or 0,
            }
            body["chars"] = sum(len(p) for p in body["paras"])
            append(texts_path("dzen"), {
                "platform": "dzen", "id": c["id"], "url": c["url"], "title": c["title"],
                "group": c.get("group", "pool"), "lead": (body["paras"] or [""])[0][:600],
                "views_till_end": data.get("views_till_end"), **body,
            })
            ok += 1
            print(f"  {i}/{len(todo)} {c['views']:>7} просм  {body['chars']:>6} зн  "
                  f"{c['title'][:52]}")
    finally:
        browser("window close")
    print(f"собрано текстов: {ok}")


if __name__ == "__main__":
    main()
