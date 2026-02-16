// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AMMStrategyBase} from "./AMMStrategyBase.sol";
import {TradeInfo} from "./IAMMStrategy.sol";

/// @title Directional Adjustment Fee Strategy (D1 variant)
/// @notice Adjusts bid/ask fees based on the current trade direction.
///         After a buy (AMM bought X), charges more on next buy and less on sell.
///         After a sell, vice versa. This penalizes repeated same-direction trades
///         (which are more likely informed/arb) and encourages mean-reversion flow.
///
/// Rationale:
///   - Arb trades tend to be unidirectional (correcting spot to fair price).
///   - Retail is random 50/50. By making the next same-direction trade more
///     expensive, we selectively tax informed flow while being neutral to retail.
///
/// Storage layout:
///   slots[0] = lastTradeIsBuy (0 = sell, 1 = buy)
///   slots[1] = initialized (0 or 1)
contract Strategy is AMMStrategyBase {
    // ── Constants ────────────────────────────────────────────────────────

    /// @notice Base fee: 80 bps (optimal static fee)
    uint256 internal constant BASE_FEE = 80 * BPS;

    /// @notice Directional adjustment: 2 bps
    uint256 internal constant DIR_ADJUST = 2 * BPS;

    // ── Interface ────────────────────────────────────────────────────────

    function afterInitialize(uint256, uint256)
        external override returns (uint256 bidFee, uint256 askFee)
    {
        return (clampFee(BASE_FEE), clampFee(BASE_FEE));
    }

    function afterSwap(TradeInfo calldata trade)
        external override returns (uint256 bidFee, uint256 askFee)
    {
        uint256 bidF;
        uint256 askF;

        if (slots[1] == 1) {
            // Adjust fees based on current trade direction:
            // If current trade is a buy, charge more for buys (same direction)
            // and less for sells (opposite direction)
            if (trade.isBuy) {
                bidF = BASE_FEE + DIR_ADJUST;
                askF = BASE_FEE - DIR_ADJUST;
            } else {
                bidF = BASE_FEE - DIR_ADJUST;
                askF = BASE_FEE + DIR_ADJUST;
            }
        } else {
            bidF = BASE_FEE;
            askF = BASE_FEE;
        }

        slots[0] = trade.isBuy ? 1 : 0;
        slots[1] = 1;

        return (clampFee(bidF), clampFee(askF));
    }

    function getName() external pure override returns (string memory) {
        return "DirAdjust_80_2";
    }
}
