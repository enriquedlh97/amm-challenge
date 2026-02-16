"""Sweep asymmetric bid/ask fee combinations.

Tests multiple bid/ask fee pairs to find the optimal asymmetric strategy.
Runs a quick screen (10 sims) for each combination, then reruns top
candidates at full resolution.
"""

import os
import re
import subprocess
import tempfile
from pathlib import Path

TEMPLATE = """\
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {{AMMStrategyBase}} from "./AMMStrategyBase.sol";
import {{TradeInfo}} from "./IAMMStrategy.sol";

contract Strategy is AMMStrategyBase {{
    uint256 internal constant BID_FEE = {bid} * BPS;
    uint256 internal constant ASK_FEE = {ask} * BPS;

    function afterInitialize(uint256, uint256)
        external override returns (uint256 bidFee, uint256 askFee)
    {{
        return (BID_FEE, ASK_FEE);
    }}

    function afterSwap(TradeInfo calldata)
        external override returns (uint256 bidFee, uint256 askFee)
    {{
        return (BID_FEE, ASK_FEE);
    }}

    function getName() external pure override returns (string memory) {{
        return "Asym_{bid}_{ask}";
    }}
}}
"""

STRATEGIES_DIR = Path(__file__).resolve().parent.parent / "strategies"

# Asymmetric pairs to test: (bid_bps, ask_bps)
PAIRS = [
    # Average ~80 bps
    (70, 90),
    (65, 95),
    (55, 105),
    (50, 110),
    (45, 115),
    # Average ~75 bps
    (50, 100),
    (40, 110),
    # Average ~85 bps
    (60, 110),
    (70, 100),
    # Average ~70 bps
    (40, 100),
    (30, 110),
    # Average ~90 bps
    (60, 120),
    (70, 110),
    # Very aggressive
    (30, 130),
    (20, 140),
    # Mild asymmetry
    (75, 85),
]


def run_strategy(bid: int, ask: int, sims: int = 10) -> float | None:
    """Generate and run an asymmetric fee strategy.

    Args:
        bid: Bid fee in basis points.
        ask: Ask fee in basis points.
        sims: Number of simulations to run.

    Returns:
        Average edge score, or None if the run failed.
    """
    code = TEMPLATE.format(bid=bid, ask=ask)

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".sol", delete=False, dir=STRATEGIES_DIR
    ) as f:
        f.write(code)
        path = f.name

    try:
        result = subprocess.run(
            ["uv", "run", "amm-match", "run", path, "--simulations", str(sims)],
            capture_output=True,
            text=True,
            timeout=300,
        )
        output = result.stdout + result.stderr
        match = re.search(r"Edge:\s*([-\d.]+)", output)
        if match:
            return float(match.group(1))
        print(f"  Could not parse output for {bid}/{ask}:\n{output}")
        return None
    except subprocess.TimeoutExpired:
        print(f"  Timeout for {bid}/{ask}")
        return None
    finally:
        os.unlink(path)


def main() -> None:
    """Run the asymmetric fee sweep and print results."""
    sims = 10
    print(f"Running asymmetric fee sweep ({sims} simulations each)\n")
    print(f"{'Bid':>6} {'Ask':>6} {'Avg':>6} {'Edge':>10}")
    print("-" * 32)

    results: dict[tuple[int, int], float] = {}
    for bid, ask in PAIRS:
        avg = (bid + ask) / 2
        print(f"{bid:>6} {ask:>6} {avg:>6.0f}", end="", flush=True)
        edge = run_strategy(bid, ask, sims)
        if edge is not None:
            print(f"{edge:>10.2f}")
            results[(bid, ask)] = edge
        else:
            print(f"{'FAILED':>10}")

    print("\n--- Top 5 ---")
    sorted_results = sorted(results.items(), key=lambda x: x[1], reverse=True)
    for (bid, ask), edge in sorted_results[:5]:
        print(f"  bid={bid}, ask={ask} → edge={edge:.2f}")


if __name__ == "__main__":
    main()
