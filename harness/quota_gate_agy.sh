#!/usr/bin/env bash
# Block until it is reasonable to start another Antigravity (agy) fixture.
#
# Reads `agy -p /usage` (Gemini pool) and waits while:
#   - a hold file exists (CGB_HOLD_FILE, default ~/agy_hold): set automatically
#     when the weekly pool is nearly used, so running fixtures finish; remove it
#     to resume;
#   - the five-hour pool has less than CGB_AGY_MIN_FIVE_HOUR percent remaining
#     (default 10), until it recovers.
# Weekly threshold: CGB_AGY_MIN_WEEKLY percent remaining (default 3).
# Usage: quota_gate_agy.sh <fixture id> <work root>
set -uo pipefail
FID="${1:-?}"
HOLD="${CGB_HOLD_FILE:-$HOME/agy_hold}"
MIN_FIVE="${CGB_AGY_MIN_FIVE_HOUR:-10}"; MIN_WEEK="${CGB_AGY_MIN_WEEKLY:-3}"
log() { echo "$(date -u +%FT%TZ) [$FID] $*"; }

remaining() {  # percent remaining for the Gemini pool's window ($1 = Weekly|Five Hour)
  (cd /tmp && timeout 120 agy -p "/usage" 2>/dev/null) \
    | awk -F'\t' -v w="$1" '$1 == "Gemini Models" && index($2, w) == 1 { gsub("%", "", $3); print $3; exit }'
}

announced=""
while true; do
  if [[ -e "$HOLD" ]]; then
    [[ "$announced" == hold ]] || log "waiting: hold file $HOLD present"
    announced=hold; sleep 300; continue
  fi
  week="$(remaining "Weekly")"; five="$(remaining "Five Hour")"
  if [[ ! "$week" =~ ^[0-9]+$ || ! "$five" =~ ^[0-9]+$ ]]; then
    [[ "$announced" == unknown ]] || log "waiting: could not read agy /usage (weekly='$week' five='$five')"
    announced=unknown; sleep 300; continue
  fi
  if (( week < MIN_WEEK )); then
    printf 'gemini weekly remaining=%s%% at %s\n' "$week" "$(date -u +%FT%TZ)" > "$HOLD"
    log "HOLD: Gemini weekly remaining $week% < $MIN_WEEK%; no new fixtures. Remove $HOLD to resume"
    announced=hold; continue
  fi
  if (( five < MIN_FIVE )); then
    [[ "$announced" == five ]] || log "waiting: Gemini five-hour remaining $five% < $MIN_FIVE%"
    announced=five; sleep 300; continue
  fi
  log "start allowed: gemini weekly=$week% five_hour=$five% remaining"
  exit 0
done
