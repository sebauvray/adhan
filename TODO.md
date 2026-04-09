# TODO — Adhan Home

## A faire


- [ ] **Page stats — améliorations futures**
  - [ ] Filtrer la heatmap par mois (pas seulement année)
  - [ ] Export des données (CSV)
  - [ ] Graphique en barres par jour de la semaine

## Fait

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
