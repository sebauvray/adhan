#!/bin/bash

# Load config from SQLite
eval "$(python3 /app/load_config.py)"

LOG_LEVEL=${LOG_LEVEL:-INFO}

log() {
  local level="$1"
  shift
  local levels=("DEBUG" "INFO" "WARN" "ERROR")

  local current_index wanted_index
  for i in "${!levels[@]}"; do
    [[ "${levels[$i]}" == "$LOG_LEVEL" ]] && current_index="$i"
    [[ "${levels[$i]}" == "$level" ]] && wanted_index="$i"
  done

  if [[ "$wanted_index" -ge "$current_index" ]]; then
    local timestamp
    timestamp=$(date "+%d.%m.%Y - %H:%M:%S")
    echo "[$timestamp] [$level] $*"
  fi
}

get_output_ids_for_names() {
  local outputs_json="$1"
  shift
  local names=("$@")

  for name in "${names[@]}"; do
    local id
    id=$(echo "$outputs_json" | jq -r --arg n "$name" '.outputs[] | select(.name == $n) | .id')
    if [[ -n "$id" ]]; then
      echo "$id"
      log DEBUG "Output found: $name → $id"
    else
      log WARN "Output not found: $name"
    fi
  done
}

set_volume_for_ids() {
  local volume="$1"
  shift
  local ids=("$@")

  for id in "${ids[@]}"; do
    curl -s -X PUT "http://${OWNTONE_HOST}:${OWNTONE_PORT}/api/outputs/${id}" \
      -H "Content-Type: application/json" \
      -d "{\"volume\":${volume}}" > /dev/null
  done
}

play_file_on_ids() {
  local track_uri="$1"
  shift
  local ids=("$@")

  if [[ -z "$track_uri" ]]; then
    log ERROR "No track URI provided"
    return 1
  fi

  if [[ ${#ids[@]} -eq 0 ]]; then
    log ERROR "No outputs provided"
    return 1
  fi

  curl -s -X PUT "http://${OWNTONE_HOST}:${OWNTONE_PORT}/api/outputs/set" \
    -H "Content-Type: application/json" \
    -d "{\"outputs\": $(printf '%s\n' "${ids[@]}" | jq -R . | jq -s .)}" \
    > /dev/null

  curl -s -X POST "http://${OWNTONE_HOST}:${OWNTONE_PORT}/api/queue/items/add?uris=${track_uri}&clear=true&playback=start" \
    > /dev/null

  log INFO "Playback started: $track_uri on ${ids[*]}"
}

resolve_track_uri() {
  local file_path="${ADHAN_FILE:-}"
  if [[ -z "$file_path" ]]; then
    log ERROR "ADHAN_FILE not set"
    return 1
  fi

  local track_id
  track_id=$(curl -s -G "http://${OWNTONE_HOST}:${OWNTONE_PORT}/api/search" \
    --data-urlencode "type=tracks" \
    --data-urlencode "expression=path is \"${file_path}\"" \
    | jq -r '.tracks.items[0].id // empty')

  if [[ -n "$track_id" ]]; then
    echo "library:track:${track_id}"
  else
    log ERROR "Track not found: $file_path"
    return 1
  fi
}

# --- Main ---

PRAYER_NAME="${1:-}"
if [[ -z "$PRAYER_NAME" ]]; then
  log ERROR "Usage: adhan.sh <prayer_name>"
  exit 1
fi

log INFO "Adhan triggered for: $PRAYER_NAME"

# Get configured outputs for this prayer
readarray -t HOMEPODS < <(python3 /app/get_homepods.py "$PRAYER_NAME")
if [ ${#HOMEPODS[@]} -eq 0 ]; then
  log WARN "No outputs configured for $PRAYER_NAME"
  exit 0
fi

log DEBUG "Outputs for $PRAYER_NAME: ${HOMEPODS[*]}"

# Get volume for this prayer (default 40)
PRAYER_VOLUME=$(python3 -c "
import sys; sys.path.insert(0,'/app')
from db.schema import init_db; from db.config import get_prayer_volume
init_db(); print(get_prayer_volume('$PRAYER_NAME', 40))
")
ADHAN_VOLUME=${PRAYER_VOLUME:-${ADHAN_VOLUME:-30}}

# Quiet hours: cap volume if current time is within quiet range
QUIET_CONFIG=$(python3 -c "
import sys; sys.path.insert(0,'/app')
from db.schema import init_db; from db.config import get_value
init_db()
print(get_value('config','QUIET_START','21:00'))
print(get_value('config','QUIET_END','07:00'))
print(get_value('config','QUIET_VOLUME','10'))
")
QUIET_START=$(echo "$QUIET_CONFIG" | sed -n '1p')
QUIET_END=$(echo "$QUIET_CONFIG" | sed -n '2p')
QUIET_VOLUME=$(echo "$QUIET_CONFIG" | sed -n '3p')

NOW_MINUTES=$(( $(date +%H) * 60 + $(date +%M) ))
QS_MINUTES=$(( ${QUIET_START%%:*} * 60 + ${QUIET_START##*:} ))
QE_MINUTES=$(( ${QUIET_END%%:*} * 60 + ${QUIET_END##*:} ))

IN_QUIET=false
if [[ $QS_MINUTES -gt $QE_MINUTES ]]; then
  # Overnight range (e.g. 21:00 → 07:00)
  [[ $NOW_MINUTES -ge $QS_MINUTES || $NOW_MINUTES -lt $QE_MINUTES ]] && IN_QUIET=true
else
  # Same-day range (e.g. 14:00 → 16:00)
  [[ $NOW_MINUTES -ge $QS_MINUTES && $NOW_MINUTES -lt $QE_MINUTES ]] && IN_QUIET=true
fi

if [[ "$IN_QUIET" == "true" && "$ADHAN_VOLUME" -gt "$QUIET_VOLUME" ]]; then
  log INFO "Quiet hours active ($QUIET_START-$QUIET_END): volume capped from $ADHAN_VOLUME to $QUIET_VOLUME"
  ADHAN_VOLUME=$QUIET_VOLUME
fi

log DEBUG "Volume for $PRAYER_NAME: $ADHAN_VOLUME"

OUTPUTS_JSON=$(curl -s "http://${OWNTONE_HOST}:${OWNTONE_PORT}/api/outputs")
readarray -t OUTPUT_IDS < <(get_output_ids_for_names "$OUTPUTS_JSON" "${HOMEPODS[@]}")

if [[ ${#OUTPUT_IDS[@]} -eq 0 ]]; then
  log ERROR "No valid OwnTone outputs found for $PRAYER_NAME"
  exit 1
fi

TRACK_URI=$(resolve_track_uri) || exit 1

set_volume_for_ids "$ADHAN_VOLUME" "${OUTPUT_IDS[@]}"
play_file_on_ids "$TRACK_URI" "${OUTPUT_IDS[@]}"
