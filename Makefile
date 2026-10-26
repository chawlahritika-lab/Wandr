PYTHON ?= python3
BACKEND_DIR := backend
VENV ?= .venv
PORT ?= 8001

.PHONY: install build backend-up backend-down frontend-up frontend-build test lint run

install:
	python3 -m venv $(VENV)
	. $(VENV)/bin/activate && pip install -U pip && pip install -r $(BACKEND_DIR)/requirements.txt

build: install
	@echo "Dependencies installed. Backend is ready for uvicorn."

backend-up:
	@if curl -sf http://127.0.0.1:$(PORT)/health >/dev/null; then \
		echo "Backend is already running at http://127.0.0.1:$(PORT)."; \
	else \
		cd $(BACKEND_DIR) && . ../$(VENV)/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port $(PORT) --reload; \
	fi

backend-down:
	@pids=$$(lsof -tiTCP:$(PORT) -sTCP:LISTEN); \
	if [ -n "$$pids" ]; then \
		kill $$pids; \
		echo "Backend stopped."; \
	else \
		echo "Backend is not running."; \
	fi

run: backend-up

frontend-up:
	npm --prefix frontend run dev -- --port 5173

frontend-build:
	npm --prefix frontend run build

test:
	cd $(BACKEND_DIR) && . ../$(VENV)/bin/activate && pytest -q
