"""Sweep static fee values and record edge scores.

Generates temporary strategy files with fixed symmetric fees,
runs each through the simulation, and reports comparative results.
"""

import os
import re
import subprocess
import tempfile
from pathlib import Path

# fmt: off
TEMPLATE = """\
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
        return "Static {bps} bps";
    }}
}}
"""
# fmt: on

STRATEGIES_DIR = Path(__file__).resolve().parent.parent / "strategies"
FEE_VALUES = [10, 20, 30, 40, 50, 60, 80, 100]
SIMULATIONS = 1000


def run_strategy(bps: int) -> float | None:
    """Generate a static fee strategy, run it, and return the average edge.

    Args:
        bps: Fee in basis points to test.

    Returns:
        Average edge score, or None if the run failed.
    """
    code = TEMPLATE.format(bps=bps)

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".sol", delete=False, dir=STRATEGIES_DIR
    ) as f:
        f.write(code)
        path = f.name

    try:
        result = subprocess.run(
            ["uv", "run", "amm-match", "run", path, "--simulations", str(SIMULATIONS)],
            capture_output=True,
            text=True,
            timeout=300,
        )
        output = result.stdout + result.stderr
        match = re.search(r"Edge:\s*([-\d.]+)", output)
        if match:
            return float(match.group(1))
        print(f"  Could not parse output for {bps} bps:\n{output}")
        return None
    except subprocess.TimeoutExpired:
        print(f"  Timeout for {bps} bps")
        return None
    finally:
        os.unlink(path)


def main() -> None:
    """Run the static fee sweep and print results."""
    print(f"Running static fee sweep ({SIMULATIONS} simulations each)\n")
    print(f"{'Fee (bps)':<12} {'Edge':>10}")
    print("-" * 24)

    results: dict[int, float] = {}
    for bps in FEE_VALUES:
        print(f"{bps:<12}", end="", flush=True)
        edge = run_strategy(bps)
        if edge is not None:
            print(f"{edge:>10.2f}")
            results[bps] = edge
        else:
            print(f"{'FAILED':>10}")

    print("\n--- Summary ---")
    if results:
        best_bps = max(results, key=results.get)
        print(f"Best static fee: {best_bps} bps with edge {results[best_bps]:.2f}")


if __name__ == "__main__":
    main()
