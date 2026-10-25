# macOS / Linux dasturchi buyruqlari. Windows: scripts/dev.ps1
PY ?= python3
VENV := engine/.venv
BIN := $(VENV)/bin

.PHONY: setup test test-ui test-engine test-offline typecheck build-ui lint check-versions licenses ci \
	dev-engine dev-ui sidecar sidecar-dry tauri-dev clean

.PHONY: setup-local setup-local-llm build-local smoke-local

# Apple Silicon local alpha. --consent explicitly allows the initial model download.
# Models are not included in the application bundle; subsequent inference is offline.
setup-local:
	$(PY) -m venv $(VENV)
	$(BIN)/pip install -e "engine[dev,desktop]"
	cd app && npm ci
	$(BIN)/python scripts/setup_local_render.py --install-deps --stage
	$(BIN)/python scripts/bootstrap_local_models.py --download --consent

# Optional real local editing AI. Explicit invocation permits model/runtime downloads.
# An existing LLM default remains selected; use the CLI's --set-default to replace it.
setup-local-llm:
	$(BIN)/python scripts/setup_local_llm.py --stage --model --consent

build-local:
	$(BIN)/python scripts/build_sidecar.py
	cd app && npm run tauri build -- --config src-tauri/tauri.local.conf.json --bundles app
	codesign --force --deep --sign - "app/src-tauri/target/release/bundle/macos/Lahza Studio.app"
	codesign --verify --deep --strict "app/src-tauri/target/release/bundle/macos/Lahza Studio.app"

smoke-local:
	@test -n "$(VIDEO)" || (echo 'VIDEO=/absolute/podcast.mp4 kerak'; exit 1)
	LAHZA_BIN_DIR=$(CURDIR)/app/src-tauri/resources/bin \
		$(BIN)/python scripts/smoke_local.py --video "$(VIDEO)"

setup:
	$(PY) -m venv $(VENV)
	$(BIN)/pip install -e "engine[dev,onnx,fonts]"
	cd app && npm ci

test: test-engine test-ui typecheck

test-engine:
	cd engine && ../$(BIN)/pytest

# NFR-01: tashqi tarmoqqa ulanish urinishi testni yiqitadi (engine/tests/conftest.py).
test-offline:
	cd engine && LAHZA_NO_NETWORK=1 ../$(BIN)/pytest

test-ui:
	cd app && node --test tests/*.test.mjs

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
ci: check-versions lint test-offline test-ui build-ui

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
