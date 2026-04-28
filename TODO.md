# TODO — Adhan Home

## A faire

### Audit architecture — priorité haute (fiabilité)

- [ ] **Verrou applicatif `flock` sur `get_time_salat.py`**
  - Le script est appelé depuis 3 sources (cron self-refresh, `/api/refresh`, `/api/config` POST sur changement MOSQUE_URL)
  - Sans verrou, deux exécutions concurrentes peuvent corrompre `/etc/cron.d/salat` (réécriture interleaved → cron ne charge plus rien, plus aucune prière ne sonne, silencieusement)
  - Solution : `fcntl.flock(LOCK_EX | LOCK_NB)` au début du script, exit 0 si déjà tenu

- [ ] **Notification d'échec adhan**
  - Si `curl` OwnTone retourne non-200 dans `adhan.sh`, aujourd'hui c'est juste loggé
  - Solution simple : envoi webhook (ntfy.sh, Discord, email) sur échec

### Audit architecture — priorité moyenne (maintenabilité)

- [ ] **Tests sur les providers Mawaqit** — fixture HTML capturé + parser pour détecter les changements de markup
- [ ] **Réécrire `adhan.sh` en Python** pour supprimer `load_config.py`/`get_homepods.py`/le shell escaping via `eval`
- [ ] **Multi-stage Dockerfile pour le container `adhan`** — image ~800MB aujourd'hui (1.1GB en `AUTONOMOUS=true`)

- [ ] **Activer `PRAGMA foreign_keys = ON` dans `_connect()`**
  - SQLite ne force pas les FK par défaut, donc `ON DELETE SET NULL` / `ON DELETE CASCADE` sont descriptifs uniquement
  - Conséquence concrète : supprimer un user laisse `auth.user_id` orphelin (cosmétique mais sale)
  - Activer PRAGMA + auditer toutes les FK déclarées avant merge

### Page stats — améliorations futures

- [ ] Filtrer la heatmap par mois (pas seulement année)
- [ ] Export des données (CSV)
- [ ] Graphique en barres par jour de la semaine

## Fait

### Audit architecture — quick wins (2026-04-28)

- [x] **Consolidation `/api/config-field` → `/api/config`**
  - Suppression de l'endpoint POST `/api/config` (ConfigPayload complet) qui n'était plus utilisé que par du code mort frontend (`submitSettings`/`loadConfig` orphelins)
  - Suppression du code mort dans `web/static/app.js`
  - Renommage `/api/config-field` → `/api/config` (POST `{table, key, value}`)
  - Ajout de l'auth admin sur cet endpoint (était sans auth — faille)
  - Re-trigger `get_time_salat.py` quand MOSQUE_URL change (sinon crontab obsolète)

- [x] **Hash SHA-256 des tokens API**
  - Tokens stockés en plaintext → désormais hashés (SHA-256 hex digest)
  - `create_token()` génère le plaintext et stocke le hash, retourne le plaintext une seule fois
  - `validate_token()` hash le token reçu et compare
  - Migration `_migrate_hash_tokens` qui hash les tokens plaintext existants au prochain `init_db()`

- [x] **Healthcheck Docker**
  - `web` : `python3 urllib` sur `/api/status` (pas de curl à installer)
  - `adhan` : `pgrep cron && test -s /etc/cron.d/salat` (ajout `procps` au Dockerfile)
  - Détecte un crontab vide ou un cron mort (sinon container "running" mais aucune prière)



- [x] **Alerte pré-iqama par prière**
  - Checkbox par prière + délai personnalisé (+X min)
  - Upload son d'alerte séparé du son adhan
  - Même volume et HomePods que l'adhan
  - Mode alert dans adhan.sh (utilise ALERT_FILE)
  - Cron automatique à heure_iqama + délai

- [x] **Suivi des prières par utilisateur**
  - Tables `users` et `prayer_logs` en SQLite
  - CRUD utilisateurs dans Settings (nom + emoji)
  - Avatars cliquables sous chaque prière sur le dashboard
  - Modal de confirmation + animation confettis
  - Page `/stats` avec classement (mois/année/tout) et heatmap façon GitLab
  - Streak (série de jours consécutifs)
