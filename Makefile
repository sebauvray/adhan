.PHONY: up down clean

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
