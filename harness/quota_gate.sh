#!/usr/bin/env bash
# Block until it is reasonable to start another Claude fixture.
#
# Reads the newest Claude Code rate_limit_event from this user's live and
# finished fixture streams and waits while:
#   - a hold file exists (CGB_HOLD_FILE, default ~/cgb_hold): set automatically
#     when the weekly or Fable allowance nears its limit, so running fixtures can
#     finish and the user can reset at a clean point; remove it to resume;
#   - the five-hour window is at or above CGB_GATE_FIVE_HOUR (default 0.85),
#     until that window's reset time passes.
# Weekly / Fable thresholds: CGB_GATE_WEEKLY and CGB_GATE_FABLE (default 0.90).
# Usage: quota_gate.sh <fixture id> <work root>
set -uo pipefail
FID="${1:-?}"; ROOT="${2:-.}"
HOLD="${CGB_HOLD_FILE:-$HOME/cgb_hold}"
FIVE="${CGB_GATE_FIVE_HOUR:-0.85}"; WEEK="${CGB_GATE_WEEKLY:-0.90}"; FABLE="${CGB_GATE_FABLE:-0.90}"
log() { echo "$(date -u +%FT%TZ) [$FID] $*"; }

reading() {
  # newest stream that has a rate_limit_event; print "window util resetsAt" lines
  local f
  f="$(ls -t "$ROOT"/*_run/stream.jsonl "$ROOT"/*_run/attempt*.jsonl /tmp/cgb_fixture.*/attempt*.jsonl 2>/dev/null \
        | while read -r p; do grep -q '"rate_limit_event"' "$p" 2>/dev/null && { echo "$p"; break; }; done)"
  [[ -n "$f" ]] || return 0
  # unifiedWindows carries every window it reports; the top-level type/utilization
  # is the window currently closest to its limit (e.g. five_hour near a session cap).
  grep '"rate_limit_event"' "$f" | tail -n1 | jq -r '
    .rate_limit_info as $r
    | (($r.unifiedWindows // {}) | to_entries[] | "\(.key) \(.value.utilization // 0) \(.value.resetsAt // 0)"),
      (if ($r.rateLimitType // "") != "" and ($r.utilization != null)
       then "\($r.rateLimitType) \($r.utilization) \($r.resetsAt // 0)" else empty end)' 2>/dev/null
}

ge() { awk -v a="$1" -v b="$2" 'BEGIN{exit !(a>=b)}'; }
announced=""
while true; do
  if [[ -e "$HOLD" ]]; then
    [[ "$announced" == hold ]] || log "waiting: hold file $HOLD present"
    announced=hold; sleep 60; continue
  fi
  now="$(date +%s)"; five=0; five_reset=0; week=0; fable=0
  while read -r name util reset; do
    [[ -n "$name" ]] || continue
    # A window whose reset time has passed no longer limits anything.
    [[ "$reset" =~ ^[0-9]+$ ]] && (( reset > 0 && reset <= now )) && util=0
    case "$name" in
      five_hour*) five="$util"; five_reset="$reset" ;;
      seven_day_overage_included) fable="$util" ;;
      seven_day) week="$util" ;;
    esac
  done < <(reading)
  if ge "$week" "$WEEK" || ge "$fable" "$FABLE"; then
    printf 'weekly=%s fable=%s at %s\n' "$week" "$fable" "$(date -u +%FT%TZ)" > "$HOLD"
    log "HOLD: weekly=$week fable=$fable; no new fixtures. Running fixtures finish; reset, then remove $HOLD"
    announced=hold; continue
  fi
  if ge "$five" "$FIVE"; then
    [[ "$announced" == five ]] || log "waiting: five-hour window at $five (resets $(date -u -d @"$five_reset" +%H:%MZ 2>/dev/null))"
    announced=five; sleep 120; continue
  fi
  log "start allowed: five_hour=$five weekly=$week fable=$fable"
  exit 0
done
