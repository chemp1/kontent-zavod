#!/usr/bin/env python3
"""Идеи из собственных звонков автора.

На входе - расшифровки встреч в JSONL: одна строка = один звонок, формат в README.
Скрипт берёт те, где говорил автор, **вырезает только его реплики** и просит
агента найти в них мысли, из которых может вырасти пост. Кандидаты ложатся
в `content/plan/candidates/`, автор принимает или отклоняет их в студии.

Главное правило, ради которого всё устроено именно так:

    из звонка наружу выходит только прямая речь автора.

Чужие реплики, имена собеседников и подробности их дел остаются в `.data/`
и в git не попадают. На это работают три слоя: `extract_speech()` берёт только
реплики автора, промпт запрещает упоминать собеседников, а `redact()` выкидывает
цитату, если в ней всё-таки всплыло имя участника того звонка.

Откуда берётся JSONL - дело приватной обвязки (`DUMP_COMMAND` в `.env.example`):
сам скрипт ни в какую базу не ходит. Кто автор - из `voice/author.json`.

Разовый прогон: `python3 tools/voice-mine/check.py --days 7 --dry-run`.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _common_dir() -> Path:
    """Где лежит `common.py` мастерской: `tools/trend-watch/` или `tools/tools/trend-watch/` выше по дереву."""
    bases = [Path(os.environ['WORKSHOP_ROOT']).expanduser()] if os.environ.get('WORKSHOP_ROOT') else []
    bases += list(HERE.parents)
    for base in bases:
        for rel in ('tools/trend-watch', 'tools/tools/trend-watch'):
            if (base / rel / 'common.py').exists():
                return base / rel
    raise SystemExit('не нашёл tools/trend-watch/common.py: инструмент запускается из клона репозитория')


sys.path.insert(0, str(_common_dir()))
from common import (dump_frontmatter, find_root, load_author, load_dotenv, log,  # noqa: E402
                    notify, render)

load_dotenv(HERE / '.env')

ROOT = find_root()
CANDIDATES = ROOT / 'content' / 'plan' / 'candidates'
DATA = ROOT / '.data' / 'tools/voice-mine'
STATE = DATA / 'state.json'
#: Куда приватная обвязка складывает расшифровки. Переопределяется `--from-jsonl`.
TRANSCRIPTS = DATA / 'transcripts.jsonl'

#: Куда ведёт ссылка в уведомлении. По умолчанию - локальная студия.
STUDIO = os.environ.get('STUDIO_URL', 'http://127.0.0.1:5180/plan/candidates')

# Потолок текста на один звонок. Час разговора - это примерно 40 тысяч знаков
# реплик одного человека; больше в промпт класть незачем.
MAX_CHARS = 60000
# Ниже этого объёма речь не разбираем: пара фраз «да, согласен» мыслей не даёт.
MIN_CHARS = 1500
# Сколько звонков берём за прогон.
MAX_CALLS = 8

TRANSLIT = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e', 'ж': 'zh',
    'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o',
    'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'h', 'ц': 'c',
    'ч': 'ch', 'ш': 'sh', 'щ': 'sch', 'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e',
    'ю': 'yu', 'я': 'ya',
}


def slugify(title: str) -> str:
    base = ''.join(TRANSLIT.get(ch, ch) for ch in title.lower())
    base = re.sub(r'[^a-z0-9]+', '-', base).strip('-')[:60].strip('-')
    return base or 'ideya'


# ---------------------------------------------------------------- вход


def read_transcripts(path: Path) -> list[dict]:
    """Звонки из JSONL. Битая строка - запись в лог и дальше, а не падение."""
    if not path.exists():
        raise SystemExit(f'нет файла расшифровок: {path} (формат и откуда брать - в README)')
    calls = []
    for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        if not line.strip():
            continue
        try:
            call = json.loads(line)
        except json.JSONDecodeError:
            log(f'{path.name}: строка {number} не JSON, пропускаю')
            continue
        if isinstance(call, dict) and isinstance(call.get('sentences'), list):
            calls.append(call)
        else:
            log(f'{path.name}: строка {number} без списка `sentences`, пропускаю')
    return calls


def sentences(call: dict) -> list[dict]:
    """Реплики в порядке произнесения.

    Если у реплик есть `index`, сортируем числом: нотетейкеры отдают его строкой,
    и при сортировке строк «10» встаёт между «1» и «2».
    """
    rows = [s for s in call['sentences'] if isinstance(s, dict)]
    if rows and all(str(s.get('index', '')).lstrip('-').isdigit() for s in rows):
        rows.sort(key=lambda s: int(s['index']))
    return rows


def extract_speech(call: dict, me: str) -> str:
    """Слой 1: из звонка берутся только реплики автора.

    Совпадение по имени точное, не регуляркой и не по подстроке: в расшифровках
    встречаются тёзки, и поиск по одному имени приведёт их вместе с автором.
    """
    return ' '.join((s.get('text') or '').strip() for s in sentences(call)
                    if s.get('speaker') == me and (s.get('text') or '').strip())


def interlocutors(call: dict, me: str) -> list[str]:
    """Кто ещё говорил. Нужно только `redact()`; наружу список не выходит."""
    return sorted({s['speaker'] for s in sentences(call)
                   if s.get('speaker') and s['speaker'] != me})


def call_id(call: dict, day: str) -> str:
    """Опознание звонка для памяти о разобранном. Без id - хэш даты и названия."""
    given = call.get('transcript_id')
    if given:
        return str(given)
    return hashlib.sha1(f'{day}|{call.get("title") or ""}'.encode('utf-8')).hexdigest()[:12]


def calls(path: Path, days: int, limit: int, me: str) -> list[dict]:
    """Звонки за период, где автор говорил, свежие сверху. Речь - только его."""
    edge = (datetime.now(timezone.utc) - timedelta(days=days)).strftime('%Y-%m-%d')
    found = []
    for call in read_transcripts(path):
        day = str(call.get('day') or '')[:10]
        if day < edge:
            continue
        speech = extract_speech(call, me)
        if not speech:
            continue
        found.append({
            'transcript_id': call_id(call, day),
            'day': day,
            'title': str(call.get('title') or ''),
            'speech': speech,
            'others': interlocutors(call, me),
        })
    found.sort(key=lambda call: call['day'], reverse=True)
    return found[:limit]


# ---------------------------------------------------------------- приватность


def name_tokens(others: list[str] | None) -> list[str]:
    """Имена собеседников по словам - для проверки цитат.

    Короткие куски отбрасываем: «Ким» ещё различает, а «Ян» вырежет пол-словаря.
    """
    tokens = set()
    for name in others or []:
        for part in re.split(r'[^\w]+', name or ''):
            if len(part) >= 4:
                tokens.add(part.lower())
    return sorted(tokens)


def redact(quotes: list[str], tokens: list[str]) -> tuple[list[str], int]:
    """Слой 3: цитата с именем участника звонка не выходит наружу.

    Промпт это запрещает, но запрет в промпте - не механизм. Здесь механизм.
    """
    kept, dropped = [], 0
    for quote in quotes:
        low = quote.lower()
        if any(re.search(rf'(?<![а-яa-z]){re.escape(t)}', low) for t in tokens):
            dropped += 1
            continue
        kept.append(quote.strip())
    return kept, dropped


# ---------------------------------------------------------------- разбор


def mine(call: dict, author: dict, timeout: int = 900) -> list[dict]:
    """Кандидаты из одного звонка через `claude -p`. Инструменты агенту не нужны."""
    speech = call['speech'].strip()
    if len(speech) > MAX_CHARS:
        speech = speech[:MAX_CHARS] + ' …'

    # Слой 2 - сам промпт: он запрещает упоминать собеседников и их дела.
    prompt = render(
        (HERE / 'prompt.md').read_text(encoding='utf-8'),
        author_name=author['name'],
        author_bio=author['bio'],
        date=call['day'],
        speech=speech,
    )
    try:
        res = subprocess.run(
            # Свой файл настроек обязателен: глобальный defaultMode=bypassPermissions
            # из-под root CLI не принимает и падает, не начав работу.
            ['claude', '-p', '--output-format', 'text',
             '--settings', str(HERE / 'agent-settings.json')],
            input=prompt, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        log(f'разбор: таймаут на звонке {call["day"]}')
        return []
    if res.returncode != 0:
        log(f'разбор: claude вернул {res.returncode}: {res.stderr.strip()[:200]}')
        return []

    raw = res.stdout.strip()
    fence = re.search(r'```(?:json)?\s*(.+?)```', raw, re.S)
    if fence:
        raw = fence.group(1).strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        log(f'разбор: не JSON на звонке {call["day"]}: {raw[:200]}')
        return []
    return [c for c in parsed.get('candidates') or [] if isinstance(c, dict)]


def save_raw(call: dict) -> None:
    """Прямая речь - в `.data/`, мимо git: это сырьё, и его место не в истории репо."""
    DATA.mkdir(parents=True, exist_ok=True)
    path = DATA / f'{call["day"]}-{call["transcript_id"]}.md'
    path.write_text(f'# {call["title"]}\n\n{call["speech"]}\n', encoding='utf-8')


def write_candidate(call: dict, candidate: dict, quotes: list[str], today: str) -> Path:
    title = (candidate.get('title') or 'Без заголовка').strip()
    frontmatter = dump_frontmatter({
        'from': 'call',
        'date': call['day'],
        'found': today,
        'title': title,
        'platform': (candidate.get('platform') or '').strip(),
        'status': 'pending',
    })

    body = [(candidate.get('thesis') or '').strip(), '', '## Прямая речь', '']
    body += [f'> {quote}' + '\n' for quote in quotes]

    CANDIDATES.mkdir(parents=True, exist_ok=True)
    path = CANDIDATES / f'{call["day"]}-{slugify(title)}.md'
    suffix = 2
    while path.exists():
        path = CANDIDATES / f'{call["day"]}-{slugify(title)}-{suffix}.md'
        suffix += 1

    path.write_text(f'---\n{frontmatter}---\n\n' + '\n'.join(body).strip() + '\n', encoding='utf-8')
    return path


def commit(paths: list[Path], today: str) -> None:
    rel = [str(path.relative_to(ROOT)) for path in paths]
    try:
        subprocess.run(['git', '-C', str(ROOT), 'add', '--', *rel],
                       check=True, capture_output=True, text=True)
        subprocess.run(['git', '-C', str(ROOT), 'commit', '--only',
                        '-m', f'Кандидаты из звонков за {today}: {len(rel)}', '--', *rel],
                       check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as error:
        log(f'коммит не прошёл: {error.stderr.strip()[:300]}')


# ---------------------------------------------------------------- прогон


def main() -> int:
    parser = argparse.ArgumentParser(description='Идеи из своих звонков')
    parser.add_argument('--from-jsonl', type=Path, default=TRANSCRIPTS,
                        help=f'файл расшифровок (по умолчанию {TRANSCRIPTS.relative_to(ROOT)})')
    parser.add_argument('--me', help='как автор подписан в расшифровках '
                                     '(по умолчанию - имя из карточки автора)')
    parser.add_argument('--days', type=int, default=7, help='за сколько суток смотреть')
    parser.add_argument('--limit', type=int, default=MAX_CALLS, help='сколько звонков за прогон')
    parser.add_argument('--dry-run', action='store_true',
                        help='показать звонки и объём речи автора, ничего не разбирая и не записывая')
    parser.add_argument('--no-notify', action='store_true', help='не слать уведомление')
    args = parser.parse_args()

    author = load_author(ROOT)
    me = (args.me or author['name']).strip()
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    state = json.loads(STATE.read_text(encoding='utf-8')) if STATE.exists() else {'done': []}
    done = set(state.get('done') or [])

    found = calls(args.from_jsonl, args.days, args.limit * 3, me)
    fresh = [call for call in found
             if call['transcript_id'] not in done and len(call['speech']) >= MIN_CHARS]
    fresh = fresh[:args.limit]
    log(f'звонков за {args.days} дней с речью «{me}»: {len(found)}, к разбору: {len(fresh)}')
    if not found:
        log('подсказка: спикер сверяется точно, как он подписан в расшифровке; см. --me')

    if args.dry_run:
        for call in found:
            mark = '' if call in fresh else ('  (уже разобран)' if call['transcript_id'] in done
                                            else '  (мало речи)')
            print(f'  {call["day"]} {len(call["speech"]):>6} знаков автора, '
                  f'собеседников {len(call["others"])} - {call["title"][:60]}{mark}')
        return 0

    written, dropped_total = [], 0
    for call in fresh:
        save_raw(call)
        tokens = name_tokens(call['others'])
        for candidate in mine(call, author):
            quotes, dropped = redact(
                [q for q in candidate.get('quotes') or [] if isinstance(q, str)], tokens)
            dropped_total += dropped
            if not quotes:
                log(f'кандидат «{candidate.get("title", "")[:40]}» снят: цитат не осталось')
                continue
            written.append(write_candidate(call, candidate, quotes, today))
        done.add(call['transcript_id'])

    DATA.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps({'done': sorted(done)[-500:], 'last_run': today},
                                ensure_ascii=False, indent=1), encoding='utf-8')

    if written:
        commit(written, today)
        if not args.no_notify:
            names = '\n'.join(f'• {path.stem[11:].replace("-", " ")}' for path in written[:8])
            notify(f'Из звонков набралось идей: {len(written)}\n\n{names}\n\n{STUDIO}')
    log(f'итог: кандидатов {len(written)}, цитат вырезано {dropped_total}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
