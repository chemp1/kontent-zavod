#!/usr/bin/env python3
"""Калибровка порогов линтера по корпусу автора.

Считает по каждому посту те же маркеры, что проверяет `lint.py` (импортирует его
детекторы, поэтому линтер и калибратор не могут разойтись), и выводит
`thresholds.json` с обоснованием: доли, квантили, размер выборки по бакетам.

Вход - корпус в одном из форматов:
  * JSON-список `[{"date": "...", "views": ..., "text": "..."}]`
  * каталог с `.md` (один пост на файл; YAML-шапка отрезается)
  * один `.md` в формате normalize.py: посты между `## <дата>` и `---`

Использование:
    python3 calibrate.py voice/corpus/channel.json --out voice/thresholds.json
    python3 calibrate.py posts/ --since 2025-01-01 --report
    python3 calibrate.py corpus.json --seed my-thresholds.json   # свои словари вместо DEFAULTS

Правила вывода порогов (одно на класс проверки):
  * «никогда»-паттерны и фразы: доля постов с признаком ≤ 2% → stop, ≤ 10% → warn, иначе off
  * счётчики на пост (копула, «данный», усилители, …): warn_at = p90 + 1
  * обязательные маркеры по бакетам длины (скобки, хеджи, первое лицо): доля постов с
    маркером ≥ 85% → stop при отсутствии, ≥ 45% → warn, иначе ok
  * ритм: минимум = p10 по корпусу; длина: ok = [p10, p90], норма = [p25, p75]
  * в бакете меньше --min-n постов → уровень понижается на ступень и пишется предупреждение
"""

import argparse
import datetime as dt
import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lint  # noqa: E402

LOWER = {"stop": "warn", "warn": "ok", "ok": "ok", "off": "off"}


# ---------------------------------------------------------------------------
# Чтение корпуса
# ---------------------------------------------------------------------------
def read_corpus(path):
    """Возвращает список (date|None, text)."""
    p = Path(path)
    if p.is_dir():
        out = []
        for f in sorted(p.glob("*.md")):
            text = lint.strip_frontmatter(f.read_text(encoding="utf-8"))
            m = re.match(r"(\d{4}-\d{2}-\d{2})", f.name)
            out.append((m.group(1) if m else None, text))
        return out
    raw = p.read_text(encoding="utf-8")
    if p.suffix == ".json":
        data = json.loads(raw)
        return [(str(x.get("date") or "")[:10] or None, x["text"]) for x in data if x.get("text")]
    # один .md в формате normalize.py
    out = []
    for m in re.finditer(r"^## (\d{4}-\d{2}-\d{2})[^\n]*\n(.*?)(?=^## \d{4}-\d{2}-\d{2}|\Z)", raw, re.S | re.M):
        text = m.group(2).strip()
        text = re.sub(r"\n---\s*\Z", "", text).strip()
        if text:
            out.append((m.group(1), text))
    return out


# ---------------------------------------------------------------------------
# Статистика
# ---------------------------------------------------------------------------
def quantile(values, q):
    vals = sorted(v for v in values if v is not None)
    if not vals:
        return None
    if len(vals) == 1:
        return vals[0]
    pos = (len(vals) - 1) * q
    lo, hi = int(pos), min(int(pos) + 1, len(vals) - 1)
    return vals[lo] + (vals[hi] - vals[lo]) * (pos - lo)


def share(flags):
    return (sum(1 for f in flags if f) / len(flags)) if flags else 0.0


def level_by_share(s):
    """Для признаков, которых у автора не должно быть."""
    if s <= 0.02:
        return "stop"
    if s <= 0.10:
        return "warn"
    return "off"


def level_by_presence(s):
    """Для маркеров, которые у автора должны быть."""
    if s >= 0.85:
        return "stop"
    if s >= 0.45:
        return "warn"
    return "ok"


def round50(x):
    return int(round(x / 50.0) * 50)


def bucket_of(chars, edges):
    for i, e in enumerate(edges):
        if chars < e:
            return i
    return len(edges)


# ---------------------------------------------------------------------------
def calibrate(posts, seed, edges, min_n, label):
    T = json.loads(json.dumps(seed))
    P = lint.compile_patterns(T)
    ms = [lint.measure(t, T, P) for _, t in posts]
    n = len(ms)
    warnings = []
    report = []  # (метрика, значение, n, основание)

    def rep(name, value, nn, basis):
        report.append((name, value, nn, basis))

    def pinned(key):
        """`"pin": true` в seed - уровень задан руками (например, в корпусе есть чужие посты)."""
        return bool(seed.get(key, {}).get("pin"))

    # --- длинное тире ---
    # Тире - структурный признак: если 90% постов автора обходятся одним, четыре тире в
    # черновике - не его текст. Поэтому уровень от p90, а не от доли «нарушителей».
    dashes = [m["dash"] for m in ms]
    p90 = int(quantile(dashes, 0.9))
    level = "stop" if p90 <= 1 else "warn" if p90 <= 3 else "off"
    if pinned("dash"):
        level = seed["dash"]["level"]
    T["dash"] = {"max_per_post": p90, "level": level}
    rep("длинное тире на пост, p90", p90, n, f"уровень {level}")

    # --- бинарные «никогда»-признаки ---
    for key, field, name in (("dash_bullets", "dash_bullets", "буллеты через тире"),
                             ("markdown", "markdown", "markdown в теле"),
                             ("list_emoji", "list_emoji", "эмодзи-маркеры списка")):
        s = share([m[field] > 0 for m in ms])
        level = seed[key]["level"] if pinned(key) else level_by_share(s)
        T[key] = {"level": level}
        if pinned(key):
            T[key]["pin"] = True
        rep(name, f"{lint.pct(s)} постов", n, f"уровень {level}" + (" (pin)" if pinned(key) else ""))

    # --- списки фраз: фраза остаётся, если встречается ≤ 10% постов ---
    for key, field, name in (("banned_phrases", "banned", "служебные обороты"),
                             ("abstract_nouns", "abstract", "абстрактные существительные")):
        kept, dropped, worst = [], [], 0.0
        low_texts = [t.lower() for _, t in posts]
        for phrase in seed[key]["items"]:
            s = share([phrase in t for t in low_texts])
            if s <= 0.10:
                kept.append(phrase)
                worst = max(worst, s)
            else:
                dropped.append((phrase, s))
        lvl = level_by_share(worst) if kept else "off"
        if key == "abstract_nouns" and lvl == "stop":
            lvl = "warn"  # абстракции - замечание, не блокер: слишком расплывчатый класс
        T[key] = {"level": lvl, "items": kept}
        for phrase, s in dropped:
            warnings.append(f"{name}: «{phrase}» встречается в {lint.pct(s)} постов - убрана из списка")
        rep(name, f"{len(kept)} фраз, худшая {lint.pct(worst)}", n, f"уровень {lvl}")

    # --- «никогда»-паттерны ---
    for lab, spec in seed["never"].items():
        s = share([m["never"].get(lab, 0) > 0 for m in ms])
        lvl = level_by_share(s)
        T["never"][lab] = dict(spec, level=lvl)
        if lvl == "off":
            warnings.append(f"«{lab}»: {lint.pct(s)} постов - проверка выключена")
        rep(f"«{lab}»", f"{lint.pct(s)} постов", n, f"уровень {lvl}")

    # --- счётчики на пост ---
    def counter_rule(key, field, name, floor=1):
        vals = [m[field] for m in ms]
        s = share([v > 0 for v in vals])
        p = int(quantile(vals, 0.9))
        T[key]["warn_at"] = max(floor, p + 1)
        T[key]["share"] = round(s, 3)
        rep(name, f"{lint.pct(s)} постов, p90 {p}", n, f"warn_at {T[key]['warn_at']}")

    counter_rule("copula", "copula", "обход «быть»", floor=2)
    counter_rule("dannyj", "dannyj", "«данный»", floor=1)
    counter_rule("math", "math", "матзнаки", floor=1)
    counter_rule("modal_hedges", "modal", "модальные хеджи", floor=1)
    counter_rule("amplifiers", "amplifiers", "усилители", floor=2)
    counter_rule("not_x_but_y", "not_x_but_y", "«не X, а Y»", floor=2)
    counter_rule("emoji", "emoji", "эмодзи", floor=3)  # пара эмодзи - ещё не маркер

    kvals = [len(m["kants"]) for m in ms]
    s = share([v > 0 for v in kvals])
    T["kants"]["warn_at"] = max(2, int(quantile(kvals, 0.9)) + 1)
    T["kants"]["share"] = round(s, 3)
    rep("канцелярские переходы", f"{lint.pct(s)} постов", n, f"warn_at {T['kants']['warn_at']}")

    noms = [m["nominal_per_1000"] for m in ms if m["words"] >= 50]
    T["nominalization"]["max_per_1000"] = int(round(quantile(noms, 0.9)))
    rep("номинализация на 1000 слов, p90", T["nominalization"]["max_per_1000"], len(noms), "max_per_1000")

    # --- концовка ---
    # Если автор регулярно заканчивает пост словом без знака, «обрыв последней строки»
    # ничего не ловит - выключаем. Иначе собираем знаки, покрывающие 95% концовок.
    last = [m["last_char"] for m in ms if m["last_char"]]
    alnum = share([ch.isalnum() for ch in last])
    if alnum >= 0.20:
        T["ending"] = {"terminals": seed["ending"]["terminals"], "level": "off"}
        rep("концовка словом без знака", f"{lint.pct(alnum)} постов", n, "проверка обрыва выключена")
    else:
        ends = Counter(ch for ch in last if not ch.isalnum())
        total, acc, terms = sum(ends.values()) or 1, 0, []
        for ch, c in ends.most_common():
            terms.append(ch)
            acc += c
            if acc / total >= 0.95:
                break
        for ch in ".!?)»…":
            if ch not in terms:
                terms.append(ch)
        T["ending"] = {"terminals": "".join(terms), "level": "warn"}
        rep("знаки в конце поста", f"{len(terms)} вариантов покрывают 95%", n, repr("".join(terms)))

    # --- бакеты по длине ---
    T["buckets"] = {"short_below": edges[0], "medium_below": edges[1] if len(edges) > 1 else edges[0]}
    groups = {}
    for m in ms:
        groups.setdefault(bucket_of(m["chars"], edges), []).append(m)
    bucket_n = {i: len(groups.get(i, [])) for i in range(len(edges) + 1)}
    T["meta"]["bucket_n"] = {("<%d" % edges[i]) if i < len(edges) else (">=%d" % edges[-1]): bucket_n[i]
                             for i in range(len(edges) + 1)}

    def lowered(lvl, i, name):
        if bucket_n[i] < min_n and lvl in ("stop", "warn"):
            warnings.append(f"{name}: в бакете {i} всего {bucket_n[i]} постов (< {min_n}) - уровень понижен")
            return LOWER[lvl]
        return lvl

    # скобки: два бакета (короткий / остальные), как в DEFAULTS
    sm_buckets = []
    for i, below in ((0, edges[0]), (1, None)):
        grp = groups.get(0, []) if i == 0 else [m for k, g in groups.items() if k >= 1 for m in g]
        s_any = share([m["smileys"] >= 1 for m in grp])
        s_two = share([m["smileys"] >= 2 for m in grp])
        missing = level_by_presence(s_any)
        if len(grp) < min_n and missing in ("stop", "warn"):
            warnings.append(f"скобки: бакет {'короткий' if i == 0 else 'длинный'} - {len(grp)} постов, уровень понижен")
            missing = LOWER[missing]
        single = "warn" if s_two >= 0.6 else "ok"
        sm_buckets.append({"below": below, "share_any": round(s_any, 3), "share_two": round(s_two, 3),
                           "missing": missing, "single": single, "n": len(grp)})
        rep(f"скобки-улыбки, {'короткие' if i == 0 else 'длинные'} посты",
            f"есть у {lint.pct(s_any)}, две и больше у {lint.pct(s_two)}", len(grp), f"missing {missing}")
    T["smileys"]["buckets"] = sm_buckets

    # хеджи: три бакета. Порог мягче, чем у скобок: хедж есть не в каждом посте даже
    # у самого сомневающегося автора, поэтому 50% → stop, 30% → warn.
    hb = []
    for i in range(len(edges) + 1):
        grp = groups.get(i, [])
        s = share([bool(m["hedges"]) for m in grp])
        lvl = "stop" if s >= 0.5 else "warn" if s >= 0.3 else "ok"
        lvl = lowered(lvl, i, "хеджи")
        hb.append({"below": edges[i] if i < len(edges) else None, "share": round(s, 3),
                   "missing": lvl, "n": len(grp)})
        rep(f"хедж в посте, бакет {i}", f"{lint.pct(s)}", len(grp), f"missing {lvl}")
    T["hedges"]["buckets"] = hb
    hedge_counts = Counter(h for m in ms for h in m["hedges"])
    unused = [h for h in seed["hedges"]["items"] if hedge_counts[h] == 0]
    T["hedges"]["items"] = [h for h in seed["hedges"]["items"] if hedge_counts[h] > 0] or seed["hedges"]["items"]
    if unused:
        warnings.append("хеджи без вхождений в корпусе (убраны из списка): " + ", ".join(unused))

    # связки
    conn_counts = Counter(c for m in ms for c in m["connectors"])
    s = share([bool(m["connectors"]) for m in ms])
    T["connectors"]["items"] = [c for c in seed["connectors"]["items"] if conn_counts[c] > 0] or seed["connectors"]["items"]
    T["connectors"]["share"] = round(s, 3)
    T["connectors"]["missing"] = "warn" if s >= 0.6 else "ok"
    rep("разговорная связка в посте", f"{lint.pct(s)}", n, f"missing {T['connectors']['missing']}")

    # первое лицо: два бакета
    fb = []
    for i, below in ((0, edges[0]), (1, None)):
        grp = groups.get(0, []) if i == 0 else [m for k, g in groups.items() if k >= 1 for m in g]
        s = share([m["first_person"] for m in grp])
        lvl = level_by_presence(s)
        if len(grp) < min_n and lvl in ("stop", "warn"):
            lvl = LOWER[lvl]
        fb.append({"below": below, "share": round(s, 3), "missing": lvl, "n": len(grp)})
        rep(f"первое лицо, {'короткие' if i == 0 else 'длинные'} посты", f"{lint.pct(s)}", len(grp), f"missing {lvl}")
    T["first_person"]["buckets"] = fb

    # --- ритм ---
    spreads = [m["para_spread"] for m in ms if m["para_spread"] is not None]
    if spreads:
        T["paragraph_spread"]["min"] = round(quantile(spreads, 0.1), 1)
        rep("разброс длин абзацев, p10", T["paragraph_spread"]["min"], len(spreads), "min")
    cvs = [m["sentence_cv"] for m in ms if m["sentence_cv"] is not None]
    if cvs:
        T["sentence_cv"] = {"min": round(quantile(cvs, 0.1), 2), "median": round(statistics.median(cvs), 2)}
        rep("CV длин предложений", f"p10 {T['sentence_cv']['min']}, медиана {T['sentence_cv']['median']}", len(cvs), "min")
    dots = [m["dotted_share"] for m in ms if m["dotted_share"] is not None]
    if dots:
        T["dotted_lines"] = {"max_share": round(quantile(dots, 0.9), 2), "typical": round(statistics.median(dots), 2)}
        rep("доля строк с точкой", f"медиана {lint.pct(T['dotted_lines']['typical'])}, p90 {lint.pct(T['dotted_lines']['max_share'])}", len(dots), "max_share")

    # --- длина ---
    chars = [m["chars"] for m in ms]
    T["length"] = {"ok_min": round50(quantile(chars, 0.1)), "ok_max": round50(quantile(chars, 0.9)),
                   "norm_min": round50(quantile(chars, 0.25)), "norm_max": round50(quantile(chars, 0.75))}
    rep("длина, знаков", f"p10 {T['length']['ok_min']}, p25 {T['length']['norm_min']}, p75 {T['length']['norm_max']}, p90 {T['length']['ok_max']}", n, "ok/norm")

    # --- заголовок: первая строка короткая, дальше пустая ---
    titled = []
    tw = []
    for _, t in posts:
        ls = t.splitlines()
        has = len(ls) >= 2 and ls[0].strip() and not ls[1].strip() and len(ls[0].split()) <= 8
        titled.append(bool(has))
        if has:
            tw.append(len(ls[0].split()))
    s = share(titled)
    # p90 + 1: заголовок на слово длиннее обычного - ещё не отклонение
    T["title"] = {"enabled": s >= 0.5, "max_words": max(4, int(quantile(tw, 0.9)) + 1) if tw else 6}
    rep("заголовок первой строкой", f"{lint.pct(s)} постов, p90 {T['title']['max_words']} слов", n, f"enabled {T['title']['enabled']}")

    # --- meta ---
    dates = sorted(d for d, _ in posts if d)
    T["meta"] = dict(T.get("meta", {}), **{
        "corpus_label": label,
        "posts": n,
        "range": [dates[0], dates[-1]] if dates else None,
        "generated": dt.date.today().isoformat(),
        "warnings": warnings,
        "bucket_n": T["meta"].get("bucket_n"),
    })
    return T, report


def render_report(report, T):
    lines = ["| Метрика | Значение | n | Порог |", "|---|---|---|---|"]
    for name, value, nn, basis in report:
        lines.append(f"| {name} | {value} | {nn} | {basis} |")
    if T["meta"].get("warnings"):
        lines.append("")
        lines.append("Предупреждения:")
        for w in T["meta"]["warnings"]:
            lines.append(f"- {w}")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Калибровка порогов линтера по корпусу автора.")
    ap.add_argument("corpus", help="JSON-список постов, каталог .md или один .md от normalize.py")
    ap.add_argument("--out", help="куда писать thresholds.json (по умолчанию - stdout)")
    ap.add_argument("--seed", help="thresholds.json со своими словарями (иначе DEFAULTS линтера)")
    ap.add_argument("--since", help="брать посты не раньше даты YYYY-MM-DD")
    ap.add_argument("--buckets", default="1000,1500", help="границы бакетов по длине, знаков")
    ap.add_argument("--min-n", type=int, default=30, help="минимум постов в бакете для stop/warn")
    ap.add_argument("--label", help="подпись корпуса для заголовка линтера")
    ap.add_argument("--report", action="store_true", help="напечатать markdown-таблицу обоснований")
    args = ap.parse_args(argv)

    posts = read_corpus(args.corpus)
    if args.since:
        posts = [(d, t) for d, t in posts if d and d >= args.since]
    if len(posts) < 5:
        print(f"слишком мало постов: {len(posts)}", file=sys.stderr)
        return 1

    seed = json.loads(json.dumps(lint.DEFAULTS))
    if args.seed:
        with open(args.seed, encoding="utf-8") as f:
            seed = lint.deep_merge(seed, json.load(f))
    edges = [int(x) for x in args.buckets.split(",") if x.strip()]
    label = args.label or f"корпус автора, {len(posts)} постов"

    T, report = calibrate(posts, seed, edges, args.min_n, label)
    out = json.dumps(T, ensure_ascii=False, indent=1) + "\n"
    if args.out:
        Path(args.out).write_text(out, encoding="utf-8")
        print(f"записано: {args.out} ({len(posts)} постов)", file=sys.stderr)
    else:
        print(out)
    if args.report:
        print(render_report(report, T))
    for w in T["meta"]["warnings"]:
        print(f"! {w}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())