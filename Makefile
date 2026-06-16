.PHONY: up down logs test shell migrate

up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f api

logs-all:
	docker compose logs -f

test:
	docker compose run --rm api pytest -v

shell:
	docker compose exec api bash

migrate:
	docker compose exec api /entrypoint.sh migrate

# Arranque limpio: elimina volúmenes (borra la BD)
reset:
	docker compose down -v
	docker compose up --build -d
