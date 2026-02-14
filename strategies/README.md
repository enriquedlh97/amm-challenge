# Experiment Log

All strategies are run locally with `amm-match run <file> --simulations 1000`.

## Static Fee Sweep

| Fee (bps) | Edge (1000 sims) |
|-----------|------------------|
| 10        | 159.19           |
| 20        | 282.49           |
| 30        | 343.60           |
| 40        | 358.61           |
| 50        | 369.45           |
| 60        | 376.23           |
| **80**    | **380.06**       |
| 100       | 374.54           |

Best static fee: **80 bps** (edge 380.06). The normalizer (30 bps) scores 343.60.

## Dynamic Strategies

| # | Strategy | Description | Edge (1000 sims) | Takeaway |
|---|----------|-------------|-------------------|----------|
| 01 | Dynamic v1 | Reactive: raise after big trades, decay | — | — |
