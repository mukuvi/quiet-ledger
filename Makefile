PY ?= python3
VENV := .venv
BIN := $(VENV)/bin
MODEL := models/gemma-3-1b-it-Q4_K_M.gguf
LLAMA_REPO := https://github.com/ggml-org/llama.cpp

.PHONY: install models llama run test clean

install:
	$(PY) -m venv $(VENV)
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install -r requirements.txt

models:
	mkdir -p models
	curl -L --fail --progress-bar \
		-o $(MODEL) \
		https://huggingface.co/ggml-org/gemma-3-1b-it-GGUF/resolve/main/gemma-3-1b-it-Q4_K_M.gguf

llama:
	git clone --depth 1 $(LLAMA_REPO) .llama.cpp
	cmake -B .llama.cpp/build -S .llama.cpp -DLLAMA_CURL=OFF -DCMAKE_BUILD_TYPE=Release
	cmake --build .llama.cpp/build -j --target llama-cli
	@echo "Built. Export LLAMA_BIN=$(CURDIR)/.llama.cpp/build/bin/llama-cli"

run:
	$(BIN)/uvicorn app:app --host 127.0.0.1 --port 8000 --reload

test:
	$(BIN)/pytest -q

clean:
	rm -rf .pytest_cache __pycache__ tests/__pycache__
