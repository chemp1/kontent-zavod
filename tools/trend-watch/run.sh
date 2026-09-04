#!/usr/bin/env bash
# Обёртка для крона: лок от параллельных запусков, лог в .data/.
# Крон даёт PATH=/usr/bin:/bin — без экспорта не найдётся `claude` (/usr/local/bin).
# Настройки прогона (NOTIFY, STUDIO_URL, WORKSHOP_ROOT) - в .env рядом, см. .env.example.
set -u
export PATH="/usr/local/bin:/usr/bin:/bin"
DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$DIR/.env" ]; then set -a; . "$DIR/.env"; set +a; fi
ROOT="${WORKSHOP_ROOT:-$(git -C "$DIR" rev-parse --show-toplevel)}"
export WORKSHOP_ROOT="$ROOT"
exec 9>"/tmp/$(basename "$ROOT")-tools/trend-watch.lock"
flock -n 9 || exit 0
mkdir -p "$ROOT/.data"
exec /usr/bin/timeout 3600 /usr/bin/python3 "$DIR/check.py" \
  >> "$ROOT/.data/tools/trend-watch.log" 2>&1
