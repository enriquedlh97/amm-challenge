// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AMMStrategyBase} from "./AMMStrategyBase.sol";
import {TradeInfo} from "./IAMMStrategy.sol";

/// @title Directional v2b — Asymmetric Fee Strategy (Nezlobin-Inspired)
/// @notice Sets asymmetric bid/ask fees based on last trade direction.
/// @dev After a trade pushes price in direction D:
///      - Same-direction trades (continuation) pay higher fees — likely adverse.
///      - Opposite-direction trades (rebalancing) pay lower fees — benign flow.
///
/// Rationale:
///   - Nezlobin et al. showed directional fees reduce LVR by 10-13%.
///   - After a buy (AMM bought X, spot price dropped), further buying is
///     potentially adverse. Selling is rebalancing — attract it.
///   - The adjustment is proportional to trade impact (amountY/reserveY),
///     so large trades cause bigger adjustments.
///   - Base fee of 80 bps matches the optimal static fee. Directional
///     adjustments create asymmetric spread around it.
///   - Smaller adjustment scale (0.3x) keeps the fee swing moderate —
///     too large an adjustment undercuts our margin on one side.
///
/// Storage layout:
///   slots[0] = lastBidFee (WAD)
///   slots[1] = lastAskFee (WAD)
contract Strategy is AMMStrategyBase {
    // ── Constants ────────────────────────────────────────────────────────

    /// @notice Base fee around which directional adjustments are made
    uint256 internal constant BASE_FEE = 80 * BPS;

    /// @notice Scaling factor for directional adjustment (0.3x impact in WAD)
    uint256 internal constant ADJUSTMENT_SCALE = 3 * WAD / 10;

    /// @notice Minimum fee floor to avoid zero or negative fees
    uint256 internal constant FEE_FLOOR = 40 * BPS;

    /// @notice Maximum fee ceiling
    uint256 internal constant FEE_CEILING = 150 * BPS;

    // ── Interface ────────────────────────────────────────────────────────

    function afterInitialize(uint256, uint256)
        external override returns (uint256 bidFee, uint256 askFee)
    {
        slots[0] = BASE_FEE;
        slots[1] = BASE_FEE;
        return (BASE_FEE, BASE_FEE);
    }

    function afterSwap(TradeInfo calldata trade)
        external override returns (uint256 bidFee, uint256 askFee)
    {
        // Compute trade impact: amountY relative to post-trade reserveY.
        uint256 impact = wdiv(trade.amountY, trade.reserveY);

        // Scale adjustment: half of impact (in WAD units, so result is WAD fraction).
        uint256 adjustment = wmul(ADJUSTMENT_SCALE, impact);

        // Convert adjustment from WAD fraction to fee units.
        // impact is a WAD fraction (e.g., 0.005 = 5e15 for 0.5% trade).
        // adjustment is half that. We use it directly as a fee delta.
        // For a 0.5% trade: adjustment = 2.5e15 = 25 bps. Reasonable.

        uint256 newBidFee;
        uint256 newAskFee;

        if (trade.isBuy) {
            // AMM bought X (trader sold X) → spot price dropped.
            // Penalize further buying (same direction) with higher bid fee.
            // Attract selling (rebalancing) with lower ask fee.
            newBidFee = BASE_FEE + adjustment;
            newAskFee = adjustment < BASE_FEE ? BASE_FEE - adjustment : FEE_FLOOR;
        } else {
            // AMM sold X (trader bought X) → spot price went up.
            // Attract buying (rebalancing) with lower bid fee.
            // Penalize further selling (same direction) with higher ask fee.
            newBidFee = adjustment < BASE_FEE ? BASE_FEE - adjustment : FEE_FLOOR;
            newAskFee = BASE_FEE + adjustment;
        }

        // Apply floor and ceiling.
        if (newBidFee < FEE_FLOOR) newBidFee = FEE_FLOOR;
        if (newAskFee < FEE_FLOOR) newAskFee = FEE_FLOOR;
        if (newBidFee > FEE_CEILING) newBidFee = FEE_CEILING;
        if (newAskFee > FEE_CEILING) newAskFee = FEE_CEILING;

        slots[0] = newBidFee;
        slots[1] = newAskFee;

        return (clampFee(newBidFee), clampFee(newAskFee));
    }

    function getName() external pure override returns (string memory) {
        return "Directional_v2b";
    }
}
