.PHONY: help up down clean open admin admin-list admin-create admin-reset admin-delete

# Pick up CONTAINER_NAME_API (and any other override) from .env if present.
ifneq (,$(wildcard .env))
include .env
export
endif

CONTAINER_API := $(or $(CONTAINER_NAME_API),adhan-api)
WEB_PORT      := $(or $(WEB_PORT),8080)
DB_PATH       := ./data/adhan.db
ADMIN_CLI     := docker exec -it $(CONTAINER_API) python3 /app/cli/admin_reset.py

## Afficher l'aide
help:
	@echo "Usage: make <commande>"
	@echo ""
	@echo "Lifecycle :"
	@echo "  up              Démarrer le projet (build + lancement)"
	@echo "  down            Arrêter le projet"
	@echo "  clean           Tout supprimer (volumes, images, base de données)"
	@echo "  open            Ouvrir le dashboard dans le navigateur par défaut"
	@echo ""
	@echo "Compte admin (api container doit être up) :"
	@echo "  admin           Menu interactif (list/create/reset/delete)"
	@echo "  admin-list      Lister les comptes admin"
	@echo "  admin-create    Créer un compte         (NAME=<username>)"
	@echo "  admin-reset     Réinitialiser un mdp    (NAME=<username>)"
	@echo "  admin-delete    Supprimer un compte     (NAME=<username>)"

## Démarrer le projet (active le profile correspondant à AUDIO_PROVIDER)
up:
	@PROVIDER=$${AUDIO_PROVIDER:-music-assistant}; \
	echo "→ Audio provider : $$PROVIDER"; \
	COMPOSE_PROFILES=$$PROVIDER docker compose up -d --build --remove-orphans

## Arrêter le projet (englobe tous les profiles audio)
down:
	docker compose --profile music-assistant --profile owntone down

## Supprimer totalement le projet (volumes, images, données)
clean:
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
