# TODO — Adhan Home

## A faire

- [ ] **Alerte pré-iqama par prière**
  But : alerter l'utilisateur X minutes avant l'iqama pour qu'il se prépare avant d'aller à la mosquée.

  ### Sous-tâches

  **Base de données :**
  - [ ] Ajouter colonne `ALERT_FILE` dans table `owntone` (défaut: `/srv/media/alert.mp3`)
  - [ ] Ajouter colonnes `alert_minutes` (int, 0=désactivé) dans table `prayer_config` pour chaque prière

  **Upload du son d'alerte :**
  - [ ] Nouveau endpoint `POST /api/upload-alert` — sauvegarde en `/srv/media/alert{ext}` (même logique que upload-adhan mais fichier séparé)
  - [ ] Endpoint `DELETE /api/upload-alert` — supprime et reset le path par défaut
  - [ ] OwnTone indexe automatiquement le nouveau fichier (même volume `/srv/media`)

  **Scheduling (cron) :**
  - [ ] Dans `get_time_salat.py`, pour chaque prière ayant `alert_minutes > 0` : calculer `heure_iqama - alert_minutes` et ajouter une ligne cron dédiée
  - [ ] La ligne cron appelle `adhan.sh` avec un flag ou un script dédié `alert.sh` pour jouer le son d'alerte au lieu de l'adhan

  **Script de lecture :**
  - [ ] Créer `alert.sh` (ou ajouter un mode à `adhan.sh`) qui :
    - Charge `ALERT_FILE` depuis la config
    - Résout le track via `resolve_track_uri()` (même mécanisme, chemin différent)
    - Joue sur les mêmes HomePods configurés pour la prière concernée
    - Utilise le même volume ou un volume alerte dédié (à décider)

  **Settings UI :**
  - [ ] Section "Alerte pré-iqama" dans la page Settings
  - [ ] Upload du son d'alerte (composant similaire à l'upload adhan)
  - [ ] Pour chaque prière : sélecteur de minutes avant iqama (0, 5, 10, 15, 20, 25, 30) — 0 = désactivé
  - [ ] Bouton test pour écouter le son d'alerte

  ### Points de décision
  - Volume alerte : même volume que l'adhan de la prière ? ou volume dédié configurable ?
  - HomePods alerte : mêmes speakers que l'adhan ? ou config séparée ?

## Fait

<!-- Items terminés -->
