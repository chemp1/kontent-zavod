#!/usr/bin/env python3
"""Проверка снапшота открытого репозитория на утечки: стоп-лист по содержимому,
именам файлов и бинарникам. Только stdlib.

    python3 check.py <каталог> [--stoplist FILE ...] [--staged]

Стоп-лист - по регэкспу на строку (без учёта регистра). Строки с `#` - комментарии,
`allow: <regex>` - исключение (совпадение, которое целиком покрывается allow, не считается).
`--staged` проверяет только файлы из `git diff --cached --name-only` (для pre-commit).

Код возврата: 0 - чисто, 2 - есть находки, 3 - ошибка аргументов.
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

TEXT_EXT = {".md", ".py", ".json", ".ts", ".tsx", ".js", ".mjs", ".cjs", ".yaml", ".yml", ".sh",
            ".txt", ".css", ".html", ".toml", ".cfg", ".ini", ".env", ".example", ".jsonl", ".svg", ".gitignore"}
BINARY_ALLOW_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".woff", ".woff2", ".pdf"}
SKIP_DIRS = {".git", "node_modules", ".next", "__pycache__", ".venv", "venv", ".data"}


def load_stoplist(paths):
    pats, allows = [], []
    for p in paths:
        for raw in Path(p).read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("allow:"):
                allows.append(re.compile(line[len("allow:"):].strip(), re.I))
            else:
                pats.append(re.compile(line, re.I))
    return pats, allows


def allowed(match_text, allows):
    return any(a.fullmatch(match_text) for a in allows)


def scan_text(rel, text, pats, allows, out):
    for i, line in enumerate(text.splitlines(), 1):
        for rx in pats:
            for m in rx.finditer(line):
                if not allowed(m.group(0), allows):
                    out.append((rel, i, m.group(0), rx.pattern))


def scan(root, pats, allows, files=None, binary_allow=None):
    """Возвращает список находок (путь, строка, совпадение, паттерн). Строка 0 - имя файла."""
    root = Path(root)
    binary_allow = binary_allow or set()
    out = []
    if files is None:
        files = [p for p in root.rglob("*") if p.is_file()
                 and not any(part in SKIP_DIRS for part in p.relative_to(root).parts)]
    else:
        files = [root / f for f in files]
    for p in files:
        if not p.exists():
            continue
        rel = str(p.relative_to(root))
        # имя пути
        for rx in pats:
            m = rx.search(rel)
            if m and not allowed(m.group(0), allows):
                out.append((rel, 0, m.group(0), rx.pattern))
        suf = p.suffix.lower()
        if "stoplist" in p.name:
            continue  # стоп-лист содержит сами паттерны - по содержимому не проверяем
        if suf in TEXT_EXT or p.name in {"Makefile", "LICENSE"} or suf == "":
            try:
                text = p.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                if rel not in binary_allow and suf not in BINARY_ALLOW_EXT:
                    out.append((rel, 0, "<бинарный файл вне allow>", "binary"))
                continue
            scan_text(rel, text, pats, allows, out)
        elif suf in BINARY_ALLOW_EXT:
            if rel not in binary_allow:
                out.append((rel, 0, "<бинарник: нужен явный allow в manifest>", "binary"))
        else:
            out.append((rel, 0, f"<неизвестное расширение {suf}>", "binary"))
    return out


def staged_files(root):
    r = subprocess.run(["git", "-C", str(root), "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
                       capture_output=True, text=True)
    return [l for l in r.stdout.splitlines() if l.strip()]


def main(argv=None):
    ap = argparse.ArgumentParser(description="Стоп-лист по снапшоту открытого репо.")
    ap.add_argument("root")
    ap.add_argument("--stoplist", action="append", default=[], help="файл стоп-листа (можно несколько)")
    ap.add_argument("--staged", action="store_true", help="только файлы из git index")
    ap.add_argument("--binary-allow", action="append", default=[], help="разрешённые бинарники (относительные пути)")
    ap.add_argument("--binary-allow-file", help="файл со списком разрешённых бинарников, по пути на строку")
    args = ap.parse_args(argv)
    if args.binary_allow_file and Path(args.binary_allow_file).is_file():
        for line in Path(args.binary_allow_file).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                args.binary_allow.append(line)

    root = Path(args.root).resolve()
    stoplists = args.stoplist or [str(Path(__file__).with_name("stoplist.txt"))]
    stoplists = [s for s in stoplists if Path(s).is_file()]
    if not stoplists:
        print("стоп-лист не найден", file=sys.stderr)
        return 3
    pats, allows = load_stoplist(stoplists)
    files = staged_files(root) if args.staged else None
    found = scan(root, pats, allows, files, set(args.binary_allow))
    for rel, line, match, pat in found:
        where = f"{rel}:{line}" if line else rel
        print(f"{where}: {match!r}  [{pat}]")
    print(f"\nнаходок: {len(found)}, стоп-лист: {', '.join(Path(s).name for s in stoplists)}", file=sys.stderr)
    return 2 if found else 0


if __name__ == "__main__":
    sys.exit(main())
