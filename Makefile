.PHONY: help up down clean

## Afficher l'aide
help:
	@echo "Usage: make <commande>"
	@echo ""
	@echo "Commandes disponibles :"
	@echo "  up      Démarrer le projet (build + lancement)"
	@echo "  down    Arrêter le projet"
	@echo "  clean   Tout supprimer (volumes, images, base de données)"
	@echo "  help    Afficher cette aide"

## Démarrer le projet
up:
	docker compose up -d --build

## Arrêter le projet
down:
	docker compose down

## Supprimer totalement le projet (volumes, images, données locales)
clean:
	docker compose down -v --rmi all
	rm -rf data/adhan.db
