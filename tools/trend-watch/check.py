#!/usr/bin/env python3
"""Сборщик трендов для контент-плана.

Раз в сутки обходит фиды из `content/trends/sources.md` — YouTube-каналы фондов
(YC, Sequoia, a16z), новостные ленты и Hacker News, — отбирает свежее, показывает
каждое агенту и складывает карточки в `content/trends/`. Карточка это суть за три
строки, ссылка и два-три угла, под которыми автор мог бы высказаться.

Постов сборщик не пишет намеренно (решение автора 29.08.2026): угол — приглашение
подумать, готовый текст из новости — конвейер слопа.

Кто автор - из `voice/author.json`; куда слать уведомление - из `NOTIFY`
(см. `.env.example`). Настройки читаются из `tools/trend-watch/.env`, если он есть.

Разовый прогон: `python3 tools/trend-watch/check.py --dry-run` покажет отобранное,
ничего не записав.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import (dump_frontmatter, find_root, load_author, load_dotenv, log,  # noqa: E402
                    notify, parse_frontmatter, render)

load_dotenv(HERE / '.env')

ROOT = find_root()
TRENDS = ROOT / 'content' / 'trends'
SOURCES = TRENDS / 'sources.md'
DATA = ROOT / '.data' / 'tools/trend-watch'
SEEN = DATA / 'seen.json'

#: Куда ведёт ссылка в уведомлении. По умолчанию - локальная студия.
STUDIO = os.environ.get('STUDIO_URL', 'http://127.0.0.1:5180/plan/trends')
UA = 'Mozilla/5.0 (compatible; tools/trend-watch/1.0)'

# Сколько дней назад ещё считается свежим. Больше трёх смысла нет: то, что
# провисело неделю, уже не тренд, а справочный материал.
FRESH_DAYS = 3
# Потолок на один фид за прогон, чтобы плодовитый TechCrunch не занял всю ленту.
MAX_PER_FEED = 2
# HN отдаёт всю главную; ниже этого порога обсуждение обычно не состоялось.
HN_MIN_POINTS = 150
# Карточки старше этого срока выпадают из памяти о виденном.
SEEN_TTL_DAYS = 90

ATOM = '{http://www.w3.org/2005/Atom}'
MEDIA = '{http://search.yahoo.com/mrss/}'

TRANSLIT = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e', 'ж': 'zh',
    'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o',
    'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'h', 'ц': 'c',
    'ч': 'ch', 'ш': 'sh', 'щ': 'sch', 'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e',
    'ю': 'yu', 'я': 'ya',
}


def slugify(title: str) -> str:
    """Слаг для имени файла. Латиница, цифры и дефис — их ждёт студия."""
    base = ''.join(TRANSLIT.get(ch, ch) for ch in title.lower())
    base = re.sub(r'[^a-z0-9]+', '-', base).strip('-')[:60].strip('-')
    return base or 'trend'


def clean_html(text: str) -> str:
    text = re.sub(r'<[^>]+>', ' ', text or '')
    for entity, char in (('&amp;', '&'), ('&quot;', '"'), ('&#8217;', '’'), ('&nbsp;', ' ')):
        text = text.replace(entity, char)
    return re.sub(r'\s+', ' ', text).strip()


def fetch(url: str, timeout: int = 30) -> str | None:
    request = urllib.request.Request(url, headers={'User-Agent': UA})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode('utf-8', 'replace')
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        log(f'фид не ответил: {url} — {error}')
        return None


# ---------------------------------------------------------------- источники


def read_sources() -> dict:
    """Список фидов и фильтры. Файл читается на каждом прогоне: правка = новая лента."""
    data, _body = parse_frontmatter(SOURCES.read_text())
    if not data:
        raise SystemExit(f'{SOURCES}: нет фронтматтера со списком фидов')
    if not data.get('feeds'):
        raise SystemExit(f'{SOURCES}: пустой список фидов')
    return data


def parse_date(value: str) -> str:
    """Дата публикации в виде `ГГГГ-ММ-ДД`; пусто, если разобрать не вышло."""
    value = (value or '').strip()
    for fmt in ('%a, %d %b %Y %H:%M:%S %z', '%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%dT%H:%M:%SZ'):
        try:
            return datetime.strptime(value, fmt).astimezone(timezone.utc).strftime('%Y-%m-%d')
        except ValueError:
            continue
    # Атом иногда отдаёт микросекунды, RSS — «GMT» вместо смещения.
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).strftime('%Y-%m-%d')
    except ValueError:
        return ''


def parse_atom(xml: str, feed: dict) -> list[dict]:
    root = ET.fromstring(xml)
    items = []
    for entry in root.findall(f'{ATOM}entry'):
        link = entry.find(f'{ATOM}link')
        description = entry.find(f'{MEDIA}group/{MEDIA}description')
        summary = entry.find(f'{ATOM}summary')
        items.append({
            'title': (entry.findtext(f'{ATOM}title') or '').strip(),
            'url': (link.get('href') if link is not None else '') or '',
            'published': parse_date(
                entry.findtext(f'{ATOM}published') or entry.findtext(f'{ATOM}updated') or ''),
            'summary': clean_html(
                (description.text if description is not None else '')
                or (summary.text if summary is not None else ''))[:1200],
        })
    return items


def parse_rss(xml: str, feed: dict) -> list[dict]:
    root = ET.fromstring(xml)
    items = []
    for item in root.findall('channel/item'):
        items.append({
            'title': (item.findtext('title') or '').strip(),
            'url': (item.findtext('link') or '').strip(),
            'published': parse_date(item.findtext('pubDate') or ''),
            'summary': clean_html(item.findtext('description') or '')[:1200],
        })
    return items


def parse_hn(payload: str, feed: dict) -> list[dict]:
    try:
        hits = json.loads(payload).get('hits', [])
    except json.JSONDecodeError:
        log('HN: неразбираемый ответ')
        return []

    items = []
    for hit in hits:
        points = hit.get('points') or 0
        if points < HN_MIN_POINTS:
            continue
        discussion = f'https://news.ycombinator.com/item?id={hit.get("objectID")}'
        items.append({
            'title': (hit.get('title') or '').strip(),
            'url': hit.get('url') or discussion,
            'published': parse_date(hit.get('created_at') or ''),
            'summary': f'{points} очков, {hit.get("num_comments") or 0} комментариев. '
                       f'Обсуждение: {discussion}',
        })
    return items


def collect(feed: dict) -> list[dict]:
    payload = fetch(feed['url'])
    if not payload:
        return []

    try:
        if feed['id'] == 'hn':
            items = parse_hn(payload, feed)
        elif payload.lstrip().startswith('{'):
            items = parse_hn(payload, feed)
        elif '<rss' in payload[:200]:
            items = parse_rss(payload, feed)
        else:
            items = parse_atom(payload, feed)
    except ET.ParseError as error:
        log(f'{feed["id"]}: фид не разобрался — {error}')
        return []

    for item in items:
        item['source'] = feed['id']
        item['source_title'] = feed.get('title', feed['id'])
        item['kind'] = feed.get('kind', 'article')
        item['filter'] = feed.get('filter', 'keywords')
    return [item for item in items if item['title'] and item['url']]


# ---------------------------------------------------------------- отбор


def load_seen() -> dict:
    if not SEEN.exists():
        return {}
    try:
        return json.loads(SEEN.read_text())
    except json.JSONDecodeError:
        log('память о виденном побилась, начинаю с чистого листа')
        return {}


def save_seen(seen: dict) -> None:
    edge = (datetime.now(timezone.utc) - timedelta(days=SEEN_TTL_DAYS)).strftime('%Y-%m-%d')
    fresh = {url: day for url, day in seen.items() if day >= edge}
    DATA.mkdir(parents=True, exist_ok=True)
    SEEN.write_text(json.dumps(fresh, ensure_ascii=False, indent=1))


def matches(text: str, pattern: re.Pattern) -> bool:
    return pattern.search(text) is not None


def keyword_pattern(keywords: list[str]) -> re.Pattern:
    """Ключевые слова — по границам слова, а не подстрокой.

    Подстрокой `ai` находится в «pair», «again» и «email», и лента наполняется
    заметками про очки и почту. Один прогон это уже показал.
    """
    words = sorted((word.strip().lower() for word in keywords if word.strip()), key=len, reverse=True)
    if not words:
        return re.compile(r'(?!)')
    return re.compile(r'(?<![a-z0-9])(?:' + '|'.join(re.escape(w) for w in words) + r')(?![a-z0-9])')


def select(items: list[dict], keywords: list[str], seen: dict, limit: int) -> list[dict]:
    """Свежее, не виденное, по теме — и поровну от источников."""
    edge = (datetime.now(timezone.utc) - timedelta(days=FRESH_DAYS)).strftime('%Y-%m-%d')
    pattern = keyword_pattern(keywords)

    fresh = []
    for item in items:
        if item['url'] in seen:
            continue
        if item['published'] and item['published'] < edge:
            continue
        # Шортсы мимо: сорок секунд под вертикальное видео — не тот материал,
        # из которого выходит угол, а квоту канала они забирают целиком.
        if '/shorts/' in item['url']:
            continue
        if item['filter'] == 'keywords' and not matches(
                f'{item["title"]} {item["summary"]}'.lower(), pattern):
            continue
        fresh.append(item)

    fresh.sort(key=lambda item: item['published'], reverse=True)

    # По кругу: сначала по одной записи от каждого источника, потом по второй.
    # Иначе плодовитый TechCrunch занимает всю ленту, а Hacker News не получает
    # ни одного места — при сортировке по дате все свежие записи равны.
    by_source: dict[str, list[dict]] = {}
    for item in fresh:
        by_source.setdefault(item['source'], []).append(item)

    chosen = []
    for round_index in range(MAX_PER_FEED):
        for queue in by_source.values():
            if len(queue) > round_index:
                chosen.append(queue[round_index])
                if len(chosen) >= limit:
                    return chosen
    return chosen


# ---------------------------------------------------------------- разбор


def analyze(item: dict, author: dict, timeout: int = 600) -> dict | None:
    """Карточка через `claude -p`. Агенту разрешён только WebFetch — файлы пишем сами."""
    prompt = render(
        (HERE / 'prompt.md').read_text(),
        author_name=author['name'],
        author_bio=author['bio'],
        source_title=item['source_title'],
        kind=item['kind'],
        title=item['title'],
        url=item['url'],
        published=item['published'] or 'неизвестно',
        summary=item['summary'] or 'ничего, кроме заголовка',
    )
    try:
        res = subprocess.run(
            # Свой файл настроек обязателен: глобальный defaultMode=bypassPermissions
            # из-под root CLI не принимает и падает, не начав работу.
            ['claude', '-p', '--output-format', 'text',
             '--settings', str(HERE / 'agent-settings.json')],
            input=prompt, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        log(f'разбор: таймаут на «{item["title"][:60]}»')
        return None
    if res.returncode != 0:
        log(f'разбор: claude вернул {res.returncode}: {res.stderr.strip()[:200]}')
        return None

    raw = res.stdout.strip()
    # Модель иногда всё-таки заворачивает JSON в ```json — снимаем обёртку.
    fence = re.search(r'```(?:json)?\s*(.+?)```', raw, re.S)
    if fence:
        raw = fence.group(1).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        log(f'разбор: не JSON на «{item["title"][:60]}»: {raw[:200]}')
        return None


def write_card(item: dict, verdict: dict, today: str) -> Path:
    angles = [a for a in verdict.get('angles') or [] if isinstance(a, dict)]

    lines = [verdict.get('summary', '').strip(), '']
    why = (verdict.get('why') or '').strip()
    if why:
        lines += ['## Почему автору', '', why, '']
    if angles:
        lines += ['## Углы', '']
        for angle in angles:
            platform = (angle.get('platform') or '').strip()
            text = (angle.get('angle') or '').strip()
            lines.append(f'- **{platform or "—"}** — {text}')
        lines.append('')

    frontmatter = dump_frontmatter({
        'source': item['source'],
        'kind': item['kind'],
        'title': item['title'],
        'url': item['url'],
        'published': item['published'] or today,
        'found': today,
        'status': 'new',
    })

    TRENDS.mkdir(parents=True, exist_ok=True)
    path = TRENDS / f'{today}-{slugify(item["title"])}.md'
    suffix = 2
    while path.exists():
        path = TRENDS / f'{today}-{slugify(item["title"])}-{suffix}.md'
        suffix += 1

    path.write_text(f'---\n{frontmatter}---\n\n' + '\n'.join(lines).strip() + '\n')
    return path


def commit(paths: list[Path], today: str) -> None:
    rel = [str(path.relative_to(ROOT)) for path in paths]
    try:
        subprocess.run(['git', '-C', str(ROOT), 'add', '--', *rel], check=True,
                       capture_output=True, text=True)
        subprocess.run(['git', '-C', str(ROOT), 'commit', '--only',
                        '-m', f'Тренды за {today}: карточек {len(rel)}', '--', *rel],
                       check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as error:
        log(f'коммит не прошёл: {error.stderr.strip()[:300]}')


# ---------------------------------------------------------------- прогон


def main() -> int:
    parser = argparse.ArgumentParser(description='Сборщик трендов для контент-плана')
    parser.add_argument('--dry-run', action='store_true',
                        help='показать отобранное, ничего не записывая')
    parser.add_argument('--limit', type=int, help='потолок карточек за прогон')
    parser.add_argument('--no-notify', action='store_true', help='не слать уведомление')
    args = parser.parse_args()

    author = load_author(ROOT)
    config = read_sources()
    limit = args.limit or config.get('limit_per_run') or 6
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')

    items = []
    for feed in config['feeds']:
        found = collect(feed)
        log(f'{feed["id"]}: {len(found)} записей')
        items += found

    seen = load_seen()
    chosen = select(items, config.get('keywords') or [], seen, limit)
    log(f'отобрано: {len(chosen)} из {len(items)}')

    if args.dry_run:
        for item in chosen:
            print(f'  [{item["source"]}] {item["published"]} {item["title"]}\n    {item["url"]}')
        return 0

    written, skipped = [], 0
    for item in chosen:
        verdict = analyze(item, author)
        # Не разобралось — url в память не кладём: пусть попробует завтра.
        if verdict is None:
            continue
        seen[item['url']] = today
        if verdict.get('skip'):
            skipped += 1
            log(f'мимо: {item["title"][:60]} — {verdict.get("reason", "")[:80]}')
            continue
        path = write_card(item, verdict, today)
        written.append(path)
        log(f'карточка: {path.name}')

    save_seen(seen)

    if written:
        commit(written, today)
        if not args.no_notify:
            names = '\n'.join(f'• {path.stem[11:].replace("-", " ")}' for path in written[:6])
            notify(f'Тренды за сутки: {len(written)} карточек\n\n{names}\n\n{STUDIO}')
    log(f'итог: карточек {len(written)}, мимо {skipped}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
