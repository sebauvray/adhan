.PHONY: help up down clean open admin admin-list admin-create admin-reset admin-delete \
        owntone-install owntone-ensure owntone-up owntone-down owntone-uninstall owntone-clean

# Pick up CONTAINER_NAME_API (and any other override) from .env if present.
ifneq (,$(wildcard .env))
include .env
export
endif

# Native OwnTone (macOS): when OWNTONE_NATIVE=true, Adhan Home builds & runs OwnTone
# on the host (a containerized AirPlay sender can't reach HomePods from the Docker VM IP).
OWNTONE_NATIVE   := $(or $(OWNTONE_NATIVE),false)
OWNTONE_NATIVE_BIN := $(HOME)/owntone_data/usr/sbin/owntone

# When native, expose the absolute media dir to docker-compose: the api container
# bind-mounts it at the same path so uploads land where OwnTone scans.
ifeq ($(OWNTONE_NATIVE),true)
export OWNTONE_MEDIA_DIR := $(or $(OWNTONE_MEDIA_DIR),$(HOME)/Music/OwnTone)
endif

CONTAINER_API := $(or $(CONTAINER_NAME_API),adhan-api)
WEB_PORT      := $(or $(WEB_PORT),8080)
DB_PATH       := ./data/adhan.db
ADMIN_CLI     := docker exec -it $(CONTAINER_API) python3 /app/cli/admin_reset.py

# Absolute host path of this checkout — propagated to docker-compose.yml so
# bind-mount sources resolve to real host paths when the api container later
# spawns provider containers itself.
export ADHAN_HOST_DIR := $(CURDIR)

## Afficher l'aide
help:
	@echo "Usage: make <commande>"
	@echo ""
	@echo "Lifecycle :"
	@echo "  up              Démarrer le projet (build + lancement)"
	@echo "  down            Arrêter le projet"
	@echo "  clean           Tout supprimer (Docker + OwnTone natif si activé)"
	@echo "  open            Ouvrir le dashboard dans le navigateur par défaut"
	@echo ""
	@echo "OwnTone natif (macOS, OWNTONE_NATIVE=true) :"
	@echo "  owntone-install   Installer (deps + build + service launchd)"
	@echo "  owntone-up        (Re)démarrer le service"
	@echo "  owntone-down      Arrêter le service"
	@echo "  owntone-uninstall Désinstaller (garde ta musique)"
	@echo ""
	@echo "Compte admin (api container doit être up) :"
	@echo "  admin           Menu interactif (list/create/reset/delete)"
	@echo "  admin-list      Lister les comptes admin"
	@echo "  admin-create    Créer un compte         (NAME=<username>)"
	@echo "  admin-reset     Réinitialiser un mdp    (NAME=<username>)"
	@echo "  admin-delete    Supprimer un compte     (NAME=<username>)"

## Démarrer le projet
## - Premier lancement (DB vide) : on démarre uniquement api + front. Le provider audio
##   sera lancé à la demande par l'API quand l'user le choisira dans le wizard.
## - Lancements suivants : si la DB contient déjà un AUDIO_PROVIDER en mode bundled,
##   on relance aussi son container pour qu'il survive à un reboot machine.
up: owntone-ensure
	@PROVIDER=$$(sqlite3 $(DB_PATH) "SELECT value FROM config WHERE key='AUDIO_PROVIDER'" 2>/dev/null); \
	MODE=$$(sqlite3 $(DB_PATH) "SELECT value FROM config WHERE key='AUDIO_PROVIDER_MODE'" 2>/dev/null); \
	if [ -n "$$PROVIDER" ] && [ "$$MODE" = "bundled" ]; then \
		echo "→ Audio provider déjà choisi : $$PROVIDER (profile $$PROVIDER actif)"; \
		COMPOSE_PROFILES=$$PROVIDER docker compose up -d --build --remove-orphans; \
	else \
		echo "→ Premier lancement : api + front uniquement (provider audio à choisir dans le wizard)"; \
		docker compose up -d --build --remove-orphans api front; \
	fi

## Installer OwnTone nativement sur le Mac (deps + build + service launchd)
owntone-install:
	bash scripts/install-owntone-native.sh

## Garantir OwnTone natif au démarrage quand OWNTONE_NATIVE=true (appelé par `up`).
## - binaire absent → install complète ; présent → on s'assure juste que le service tourne.
owntone-ensure:
	@if [ "$(OWNTONE_NATIVE)" = "true" ]; then \
		if [ ! -x "$(OWNTONE_NATIVE_BIN)" ]; then \
			echo "→ OwnTone natif absent : installation…"; \
			bash scripts/install-owntone-native.sh; \
		else \
			echo "→ OwnTone natif présent : vérification du service launchd…"; \
			bash scripts/install-owntone-native.sh --service-only; \
		fi; \
	fi

## (Re)démarrer le service OwnTone natif
owntone-up:
	@launchctl kickstart -k gui/$$(id -u)/com.adhanhome.owntone 2>/dev/null \
		&& echo "→ OwnTone natif (re)démarré" \
		|| echo "Service introuvable — lance d'abord : make owntone-install"

## Arrêter le service OwnTone natif
owntone-down:
	@launchctl bootout gui/$$(id -u)/com.adhanhome.owntone 2>/dev/null \
		&& echo "→ OwnTone natif arrêté" \
		|| echo "Service déjà arrêté"

## Désinstaller OwnTone natif (service + build + config + base ; garde la musique)
owntone-uninstall:
	bash scripts/install-owntone-native.sh --uninstall

## Désinstallation native conditionnelle, appelée par `clean`.
owntone-clean:
	@if [ "$(OWNTONE_NATIVE)" = "true" ]; then \
		echo "→ Désinstallation d'OwnTone natif…"; \
		bash scripts/install-owntone-native.sh --uninstall; \
	fi

## Arrêter le projet (englobe tous les profiles audio)
down:
	docker compose --profile music-assistant --profile owntone down

## Supprimer totalement le projet (Docker + OwnTone natif si activé)
clean: owntone-clean
	docker compose --profile music-assistant --profile owntone down -v --rmi all

## Ouvrir le dashboard dans le navigateur par défaut
open:
	@URL=http://localhost:$(WEB_PORT); \
	case "$$(uname -s)" in \
	  Darwin) open "$$URL" ;; \
	  Linux)  xdg-open "$$URL" >/dev/null 2>&1 || echo "Ouvrez manuellement : $$URL" ;; \
	  MINGW*|MSYS*|CYGWIN*) start "$$URL" ;; \
	  *) echo "Ouvrez manuellement : $$URL" ;; \
	esac

## Menu interactif de gestion des comptes admin
admin:
	$(ADMIN_CLI)

## Lister les comptes admin
admin-list:
	$(ADMIN_CLI) list

## Créer un compte admin (usage : make admin-create NAME=jean)
admin-create:
	@if [ -z "$(NAME)" ]; then echo "Usage: make admin-create NAME=<username>"; exit 1; fi
	$(ADMIN_CLI) create $(NAME)

## Réinitialiser un mot de passe (usage : make admin-reset NAME=jean)
admin-reset:
	@if [ -z "$(NAME)" ]; then echo "Usage: make admin-reset NAME=<username>"; exit 1; fi
	$(ADMIN_CLI) reset $(NAME)

## Supprimer un compte admin (usage : make admin-delete NAME=jean)
admin-delete:
	@if [ -z "$(NAME)" ]; then echo "Usage: make admin-delete NAME=<username>"; exit 1; fi
	$(ADMIN_CLI) delete $(NAME)
