# Format attendu : HH:MM-HH:MM
MORNING_TIME=${MORNING_TIME:-"07:00-11:00"}
AFTERNOON_TIME=${AFTERNOON_TIME:-"11:00-20:00"}
EVENING_TIME=${EVENING_TIME:-"20:00-06:00"}

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
      [[ "$time" > "$start" && "$time" < "$end" ]]
    else
      [[ "$time" > "$start" || "$time" < "$end" ]]
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
  local config_file="${HOMEPOD_FILE:-./HomePod.json}"

  if [ ! -f "$config_file" ]; then
    log ERROR "❌ Fichier $config_file introuvable"
    return 1
  else
    log DEBUG "📂 Lecture du fichier de config : $config_file"
  fi

  jq -r --arg p "$period" '.ListHomePod[] | select(.[$p] == true) | .name' "$config_file"
}

set_volume_for_outputs() {
  local volume="$1"
  shift
  local outputs=("$@")

  for name in "${outputs[@]}"; do
    local id=$(curl -s "http://${OWNTONE_HOST}:${OWNTONE_PORT}/api/outputs" | jq -r --arg NAME "$name" '.outputs[] | select(.name == $NAME) | .id')
    if [ -n "$id" ]; then
      curl -s -X PUT "http://${OWNTONE_HOST}:${OWNTONE_PORT}/api/outputs/${id}" \
        -H "Content-Type: application/json" \
        -d "{\"volume\":${volume}}" > /dev/null
    fi
  done
}

play_file_on_outputs() {
  local track_arg="$1"
  shift
  local outputs=("$@")
  local track_uri

  if [[ "$track_arg" =~ ^[0-9]+$ ]]; then
    track_uri="library:track:${track_arg}"
  else
    track_uri="$track_arg"
  fi

  if [[ -z "$track_uri" ]]; then
    log ERROR "❌ Aucun track_id/URI fourni"
    return 1
  fi

  if [[ ${#outputs[@]} -eq 0 ]]; then
    log ERROR "❌ Aucun HomePod fourni"
    return 1
  fi

  log DEBUG "▶️ Lecture du track URI: $track_uri"
  log DEBUG "🟢 Activation des outputs: ${outputs[*]}"

  local ids=()
  for name in "${outputs[@]}"; do
    local outid
    outid=$(curl -s "http://${OWNTONE_HOST}:${OWNTONE_PORT}/api/outputs" \
      | jq -r --arg name "$name" '.outputs[] | select(.name == $name) | .id')
    if [[ -n "$outid" ]]; then
      ids+=("$outid")
      log DEBUG "✅ Output trouvé: $name → $outid"
    else
      log WARN "⚠️ Output ABSENT: $name"
    fi
  done

  if [[ ${#ids[@]} -eq 0 ]]; then
    log ERROR "❌ Aucune sortie valide"
    return 1
  fi

  curl -s -X PUT "http://${OWNTONE_HOST}:${OWNTONE_PORT}/api/outputs/set" \
    -H "Content-Type: application/json" \
    -d "{\"outputs\": $(printf '%s\n' "${ids[@]}" | jq -R . | jq -s .)}" \
    > /dev/null

  log DEBUG "➕ Ajout de la piste à la queue et lecture"
  curl -s -X POST "http://${OWNTONE_HOST}:${OWNTONE_PORT}/api/queue/items/add?uris=${track_uri}&clear=true&playback=start" \
    > /dev/null

  log INFO "✅ Déclenchement fini: track $track_uri sur ${outputs[*]}"
}

CURRENT_PERIOD=$(get_current_period)
log DEBUG "📆 Période actuelle : $CURRENT_PERIOD"
readarray -t HOMEPODS < <(get_outputs_for_period "$CURRENT_PERIOD")
if [ ${#HOMEPODS[@]} -eq 0 ]; then
  log WARN "⚠️ Aucun HomePod configuré pour la période '$CURRENT_PERIOD'"
  exit 0
fi

log DEBUG "📦 HomePods détectés pour cette période : ${HOMEPODS[*]}"

if [[ "$CURRENT_PERIOD" == "evening" ]]; then
  ADHAN_VOLUME=20
fi

set_volume_for_outputs "$ADHAN_VOLUME" "${HOMEPODS[@]}"
play_file_on_outputs "1" "${HOMEPODS[@]}"