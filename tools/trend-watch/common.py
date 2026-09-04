"""Общий код инструментов мастерской: корень репо, автор, лог, уведомления, `.env`
и плоский YAML-фронтматтер.

Лежит в `tools/trend-watch/`, потому что понадобился здесь первым; `tools/voice-mine`,
`tools/threads-lab` и `tools/platform-lab` берут его отсюда через `sys.path`. Ничего личного
внутри нет: имя автора и адреса приходят из `voice/author.json` и окружения.

Использование:

    import sys; sys.path.insert(0, '<путь к tools/trend-watch>')
    from common import find_root, load_author, load_dotenv, log, notify, parse_frontmatter

Стандартная библиотека и ничего больше - так инструменты переносятся копированием.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

#: Что возвращает `load_author()`, если файла автора нет.
DEFAULT_AUTHOR: dict[str, Any] = {
    'name': 'автор',
    'short': '',
    'handle': '',
    'channel': '',
    'channel_url': '',
    'bio': '',
    'platforms': [],
}


def log(msg: str) -> None:
    print(f'[{datetime.now().isoformat(timespec="seconds")}] {msg}', flush=True)


# ---------------------------------------------------------------- корень и окружение


def find_root() -> Path:
    """Корень репозитория: `WORKSHOP_ROOT`, иначе ближайший родитель с `.git`.

    `.git` может быть и каталогом, и файлом (worktree) - проверяем существование.
    """
    override = os.environ.get('WORKSHOP_ROOT')
    if override:
        root = Path(override).expanduser()
        if root.is_dir():
            return root.resolve()
        raise SystemExit(f'WORKSHOP_ROOT указывает на несуществующий каталог: {override}')

    here = Path(__file__).resolve()
    for parent in (here.parent, *here.parents):
        if (parent / '.git').exists():
            return parent
    raise SystemExit(
        'не нашёл корень репозитория: нет `.git` ни в одном родителе '
        f'{here.parent}. Задай переменную WORKSHOP_ROOT или запускай из клона.')


def load_dotenv(path: Path | str) -> dict[str, str]:
    """Прочитать `KEY=value` из файла в `os.environ`, не затирая уже заданное.

    Формат совместим с `set -a; . файл` в shell: `#` - комментарий, `export`
    впереди допустим, значения со пробелами - в кавычках. Возвращает то, что
    реально добавилось.
    """
    path = Path(path)
    added: dict[str, str] = {}
    if not path.exists():
        return added
    for raw in path.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        if line.startswith('export '):
            line = line[len('export '):].lstrip()
        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in '"\'':
            value = value[1:-1]
        else:
            value = re.split(r'\s+#', value, 1)[0].rstrip()
        if key and key not in os.environ:
            os.environ[key] = value
            added[key] = value
    return added


def load_author(root: Path | None = None) -> dict[str, Any]:
    """Карточка автора из `voice/author.json` (или `AUTHOR_FILE`).

    Файла может не быть - тогда автор безымянный: `name` = «автор», `bio` пустой.
    Инструменты обязаны работать и так.
    """
    override = os.environ.get('AUTHOR_FILE')
    path = Path(override).expanduser() if override else (root or find_root()) / 'posts' / 'voice' / 'author.json'

    author: dict[str, Any] = {key: (list(value) if isinstance(value, list) else value)
                              for key, value in DEFAULT_AUTHOR.items()}
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        data = {}
    except (OSError, json.JSONDecodeError) as error:
        log(f'файл автора не прочитался ({path}): {error}')
        data = {}
    if isinstance(data, dict):
        author.update({key: value for key, value in data.items() if value is not None})

    author['name'] = str(author.get('name') or DEFAULT_AUTHOR['name']).strip()
    author['short'] = str(author.get('short') or author['name']).strip()
    author['bio'] = str(author.get('bio') or '').strip()
    if not isinstance(author.get('platforms'), list):
        author['platforms'] = []
    return author


def render(template: str, **values: Any) -> str:
    """Подставить `{имя}` в шаблон за один проход.

    Не `str.format`: в подставляемом тексте (bio, выдержки из фидов, речь) бывают
    фигурные скобки, а в промптах - JSON-примеры. Один проход `re.sub` значит,
    что подставленное значение повторно не разбирается. Незнакомые `{слова}`
    остаются как есть.
    """
    return re.sub(r'\{([A-Za-z_][A-Za-z0-9_]*)\}',
                  lambda match: str(values[match.group(1)]) if match.group(1) in values else match.group(0),
                  template)


# ---------------------------------------------------------------- уведомления


def notify(text: str, timeout: int = 60) -> bool:
    """Отправить короткое сообщение туда, куда указывает `NOTIFY`.

    - `stdout` (по умолчанию) - напечатать;
    - `webhook` - POST JSON `{"text": ...}` на `NOTIFY_URL`;
    - `telegram` - Bot API по `TELEGRAM_BOT_TOKEN` и `TELEGRAM_CHAT_ID`;
    - `command` - запустить `NOTIFY_COMMAND` через shell, текст в stdin.

    Ошибка - строка в лог и `False`, исключений наружу нет: уведомление не
    должно ронять прогон, который уже всё сделал.
    """
    mode = (os.environ.get('NOTIFY') or 'stdout').strip().lower()
    try:
        if mode == 'stdout':
            print(text, flush=True)
            return True
        if mode == 'webhook':
            return _notify_webhook(text, timeout)
        if mode == 'telegram':
            return _notify_telegram(text, timeout)
        if mode == 'command':
            return _notify_command(text, timeout)
        log(f'уведомление: неизвестный NOTIFY={mode!r} (жду stdout, webhook, telegram или command)')
        return False
    except Exception as error:  # noqa: BLE001 - любая ошибка канала = лог, не падение
        log(f'уведомление не ушло ({mode}): {error}')
        return False


def _post(url: str, data: bytes, content_type: str, timeout: int) -> tuple[int, str]:
    request = urllib.request.Request(url, data=data, method='POST',
                                     headers={'Content-Type': content_type,
                                              'User-Agent': 'workshop-notify/1.0'})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read().decode('utf-8', 'replace')
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode('utf-8', 'replace')


def _notify_webhook(text: str, timeout: int) -> bool:
    url = os.environ.get('NOTIFY_URL')
    if not url:
        log('уведомление: NOTIFY=webhook, но NOTIFY_URL пуст')
        return False
    status, body = _post(url, json.dumps({'text': text}, ensure_ascii=False).encode('utf-8'),
                         'application/json', timeout)
    ok = 200 <= status < 300
    log('уведомление отправлено' if ok else f'уведомление не ушло: HTTP {status} {body[:200]}')
    return ok


def _notify_telegram(text: str, timeout: int) -> bool:
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    if not token or not chat_id:
        log('уведомление: NOTIFY=telegram, но TELEGRAM_BOT_TOKEN или TELEGRAM_CHAT_ID пуст')
        return False
    payload = urllib.parse.urlencode({
        'chat_id': chat_id,
        'text': text,
        'disable_web_page_preview': 'true',
    }).encode('utf-8')
    status, body = _post(f'https://api.telegram.org/bot{token}/sendMessage', payload,
                         'application/x-www-form-urlencoded', timeout)
    ok = status == 200 and '"ok":true' in body
    # Тело ответа Telegram токена не содержит, но на всякий случай режем.
    log('уведомление отправлено' if ok else f'уведомление не ушло: HTTP {status} {body[:200]}')
    return ok


def _notify_command(text: str, timeout: int) -> bool:
    command = os.environ.get('NOTIFY_COMMAND')
    if not command:
        log('уведомление: NOTIFY=command, но NOTIFY_COMMAND пуст')
        return False
    try:
        res = subprocess.run(command, shell=True, input=text, capture_output=True,
                             text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        log(f'уведомление не ушло: команда не уложилась в {timeout}s')
        return False
    ok = res.returncode == 0
    if not ok:
        why = (res.stderr.strip() or res.stdout.strip())[:200]
        log(f'уведомление не ушло: команда вернула {res.returncode}: {why}')
    return ok


# ---------------------------------------------------------------- фронтматтер

# Ровно то подмножество YAML, что встречается в `content/`: скаляры, списки
# `- item` и `[a, b]`, вложенные словари и списки словарей (`feeds:`), блочные
# скаляры `|` и `>`. Якоря, теги, многострочные ключи и inline-словари не
# поддерживаются нарочно - их в файлах нет, а PyYAML ради них тащить не хочется.

_KEY = re.compile(r'^([A-Za-z0-9_.\-]+)\s*:(?:\s+(.*))?$')
_BLOCK_MARKERS = ('|', '|-', '|+', '>', '>-', '>+')


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """`(данные, тело)` из markdown с фронтматтером. Без фронтматтера - `({}, text)`."""
    if not text.startswith('---'):
        return {}, text
    lines = text.splitlines(keepends=True)
    if lines[0].strip() != '---':
        return {}, text
    for index in range(1, len(lines)):
        if lines[index].strip() == '---':
            data = parse_yaml(''.join(lines[1:index]))
            return (data if isinstance(data, dict) else {}), ''.join(lines[index + 1:])
    return {}, text


def parse_yaml(source: str) -> Any:
    """Разобрать плоский YAML. Пустой документ - `{}`."""
    lines = _yaml_lines(source)
    start = _skip(lines, 0)
    if start >= len(lines):
        return {}
    value, index = _parse_block(lines, start, lines[start][0])
    index = _skip(lines, index)
    if index < len(lines):
        raise ValueError(f'YAML: не разобрал строку {index + 1}: {lines[index][1]!r}')
    return value


def _yaml_lines(source: str) -> list[tuple[int | None, str]]:
    out: list[tuple[int | None, str]] = []
    for raw in source.splitlines():
        if not raw.strip():
            out.append((None, ''))
        else:
            out.append((len(raw) - len(raw.lstrip(' ')), raw.strip()))
    return out


def _skip(lines: list[tuple[int | None, str]], index: int) -> int:
    while index < len(lines) and (lines[index][0] is None or lines[index][1].startswith('#')):
        index += 1
    return index


def _parse_block(lines, index: int, indent: int):
    text = lines[index][1]
    if text == '-' or text.startswith('- '):
        return _parse_list(lines, index, indent)
    return _parse_map(lines, index, indent)


def _parse_map(lines, index: int, indent: int) -> tuple[dict[str, Any], int]:
    result: dict[str, Any] = {}
    while True:
        index = _skip(lines, index)
        if index >= len(lines) or lines[index][0] != indent:
            return result, index
        text = lines[index][1]
        match = _KEY.match(text)
        if not match:
            raise ValueError(f'YAML: строка {index + 1}: ожидал `ключ: значение`, а там {text!r}')
        key, rest = match.group(1), (match.group(2) or '').strip()
        index += 1
        if rest == '' or rest.startswith('#'):
            nxt = _skip(lines, index)
            if nxt < len(lines) and (lines[nxt][0] > indent or (
                    lines[nxt][0] == indent and lines[nxt][1].startswith('-'))):
                result[key], index = _parse_block(lines, nxt, lines[nxt][0])
            else:
                result[key] = None
        elif rest in _BLOCK_MARKERS:
            result[key], index = _parse_block_scalar(lines, index, indent, rest)
        else:
            result[key] = _parse_scalar(rest)


def _parse_list(lines, index: int, indent: int) -> tuple[list[Any], int]:
    result: list[Any] = []
    while True:
        index = _skip(lines, index)
        if index >= len(lines) or lines[index][0] != indent:
            return result, index
        text = lines[index][1]
        if not (text == '-' or text.startswith('- ')):
            return result, index
        item = text[1:].strip()
        index += 1
        if item == '':
            nxt = _skip(lines, index)
            if nxt < len(lines) and lines[nxt][0] > indent:
                value, index = _parse_block(lines, nxt, lines[nxt][0])
            else:
                value = None
            result.append(value)
        elif item[0] not in '"\'[' and _KEY.match(item):
            # `- id: yc` - словарь, первая пара стоит на строке с дефисом.
            # Подменяем строку на «ключ с отступом после дефиса» и читаем словарь.
            sub_indent = indent + (len(text) - len(item))
            lines[index - 1] = (sub_indent, item)
            value, index = _parse_map(lines, index - 1, sub_indent)
            result.append(value)
        elif item in _BLOCK_MARKERS:
            value, index = _parse_block_scalar(lines, index, indent, item)
            result.append(value)
        else:
            result.append(_parse_scalar(item))


def _parse_block_scalar(lines, index: int, indent: int, marker: str) -> tuple[str, int]:
    chunks: list[str] = []
    block_indent: int | None = None
    while index < len(lines):
        line_indent, text = lines[index]
        if line_indent is None:
            chunks.append('')
            index += 1
            continue
        if line_indent <= indent:
            break
        if block_indent is None:
            block_indent = line_indent
        chunks.append(' ' * (line_indent - block_indent) + text)
        index += 1
    while chunks and chunks[-1] == '':
        chunks.pop()

    if marker[0] == '>':
        paragraphs: list[list[str]] = [[]]
        for chunk in chunks:
            if chunk == '':
                paragraphs.append([])
            else:
                paragraphs[-1].append(chunk)
        value = '\n'.join(' '.join(p) for p in paragraphs)
    else:
        value = '\n'.join(chunks)
    if not marker.endswith('-'):
        value += '\n'
    return value, index


def _parse_scalar(text: str) -> Any:
    text = text.strip()
    if text == '':
        return ''
    if text[0] == '"':
        match = re.match(r'^"((?:[^"\\]|\\.)*)"', text)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return match.group(1)
        return text.strip('"')
    if text[0] == "'":
        match = re.match(r"^'((?:[^']|'')*)'", text)
        return match.group(1).replace("''", "'") if match else text.strip("'")
    if text[0] == '[' and text.endswith(']'):
        inner = text[1:-1].strip()
        return [_parse_scalar(part) for part in _split_inline(inner)] if inner else []

    text = re.split(r'\s+#', text, 1)[0].strip()
    low = text.lower()
    if low in ('null', '~'):
        return None
    if low == 'true':
        return True
    if low == 'false':
        return False
    if re.fullmatch(r'[-+]?\d+', text):
        return int(text)
    if re.fullmatch(r'[-+]?(?:\d+\.\d*|\.\d+)(?:[eE][-+]?\d+)?', text):
        return float(text)
    return text


def _split_inline(inner: str) -> list[str]:
    parts, current, quote = [], [], ''
    for char in inner:
        if quote:
            current.append(char)
            if char == quote:
                quote = ''
        elif char in '"\'':
            quote = char
            current.append(char)
        elif char == ',':
            parts.append(''.join(current).strip())
            current = []
        else:
            current.append(char)
    tail = ''.join(current).strip()
    if tail or parts:
        parts.append(tail)
    return [part for part in parts if part != '']


# Плоский скаляр без кавычек: буквы, цифры, пробелы, точки, дефисы и немного
# пунктуации. Всё, что может быть прочитано как число, дата, булево или
# спецсимвол YAML, уходит в двойные кавычки JSON-стилем - это валидный YAML.
_PLAIN = re.compile(r'^[0-9A-Za-zА-Яа-яЁё_][0-9A-Za-zА-Яа-яЁё_ .,;()/+$€₽«»—\-]*$')
_LOOKS_TYPED = re.compile(r'^(?:[-+]?\d[\d_]*(?:\.\d*)?(?:[eE][-+]?\d+)?|\d{4}-\d{2}-\d{2}.*|'
                          r'true|false|yes|no|on|off|null|~)$', re.I)


def _dump_scalar(value: Any) -> str:
    if value is None:
        return 'null'
    if value is True:
        return 'true'
    if value is False:
        return 'false'
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if (_PLAIN.match(text) and not _LOOKS_TYPED.match(text)
            and text == text.strip() and not text.endswith(':')):
        return text
    return json.dumps(text, ensure_ascii=False)


def dump_frontmatter(data: dict[str, Any]) -> str:
    """Словарь в YAML для фронтматтера. Порядок ключей сохраняется.

    Поддерживает то же подмножество, что и парсер: скаляры, списки скаляров,
    списки словарей и словари на один уровень вглубь.
    """
    return ''.join(_dump_lines(data, 0))


def _dump_lines(data: dict[str, Any], indent: int) -> list[str]:
    pad = ' ' * indent
    lines: list[str] = []
    for key, value in data.items():
        if isinstance(value, dict):
            lines.append(f'{pad}{key}:\n')
            lines += _dump_lines(value, indent + 2)
        elif isinstance(value, list):
            if not value:
                lines.append(f'{pad}{key}: []\n')
                continue
            lines.append(f'{pad}{key}:\n')
            for item in value:
                if isinstance(item, dict):
                    inner = _dump_lines(item, indent + 4)
                    if inner:
                        inner[0] = f'{pad}  - ' + inner[0].lstrip()
                    lines += inner
                else:
                    lines.append(f'{pad}  - {_dump_scalar(item)}\n')
        else:
            lines.append(f'{pad}{key}: {_dump_scalar(value)}\n')
    return lines


if __name__ == '__main__':
    # `python3 common.py файл.md` - показать разобранный фронтматтер, чтобы
    # проверить парсер на живом файле без PyYAML.
    for arg in sys.argv[1:]:
        data, body = parse_frontmatter(Path(arg).read_text(encoding='utf-8'))
        print(json.dumps(data, ensure_ascii=False, indent=1))
        print(f'--- тело: {len(body)} знаков')
