#!/usr/bin/env bash
# Foreground watchdog for the long subscription-backed baseline sweep.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUN="${1:-opus5-xhigh-official-baseline-prompt-full-r1}"
INTERVAL="${WATCH_INTERVAL_SECONDS:-30}"
MODEL="claude-opus-5:xhigh"
RESULTS="$ROOT/results/$RUN"
WORK="$ROOT/work/$RUN"
ALL="$ROOT/splits/all.txt"
PACKAGE="$ROOT/submit/build123d-direct-opus-5-xhigh.zip"
CLAUDE=/home/teleclaude/.npm-global/bin/claude

mkdir -p "$RESULTS" "$WORK" "$ROOT/logs/$RUN"

fixture_ids() {
  sed 's/#.*//' "$ALL" | tr -d '[:blank:]' | grep -E '^[0-9]+$'
}

write_missing() {
  local tmp="$WORK/watch-missing.txt.tmp.$$"
  comm -23 \
    <(fixture_ids | sort -n) \
    <(find "$RESULTS" -mindepth 2 -maxdepth 2 -name output.step -size +0c -printf '%h\n' 2>/dev/null | sed 's#.*/##' | sort -n) \
    > "$tmp" || { rm -f "$tmp"; return 1; }
  [[ $(wc -l < "$tmp") -le 81 ]] || { rm -f "$tmp"; return 1; }
  mv "$tmp" "$WORK/watch-missing.txt"
}

live_controller_count() {
  ps -eo stat=,args= | awk -v run="$RUN" '
    $1 !~ /^Z/ && $0 ~ run && ($0 ~ /cgb-full-baseline/ || $0 ~ /cgb-watch-retry/) && $0 !~ /watch_full_baseline/ {n++}
    END {print n+0}'
}

active_ids() {
  ps -eo stat=,args= | awk -v run="$RUN" '
    $1 !~ /^Z/ && $0 ~ ("run_sweep.sh --one") && $0 ~ run {
      for (i=1; i<=NF; i++) if ($i=="--one") printf "%s ", $(i+1)
    }'
}

quota_failure_seen() {
  find "$WORK" -maxdepth 1 -name '*.driver.log' -mmin -15 -print0 2>/dev/null \
    | xargs -0 -r grep -Eil 'session limit|usage limit|quota|rate.?limit|resets at|capacity' >/dev/null 2>&1
}

access_available() {
  local probe="$WORK/access-probe.jsonl"
  "$CLAUDE" -p 'Reply with exactly OK.' --model claude-opus-5 --effort xhigh \
    --output-format stream-json --verbose > "$probe" 2>&1
}

launch_missing() {
  write_missing
  local missing
  missing=$(wc -l < "$WORK/watch-missing.txt" | tr -d ' ')
  if [[ "$missing" -eq 0 ]]; then
    uv run --python 3.12 --with build123d-mcp==0.3.81 --with trimesh --with scipy \
      python "$ROOT/package_submission.py" "$RESULTS" --zip --full-set "$ALL"
    return $?
  fi
  rm -f "$WORK/full-supervisor.done"
  setsid -f bash -c '
    set -uo pipefail
    export PATH=/home/teleclaude/.npm-global/bin:/usr/local/bin:/usr/bin:/bin
    export CGB_PROMPT_STYLE=official-baseline
    run_name="$1"
    ./run_sweep.sh "work/$run_name/watch-missing.txt" "$run_name" claude-opus-5:xhigh none 2 ""
    sweep_status=$?
    count=$(find "results/$run_name" -mindepth 2 -maxdepth 2 -name output.step -size +0c | wc -l | tr -d " ")
    package_status=98
    if [[ "$count" -eq 81 ]]; then
      uv run --python 3.12 --with build123d-mcp==0.3.81 --with trimesh --with scipy \
        python package_submission.py "results/$run_name" --zip --full-set splits/all.txt
      package_status=$?
    fi
    printf "sweep_status=%s package_status=%s outputs=%s completed_utc=%s\n" \
      "$sweep_status" "$package_status" "$count" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
      > "work/$run_name/full-supervisor.done"
  ' cgb-watch-retry "$RUN" >> "$WORK/full-supervisor.log" 2>&1
  printf '%s watchdog relaunched %s missing fixtures\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$missing"
}

printf '%s watchdog foreground start run=%s interval=%ss\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$RUN" "$INTERVAL"
while true; do
  if ! write_missing; then
    printf '%s ERROR could not atomically refresh missing list; disk may be full\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    sleep "$INTERVAL"
    continue
  fi
  missing=$(wc -l < "$WORK/watch-missing.txt" | tr -d ' ')
  complete=$((81 - missing))
  controllers=$(live_controller_count)
  active=$(active_ids)
  printf '%s complete=%s/81 controllers=%s active=[%s]\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$complete" "$controllers" "$active"

  if [[ "$missing" -eq 0 ]]; then
    if [[ -f "$PACKAGE" ]]; then
      printf '%s COMPLETE package=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$PACKAGE"
      exit 0
    fi
    if [[ "$controllers" -eq 0 ]]; then
      launch_missing
    fi
  elif [[ "$controllers" -eq 0 ]]; then
    if quota_failure_seen; then
      printf '%s quota/session failure detected; probing access before relaunch\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
      if access_available; then
        printf '%s access probe passed\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
        launch_missing
      else
        printf '%s access still unavailable; will retry in 300s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
        sleep 270
      fi
    else
      launch_missing
    fi
  fi
  sleep "$INTERVAL"
done
