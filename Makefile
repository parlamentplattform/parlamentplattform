.PHONY: dev test lint run seed check

dev:            ## Entwicklungsumgebung aufsetzen
	python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"

test:           ## Alle Tests mit Abdeckungsmessung des Kerns
	.venv/bin/coverage run -m pytest -q && .venv/bin/coverage report

lint:           ## Statische Prüfung
	.venv/bin/ruff check .

run:            ## Entwicklungsserver (SQLite)
	.venv/bin/python manage.py migrate && .venv/bin/python manage.py runserver

seed:           ## Demo-Daten einspielen
	.venv/bin/python manage.py demo_seed

check:          ## Django-Systemcheck inkl. Deployment-Hinweisen
	.venv/bin/python manage.py check --deploy
