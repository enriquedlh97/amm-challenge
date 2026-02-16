// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AMMStrategyBase} from "./AMMStrategyBase.sol";
import {TradeInfo} from "./IAMMStrategy.sol";

/// @title Asymmetric v3b — Aggressive Asymmetric Bid/Ask Fees
/// @notice More aggressive asymmetry: very low bid, very high ask.
/// @dev bid = 40 bps → captures ~71% of sell-X orders (threshold ~5 Y)
///      ask = 120 bps → captures ~8% of buy-X orders (threshold ~45 Y)
///      Tests whether extreme asymmetry captures enough volume to offset
///      the margin imbalance.
///
/// Storage layout:
///   (no dynamic state — purely static)
contract Strategy is AMMStrategyBase {
    uint256 internal constant BID_FEE = 40 * BPS;
    uint256 internal constant ASK_FEE = 120 * BPS;

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
        return "Asymmetric_v3b_40_120";
    }
}
