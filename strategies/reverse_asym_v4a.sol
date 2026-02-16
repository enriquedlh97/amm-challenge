// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AMMStrategyBase} from "./AMMStrategyBase.sol";
import {TradeInfo} from "./IAMMStrategy.sol";

/// @title ReverseAsym v4a — Routing-Informed Asymmetric Fees
/// @notice Exploits the directional routing asymmetry caused by reserve ratio.
/// @dev With initial reserves x=100, y=10000, routing thresholds differ:
///      - Sell-X orders (bidFee): threshold ≈ x₀ * ε / (r * γ_norm) in X units.
///        At 90 bps: ~0.30 X. Since mean order = 20 X, virtually ALL orders
///        route to us → charge HIGH bid fee for maximum margin.
///      - Buy-X orders (askFee): threshold ≈ y₀ * ε / (r * γ_norm) in Y units.
///        At 60 bps: ~15 Y. With lognormal mean ≈ 20 Y, captures ~36% of
///        buy orders vs ~22% at 80 bps → set LOWER ask fee for more volume.
///
///      The asymmetry arises because x₀ = 100 (small) → X thresholds tiny,
///      while y₀ = 10000 (large) → Y thresholds meaningful.
///
/// Storage layout:
///   (no dynamic state — purely static asymmetric)
contract Strategy is AMMStrategyBase {
    /// @notice High bid fee — we capture nearly ALL sell-X orders regardless
    uint256 internal constant BID_FEE = 90 * BPS;

    /// @notice Low ask fee — lowers buy-X routing threshold, captures more orders
    uint256 internal constant ASK_FEE = 70 * BPS;

    function afterInitialize(uint256, uint256)
        external override returns (uint256 bidFee, uint256 askFee)
    {
        return (BID_FEE, ASK_FEE);
    }

    function afterSwap(TradeInfo calldata)
        external override returns (uint256 bidFee, uint256 askFee)
    {
        return (BID_FEE, ASK_FEE);
    }

    function getName() external pure override returns (string memory) {
        return "ReverseAsym_v4a_90_70";
    }
}
