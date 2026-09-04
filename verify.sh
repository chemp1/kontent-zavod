#!/usr/bin/env bash
# Проверка открытого репо: всё запускается, пороги честные, личного нет.
set -uo pipefail
cd "$(dirname "$0")"
fail=0
ok()   { printf '  ok  %s\n' "$1"; }
bad()  { printf '  !!  %s\n' "$1"; fail=1; }

LINT=.claude/skills/corrector/scripts/lint.py
CAL=.claude/skills/corrector/scripts/calibrate.py

echo "== стоп-лист =="
CHECK=(python3 export/check.py . --stoplist export/stoplist.example.txt --binary-allow-file export/binary-allow.txt)
[ -f export/stoplist.local.txt ] && CHECK+=(--stoplist export/stoplist.local.txt)
if "${CHECK[@]}" >/dev/null 2>&1; then ok "стоп-лист чист"; else bad "стоп-лист нашёл личное (${CHECK[*]})"; fi

echo "== линтер =="
python3 "$LINT" --strict voice/corpus/samples/draft-ok.md >/dev/null 2>&1 && ok "draft-ok проходит без блокеров" || bad "draft-ok: есть блокеры"
python3 "$LINT" --strict voice/corpus/samples/draft-slop.md >/dev/null 2>&1; [ $? -eq 2 ] && ok "draft-slop ловится" || bad "draft-slop: линтер пропустил слоп"

echo "== калибровка =="
tmp=$(mktemp)
SEED=(); [ -f voice/seed.json ] && SEED=(--seed voice/seed.json)
python3 "$CAL" voice/corpus/channel.json "${SEED[@]}" --out "$tmp" --label "$(python3 -c 'import json;print(json.load(open("voice/thresholds.json"))["meta"]["corpus_label"])')" >/dev/null 2>&1
python3 - "$tmp" <<'EOF' && ok "thresholds.json совпадает с пересчётом" || bad "thresholds.json разошёлся с пересчётом - его правили руками?"
import json, sys
a = json.load(open(sys.argv[1])); b = json.load(open("voice/thresholds.json"))
for d in (a, b): d["meta"].pop("generated", None)
sys.exit(0 if a == b else 1)
EOF
rm -f "$tmp"
python3 voice/corpus/normalize.py --check --dir voice/corpus >/dev/null 2>&1 && ok "корпус нормализован" || bad "normalize.py --check"

echo "== тесты =="
python3 .claude/skills/corrector/scripts/test_lint.py >/dev/null 2>&1 && ok "test_lint.py" || bad "test_lint.py"

echo "== сборщики =="
python3 tools/voice-mine/check.py --from-jsonl voice/calls.jsonl --dry-run >/dev/null 2>&1 && ok "voice-mine --dry-run" || bad "voice-mine --dry-run"
if [ "${VERIFY_NETWORK:-0}" = "1" ]; then
  NOTIFY=stdout python3 tools/trend-watch/check.py --dry-run --limit 1 >/dev/null 2>&1 && ok "trend-watch --dry-run" || bad "trend-watch --dry-run"
else
  echo "  --  trend-watch пропущен (нужна сеть: VERIFY_NETWORK=1)"
fi

echo "== плейсхолдеры =="
if grep -rn "{{" --include=*.md --include=*.json . 2>/dev/null | grep -v "_templates/" | grep -v "docs/boundaries.md" | grep -v node_modules | grep -v "/\.next/" | grep -q .; then
  bad "плейсхолдеры {{...}} вне _templates/ и docs/boundaries.md"; else ok "плейсхолдеры только в шаблонах"; fi

echo "== студия =="
if [ "${VERIFY_STUDIO:-0}" = "1" ]; then
  (cd studio && npm ci >/dev/null 2>&1 && npm run typecheck >/dev/null 2>&1 && npm run build >/dev/null 2>&1) && ok "studio typecheck+build" || bad "studio typecheck+build"
else
  echo "  --  студия пропущена (VERIFY_STUDIO=1 для npm ci + build)"
fi

[ $fail -eq 0 ] && echo "ВСЁ ЧИСТО" || { echo "ЕСТЬ ПРОБЛЕМЫ"; exit 1; }
