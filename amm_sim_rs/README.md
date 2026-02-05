# AMM Simulation Engine (Rust)

High-performance AMM simulation engine written in Rust for the fee algorithm competition.

## Features

- EVM execution using `revm`
- Parallel simulation with `rayon`
- WAD (18-decimal) fixed-point arithmetic
- GBM price process
- Arbitrageur with closed-form solutions
- Optimal order routing

## Building

```bash
pip install maturin
maturin develop --release
```

## Usage

```python
import amm_sim_rs

# Run batch of simulations
results = amm_sim_rs.run_batch(
    submission_bytecode,
    baseline_bytecode,
    configs,
    n_workers=8
)

# Get win counts
wins_a, wins_b, draws = results.win_counts()
```
