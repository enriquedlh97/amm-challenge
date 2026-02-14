# Project Conventions

## Overview

This is a take-home challenge for Galaxy DeFi Trading. We design a dynamic fee strategy for a constant-product AMM. The final submission is a **single `.sol` file** uploaded to ammchallenge.com.

## Repository Structure

```
contracts/src/          # Upstream strategy contracts (DO NOT modify)
strategies/             # Our experiment strategies and logs
scripts/                # Automation scripts (sweep, analysis)
amm_competition/        # Upstream simulation pipeline (DO NOT modify)
amm_sim_rs/             # Upstream Rust simulator (DO NOT modify)
tests/                  # Upstream test suite (DO NOT modify)
APPROACH.md             # Our methodology, observations, and rationale
```

## Engineering Standards

### General

- All code must be production-quality — clean, documented, no hacks
- Run `make check` before every commit to validate all constraints
- Keep git history clean: one logical change per commit, conventional commit messages
- Use `uv run` for all Python commands; never install globally

### Solidity (Strategy Files)

- Contract MUST be named `Strategy` and inherit `AMMStrategyBase`
- Imports MUST be `./AMMStrategyBase.sol` and `./IAMMStrategy.sol` (relative only)
- Fees returned in WAD precision (`bpsToWad(30)` for 30 bps)
- Fee range: 0 to 1000 bps (0% to 10%) — use `clampFee()` on all returned fees
- Storage: only `slots[0]` through `slots[31]` (32 uint256 values)
- Gas limit: 250,000 per function call
- FORBIDDEN: assembly, inline Yul, external calls, contract creation, selfdestruct
- Always validate with `make validate STRATEGY=<file>` before running
- Document each slot's purpose with a comment at the top of the contract

### Python (Scripts)

- Type hints on all function signatures
- Docstrings on all public functions
- Use pathlib for file paths, not string concatenation
- Run ruff for linting: `make lint`

### Documentation

- `APPROACH.md` is the primary deliverable alongside the `.sol` file
- Log every experiment in `strategies/README.md` with edge scores and takeaways
- Document the "why" not just the "what"

## Submission Constraints Checklist

Before submitting, verify ALL of these:

- [ ] Contract is named `Strategy`
- [ ] Inherits from `AMMStrategyBase`
- [ ] Implements `afterInitialize`, `afterSwap`, `getName`
- [ ] Imports use `./AMMStrategyBase.sol` and `./IAMMStrategy.sol`
- [ ] No assembly or inline Yul
- [ ] No external calls (`.call()`, `.delegatecall()`, etc.)
- [ ] No contract creation (`new`, `create`, `create2`)
- [ ] All fees pass through `clampFee()`
- [ ] Storage uses only `slots[0..31]`
- [ ] Each storage slot's purpose is documented
- [ ] `getName()` returns a descriptive string
- [ ] `make validate` passes
- [ ] `make run` completes without errors
- [ ] Edge score is documented in `strategies/README.md`

## Common Commands

```bash
make test               # Run upstream test suite
make validate STRATEGY=strategies/my_strat.sol
make run STRATEGY=strategies/my_strat.sol
make run STRATEGY=strategies/my_strat.sol SIMS=10   # Quick test
make sweep              # Run static fee sweep
make lint               # Lint Python code
make check              # Run all checks (lint + test + validate)
```
