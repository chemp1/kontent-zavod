#!/usr/bin/env python3
"""Прогнать свои черновики через ту же разметку, что и чужие посты.

Смысл не в оценке «хороший или плохой» — модель этого не знает. Смысл в том,
чтобы увидеть, попадают ли наши посты в тот профиль признаков, который в замере
отличал удачные посты от обычных.

    python3 score_own.py --drafts /path/to/drafts    # папка с черновиками автора, *.md
"""

import argparse
from pathlib import Path

from features import extract

# Профиль удачных постов из замера 19.08.2026: доля признака в лучшей четверти
# лент против остальных постов.
TARGET = {
    "ends_with_question": (0.20, 0.13, "+"),
    "first_person": (0.42, 0.29, "+"),
    "has_link": (0.02, 0.07, "-"),
    "has_list": (0.10, 0.12, "."),
    "has_number": (0.54, 0.52, "."),
}


def body(path: Path) -> str:
    text = path.read_text()
    return text.split("---", 1)[1].strip() if "---" in text else text.strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--drafts", type=Path, required=True,
                        help="папка с черновиками автора (*.md, фронтматтер необязателен)")
    args = parser.parse_args()

    rows = []
    for path in sorted(args.drafts.glob("*.md")):
        text = body(path)
        f = extract({"text": text})
        rows.append((path.stem, text, f))
    if not rows:
        raise SystemExit(f"в {args.drafts} нет *.md")

    print(f"{'пост':<28} {'знаков':>6} {'хук':>10} {'?конец':>7} {'я':>3} {'цифр':>5} {'ссыл':>5}")
    for name, text, f in rows:
        print(
            f"{name[:28]:<28} {f['length']:>6} {f['hook_type']:>10} "
            f"{'да' if f['ends_with_question'] else 'нет':>7} "
            f"{'да' if f['first_person'] else 'нет':>3} "
            f"{'да' if f['has_number'] else 'нет':>5} "
            f"{'да' if f['has_link'] else 'нет':>5}"
        )

    n = len(rows)
    print(f"\nдоля признака у нас ({n} постов) против профиля удачных чужих:")
    for key, (top, rest, sign) in TARGET.items():
        ours = sum(1 for _, _, f in rows if f[key]) / n
        mark = {"+": "хотим больше", "-": "хотим меньше", ".": "не влияет"}[sign]
        print(f"  {key:<20} у нас {ours:>5.0%}   удачные {top:>4.0%}   обычные {rest:>4.0%}   {mark}")

    hooks = {}
    for _, _, f in rows:
        hooks[f["hook_type"]] = hooks.get(f["hook_type"], 0) + 1
    print(f"\nзачины у нас: {hooks}")
    print("в замере: вопрос 24% у удачных против 18% у обычных, "
          "заявление 32% против 44%")
    print(f"\nмедианная длина первой строки у нас: "
          f"{sorted(f['hook_len'] for _, _, f in rows)[n // 2]}  "
          f"(у удачных чужих 83, у обычных 68)")


if __name__ == "__main__":
    main()
