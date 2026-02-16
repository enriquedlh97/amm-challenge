// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AMMStrategyBase} from "./AMMStrategyBase.sol";
import {TradeInfo} from "./IAMMStrategy.sol";

/// @title EWMAVol v2c — Volatility-Responsive Fee Strategy
/// @notice Adapts fees based on EWMA-estimated realized volatility per step.
/// @dev Only updates the volatility estimate on step boundaries (timestamp
///      changes) to measure the exogenous price process, not within-step
///      trade-to-trade noise. Uses the spot price after the first trade of
///      each step as the reference price.
///
/// Rationale:
///   - Optimal AMM fee scales with σ (volatility per step).
///   - Config randomizes σ ∈ [0.000882, 0.001008]. Adapting to realized σ
///     lets us optimize fees for the actual volatility regime.
///   - EWMA with λ = 0.94 gives ~17-step half-life, responsive but smooth.
///   - Fee = BASE + SCALE * sqrt(ewmaVariance), calibrated so nominal
///     σ ≈ 9.4 bps maps to ~80 bps fee.
///
/// Storage layout:
///   slots[0] = lastTimestamp
///   slots[1] = prevStepSpotPrice (WAD) — spot after first trade of previous step
///   slots[2] = ewmaVariance (WAD-scale)
///   slots[3] = currentFee (WAD)
///   slots[4] = initialized (0 = not yet, 1 = has one step reference)
contract Strategy is AMMStrategyBase {
    // ── Constants ────────────────────────────────────────────────────────

    /// @notice EWMA decay factor λ = 0.94 (in WAD)
    uint256 internal constant LAMBDA = 94 * WAD / 100;

    /// @notice 1 - λ = 0.06 (in WAD)
    uint256 internal constant ONE_MINUS_LAMBDA = 6 * WAD / 100;

    /// @notice Base fee when volatility is zero
    uint256 internal constant BASE_FEE = 40 * BPS;

    /// @notice Scaling factor: maps estimated σ to fee delta.
    /// @dev At nominal σ ≈ 9.4 bps (9.4e14 WAD), target fee = 80 bps.
    ///      80e14 = 40e14 + SCALE * 9.4e14 → SCALE ≈ 4.25
    uint256 internal constant VOL_SCALE = 425 * WAD / 100;

    /// @notice Default fee before we have volatility data
    uint256 internal constant DEFAULT_FEE = 80 * BPS;

    // ── Interface ────────────────────────────────────────────────────────

    function afterInitialize(uint256, uint256)
        external override returns (uint256 bidFee, uint256 askFee)
    {
        slots[3] = DEFAULT_FEE;
        return (DEFAULT_FEE, DEFAULT_FEE);
    }

    function afterSwap(TradeInfo calldata trade)
        external override returns (uint256 bidFee, uint256 askFee)
    {
        uint256 lastTimestamp = slots[0];
        uint256 fee = slots[3];

        if (trade.timestamp > lastTimestamp) {
            // New step boundary — first trade of a new simulation step.
            uint256 spotPrice = wdiv(trade.reserveY, trade.reserveX);

            if (slots[4] == 0) {
                // Very first step: just record reference price.
                slots[1] = spotPrice;
                slots[4] = 1;
            } else {
                // We have a previous step reference — compute return.
                uint256 prevSpot = slots[1];
                uint256 diff = absDiff(spotPrice, prevSpot);
                uint256 relReturn = wdiv(diff, prevSpot);
                uint256 returnSquared = wmul(relReturn, relReturn);

                // Update EWMA variance.
                uint256 ewmaVar = slots[2];
                ewmaVar = wmul(LAMBDA, ewmaVar) + wmul(ONE_MINUS_LAMBDA, returnSquared);
                slots[2] = ewmaVar;

                // Compute std dev (WAD-scale).
                // ewmaVar is WAD-scale. sqrt(ewmaVar * WAD) → WAD-scale stdDev.
                uint256 stdDev = sqrt(ewmaVar * WAD);

                // Fee = BASE + SCALE * stdDev.
                fee = BASE_FEE + wmul(VOL_SCALE, stdDev);
                slots[3] = fee;

                // Update reference price for next step.
                slots[1] = spotPrice;
            }

            slots[0] = trade.timestamp;
        }
        // Same-step trades: just return current fee (no EWMA update).

        fee = clampFee(fee);
        return (fee, fee);
    }

    function getName() external pure override returns (string memory) {
        return "EWMAVol_v2c";
    }
}
