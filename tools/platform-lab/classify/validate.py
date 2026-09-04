#!/usr/bin/env python3
"""Проверка разметки: схема, дословность цитат, согласие с признаками.

Разметку делает модель, и верить ей на слово нельзя. Три дешёвые проверки
ловят почти всё: невалидные значения, выдуманные цитаты и суждения,
которые противоречат тому, что посчитано кодом.

    python3 classify/validate.py habr
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.store import TEXTS, read_jsonl, texts_path

ENUMS = {
    "genre": {"кейс", "гайд", "разбор", "мнение", "новость_с_комментарием", "исповедь",
              "подборка", "интервью", "обзор", "туториал", "художественное"},
    "speaker": {"частное_лицо", "лицо_от_компании", "корпоративный_блог", "редакция", "аноним"},
    "lead_hook": {"история", "цифра", "конфликт", "вопрос", "определение",
                  "анонс_итога", "обещание_пользы"},
    "specificity": {"свои_цифры", "чужие_цифры", "примеры_без_цифр", "общие_слова"},
    "promise_kept": {"да", "частично", "нет", "заголовок_ничего_не_обещает"},
    "cta": {"нет", "мягкий", "прямой", "сбор_лидов"},
    "confidence": {"high", "med", "low"},
}


def norm(s: str) -> str:
    """Цитату ищем после нормализации: ё, кавычки и пробелы гуляют."""
    s = (s or "").lower().replace("ё", "е").replace("\xa0", " ")
    s = re.sub(r"[«»\"“”„'’*_]", "", s)
    return re.sub(r"\s+", " ", s).strip()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("platform")
    args = ap.parse_args()

    texts = {r["id"]: norm(" ".join(r.get("paras") or []) + " " + (r.get("title") or ""))
             for r in read_jsonl(texts_path(args.platform))}
    folder = TEXTS / args.platform / "labels"
    rows = [r for p in sorted(folder.glob("batch-*.jsonl")) for r in read_jsonl(p)]

    bad_enum: list[str] = []
    missing_text: list[str] = []
    evidence_miss: list[str] = []
    contradictions: list[str] = []

    for r in rows:
        rid = str(r.get("id"))
        for field, allowed in ENUMS.items():
            val = r.get(field)
            if val is not None and val not in allowed:
                bad_enum.append(f"{rid}: {field}={val}")
        body = texts.get(rid)
        if body is None:
            missing_text.append(rid)
            continue
        ev = norm(r.get("evidence") or "")
        if ev and ev not in body:
            evidence_miss.append(rid)
        if r.get("specificity") == "свои_цифры" and not re.search(r"\d", body):
            contradictions.append(f"{rid}: свои цифры без единой цифры")
        if r.get("genre") == "туториал" and "```" not in body and r.get("own_numbers") == 0:
            pass  # у Дзена и TenChat туториал без кода — норма, не ошибка

    n = len(rows)
    print(f"{args.platform}: строк разметки {n}, статей с текстом {len(texts)}")
    print(f"  невалидных значений: {len(bad_enum)}")
    print(f"  разметка без текста: {len(missing_text)}")
    print(f"  цитата не найдена в тексте: {len(evidence_miss)} "
          f"({100 * len(evidence_miss) / max(1, n):.0f}%)")
    print(f"  противоречий признакам: {len(contradictions)}")
    for label, items in (("значения", bad_enum), ("цитаты", evidence_miss),
                         ("противоречия", contradictions)):
        for x in items[:5]:
            print(f"    {label}: {x}")
    conf = {}
    for r in rows:
        conf[r.get("confidence")] = conf.get(r.get("confidence"), 0) + 1
    print(f"  уверенность: {conf}")


if __name__ == "__main__":
    main()
