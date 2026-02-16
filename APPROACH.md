# AMM Fee Strategy Challenge: Approach

## Problem Understanding

We operate an Automated Market Maker (AMM) that holds two tokens (X and Y) and trades with anyone using the constant product formula (x * y = k). We control **one thing**: the fees we charge on each trade (bid fee for buys, ask fee for sells). After every trade, we can update our fees.

Two types of traders interact with our AMM:
- **Retail traders**: uninformed, pay fees willingly — this is our revenue
- **Arbitrageurs**: informed, exploit stale prices — this is our cost

Our AMM competes against a normalizer AMM running fixed 30 bps fees. Retail flow splits between us based on who offers better prices (lower fees). If our fees are too high, we get no retail volume.

**Objective**: maximize average **edge** (net profit) across 1,000 randomized simulations.

## Methodology

### Phase 1: Static Baselines

Before building anything dynamic, establish how fixed fees perform. This tells us:
- What the baseline landscape looks like
- Whether there's a clear "best static fee"
- How much variance there is across simulations
- What edge values to expect

**Strategies**: fixed symmetric fees at 20, 30, 40, 50, 60, 80, 100 bps.

### Phase 2: Simple Dynamic Strategy

Build a minimal reactive strategy based on observations from Phase 1. The goal is something interpretable — a strategy where we can explain *why* it works in 2 minutes.

Key insight to test: big trades relative to reserves are likely arbitrage (price correction), small trades are likely retail. After a big trade, the price has been corrected, so it's safe to lower fees and attract retail.

### Phase 3: Systematic Parameter Search

Rather than guessing improvements, run a theory-constrained search across four
strategy families, using paired-seed evaluation (same seeds for candidate and
baseline) to cut through noise. The search protocol has three stages:

1. **Broad screen** (200 sims): test all ~18 candidates, promote top 8
2. **Narrow** (500 sims): re-evaluate top 8, promote top 3
3. **Final validation** (1000 sims): confirm top 3 with high statistical power

**Four families tested:**
- **Static Asymmetric**: different bid/ask fees around 80 bps
- **Volatility-Responsive**: EWMA of squared returns vs nominal variance
- **Directional**: adjust fees based on trade direction
- **Combined**: dual-EWMA volatility ratio + regime detection + optional direction

## Observations

### Phase 1 Results

Static fee sweep (1000 sims each):

```
 10 bps → 159.19 edge
 20 bps → 282.49
 30 bps → 343.60  ← normalizer baseline
 40 bps → 358.61
 50 bps → 369.45
 60 bps → 376.23
 80 bps → 380.06  ← best static
100 bps → 374.54
```

Key observations:
1. **Higher fees generally win** — 80 bps beats 30 bps by ~36 points. The arb protection from higher fees outweighs the lost retail volume.
2. **Diminishing returns** — the curve flattens from 50-80 bps and starts declining at 100 bps. At 100 bps we lose too much retail to the competitor.
3. **The normalizer is beatable with static fees alone** — simply setting 80 bps outperforms 30 bps. This suggests the normalizer's fee is suboptimal and there's room for improvement.
4. **10 bps is terrible** — undercutting aggressively gives us volume but arbs destroy us.

This tells us: a good dynamic strategy should default to something in the 50-80 bps range and adjust from there.

### Phase 2 Results

**ImpactReactive_v1**: bump fees to 150 bps after large trades (>0.5% of reserves), decay 3 bps per trade back to 80 bps base.

Result: **379.78 edge** (1000 sims) — essentially matches static 80 bps (380.06) but doesn't beat it.

Key insight from deeper analysis:
- At 80 bps, the no-arb band is ~±0.8%, requiring ~8.5σ price moves (extremely rare with σ ≈ 0.094%/step)
- **Arbs barely trade at this fee level** — the impact detection rarely triggers
- The routing formula is nearly insensitive to fee differences in the 60-100 bps range (~0.04% volume difference)
- **Per-trade fee revenue dominates over volume share** — this is why higher static fees win

This tells us: simply reacting to trade impact is insufficient because the signal (arb trades) is too rare. We need a different approach — either exploit the within-step timing (arb → retail ordering) or find a signal that fires more often.

### Phase 3 Results

The paired search revealed a striking pattern:

**What didn't work:**
- **Static Asymmetry** (delta ≈ 0): Asymmetric bid/ask fees around 80 bps have
  no measurable effect. The routing formula is insensitive to small fee differences
  at this level.
- **Volatility-Responsive with absolute EWMA** (delta ≈ -45): Using EWMA variance
  against a fixed nominal variance badly miscalibrates — the actual per-trade
  squared return (~1.6e-5) is much higher than the nominal (2e-6), so the fee
  is systematically pushed above optimal.
- **Directional Adjustment** (delta ≈ -1 to -5, scaling linearly with adjustment
  size): This creates a cheaper side that arbs can exploit on the return leg of
  round trips. The penalty scales precisely with the adjustment amount.

**What worked spectacularly:**
- **Dual-EWMA Volatility Ratio** (delta ≈ +28): Using the ratio of a fast EWMA
  (lambda=0.90) to a slow EWMA (lambda=0.98) of squared spot returns. This
  self-calibrates per simulation — no need for a nominal variance constant.
  - After large trades: shortVar spikes → fee increases → arb protection
  - During quiet periods: shortVar decays → fee decreases → attracts retail
  - Adding a ±3 bps regime adjustment (based on shortVar vs longVar) provides
    an additional ~2-3 edge points
  - Removing directional adjustment adds ~2 edge points

**Key insight**: Static 80 bps is the best *unconditional* fee. But the dual-EWMA
strategy provides *conditional* optimization — it adapts to each simulation's
realized volatility, effectively choosing a better fee for each market environment.
The hyperparameter variance (sigma: 0.000882-0.001008, retail rate: 0.6-1.0)
means different simulations have different optimal fees, and the strategy learns
which regime it's in.

## Final Strategy

**DualEWMA_VolRegime_80_3** (`strategies/vol_regime_dir_v5.sol`)

Edge: **407.97** (1000 sims) — beats static 80 bps (380.06) by +27.92 points
(t=127.91, p≈0, 100% win rate across 1000 paired seeds).

### How it works

Two layers on top of an 80 bps base fee:

1. **Vol scaling**: `fee = baseFee * (0.5 + 0.5 * shortVar/longVar)`
   - `shortVar`: fast EWMA (lambda=0.90) of squared spot price returns
   - `longVar`: slow EWMA (lambda=0.98) of the same
   - Self-calibrating: no absolute variance threshold needed
   - Clamped to [40, 160] bps range

2. **Regime detection**: `fee += 3 bps` when shortVar > longVar (vol increasing),
   `fee -= 3 bps` otherwise (vol stable/decreasing)

### Storage (5 of 32 slots used)

| Slot | Purpose |
|------|---------|
| 0 | lastTimestamp |
| 1 | prevSpotPrice (WAD) |
| 2 | shortTermVar (fast EWMA, WAD-scaled) |
| 3 | longTermVar (slow EWMA, WAD-scaled) |
| 4 | initialized flag |

### Why no directional adjustment?

The search showed directional adjustment consistently hurts (delta -1 to -5 bps
per bps of adjustment). The mechanism: after a buy, lowering the ask fee gives
arbs a cheaper path on the return leg. Since retail direction is random (50/50),
the asymmetry only benefits informed flow.

## What I Would Do With More Time

1. **Finer parameter grid**: The search tested discrete lambda values (0.90, 0.98).
   A continuous optimization over lambda_short in [0.85, 0.95] and lambda_long in
   [0.96, 0.99] could find the exact optimum.

2. **Regime-dependent base fee**: Instead of a fixed 80 bps base, use the long-term
   variance estimate to shift the base (e.g., 75 bps in low-vol, 85 bps in high-vol).

3. **Multi-step lookback**: The current strategy only uses the latest trade's spot
   change. Tracking cumulative price drift over multiple trades could detect trending
   markets earlier.

4. **Order flow imbalance**: Track the ratio of buy vs sell volume over a window.
   Persistent imbalance suggests informed flow, warranting higher fees on the
   overrepresented side.

5. **Adaptive regime adjustment**: Instead of fixed ±3 bps, scale the regime
   adjustment by the magnitude of the shortVar/longVar ratio deviation.
