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

demo:
	docker compose up -d
	@echo "Esperando API..."
	@for i in 1 2 3 4 5 6 7 8 9 10; do \
		curl -sf http://localhost:8000/health > /dev/null 2>&1 && break || sleep 3; \
	done
	cd backend && python ../tools/cargar_docs_prueba.py
	cp tools/datos_muestra/transmisiones_muestra.csv data/watch/transmisiones_$(shell date +%Y%m%d).csv
	cp tools/datos_muestra/matriculas_muestra.csv data/watch/matriculas_$(shell date +%Y%m%d).csv
	@sleep 5
	@echo "Tyrion corriendo en http://localhost:8000"
