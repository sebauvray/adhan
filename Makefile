.PHONY: help up down clean admin admin-list admin-create admin-reset admin-delete

# Pick up CONTAINER_NAME_WEB (and any other override) from .env if present.
ifneq (,$(wildcard .env))
include .env
export
endif

CONTAINER_WEB := $(or $(CONTAINER_NAME_WEB),adhan-web)
ADMIN_CLI     := docker exec -it $(CONTAINER_WEB) python3 /app/cli/admin_reset.py

## Afficher l'aide
help:
	@echo "Usage: make <commande>"
	@echo ""
	@echo "Lifecycle :"
	@echo "  up              Démarrer le projet (build + lancement)"
	@echo "  down            Arrêter le projet"
	@echo "  clean           Tout supprimer (volumes, images, base de données)"
	@echo ""
	@echo "Compte admin (web container doit être up) :"
	@echo "  admin           Menu interactif (list/create/reset/delete)"
	@echo "  admin-list      Lister les comptes admin"
	@echo "  admin-create    Créer un compte         (NAME=<username>)"
	@echo "  admin-reset     Réinitialiser un mdp    (NAME=<username>)"
	@echo "  admin-delete    Supprimer un compte     (NAME=<username>)"

## Démarrer le projet
up:
	docker compose up -d --build

## Arrêter le projet
down:
	docker compose down

## Supprimer totalement le projet (volumes, images, données)
clean:
	docker compose down -v --rmi all

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
