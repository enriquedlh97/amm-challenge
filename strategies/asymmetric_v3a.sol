// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AMMStrategyBase} from "./AMMStrategyBase.sol";
import {TradeInfo} from "./IAMMStrategy.sol";

/// @title Asymmetric v3a — Static Asymmetric Bid/Ask Fees
/// @notice Exploits the fact that routing uses direction-specific fees.
/// @dev By setting a low bid fee and high ask fee (or vice versa), we create
///      a lower routing threshold for one direction, capturing more volume
///      on that side at lower margin, while extracting higher margin on the
///      other side. Since buy_prob = 0.5, this creates an asymmetric volume
///      profile.
///
///      bid = 60 bps → captures ~36% of sell-X orders (threshold ~15 Y)
///      ask = 100 bps → captures ~14% of buy-X orders (threshold ~35 Y)
///      Hypothesis: total revenue may exceed symmetric 80 bps.
///
/// Storage layout:
///   (no dynamic state — purely static)
contract Strategy is AMMStrategyBase {
    uint256 internal constant BID_FEE = 60 * BPS;
    uint256 internal constant ASK_FEE = 100 * BPS;

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
        return "Asymmetric_v3a_60_100";
    }
}
