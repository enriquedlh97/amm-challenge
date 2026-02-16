// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AMMStrategyBase} from "./AMMStrategyBase.sol";
import {TradeInfo} from "./IAMMStrategy.sol";

/// @title Volatility-Responsive Fee Strategy (V1 variant)
/// @notice Tracks EWMA of squared spot price returns and scales the fee
///         proportionally. Higher realized vol → higher fee (protect from arbs).
///         Lower vol → lower fee (attract more retail).
///
/// Fee formula: baseFee * (0.5 + 0.5 * ewmaVar / nominalVar)
///   - When ewmaVar = nominalVar → fee = baseFee
///   - When ewmaVar = 0          → fee = baseFee * 0.5
///   - When ewmaVar = 2*nominal  → fee = baseFee * 1.5
///   Clamped to [50%, 200%] of baseFee.
///
/// Storage layout:
///   slots[0] = prevSpotPrice (WAD)
///   slots[1] = ewmaVariance (WAD-scaled squared return)
///   slots[2] = lastTimestamp
///   slots[3] = initialized (0 or 1)
contract Strategy is AMMStrategyBase {
    // ── Constants ────────────────────────────────────────────────────────

    /// @notice Base fee: 80 bps (optimal static fee)
    uint256 internal constant BASE_FEE = 80 * BPS;

    /// @notice EWMA decay factor: 0.94 (moderate smoothing)
    uint256 internal constant LAMBDA = 940000000000000000;
    uint256 internal constant ONE_MINUS_LAMBDA = 60000000000000000;

    /// @notice Nominal variance: ~2e-6 in decimal (calibrated per-trade squared return)
    uint256 internal constant NOMINAL_VAR = 2000000000000;

    /// @notice Volatility scale: 1.0 (full responsiveness)
    uint256 internal constant VOL_SCALE = 1000000000000000000;

    uint256 internal constant HALF_WAD = WAD / 2;
    uint256 internal constant MIN_MULTIPLIER = HALF_WAD;
    uint256 internal constant MAX_MULTIPLIER = 2 * WAD;

    // ── Interface ────────────────────────────────────────────────────────

    function afterInitialize(uint256 initialX, uint256 initialY)
        external override returns (uint256 bidFee, uint256 askFee)
    {
        // Initialize spot price and variance estimate
        slots[0] = wdiv(initialY, initialX);
        slots[1] = NOMINAL_VAR;
        slots[3] = 1;
        return (clampFee(BASE_FEE), clampFee(BASE_FEE));
    }

    function afterSwap(TradeInfo calldata trade)
        external override returns (uint256 bidFee, uint256 askFee)
    {
        uint256 spotPrice = wdiv(trade.reserveY, trade.reserveX);
        uint256 prevSpot = slots[0];
        uint256 ewmaVar = slots[1];

        // Update EWMA variance from squared spot return
        if (slots[3] == 1 && prevSpot > 0) {
            uint256 delta = absDiff(spotPrice, prevSpot);
            // sqReturn = (delta/prevSpot)^2 in WAD
            uint256 sqReturn = wdiv(wmul(delta, delta), wmul(prevSpot, prevSpot));
            ewmaVar = wmul(LAMBDA, ewmaVar) + wmul(ONE_MINUS_LAMBDA, sqReturn);
            slots[1] = ewmaVar;
        }

        slots[0] = spotPrice;
        slots[2] = trade.timestamp;

        // Compute fee multiplier: 0.5 + 0.5 * volScale * ewmaVar / nominalVar
        uint256 ratio = wdiv(ewmaVar, NOMINAL_VAR);
        uint256 scaledRatio = wmul(VOL_SCALE, ratio);
        uint256 multiplier = HALF_WAD + scaledRatio / 2;
        if (multiplier < MIN_MULTIPLIER) multiplier = MIN_MULTIPLIER;
        if (multiplier > MAX_MULTIPLIER) multiplier = MAX_MULTIPLIER;

        uint256 fee = clampFee(wmul(BASE_FEE, multiplier));
        return (fee, fee);
    }

    function getName() external pure override returns (string memory) {
        return "VolResponsive_80";
    }
}
