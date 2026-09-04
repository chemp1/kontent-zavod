#!/usr/bin/env python3
"""Воспроизводимый экспорт открытого репозитория из личной мастерской. Только stdlib.

    python3 export.py [--dry-run] [--check] [--commit "сообщение"] [--manifest manifest.json]

Как работает:
  1. По `manifest.json` собирает файлы источника (allowlist с исключениями; записи с
     `"tracked": true` берут только то, что отслеживает git - неотслеживаемое не утечёт).
  2. Копирует во временный stage, переписывая пути (`src` → `dst` для всех записей манифеста)
     и применяя `replacements.json` - ТОЛЬКО к файлам источника.
  3. Кладёт поверх `overlay/` как есть (README, шаблоны, выдуманный автор).
  4. Прогоняет `check.py` по стоп-листу. Есть находки - stage удаляется, dest не тронут.
  5. Синхронизирует stage в `dest`, сохраняя там `.git/` и `node_modules/`.

Файлы manifest.json, replacements.json и stoplist.txt - приватные: они описывают раскладку
мастерской и содержат имена. В открытый репо уходят только *.example.

Коды возврата: 0 - ок, 2 - стоп-лист, 3 - ошибка манифеста/аргументов.
"""

import argparse
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import check  # noqa: E402

PRIVATE_FILES = {"manifest.json", "replacements.json", "stoplist.txt"}


def log(msg):
    print(msg, file=sys.stderr)


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def excluded(rel, patterns):
    return any(fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(rel, pat.rstrip("/") + "/*") for pat in patterns)


def git_tracked(root, sub):
    r = subprocess.run(["git", "-C", str(root), "ls-files", "--", sub], capture_output=True, text=True, check=True)
    return [l for l in r.stdout.splitlines() if l.strip()]


def collect(root, entries):
    """→ список (абсолютный источник, относительный путь в снапшоте)."""
    out = []
    for e in entries:
        src = e["src"].rstrip("/")
        dst = e.get("dst", src).rstrip("/")
        excl = e.get("exclude", [])
        abs_src = root / src
        if e.get("tracked"):
            files = [Path(f) for f in git_tracked(root, src)]
            if not files:
                raise SystemExit(f"манифест: `{src}` не содержит отслеживаемых файлов")
            for f in files:
                rel_in = str(f.relative_to(src)) if src else str(f)
                if excluded(rel_in, excl):
                    continue
                out.append((root / f, str(Path(dst) / rel_in)))
            continue
        if not abs_src.exists():
            raise SystemExit(f"манифест устарел: нет `{src}`")
        if abs_src.is_file():
            out.append((abs_src, dst if e.get("dst") else src))
            continue
        for p in sorted(abs_src.rglob("*")):
            if not p.is_file():
                continue
            rel_in = str(p.relative_to(abs_src))
            if any(part in check.SKIP_DIRS for part in p.relative_to(root).parts):
                continue
            if excluded(rel_in, excl):
                continue
            out.append((p, str(Path(dst) / rel_in)))
    return out


def path_rewrites(entries, extra=()):
    """Пары (src, dst) для переписывания путей внутри текстов, длинные сначала.

    `extra` - явные пары из манифеста (`path_rewrites`): для каталогов, которые в снапшот
    не копируются, но на которые ссылаются тексты (личные данные, заменяемые overlay).
    """
    pairs = [tuple(p) for p in extra]
    for e in entries:
        src, dst = e["src"].rstrip("/"), e.get("dst", e["src"]).rstrip("/")
        if src != dst:
            pairs.append((src, dst))
    pairs.sort(key=lambda p: -len(p[0]))
    return pairs


def compile_replacements(rules):
    out = []
    for r in rules:
        if "regex" in r:
            out.append((re.compile(r["regex"]), r["to"], r.get("regex")))
        else:
            out.append((re.compile(re.escape(r["from"])), r["to"], r["from"]))
    return out


def rewrite(text, pairs, repls, counters):
    for src, dst in pairs:
        n = text.count(src)
        if n:
            counters[f"path {src} → {dst}"] += n
            text = text.replace(src, dst)
    for rx, to, label in repls:
        text, n = rx.subn(to, text)
        counters[f"repl {label}"] += n
    return text


def is_text(path, text_ext):
    return path.suffix.lower() in text_ext or path.suffix == ""


def copy_source(files, stage, pairs, repls, text_ext, counters):
    for src, rel in files:
        dst = stage / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if is_text(src, text_ext):
            try:
                text = src.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                shutil.copy2(src, dst)
                continue
            dst.write_text(rewrite(text, pairs, repls, counters), encoding="utf-8")
            shutil.copymode(src, dst)
        else:
            shutil.copy2(src, dst)


def copy_overlay(overlay, stage):
    n = 0
    for p in overlay.rglob("*"):
        if p.is_file() and not any(part in check.SKIP_DIRS for part in p.relative_to(overlay).parts):
            rel = p.relative_to(overlay)
            dst = stage / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dst)
            n += 1
    return n


def clear(directory, keep):
    """Удаляет содержимое каталога, оставляя `keep` (по имени, на любой глубине)."""
    for child in directory.iterdir():
        if child.name in keep:
            continue
        if child.is_dir() and not child.is_symlink():
            clear(child, keep)
            try:
                child.rmdir()
            except OSError:
                pass  # внутри остался keep-каталог
        else:
            child.unlink()


def sync(stage, dest, keep=(".git", "node_modules", ".next")):
    dest.mkdir(parents=True, exist_ok=True)
    clear(dest, keep)
    shutil.copytree(stage, dest, symlinks=True, dirs_exist_ok=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Экспорт открытого репо из мастерской.")
    ap.add_argument("--manifest", default=str(HERE / "manifest.json"))
    ap.add_argument("--dry-run", action="store_true", help="только план и счётчики, dest не трогать")
    ap.add_argument("--check", action="store_true", help="только стоп-лист по существующему dest")
    ap.add_argument("--commit", help="после синхронизации сделать git commit в dest с этим сообщением")
    args = ap.parse_args(argv)

    man = load_json(args.manifest)
    root = Path(man.get("root") or HERE.parent).resolve()
    dest = Path(man["dest"]).resolve()
    if dest == root or root in dest.parents:
        raise SystemExit(f"dest {dest} внутри мастерской {root} - так нельзя")
    text_ext = set(man.get("text_ext", sorted(check.TEXT_EXT)))
    stoplist = HERE / "stoplist.txt"
    binary_allow = set(man.get("binary_allow", []))

    if args.check:
        pats, allows = check.load_stoplist([stoplist])
        found = check.scan(dest, pats, allows, binary_allow=binary_allow)
        for rel, line, match, pat in found:
            print(f"{rel}:{line}: {match!r}  [{pat}]")
        log(f"находок: {len(found)}")
        return 2 if found else 0

    files = collect(root, man["entries"])
    pairs = path_rewrites(man["entries"], man.get("path_rewrites", []))
    repls = compile_replacements(load_json(HERE / "replacements.json")) if (HERE / "replacements.json").exists() else []
    from collections import Counter
    counters = Counter()

    stage = Path(tempfile.mkdtemp(prefix="kz-stage-"))
    try:
        copy_source(files, stage, pairs, repls, text_ext, counters)
        overlay_n = copy_overlay(root / man.get("overlay", "export/overlay"), stage)

        # приватные файлы экспорта не должны оказаться в снапшоте
        for p in stage.rglob("*"):
            if p.is_file() and p.name in PRIVATE_FILES and "export" in p.parts:
                raise SystemExit(f"в снапшот попал приватный файл экспорта: {p.relative_to(stage)}")

        pats, allows = check.load_stoplist([stoplist])
        found = check.scan(stage, pats, allows, binary_allow=binary_allow)

        log(f"источник: {len(files)} файлов, overlay: {overlay_n}, замен путей и правил: "
            f"{sum(v for k, v in counters.items())}")
        unused = [r[2] for r in repls if counters[f"repl {r[2]}"] == 0]
        if unused:
            log("правила без срабатываний (сигнал почистить источник или список): " + "; ".join(unused))
        for k, v in sorted(counters.items()):
            log(f"  {v:5d}  {k}")

        if found:
            for rel, line, match, pat in found:
                where = f"{rel}:{line}" if line else rel
                print(f"{where}: {match!r}  [{pat}]")
            log(f"\nСТОП: {len(found)} находок по стоп-листу. dest не тронут.")
            return 2
        log("стоп-лист: чисто")

        if args.dry_run:
            log(f"dry-run: dest {dest} не тронут")
            return 0

        sync(stage, dest)
        log(f"синхронизировано в {dest}")
        st = subprocess.run(["git", "-C", str(dest), "status", "--short"], capture_output=True, text=True)
        if st.returncode == 0:
            lines = st.stdout.splitlines()
            log(f"git status: {len(lines)} изменений" + ("" if len(lines) < 12 else " (первые 12)"))
            for l in lines[:12]:
                log("  " + l)
            if args.commit and lines:
                subprocess.run(["git", "-C", str(dest), "add", "-A"], check=True)
                subprocess.run(["git", "-C", str(dest), "commit", "-q", "-m", args.commit], check=True)
                log("закоммичено")
        return 0
    finally:
        shutil.rmtree(stage, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
