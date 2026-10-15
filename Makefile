# macOS / Linux dasturchi buyruqlari. Windows: scripts/dev.ps1
PY ?= python3
VENV := engine/.venv
BIN := $(VENV)/bin

.PHONY: setup test test-engine test-offline typecheck build-ui lint check-versions licenses ci \
	dev-engine dev-ui sidecar sidecar-dry tauri-dev clean

setup:
	$(PY) -m venv $(VENV)
	$(BIN)/pip install -e "engine[dev,onnx,fonts]"
	cd app && npm ci

test: test-engine typecheck

test-engine:
	cd engine && ../$(BIN)/pytest

# NFR-01: tashqi tarmoqqa ulanish urinishi testni yiqitadi (engine/tests/conftest.py).
test-offline:
	cd engine && LAHZA_NO_NETWORK=1 ../$(BIN)/pytest

typecheck:
	cd app && npm run typecheck

build-ui:
	cd app && npm run build

lint:
	$(BIN)/ruff check engine/src engine/tests eval scripts

check-versions:
	$(PY) scripts/check_versions.py

licenses:
	$(BIN)/python scripts/gen_licenses.py

# CI'ning lokal ekvivalenti (cargo check'siz): versiyalar + lint + testlar + UI typecheck va build.
ci: check-versions lint test-offline build-ui

dev-engine:
	LAHZA_DEV=1 LAHZA_TOKEN=dev-token LAHZA_CATALOG=$(CURDIR)/catalog/catalog.json \
		$(BIN)/python -m lahza_engine serve --port 8765

dev-ui:
	cd app && VITE_ENGINE_URL=http://127.0.0.1:8765 VITE_ENGINE_TOKEN=dev-token npm run dev

sidecar:
	$(BIN)/python scripts/build_sidecar.py

sidecar-dry:
	$(BIN)/python scripts/build_sidecar.py --dry-run

tauri-dev: sidecar
	cd app && npm run tauri dev

clean:
	rm -rf build app/dist app/src-tauri/target engine/.pytest_cache
