// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AMMStrategyBase} from "./AMMStrategyBase.sol";
import {TradeInfo} from "./IAMMStrategy.sol";

/// @title Combined v4c — Timestamp + Routing-Asymmetry + Directional
/// @notice Combines three insights for maximum edge:
///
///   1. ROUTING ASYMMETRY: sell-X orders always route to us (X reserves small),
///      so bidFee can be high. Buy-X orders face a Y-threshold, so askFee
///      should be lower to capture more volume.
///
///   2. TIMESTAMP: After the arb trade (new step), the next trades are retail.
///      We can set a slightly more aggressive ask fee in the retail window
///      to attract buy-X flow, then restore after retail trades.
///
///   3. DIRECTIONAL: After a buy trade (spot dropped), raise bidFee slightly
///      (penalize continuation) and lower askFee (reward rebalancing).
///      Vice versa for sell trades.
///
/// Strategy:
///   New step (after arb):
///     bidFee = 88 bps (high — sell-X always routes)
///     askFee = 68 bps (low — maximize buy-X routing in retail window)
///   Same step (after retail):
///     bidFee = 90 bps + directional adjustment
///     askFee = 78 bps + directional adjustment
///
/// Storage layout:
///   slots[0] = lastTimestamp
///   slots[1] = lastTradeIsBuy (0 = sell, 1 = buy)
contract Strategy is AMMStrategyBase {
    // ── Fee Constants ────────────────────────────────────────────────────

    /// @notice Retail-window fees (after arb, before retail trades)
    uint256 internal constant RETAIL_BID = 88 * BPS;
    uint256 internal constant RETAIL_ASK = 68 * BPS;

    /// @notice Default fees (after retail, before next arb)
    uint256 internal constant DEFAULT_BID = 90 * BPS;
    uint256 internal constant DEFAULT_ASK = 78 * BPS;

    /// @notice Directional adjustment magnitude
    uint256 internal constant DIR_ADJUST = 3 * BPS;

    // ── Interface ────────────────────────────────────────────────────────

    function afterInitialize(uint256, uint256)
        external override returns (uint256 bidFee, uint256 askFee)
    {
        // Start with default (high bid, moderate ask) for first arb.
        return (DEFAULT_BID, DEFAULT_ASK);
    }

    function afterSwap(TradeInfo calldata trade)
        external override returns (uint256 bidFee, uint256 askFee)
    {
        uint256 lastTimestamp = slots[0];

        if (trade.timestamp > lastTimestamp) {
            // New step — first trade (likely arb). Set retail-window fees.
            slots[0] = trade.timestamp;
            slots[1] = trade.isBuy ? 1 : 0;
            return (clampFee(RETAIL_BID), clampFee(RETAIL_ASK));
        }

        // Same step — retail trade just executed.
        // Apply directional adjustment based on the trade direction.
        uint256 newBidFee = DEFAULT_BID;
        uint256 newAskFee = DEFAULT_ASK;

        if (trade.isBuy) {
            // AMM bought X → spot dropped. Penalize more buying, attract selling.
            newBidFee = DEFAULT_BID + DIR_ADJUST;
            newAskFee = DEFAULT_ASK - DIR_ADJUST;
        } else {
            // AMM sold X → spot rose. Attract buying, penalize more selling.
            newBidFee = DEFAULT_BID - DIR_ADJUST;
            newAskFee = DEFAULT_ASK + DIR_ADJUST;
        }

        slots[1] = trade.isBuy ? 1 : 0;

        return (clampFee(newBidFee), clampFee(newAskFee));
    }

    function getName() external pure override returns (string memory) {
        return "Combined_v4c";
    }
}
