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

### Phase 3: Iterate (if time allows)

Potential improvements to explore:
- Asymmetric bid/ask fees
- Volatility estimation from trade patterns
- Time-based decay / regime detection
- Parameter tuning

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

*(To be filled after implementing dynamic strategy)*

## Final Strategy

*(To be filled)*

## What I Would Do With More Time

*(To be filled)*
