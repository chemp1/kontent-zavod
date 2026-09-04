#!/usr/bin/env python3
"""HTTP через curl: так же, как в старом замере vc, только с ретраями и cookie-jar.

Питоновского клиента в репо нет и заводить его незачем: curl уже стоит,
а сетевые грабли у площадок одинаковые — таймаут, редирект на паспорт,
разовый 5xx. Всё это лечится тремя попытками с паузой.
"""

from __future__ import annotations

import json
import random
import subprocess
import time
from pathlib import Path

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.6478.127 Safari/537.36")

# Пауза между запросами. Нижняя граница взята из замера vc: она там ни разу
# не привела к блокировке за 418 статей.
PAUSE_MIN, PAUSE_MAX = 1.0, 2.5

BACKOFF = (3, 10, 30)


def pause(lo: float = PAUSE_MIN, hi: float = PAUSE_MAX) -> None:
    time.sleep(random.uniform(lo, hi))


def get(url: str, *, jar: Path | None = None, headers: dict[str, str] | None = None,
        timeout: int = 45, retries: int = 3, follow: bool = True) -> str | None:
    """Возвращает тело ответа или None, если все попытки провалились."""
    cmd = ["curl", "-sS", "-m", str(timeout), "-H", f"User-Agent: {UA}",
           "-H", "Accept-Language: ru-RU,ru;q=0.9"]
    if follow:
        cmd.append("-L")
    if jar is not None:
        jar.parent.mkdir(parents=True, exist_ok=True)
        cmd += ["-c", str(jar), "-b", str(jar)]
    for k, v in (headers or {}).items():
        cmd += ["-H", f"{k}: {v}"]
    cmd.append(url)

    for attempt in range(retries):
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 15)
        except subprocess.TimeoutExpired:
            res = None
        if res is not None and res.returncode == 0 and res.stdout:
            return res.stdout
        if attempt < retries - 1:
            time.sleep(BACKOFF[min(attempt, len(BACKOFF) - 1)])
    return None


def get_json(url: str, **kw) -> dict | None:
    body = get(url, **kw)
    if not body:
        return None
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return None


def warm_jar(home_url: str, jar: Path) -> None:
    """Дзен без кук редиректит на паспорт. Один заход на главную это чинит."""
    get(home_url, jar=jar, timeout=30)
