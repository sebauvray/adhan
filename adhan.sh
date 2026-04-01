#!/bin/bash

# Charge la configuration depuis SQLite
eval "$(python3 /app/load_config.py)"

# Niveaux possibles : DEBUG < INFO < WARN < ERROR
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

get_current_period() {
  local now=$(date +%H:%M)

  is_in_range() {
    local time="$1"
    local range="$2"
    local start="${range%-*}"
    local end="${range#*-}"

    if [[ "$start" < "$end" ]]; then
      [[ "$time" >= "$start" && "$time" < "$end" ]]
    else
      [[ "$time" >= "$start" || "$time" < "$end" ]]
    fi
  }

  if is_in_range "$now" "$MORNING_TIME"; then
    echo "morning"
  elif is_in_range "$now" "$AFTERNOON_TIME"; then
    echo "afternoon"
  elif is_in_range "$now" "$EVENING_TIME"; then
    echo "evening"
  else
    echo "none"
  fi
}

get_outputs_for_period() {
  local period="$1"
  python3 /app/get_homepods.py "$period"
}

# Récupère les IDs OwnTone pour une liste de noms d'outputs
get_output_ids_for_names() {
  local outputs_json="$1"
  shift
  local names=("$@")

  for name in "${names[@]}"; do
    local id
    id=$(echo "$outputs_json" | jq -r --arg n "$name" '.outputs[] | select(.name == $n) | .id')
    if [[ -n "$id" ]]; then
      echo "$id"
      log DEBUG "Output trouvé: $name → $id"
    else
      log WARN "Output ABSENT: $name"
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
    log ERROR "Aucun track URI fourni"
    return 1
  fi

  if [[ ${#ids[@]} -eq 0 ]]; then
    log ERROR "Aucun output fourni"
    return 1
  fi

  log DEBUG "Lecture du track URI: $track_uri"
  log DEBUG "Activation des outputs: ${ids[*]}"

  curl -s -X PUT "http://${OWNTONE_HOST}:${OWNTONE_PORT}/api/outputs/set" \
    -H "Content-Type: application/json" \
    -d "{\"outputs\": $(printf '%s\n' "${ids[@]}" | jq -R . | jq -s .)}" \
    > /dev/null

  curl -s -X POST "http://${OWNTONE_HOST}:${OWNTONE_PORT}/api/queue/items/add?uris=${track_uri}&clear=true&playback=start" \
    > /dev/null

  log INFO "Déclenchement fini: track $track_uri sur ${ids[*]}"
}

resolve_track_uri() {
  local file_path="${ADHAN_FILE:-}"
  if [[ -z "$file_path" ]]; then
    log ERROR "ADHAN_FILE non défini"
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
    log ERROR "Track non trouvé pour: $file_path"
    return 1
  fi
}

# --- Main ---

CURRENT_PERIOD=$(get_current_period)
log DEBUG "Période actuelle : $CURRENT_PERIOD"

readarray -t HOMEPODS < <(get_outputs_for_period "$CURRENT_PERIOD")
if [ ${#HOMEPODS[@]} -eq 0 ]; then
  log WARN "Aucun HomePod configuré pour la période '$CURRENT_PERIOD'"
  exit 0
fi

log DEBUG "HomePods détectés pour cette période : ${HOMEPODS[*]}"

if [[ "$CURRENT_PERIOD" == "evening" ]]; then
  ADHAN_VOLUME=20
fi

OUTPUTS_JSON=$(curl -s "http://${OWNTONE_HOST}:${OWNTONE_PORT}/api/outputs")
readarray -t OUTPUT_IDS < <(get_output_ids_for_names "$OUTPUTS_JSON" "${HOMEPODS[@]}")

if [[ ${#OUTPUT_IDS[@]} -eq 0 ]]; then
  log ERROR "Aucune sortie valide trouvée dans OwnTone"
  exit 1
fi

TRACK_URI=$(resolve_track_uri) || exit 1

set_volume_for_ids "$ADHAN_VOLUME" "${OUTPUT_IDS[@]}"
play_file_on_ids "$TRACK_URI" "${OUTPUT_IDS[@]}"
