"""Paired-seed evaluation harness for AMM strategies.

Runs candidate and baseline strategies on identical seeds and computes
per-seed edge deltas to dramatically reduce variance in comparisons.

Usage:
  # Compare a candidate against static 80 bps (default baseline):
  uv run python scripts/paired_eval.py strategies/my_strat.sol --sims 200

  # Compare two .sol files:
  uv run python scripts/paired_eval.py strategies/a.sol --baseline strategies/b.sol --sims 200

  # Run full search protocol across all candidate families:
  uv run python scripts/paired_eval.py --search \
      --stage1-sims 200 --stage2-sims 500 --stage3-sims 1000
"""

import argparse
import math
import sys
from pathlib import Path

import numpy as np

import amm_sim_rs
from amm_competition.competition.config import (
    BASELINE_SETTINGS,
    BASELINE_VARIANCE,
    baseline_nominal_retail_rate,
    baseline_nominal_retail_size,
    baseline_nominal_sigma,
)
from amm_competition.competition.match import MatchRunner
from amm_competition.evm.adapter import EVMStrategyAdapter
from amm_competition.evm.baseline import load_vanilla_strategy

STRATEGIES_DIR = Path(__file__).resolve().parent.parent / "strategies"

# ── Strategy Templates ───────────────────────────────────────────────────────

STATIC_ASYM_TEMPLATE = """\
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {{AMMStrategyBase}} from "./AMMStrategyBase.sol";
import {{TradeInfo}} from "./IAMMStrategy.sol";

/// @title Static Asymmetric Fee Strategy
/// @notice Fixed asymmetric bid/ask fees
/// Storage: none needed
contract Strategy is AMMStrategyBase {{
    uint256 internal constant BID_FEE = {bid_bps} * BPS;
    uint256 internal constant ASK_FEE = {ask_bps} * BPS;

    function afterInitialize(uint256, uint256)
        external override returns (uint256 bidFee, uint256 askFee)
    {{
        return (clampFee(BID_FEE), clampFee(ASK_FEE));
    }}

    function afterSwap(TradeInfo calldata)
        external override returns (uint256 bidFee, uint256 askFee)
    {{
        return (clampFee(BID_FEE), clampFee(ASK_FEE));
    }}

    function getName() external pure override returns (string memory) {{
        return "StaticAsym_{bid_bps}_{ask_bps}";
    }}
}}
"""

STATIC_SYM_TEMPLATE = """\
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {{AMMStrategyBase}} from "./AMMStrategyBase.sol";
import {{TradeInfo}} from "./IAMMStrategy.sol";

contract Strategy is AMMStrategyBase {{
    function afterInitialize(uint256, uint256)
        external override returns (uint256 bidFee, uint256 askFee)
    {{
        uint256 fee = bpsToWad({bps});
        return (fee, fee);
    }}

    function afterSwap(TradeInfo calldata)
        external override returns (uint256 bidFee, uint256 askFee)
    {{
        uint256 fee = bpsToWad({bps});
        return (fee, fee);
    }}

    function getName() external pure override returns (string memory) {{
        return "Static_{bps}";
    }}
}}
"""

VOL_RESPONSIVE_TEMPLATE = """\
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {{AMMStrategyBase}} from "./AMMStrategyBase.sol";
import {{TradeInfo}} from "./IAMMStrategy.sol";

/// @title Volatility-Responsive Fee Strategy
/// @notice Adjusts fee based on EWMA of squared spot price returns.
///         Fee = baseFee * (0.5 + 0.5 * ewmaVar / nominalVar), clamped.
///
/// Storage layout:
///   slots[0] = prevSpotPrice (WAD)
///   slots[1] = ewmaVariance (WAD-scaled)
///   slots[2] = lastTimestamp
///   slots[3] = initialized (0 or 1)
contract Strategy is AMMStrategyBase {{
    uint256 internal constant BASE_FEE = {base_bps} * BPS;
    uint256 internal constant LAMBDA = {lambda_e18};
    uint256 internal constant ONE_MINUS_LAMBDA = WAD - LAMBDA;
    uint256 internal constant NOMINAL_VAR = {nominal_var};
    uint256 internal constant VOL_SCALE = {vol_scale_e18};
    uint256 internal constant HALF_WAD = WAD / 2;
    uint256 internal constant MIN_MULTIPLIER = HALF_WAD;
    uint256 internal constant MAX_MULTIPLIER = 2 * WAD;

    function afterInitialize(uint256 initialX, uint256 initialY)
        external override returns (uint256 bidFee, uint256 askFee)
    {{
        slots[0] = wdiv(initialY, initialX);
        slots[1] = NOMINAL_VAR;
        slots[3] = 1;
        return (clampFee(BASE_FEE), clampFee(BASE_FEE));
    }}

    function afterSwap(TradeInfo calldata trade)
        external override returns (uint256 bidFee, uint256 askFee)
    {{
        uint256 spotPrice = wdiv(trade.reserveY, trade.reserveX);
        uint256 prevSpot = slots[0];
        uint256 ewmaVar = slots[1];

        if (slots[3] == 1 && prevSpot > 0) {{
            uint256 delta = absDiff(spotPrice, prevSpot);
            uint256 sqReturn = wdiv(wmul(delta, delta), wmul(prevSpot, prevSpot));
            ewmaVar = wmul(LAMBDA, ewmaVar) + wmul(ONE_MINUS_LAMBDA, sqReturn);
            slots[1] = ewmaVar;
        }}

        slots[0] = spotPrice;
        slots[2] = trade.timestamp;

        uint256 ratio = wdiv(ewmaVar, NOMINAL_VAR);
        uint256 scaledRatio = wmul(VOL_SCALE, ratio);
        uint256 multiplier = HALF_WAD + scaledRatio / 2;
        if (multiplier < MIN_MULTIPLIER) multiplier = MIN_MULTIPLIER;
        if (multiplier > MAX_MULTIPLIER) multiplier = MAX_MULTIPLIER;

        uint256 fee = clampFee(wmul(BASE_FEE, multiplier));
        return (fee, fee);
    }}

    function getName() external pure override returns (string memory) {{
        return "VolResponsive_{base_bps}";
    }}
}}
"""

DIR_ADJUST_TEMPLATE = """\
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {{AMMStrategyBase}} from "./AMMStrategyBase.sol";
import {{TradeInfo}} from "./IAMMStrategy.sol";

/// @title Directional Adjustment Fee Strategy
/// @notice Adjusts fees based on trade direction — charges more for repeated
///         same-direction trades (likely informed flow).
///
/// Storage layout:
///   slots[0] = lastTradeIsBuy (0 or 1)
///   slots[1] = initialized (0 or 1)
contract Strategy is AMMStrategyBase {{
    uint256 internal constant BASE_FEE = {base_bps} * BPS;
    uint256 internal constant DIR_ADJUST = {dir_bps} * BPS;

    function afterInitialize(uint256, uint256)
        external override returns (uint256 bidFee, uint256 askFee)
    {{
        return (clampFee(BASE_FEE), clampFee(BASE_FEE));
    }}

    function afterSwap(TradeInfo calldata trade)
        external override returns (uint256 bidFee, uint256 askFee)
    {{
        uint256 fee = BASE_FEE;
        uint256 bidF;
        uint256 askF;

        if (slots[1] == 1) {{
            if (trade.isBuy) {{
                bidF = fee + DIR_ADJUST;
                askF = fee > DIR_ADJUST ? fee - DIR_ADJUST : 0;
            }} else {{
                bidF = fee > DIR_ADJUST ? fee - DIR_ADJUST : 0;
                askF = fee + DIR_ADJUST;
            }}
        }} else {{
            bidF = fee;
            askF = fee;
        }}

        slots[0] = trade.isBuy ? 1 : 0;
        slots[1] = 1;

        return (clampFee(bidF), clampFee(askF));
    }}

    function getName() external pure override returns (string memory) {{
        return "DirAdjust_{base_bps}_{dir_bps}";
    }}
}}
"""

COMBINED_TEMPLATE = """\
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {{AMMStrategyBase}} from "./AMMStrategyBase.sol";
import {{TradeInfo}} from "./IAMMStrategy.sol";

/// @title Combined Vol+Regime+Direction Strategy
/// @notice Three-layer fee adjustment:
///   1. Volatility: scale base fee by EWMA variance ratio
///   2. Regime: shift fee based on short/long variance ratio
///   3. Direction: asymmetric adjustment based on last trade direction
///
/// Storage layout:
///   slots[0] = lastTimestamp
///   slots[1] = prevSpotPrice (WAD)
///   slots[2] = shortTermVar (WAD, fast EWMA lambda=0.90)
///   slots[3] = longTermVar (WAD, slow EWMA lambda=0.98)
///   slots[4] = lastTradeIsBuy (0 or 1)
///   slots[5] = initialized (0 or 1)
contract Strategy is AMMStrategyBase {{
    uint256 internal constant BASE_FEE = {base_bps} * BPS;
    uint256 internal constant VOL_SCALE = {vol_scale_e18};
    uint256 internal constant REGIME_ADJUST = {regime_bps} * BPS;
    uint256 internal constant DIR_ADJUST = {dir_bps} * BPS;

    uint256 internal constant LAMBDA_SHORT = 900000000000000000;
    uint256 internal constant ONE_MINUS_SHORT = 100000000000000000;
    uint256 internal constant LAMBDA_LONG = 980000000000000000;
    uint256 internal constant ONE_MINUS_LONG = 20000000000000000;

    uint256 internal constant HALF_WAD = WAD / 2;
    uint256 internal constant INIT_VAR = 2e12;

    function afterInitialize(uint256 initialX, uint256 initialY)
        external override returns (uint256 bidFee, uint256 askFee)
    {{
        slots[1] = wdiv(initialY, initialX);
        slots[2] = INIT_VAR;
        slots[3] = INIT_VAR;
        slots[5] = 1;
        return (clampFee(BASE_FEE), clampFee(BASE_FEE));
    }}

    function afterSwap(TradeInfo calldata trade)
        external override returns (uint256 bidFee, uint256 askFee)
    {{
        uint256 spotPrice = wdiv(trade.reserveY, trade.reserveX);
        uint256 prevSpot = slots[1];
        uint256 shortVar = slots[2];
        uint256 longVar = slots[3];

        // --- Layer 0: Update EWMA variance estimates ---
        if (slots[5] == 1 && prevSpot > 0) {{
            uint256 delta = absDiff(spotPrice, prevSpot);
            uint256 sqReturn = wdiv(wmul(delta, delta), wmul(prevSpot, prevSpot));
            shortVar = wmul(LAMBDA_SHORT, shortVar) + wmul(ONE_MINUS_SHORT, sqReturn);
            longVar = wmul(LAMBDA_LONG, longVar) + wmul(ONE_MINUS_LONG, sqReturn);
            slots[2] = shortVar;
            slots[3] = longVar;
        }}

        slots[0] = trade.timestamp;
        slots[1] = spotPrice;
        slots[5] = 1;

        // --- Layer 1: Vol-adjusted base fee ---
        uint256 fee = BASE_FEE;
        if (longVar > 0) {{
            uint256 ratio = wdiv(shortVar, longVar);
            uint256 scaledHalf = wmul(HALF_WAD, ratio);
            uint256 multiplier = HALF_WAD + scaledHalf;
            if (multiplier > 2 * WAD) multiplier = 2 * WAD;
            if (multiplier < HALF_WAD) multiplier = HALF_WAD;
            fee = wmul(BASE_FEE, multiplier);
        }}

        // --- Layer 2: Regime adjustment ---
        if (REGIME_ADJUST > 0 && longVar > 0) {{
            if (shortVar > longVar) {{
                fee = fee + REGIME_ADJUST;
            }} else if (fee > REGIME_ADJUST) {{
                fee = fee - REGIME_ADJUST;
            }}
        }}

        // --- Layer 3: Directional adjustment ---
        uint256 bidF = fee;
        uint256 askF = fee;
        if (DIR_ADJUST > 0) {{
            if (trade.isBuy) {{
                bidF = fee + DIR_ADJUST;
                askF = fee > DIR_ADJUST ? fee - DIR_ADJUST : 0;
            }} else {{
                bidF = fee > DIR_ADJUST ? fee - DIR_ADJUST : 0;
                askF = fee + DIR_ADJUST;
            }}
        }}

        slots[4] = trade.isBuy ? 1 : 0;

        return (clampFee(bidF), clampFee(askF));
    }}

    function getName() external pure override returns (string memory) {{
        return "Combined_{base_bps}_{regime_bps}_{dir_bps}";
    }}
}}
"""


# ── Candidate Definitions ────────────────────────────────────────────────────


def _build_candidates() -> list[dict]:
    """Build the full list of candidates across all families.

    Returns:
        List of dicts with keys: name, template, params.
    """
    candidates = []

    # Family 1: Static Asymmetric
    for name, bid, ask in [
        ("A1", 82, 78),
        ("A2", 84, 76),
        ("A3", 78, 82),
        ("A4", 85, 75),
    ]:
        candidates.append(
            {
                "name": name,
                "family": "StaticAsym",
                "template": STATIC_ASYM_TEMPLATE,
                "params": {"bid_bps": bid, "ask_bps": ask},
            }
        )

    # Family 2: Volatility-Responsive
    # lambda_e18 values: 0.94*1e18, 0.90*1e18
    # vol_scale_e18: 1.0*1e18, 1.5*1e18
    # nominal_var: 2e12 (calibrated estimate)
    for name, base, lam, scale in [
        ("V1", 80, "940000000000000000", "1000000000000000000"),
        ("V2", 80, "900000000000000000", "1000000000000000000"),
        ("V3", 80, "940000000000000000", "1500000000000000000"),
        ("V4", 78, "940000000000000000", "1000000000000000000"),
    ]:
        candidates.append(
            {
                "name": name,
                "family": "VolResponsive",
                "template": VOL_RESPONSIVE_TEMPLATE,
                "params": {
                    "base_bps": base,
                    "lambda_e18": lam,
                    "nominal_var": "2000000000000",
                    "vol_scale_e18": scale,
                },
            }
        )

    # Family 3: Directional
    for name, base, d in [
        ("D1", 80, 2),
        ("D2", 80, 3),
        ("D3", 80, 4),
        ("D4", 80, 1),
    ]:
        candidates.append(
            {
                "name": name,
                "family": "DirAdjust",
                "template": DIR_ADJUST_TEMPLATE,
                "params": {"base_bps": base, "dir_bps": d},
            }
        )

    # Family 4: Combined
    for name, base, vol_s, regime, d in [
        ("C1", 80, "1000000000000000000", 3, 2),
        ("C2", 80, "1000000000000000000", 0, 2),
        ("C3", 80, "1500000000000000000", 3, 0),
        ("C4", 78, "1000000000000000000", 3, 2),
        ("C5", 80, "500000000000000000", 2, 1),
        ("C6", 82, "1000000000000000000", 3, 2),
    ]:
        candidates.append(
            {
                "name": name,
                "family": "Combined",
                "template": COMBINED_TEMPLATE,
                "params": {
                    "base_bps": base,
                    "vol_scale_e18": vol_s,
                    "regime_bps": regime,
                    "dir_bps": d,
                },
            }
        )

    return candidates


# ── Core Evaluation ──────────────────────────────────────────────────────────


def _normal_cdf(x: float) -> float:
    """Standard normal CDF via erfc (good approximation for t-dist when df > 30)."""
    return 0.5 * math.erfc(-x / math.sqrt(2))


def compile_sol(sol_path: Path) -> EVMStrategyAdapter:
    """Compile a .sol file and return an adapter."""
    source = sol_path.read_text()
    return EVMStrategyAdapter.from_source(source)


def compile_source(source: str) -> EVMStrategyAdapter:
    """Compile Solidity source code and return an adapter."""
    return EVMStrategyAdapter.from_source(source)


def generate_strategy(template: str, params: dict) -> str:
    """Generate Solidity source from template and parameters."""
    return template.format(**params)


def build_runner(n_sims: int) -> MatchRunner:
    """Build a MatchRunner with baseline config and n_workers=1."""
    config = amm_sim_rs.SimulationConfig(
        n_steps=BASELINE_SETTINGS.n_steps,
        initial_price=BASELINE_SETTINGS.initial_price,
        initial_x=BASELINE_SETTINGS.initial_x,
        initial_y=BASELINE_SETTINGS.initial_y,
        gbm_mu=BASELINE_SETTINGS.gbm_mu,
        gbm_sigma=baseline_nominal_sigma(),
        gbm_dt=BASELINE_SETTINGS.gbm_dt,
        retail_arrival_rate=baseline_nominal_retail_rate(),
        retail_mean_size=baseline_nominal_retail_size(),
        retail_size_sigma=BASELINE_SETTINGS.retail_size_sigma,
        retail_buy_prob=BASELINE_SETTINGS.retail_buy_prob,
        seed=None,
    )
    return MatchRunner(
        n_simulations=n_sims,
        config=config,
        n_workers=1,
        variance=BASELINE_VARIANCE,
    )


def extract_per_seed_edges(result) -> np.ndarray:
    """Extract per-seed edge array from a MatchResult with stored results."""
    edges = []
    for sim in result.simulation_results:
        edges.append(float(sim.edges["submission"]))
    return np.array(edges)


def paired_compare(
    cand_edges: np.ndarray,
    base_edges: np.ndarray,
) -> dict:
    """Compute paired-seed statistics between candidate and baseline edges.

    Args:
        cand_edges: Per-seed edges for the candidate.
        base_edges: Per-seed edges for the baseline.

    Returns:
        Dict with mean_delta, se, t_stat, p_value, win_rate, etc.
    """
    n = len(cand_edges)
    deltas = cand_edges - base_edges

    mean_delta = float(np.mean(deltas))
    std_delta = float(np.std(deltas, ddof=1)) if n > 1 else 0.0
    se = std_delta / math.sqrt(n) if n > 0 else 0.0
    t_stat = mean_delta / se if se > 0 else 0.0
    # Normal approx for p-value (good for n > 30)
    p_value = 2.0 * (1.0 - _normal_cdf(abs(t_stat))) if se > 0 else 1.0
    win_rate = float(np.mean(deltas > 0))

    return {
        "n": n,
        "cand_mean": float(np.mean(cand_edges)),
        "base_mean": float(np.mean(base_edges)),
        "mean_delta": mean_delta,
        "se": se,
        "t_stat": t_stat,
        "p_value": p_value,
        "win_rate": win_rate,
    }


def run_single_eval(
    candidate_path: Path,
    baseline_path: Path | None,
    n_sims: int,
) -> dict:
    """Run a single paired evaluation between two .sol files.

    Args:
        candidate_path: Path to the candidate .sol file.
        baseline_path: Path to the baseline .sol file (default: static 80 bps).
        n_sims: Number of simulations to run.

    Returns:
        Dict with paired comparison statistics.
    """
    print(f"Compiling candidate: {candidate_path.name}")
    candidate = compile_sol(candidate_path)
    cand_name = candidate.get_name()

    if baseline_path:
        print(f"Compiling baseline: {baseline_path.name}")
        baseline = compile_sol(baseline_path)
    else:
        print("Using default baseline: Static 80 bps")
        source = generate_strategy(STATIC_SYM_TEMPLATE, {"bps": 80})
        baseline = compile_source(source)
    base_name = baseline.get_name()

    normalizer = load_vanilla_strategy()
    runner = build_runner(n_sims)

    print(f"Running {n_sims} sims for candidate ({cand_name})...")
    cand_result = runner.run_match(candidate, normalizer, store_results=True)
    cand_edges = extract_per_seed_edges(cand_result)

    print(f"Running {n_sims} sims for baseline ({base_name})...")
    base_result = runner.run_match(baseline, normalizer, store_results=True)
    base_edges = extract_per_seed_edges(base_result)

    stats = paired_compare(cand_edges, base_edges)
    stats["candidate"] = cand_name
    stats["baseline"] = base_name

    return stats


def print_stats(stats: dict) -> None:
    """Print paired evaluation statistics."""
    print(f"\n{'=' * 60}")
    print(f"  Candidate: {stats['candidate']}")
    print(f"  Baseline:  {stats['baseline']}")
    print(f"  Sims:      {stats['n']}")
    print(f"{'=' * 60}")
    print(f"  Candidate mean edge: {stats['cand_mean']:.2f}")
    print(f"  Baseline mean edge:  {stats['base_mean']:.2f}")
    print(f"  Mean delta:          {stats['mean_delta']:+.2f}")
    print(f"  SE(delta):           {stats['se']:.2f}")
    print(f"  t-stat:              {stats['t_stat']:+.3f}")
    print(f"  p-value:             {stats['p_value']:.4f}")
    print(f"  Win rate:            {stats['win_rate']:.1%}")
    if stats["p_value"] < 0.01:
        sig = "***"
    elif stats["p_value"] < 0.05:
        sig = "**"
    elif stats["p_value"] < 0.10:
        sig = "*"
    else:
        sig = ""
    if stats["mean_delta"] > 0:
        print(f"  => Candidate BETTER by {stats['mean_delta']:.2f} {sig}")
    elif stats["mean_delta"] < 0:
        print(f"  => Candidate WORSE by {abs(stats['mean_delta']):.2f} {sig}")
    else:
        print("  => No difference")
    print()


# ── Search Protocol ──────────────────────────────────────────────────────────


def run_search(
    stage1_sims: int = 200,
    stage2_sims: int = 500,
    stage3_sims: int = 1000,
) -> None:
    """Run the full staged search protocol.

    Stage 0: Lock baseline (static 80 bps) at stage1_sims.
    Stage 1: Broad screen — all candidates at stage1_sims, promote top 8.
    Stage 2: Narrow — top 8 at stage2_sims, promote top 3.
    Stage 3: Final — top 3 at stage3_sims.
    """
    normalizer = load_vanilla_strategy()
    candidates = _build_candidates()

    # ── Stage 0: Lock baseline ───────────────────────────────────────────
    print("=" * 70)
    print(f"  STAGE 0: Lock baseline (Static 80 bps) at {stage1_sims} sims")
    print("=" * 70)

    base_source = generate_strategy(STATIC_SYM_TEMPLATE, {"bps": 80})
    baseline = compile_source(base_source)
    runner = build_runner(stage1_sims)
    base_result = runner.run_match(baseline, normalizer, store_results=True)
    base_edges = extract_per_seed_edges(base_result)
    base_mean = float(np.mean(base_edges))
    print(f"  Baseline mean edge: {base_mean:.2f} ({stage1_sims} sims)")
    print()

    # ── Stage 1: Broad screen ────────────────────────────────────────────
    print("=" * 70)
    print(f"  STAGE 1: Broad screen — {len(candidates)} candidates at {stage1_sims} sims")
    print("=" * 70)

    stage1_results = []
    for i, cand_def in enumerate(candidates):
        name = cand_def["name"]
        source = generate_strategy(cand_def["template"], cand_def["params"])
        try:
            adapter = compile_source(source)
        except Exception as e:
            print(f"  [{i + 1}/{len(candidates)}] {name}: COMPILE FAILED — {e}")
            continue

        cand_name = adapter.get_name()
        print(f"  [{i + 1}/{len(candidates)}] {name} ({cand_name})...", end=" ", flush=True)

        cand_result = runner.run_match(adapter, normalizer, store_results=True)
        cand_edges = extract_per_seed_edges(cand_result)
        stats = paired_compare(cand_edges, base_edges)
        stats["candidate"] = cand_name
        stats["baseline"] = "Static_80"
        stats["def"] = cand_def

        sig = ""
        if stats["p_value"] < 0.01:
            sig = "***"
        elif stats["p_value"] < 0.05:
            sig = "**"
        elif stats["p_value"] < 0.10:
            sig = "*"

        print(
            f"delta={stats['mean_delta']:+.2f}  "
            f"SE={stats['se']:.2f}  "
            f"t={stats['t_stat']:+.2f}  "
            f"win={stats['win_rate']:.0%} {sig}"
        )
        stage1_results.append(stats)

    # Sort by mean delta descending
    stage1_results.sort(key=lambda s: s["mean_delta"], reverse=True)

    # Eliminate anything with mean delta < -5
    filtered = [s for s in stage1_results if s["mean_delta"] >= -5]
    promoted = filtered[:8]

    print(
        f"\n  Stage 1 summary: {len(stage1_results)} evaluated, {len(promoted)} promoted to Stage 2"
    )
    print("  Promoted:")
    for s in promoted:
        print(f"    {s['candidate']}: delta={s['mean_delta']:+.2f} (t={s['t_stat']:+.2f})")
    print()

    if not promoted:
        print("  No candidates survived Stage 1. Stopping.")
        _print_final_summary([], base_mean)
        return

    # ── Stage 2: Narrow evaluation ───────────────────────────────────────
    print("=" * 70)
    print(f"  STAGE 2: Narrow — {len(promoted)} candidates at {stage2_sims} sims")
    print("=" * 70)

    runner2 = build_runner(stage2_sims)
    # Rerun baseline at stage2_sims
    base_result2 = runner2.run_match(baseline, normalizer, store_results=True)
    base_edges2 = extract_per_seed_edges(base_result2)

    stage2_results = []
    for i, s1 in enumerate(promoted):
        cand_def = s1["def"]
        source = generate_strategy(cand_def["template"], cand_def["params"])
        adapter = compile_source(source)
        cand_name = adapter.get_name()
        print(f"  [{i + 1}/{len(promoted)}] {cand_name}...", end=" ", flush=True)

        cand_result = runner2.run_match(adapter, normalizer, store_results=True)
        cand_edges = extract_per_seed_edges(cand_result)
        stats = paired_compare(cand_edges, base_edges2)
        stats["candidate"] = cand_name
        stats["baseline"] = "Static_80"
        stats["def"] = cand_def

        sig = ""
        if stats["p_value"] < 0.01:
            sig = "***"
        elif stats["p_value"] < 0.05:
            sig = "**"
        elif stats["p_value"] < 0.10:
            sig = "*"

        print(
            f"delta={stats['mean_delta']:+.2f}  "
            f"SE={stats['se']:.2f}  "
            f"t={stats['t_stat']:+.2f}  "
            f"win={stats['win_rate']:.0%} {sig}"
        )
        stage2_results.append(stats)

    stage2_results.sort(key=lambda s: s["mean_delta"], reverse=True)

    # Check stop condition
    any_positive = any(s["mean_delta"] > 0 for s in stage2_results)
    if not any_positive:
        print("\n  No candidate shows positive mean delta after Stage 2.")
        print("  Conclusion: practical ceiling is near static 80 bps.")
        _print_final_summary(stage2_results, base_mean)
        return

    promoted2 = [s for s in stage2_results if s["mean_delta"] > 0][:3]
    print(
        f"\n  Stage 2 summary: {len(stage2_results)} evaluated, "
        f"{len(promoted2)} promoted to Stage 3"
    )
    for s in promoted2:
        print(f"    {s['candidate']}: delta={s['mean_delta']:+.2f} (t={s['t_stat']:+.2f})")
    print()

    # ── Stage 3: Final validation ────────────────────────────────────────
    print("=" * 70)
    print(f"  STAGE 3: Final validation — {len(promoted2)} candidates at {stage3_sims} sims")
    print("=" * 70)

    runner3 = build_runner(stage3_sims)
    base_result3 = runner3.run_match(baseline, normalizer, store_results=True)
    base_edges3 = extract_per_seed_edges(base_result3)

    stage3_results = []
    for i, s2 in enumerate(promoted2):
        cand_def = s2["def"]
        source = generate_strategy(cand_def["template"], cand_def["params"])
        adapter = compile_source(source)
        cand_name = adapter.get_name()
        print(f"  [{i + 1}/{len(promoted2)}] {cand_name}...", end=" ", flush=True)

        cand_result = runner3.run_match(adapter, normalizer, store_results=True)
        cand_edges = extract_per_seed_edges(cand_result)
        stats = paired_compare(cand_edges, base_edges3)
        stats["candidate"] = cand_name
        stats["baseline"] = "Static_80"
        stats["def"] = cand_def

        sig = ""
        if stats["p_value"] < 0.01:
            sig = "***"
        elif stats["p_value"] < 0.05:
            sig = "**"
        elif stats["p_value"] < 0.10:
            sig = "*"

        print(
            f"delta={stats['mean_delta']:+.2f}  "
            f"SE={stats['se']:.2f}  "
            f"t={stats['t_stat']:+.2f}  "
            f"win={stats['win_rate']:.0%} {sig}"
        )
        stage3_results.append(stats)

    stage3_results.sort(key=lambda s: s["mean_delta"], reverse=True)
    _print_final_summary(stage3_results, float(np.mean(base_edges3)))


def _print_final_summary(results: list[dict], base_mean: float) -> None:
    """Print the final summary of the search protocol."""
    print("\n" + "=" * 70)
    print("  FINAL SUMMARY")
    print("=" * 70)
    print(f"  Baseline (Static 80 bps) mean edge: {base_mean:.2f}")
    print()

    if not results:
        print("  No candidates to report.")
        print("  Recommendation: submit static 80 bps.")
        return

    best = results[0]
    print("  Ranking:")
    for i, s in enumerate(results):
        marker = " <-- BEST" if i == 0 else ""
        print(
            f"    {i + 1}. {s['candidate']}: "
            f"edge={s['cand_mean']:.2f}  "
            f"delta={s['mean_delta']:+.2f}  "
            f"t={s['t_stat']:+.2f}  "
            f"p={s['p_value']:.4f}{marker}"
        )

    print()
    if best["mean_delta"] > 3 and abs(best["t_stat"]) > 1.5:
        cname = best["candidate"]
        d, t = best["mean_delta"], best["t_stat"]
        print(f"  Recommendation: use {cname} (delta={d:+.2f}, t={t:+.2f})")
    elif best["mean_delta"] > 0:
        print(f"  Marginal improvement: {best['candidate']} (delta={best['mean_delta']:+.2f})")
        print("  Consider submitting this, but static 80 is also a strong choice.")
    else:
        print("  No candidate beats static 80 bps.")
        print("  Recommendation: submit static 80 bps.")


# ── CLI ──────────────────────────────────────────────────────────────────────


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Paired-seed evaluation for AMM strategies",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "candidate",
        nargs="?",
        help="Path to candidate .sol file (for single-pair mode)",
    )
    parser.add_argument(
        "--baseline",
        type=str,
        default=None,
        help="Path to baseline .sol file (default: static 80 bps)",
    )
    parser.add_argument(
        "--sims",
        type=int,
        default=200,
        help="Number of simulations (for single-pair mode)",
    )
    parser.add_argument(
        "--search",
        action="store_true",
        help="Run the full staged search protocol",
    )
    parser.add_argument("--stage1-sims", type=int, default=200)
    parser.add_argument("--stage2-sims", type=int, default=500)
    parser.add_argument("--stage3-sims", type=int, default=1000)

    args = parser.parse_args()

    if args.search:
        run_search(
            stage1_sims=args.stage1_sims,
            stage2_sims=args.stage2_sims,
            stage3_sims=args.stage3_sims,
        )
        return 0

    if not args.candidate:
        parser.error("Provide a candidate .sol file or use --search for batch mode")
        return 1

    candidate_path = Path(args.candidate)
    if not candidate_path.exists():
        print(f"Error: {candidate_path} not found")
        return 1

    baseline_path = Path(args.baseline) if args.baseline else None
    if baseline_path and not baseline_path.exists():
        print(f"Error: {baseline_path} not found")
        return 1

    stats = run_single_eval(candidate_path, baseline_path, args.sims)
    print_stats(stats)
    return 0


if __name__ == "__main__":
    sys.exit(main())
