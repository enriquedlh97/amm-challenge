.PHONY: test lint validate run sweep check setup

# Defaults
STRATEGY ?= strategies/static_fee.sol
SIMS ?= 1000

# ─── Setup ────────────────────────────────────────────────────────────────────

setup: ## Install all dependencies and build Rust simulator
	uv sync
	uv pip install pytest ruff
	maturin develop --release --manifest-path amm_sim_rs/Cargo.toml

# ─── Quality ──────────────────────────────────────────────────────────────────

lint: ## Lint Python code with ruff
	uv run ruff check scripts/ --fix
	uv run ruff format scripts/

test: ## Run upstream test suite
	uv run python -m pytest tests/ -v

# ─── Strategy ─────────────────────────────────────────────────────────────────

validate: ## Validate a strategy (STRATEGY=path/to/file.sol)
	uv run amm-match validate $(STRATEGY)

run: ## Run a strategy (STRATEGY=path/to/file.sol SIMS=1000)
	uv run amm-match run $(STRATEGY) --simulations $(SIMS)

sweep: ## Run static fee sweep across multiple fee values
	uv run python scripts/sweep_static_fees.py

# ─── Combined ─────────────────────────────────────────────────────────────────

check: lint test validate ## Run all checks: lint, test, validate

# ─── Help ─────────────────────────────────────────────────────────────────────

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'
