#!/usr/bin/env python3
"""Единое представление статьи: четыре площадки отдают текст четырьмя способами.

Хабр — HTML в `textHtml`, DTF — блоки Editor.js, TenChat — HTML страницы,
Дзен — DOM из живого браузера. Чтобы `features.py` был один на всех,
всё сводится к одной форме:

    {paras[], headers[], list_items, media, quotes, code_blocks, code_chars,
     links, chars}

Абзацы хранятся текстами, а не счётчиками: ритм абзацев — главный признак
из замера vc, и его нельзя посчитать по числу.
"""

from __future__ import annotations

import re

from lxml import html as lhtml

EMPTY = {
    "paras": [], "headers": [], "list_items": 0, "media": 0, "quotes": 0,
    "code_blocks": 0, "code_chars": 0, "links": 0, "chars": 0,
}

# Хвосты, которые площадки дописывают в тело: подписки, дисклеймеры, реклама.
TAIL = re.compile(
    r"^(подпис\w+ на|читайте так\w+|источник:|реклама\b|erid:|"
    r"больше материалов|наш телеграм|telegram-канал|#\w+\s*$)", re.I)


def _clean(s: str) -> str:
    s = s.replace("\xa0", " ").replace(" ", " ").replace(" ", " ")
    return re.sub(r"\s+", " ", s).strip()


def _finish(d: dict) -> dict:
    d["paras"] = [p for p in d["paras"] if len(p) > 1 and not TAIL.match(p)]
    d["headers"] = [h for h in d["headers"] if h]
    d["chars"] = sum(len(p) for p in d["paras"])
    return d


def from_html(source: str) -> dict:
    """HTML тела статьи → единая форма. Годится для Хабра, TenChat, Дзена."""
    d = {k: (list(v) if isinstance(v, list) else v) for k, v in EMPTY.items()}
    if not source or not source.strip():
        return _finish(d)
    try:
        root = lhtml.fromstring(source)
    except Exception:
        return _finish(d)

    # Код считаем до того, как вырежем его из текста: на Хабре доля кода —
    # самостоятельный признак жанра, а внутри абзацев он только мусорит.
    for pre in root.xpath("//pre|//code[not(ancestor::pre)]"):
        text = _clean(pre.text_content())
        if len(text) < 20:
            continue
        d["code_blocks"] += 1
        d["code_chars"] += len(text)

    d["media"] = len(root.xpath("//img|//video|//iframe|//figure"))
    d["links"] = len(root.xpath("//a[@href]"))
    d["list_items"] = len(root.xpath("//li"))
    d["quotes"] = len(root.xpath("//blockquote"))

    for node in root.xpath("//h1|//h2|//h3|//h4"):
        d["headers"].append(_clean(node.text_content()))

    for node in root.xpath("//p|//div[not(descendant::p) and not(descendant::div)]"):
        if node.xpath("ancestor::pre|ancestor::blockquote|ancestor::li|ancestor::figure"):
            continue
        text = _clean(node.text_content())
        if len(text) >= 2:
            d["paras"].append(text)

    # Некоторые редакторы (Дзен) отдают текст без <p>: абзацы разделены <br>.
    if not d["paras"]:
        raw = _clean(root.text_content())
        if raw:
            d["paras"] = [p for p in re.split(r"(?<=[.!?])\s{2,}", raw) if p]

    return _finish(d)


def from_osnova_blocks(blocks: list[dict]) -> dict:
    """Блоки Editor.js: vc.ru и DTF отдают их прямо в ответе API."""
    d = {k: (list(v) if isinstance(v, list) else v) for k, v in EMPTY.items()}
    for b in blocks or []:
        t = b.get("type")
        data = b.get("data") or {}
        if t == "header":
            d["headers"].append(_clean(strip_tags(data.get("text", ""))))
        elif t == "text":
            text = _clean(strip_tags(data.get("text", "")))
            d["links"] += len(re.findall(r"<a\s", data.get("text", "")))
            if text:
                d["paras"].append(text)
        elif t == "list":
            d["list_items"] += len(data.get("items") or [])
        elif t in ("media", "image", "video", "gallery"):
            items = data.get("items")
            d["media"] += len(items) if isinstance(items, list) else 1
        elif t == "quote":
            d["quotes"] += 1
            text = _clean(strip_tags(data.get("text", "")))
            if text:
                d["paras"].append(text)
        elif t == "code":
            code = data.get("text", "")
            d["code_blocks"] += 1
            d["code_chars"] += len(code)
    return _finish(d)


def from_markdown(text: str) -> dict:
    """TenChat отдаёт тело поста маркдауном прямо в пейлоаде страницы."""
    d = {k: (list(v) if isinstance(v, list) else v) for k, v in EMPTY.items()}
    if not text:
        return _finish(d)
    in_code = False
    buf: list[str] = []

    def flush():
        if buf:
            para = _clean(" ".join(buf))
            if para:
                d["paras"].append(para)
            buf.clear()

    for raw in text.splitlines():
        line = raw.rstrip()
        if line.strip().startswith("```"):
            flush()
            in_code = not in_code
            if in_code:
                d["code_blocks"] += 1
            continue
        if in_code:
            d["code_chars"] += len(line)
            continue
        if not line.strip():
            flush()
            continue
        if re.match(r"^#{1,4}\s+", line):
            flush()
            d["headers"].append(_clean(re.sub(r"^#{1,4}\s+", "", line)))
        elif re.match(r"^\s*([-*•]|\d+[.)])\s+", line):
            flush()
            d["list_items"] += 1
        elif line.lstrip().startswith(">"):
            flush()
            d["quotes"] += 1
            d["paras"].append(_clean(line.lstrip("> ")))
        elif re.match(r"^\s*!\[", line):
            flush()
            d["media"] += 1
        elif re.match(r"^\s*[-—_]{3,}\s*$", line):
            flush()
        else:
            buf.append(line)
    flush()
    d["links"] = len(re.findall(r"https?://", text))
    return _finish(d)


def strip_tags(s: str) -> str:
    """Посимвольно, как в старом замере vc: регексп на вложенных тегах ошибается."""
    out, depth = [], 0
    for ch in s or "":
        if ch == "<":
            depth += 1
        elif ch == ">":
            depth = max(0, depth - 1)
        elif depth == 0:
            out.append(ch)
    return "".join(out)


def card(platform: str, *, id, url: str, title: str, author: str | None,
         author_kind: str, published_at: str, views: int | None,
         likes: int | None = None, comments: int | None = None,
         topic: str | None = None, extra: dict | None = None) -> dict:
    """Карточка статьи в общем виде — одна форма на все четыре площадки.

    author_kind: 'person' | 'company' | 'media' — главный срез замера.
    На vc это было is_editorial, здесь у каждой площадки свой признак,
    но смысл один: с кем себя сравнивать бессмысленно.
    """
    return {
        "platform": platform,
        "id": str(id),
        "url": url,
        "title": title,
        "author": author,
        "author_kind": author_kind,
        "published_at": published_at,
        "views": views,
        "likes": likes,
        "comments": comments,
        "topic": topic,
        "extra": extra or {},
    }
