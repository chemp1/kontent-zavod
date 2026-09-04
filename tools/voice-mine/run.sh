#!/usr/bin/env bash
# Обёртка для крона: лок от параллельных запусков, лог в .data/.
# Сначала DUMP_COMMAND из .env (если задана) обновляет .data/tools/voice-mine/transcripts.jsonl,
# потом check.py разбирает свежие звонки. Без DUMP_COMMAND файл должен лежать заранее.
# Крон даёт PATH=/usr/bin:/bin - без экспорта не найдётся `claude` (/usr/local/bin).
# Настройки прогона (NOTIFY, STUDIO_URL, WORKSHOP_ROOT, DUMP_COMMAND) - в .env рядом, см. .env.example.
set -u
export PATH="/usr/local/bin:/usr/bin:/bin"
DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$DIR/.env" ]; then set -a; . "$DIR/.env"; set +a; fi
ROOT="${WORKSHOP_ROOT:-$(git -C "$DIR" rev-parse --show-toplevel)}"
export WORKSHOP_ROOT="$ROOT"
exec 9>"/tmp/$(basename "$ROOT")-tools/voice-mine.lock"
flock -n 9 || exit 0
mkdir -p "$ROOT/.data/tools/voice-mine"
LOG="$ROOT/.data/tools/voice-mine.log"
if [ -n "${DUMP_COMMAND:-}" ]; then
  /usr/bin/timeout 900 sh -c "$DUMP_COMMAND" >> "$LOG" 2>&1 \
    || { echo "[$(date -Is)] дамп расшифровок не удался, разбор пропущен" >> "$LOG"; exit 0; }
fi
exec /usr/bin/timeout 3600 /usr/bin/python3 "$DIR/check.py" --days "${VOICE_MINE_DAYS:-2}" \
  >> "$LOG" 2>&1
