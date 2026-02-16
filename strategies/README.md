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
| 01 | ImpactReactive_v1 | Bump to 150 bps on large trades, decay 3 bps/trade back to 80 bps base | 379.78 | Matches static 80 bps but doesn't beat it — arbs are too rare at this fee level for impact detection to help |

## Phase 3: Theory-Constrained Search (Paired-Seed Evaluation)

All candidates evaluated against static 80 bps using paired-seed comparison
(same seeds for both strategies, compute per-seed delta). This reduces
variance and enables detection of smaller improvements.

### Stage 1: Broad Screen (200 sims, paired vs static 80 bps)

| Name | Family | Config | Delta | SE | t-stat | Win% |
|------|--------|--------|-------|-----|--------|------|
| A1 | StaticAsym | bid=82, ask=78 | +0.00 | 0.00 | +1.57 | 53% |
| A2 | StaticAsym | bid=84, ask=76 | +0.00 | 0.00 | +1.58 | 54% |
| A3 | StaticAsym | bid=78, ask=82 | -0.00 | 0.00 | -1.70 | 47% |
| A4 | StaticAsym | bid=85, ask=75 | +0.00 | 0.00 | +1.55 | 52% |
| V1 | VolResponsive | base=80, lam=0.94 | -45.40 | 1.03 | -44.28 | 0% |
| V2 | VolResponsive | base=80, lam=0.90 | -45.20 | 1.02 | -44.13 | 0% |
| V3 | VolResponsive | base=80, lam=0.94, scale=1.5 | -45.53 | 1.02 | -44.48 | 0% |
| V4 | VolResponsive | base=78, lam=0.94 | -42.26 | 0.98 | -43.21 | 0% |
| D1 | DirAdjust | base=80, dir=2 | -2.46 | 0.04 | -69.50 | 0% |
| D2 | DirAdjust | base=80, dir=3 | -3.67 | 0.05 | -70.24 | 0% |
| D3 | DirAdjust | base=80, dir=4 | -4.85 | 0.07 | -69.86 | 0% |
| D4 | DirAdjust | base=80, dir=1 | -1.23 | 0.02 | -69.29 | 0% |
| **C1** | **Combined** | **base=80, regime=3, dir=2** | **+25.76** | **0.46** | **+55.75** | **100%** |
| **C2** | **Combined** | **base=80, regime=0, dir=2** | **+25.15** | **0.44** | **+57.26** | **100%** |
| **C3** | **Combined** | **base=80, regime=3, dir=0** | **+28.06** | **0.48** | **+58.61** | **100%** |
| **C4** | **Combined** | **base=78, regime=3, dir=2** | **+26.00** | **0.43** | **+60.03** | **100%** |
| **C5** | **Combined** | **base=80, regime=2, dir=1** | **+26.84** | **0.47** | **+57.35** | **100%** |
| **C6** | **Combined** | **base=82, regime=3, dir=2** | **+25.44** | **0.49** | **+51.54** | **100%** |

Key findings:
- **Static Asymmetric**: zero impact — asymmetry around 80 bps doesn't help
- **Vol Responsive (absolute EWMA)**: badly miscalibrated, delta -45 — NOMINAL_VAR too low
- **Directional**: harmful, delta -1 to -5 — gives arbs cheaper back-leg trades
- **Combined (dual-EWMA ratio)**: massive improvement, delta +25 to +28 — self-calibrating vol ratio works

### Stage 2: Narrow (500 sims, top 8)

| Name | Delta | SE | t-stat | Win% |
|------|-------|-----|--------|------|
| Combined_80_3_0 | +28.25 | 0.30 | +93.98 | 100% |
| Combined_80_2_1 | +26.99 | 0.29 | +92.82 | 100% |
| Combined_78_3_2 | +26.24 | 0.27 | +96.76 | 100% |
| Combined_80_3_2 | +25.96 | 0.29 | +90.18 | 100% |
| Combined_82_3_2 | +25.60 | 0.31 | +83.47 | 100% |
| Combined_80_0_2 | +25.31 | 0.27 | +92.62 | 100% |
| StaticAsym_85_75 | -0.00 | 0.00 | -0.11 | 49% |
| StaticAsym_84_76 | -0.00 | 0.00 | -0.10 | 50% |

### Stage 3: Final Validation (1000 sims, top 3)

| Rank | Name | Edge | Delta | SE | t-stat | Win% |
|------|------|------|-------|-----|--------|------|
| **1** | **Combined_80_3_0** | **407.97** | **+27.92** | **0.22** | **+127.91** | **100%** |
| 2 | Combined_80_2_1 | 406.70 | +26.64 | 0.21 | +126.67 | 100% |
| 3 | Combined_78_3_2 | 405.94 | +25.88 | 0.20 | +131.35 | 100% |

**Winner: Combined_80_3_0** (DualEWMA_VolRegime_80_3) — edge 407.97, delta +27.92 vs static 80 bps.
