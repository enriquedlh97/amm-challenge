// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AMMStrategyBase} from "./AMMStrategyBase.sol";
import {TradeInfo} from "./IAMMStrategy.sol";

/// @title Timestamp v3d — Moderate Two-Tier With Higher Base
/// @notice Alternate between 60 bps (retail window) and 90 bps (arb window).
/// @dev Unlike v2a which undercut the normalizer (29 bps), this uses a more
///      moderate low fee (60 bps) that still captures reasonable margin while
///      having a lower routing threshold. The high fee (90 bps) applies to
///      same-step continuation trades and the next step's arb.
///
///      At 60 bps: routing threshold ~15 Y, captures ~36% of orders.
///      At 90 bps: routing threshold ~30 Y, captures ~17% of orders.
///
/// Storage layout:
///   slots[0] = lastTimestamp
contract Strategy is AMMStrategyBase {
    uint256 internal constant LOW_FEE = 60 * BPS;
    uint256 internal constant HIGH_FEE = 90 * BPS;

    function afterInitialize(uint256, uint256)
        external override returns (uint256 bidFee, uint256 askFee)
    {
        return (HIGH_FEE, HIGH_FEE);
    }

    function afterSwap(TradeInfo calldata trade)
        external override returns (uint256 bidFee, uint256 askFee)
    {
        uint256 lastTimestamp = slots[0];

        uint256 fee;
        if (trade.timestamp > lastTimestamp) {
            // New step — arb just happened. Set low fee for retail.
            fee = LOW_FEE;
        } else {
            // Same step — retail just traded. Set high fee.
            fee = HIGH_FEE;
        }

        slots[0] = trade.timestamp;
        fee = clampFee(fee);
        return (fee, fee);
    }

    function getName() external pure override returns (string memory) {
        return "Timestamp_v3d_60_90";
    }
}
