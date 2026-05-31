.PHONY: setup dev dev-backend dev-frontend test seed build clean

PYTHON := /opt/homebrew/bin/python3.12

setup: setup-backend setup-frontend

setup-backend:
	cd backend && $(PYTHON) -m venv venv && . venv/bin/activate && pip install -r requirements.txt

setup-frontend:
	cd frontend && npm install

dev:
	@echo "Starting backend and frontend..."
	$(MAKE) dev-backend & $(MAKE) dev-frontend & wait

dev-backend:
	cd backend && . venv/bin/activate && uvicorn app.main:app --reload --port 8000

dev-frontend:
	cd frontend && npm run dev

test: test-backend test-frontend

test-backend:
	cd backend && . venv/bin/activate && pytest

test-frontend:
	cd frontend && npm test

seed:
	cd backend && . venv/bin/activate && python -m app.db.seed

build:
	cd frontend && npm run build
	docker-compose build

clean:
	rm -rf backend/venv backend/__pycache__ backend/*.db
	rm -rf frontend/node_modules frontend/dist
