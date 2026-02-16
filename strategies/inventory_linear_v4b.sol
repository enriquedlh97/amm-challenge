// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AMMStrategyBase} from "./AMMStrategyBase.sol";
import {TradeInfo} from "./IAMMStrategy.sol";

/// @title InventoryLinear v4b — Inventory-Deviation Fee Adjustment
/// @notice Adjusts fees based on how far reserves have drifted from equilibrium.
/// @dev Inspired by Baggiani et al. (2025): "linear fee approximations capture
///      95%+ of optimal revenue." When reserves are balanced (near initial ratio),
///      use base fee. When skewed, adjust fees directionally:
///
///      If we have too much X (reserveX > initialX → spot < fair):
///        - Raise bidFee (discourage more X inflow)
///        - Lower askFee (encourage X outflow / attract buy-X orders)
///      If we have too much Y (reserveX < initialX → spot > fair):
///        - Lower bidFee (encourage X inflow / attract sell-X orders)
///        - Raise askFee (discourage more Y inflow)
///
///      The adjustment is LINEAR in the log-price deviation:
///        deviation = |ln(spot/initial_spot)| ≈ |spot/initial_spot - 1|
///
///      Combined with the routing asymmetry insight: use a higher base bid fee
///      (sell-X orders route to us regardless) and lower base ask fee (to capture
///      more buy-X orders that face the Y-threshold barrier).
///
/// Storage layout:
///   slots[0] = initialSpotPrice (WAD) — set at initialization
///   slots[1] = currentBidFee (WAD)
///   slots[2] = currentAskFee (WAD)
contract Strategy is AMMStrategyBase {
    // ── Constants ────────────────────────────────────────────────────────

    /// @notice Base bid fee (high — sell-X always routes to us)
    uint256 internal constant BASE_BID = 85 * BPS;

    /// @notice Base ask fee (lower — to capture more buy-X orders)
    uint256 internal constant BASE_ASK = 75 * BPS;

    /// @notice Sensitivity of fee adjustment to inventory deviation
    /// @dev At 1% deviation from equilibrium: adjustment = 0.01 * 500 * BPS = 5 bps
    uint256 internal constant INVENTORY_SENSITIVITY = 500 * BPS;

    /// @notice Floor and ceiling for fees
    uint256 internal constant FEE_FLOOR = 50 * BPS;
    uint256 internal constant FEE_CEILING = 120 * BPS;

    // ── Interface ────────────────────────────────────────────────────────

    function afterInitialize(uint256 initialX, uint256 initialY)
        external override returns (uint256 bidFee, uint256 askFee)
    {
        // Store initial spot price for deviation calculation.
        uint256 initSpot = wdiv(initialY, initialX);
        slots[0] = initSpot;
        slots[1] = BASE_BID;
        slots[2] = BASE_ASK;
        return (BASE_BID, BASE_ASK);
    }

    function afterSwap(TradeInfo calldata trade)
        external override returns (uint256 bidFee, uint256 askFee)
    {
        uint256 initSpot = slots[0];
        uint256 currentSpot = wdiv(trade.reserveY, trade.reserveX);

        // Compute deviation: |currentSpot - initSpot| / initSpot (WAD fraction).
        uint256 diff = absDiff(currentSpot, initSpot);
        uint256 deviation = wdiv(diff, initSpot);

        // Compute adjustment: linear in deviation.
        uint256 adjustment = wmul(INVENTORY_SENSITIVITY, deviation);

        uint256 newBidFee;
        uint256 newAskFee;

        if (currentSpot < initSpot) {
            // Spot dropped → we have too much X (or too little Y).
            // Raise bid fee (discourage more X), lower ask fee (encourage X sales).
            newBidFee = BASE_BID + adjustment;
            newAskFee = adjustment < BASE_ASK ? BASE_ASK - adjustment : FEE_FLOOR;
        } else {
            // Spot rose → we have too little X (or too much Y).
            // Lower bid fee (encourage X inflow), raise ask fee (discourage Y inflow).
            newBidFee = adjustment < BASE_BID ? BASE_BID - adjustment : FEE_FLOOR;
            newAskFee = BASE_ASK + adjustment;
        }

        // Apply floor and ceiling.
        if (newBidFee < FEE_FLOOR) newBidFee = FEE_FLOOR;
        if (newAskFee < FEE_FLOOR) newAskFee = FEE_FLOOR;
        if (newBidFee > FEE_CEILING) newBidFee = FEE_CEILING;
        if (newAskFee > FEE_CEILING) newAskFee = FEE_CEILING;

        slots[1] = newBidFee;
        slots[2] = newAskFee;

        return (clampFee(newBidFee), clampFee(newAskFee));
    }

    function getName() external pure override returns (string memory) {
        return "InventoryLinear_v4b";
    }
}
