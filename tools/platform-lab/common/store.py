#!/usr/bin/env python3
"""JSONL с чекпоинтами: дописываем, дедуплицируем, продолжаем с места обрыва.

Приём взят из старого замера vc: перед проходом читаем, что уже собрано,
и качаем только недостающее. Сбор идёт десятками минут, обрыв не должен
стоить прогона.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterator


def _workshop_common():
    """`common.py` мастерской: `tools/trend-watch/` или `tools/tools/trend-watch/` выше по дереву.

    Имя `common` здесь занято собственным пакетом tools/platform-lab, поэтому модуль
    грузится по пути, а не через `import common`.
    """
    import importlib.util

    here = Path(__file__).resolve()
    bases = [Path(os.environ["WORKSHOP_ROOT"]).expanduser()] if os.environ.get("WORKSHOP_ROOT") else []
    bases += list(here.parents)
    for base in bases:
        for rel in ("tools/trend-watch", "tools/tools/trend-watch"):
            path = base / rel / "common.py"
            if path.exists():
                spec = importlib.util.spec_from_file_location("workshop_common", path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                return module
    raise SystemExit("не нашёл tools/trend-watch/common.py: инструмент запускается из клона репозитория")


REPO = _workshop_common().find_root()              # корень репозитория
LAB = Path(__file__).resolve().parents[1]          # сама папка tools/platform-lab
DATA = LAB / "data"                                # карточки и признаки, в git
TEXTS = REPO / ".data" / "tools/platform-lab"            # полные чужие тексты, не в git


def read_jsonl(path: Path) -> Iterator[dict]:
    if not path.exists():
        return
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def load_by_id(path: Path, key: str = "id") -> dict:
    """Последняя запись побеждает — пересбор в другой день обновляет карточку."""
    return {r[key]: r for r in read_jsonl(path) if key in r}


def done_ids(path: Path, key: str = "id") -> set:
    return {r[key] for r in read_jsonl(path) if key in r}


def append(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        fh.flush()


def append_many(path: Path, rows: list[dict]) -> int:
    for r in rows:
        append(path, r)
    return len(rows)


def cards_path(platform: str) -> Path:
    return DATA / platform / "cards.jsonl"


def texts_path(platform: str) -> Path:
    return TEXTS / platform / "texts.jsonl"
