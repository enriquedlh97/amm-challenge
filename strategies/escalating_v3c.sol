// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AMMStrategyBase} from "./AMMStrategyBase.sol";
import {TradeInfo} from "./IAMMStrategy.sol";

/// @title Escalating v3c — Within-Step Fee Escalation
/// @notice Starts with a competitive fee after arb trade, escalates with
///         each subsequent trade within the same step.
/// @dev Exploits sequential retail processing: each trade's afterSwap fires
///      before the next trade is routed. By starting low and escalating,
///      we capture the first (most likely) retail order at competitive rates,
///      then charge more for any additional orders in the same step.
///
///      With Poisson(0.8), ~36% of steps have exactly 1 retail order,
///      ~14% have 2, and ~5% have 3+.
///
/// Storage layout:
///   slots[0] = lastTimestamp
///   slots[1] = tradeCountInStep
contract Strategy is AMMStrategyBase {
    /// @notice Fee for first retail order after arb (competitive)
    uint256 internal constant FIRST_FEE = 50 * BPS;

    /// @notice Fee increment per additional trade within the step
    uint256 internal constant FEE_STEP = 30 * BPS;

    /// @notice Maximum fee ceiling
    uint256 internal constant MAX_STEP_FEE = 150 * BPS;

    function afterInitialize(uint256, uint256)
        external override returns (uint256 bidFee, uint256 askFee)
    {
        uint256 fee = 80 * BPS;
        return (fee, fee);
    }

    function afterSwap(TradeInfo calldata trade)
        external override returns (uint256 bidFee, uint256 askFee)
    {
        uint256 lastTimestamp = slots[0];
        uint256 tradeCount = slots[1];

        if (trade.timestamp > lastTimestamp) {
            // New step — first trade (arb or first retail if no arb).
            // Set competitive fee for the retail window.
            slots[0] = trade.timestamp;
            slots[1] = 1;
            uint256 fee = clampFee(FIRST_FEE);
            return (fee, fee);
        }

        // Same step — escalate fee for subsequent trades.
        tradeCount = tradeCount + 1;
        slots[1] = tradeCount;

        // Fee escalates: FIRST_FEE + (tradeCount - 1) * FEE_STEP
        uint256 fee = FIRST_FEE + (tradeCount - 1) * FEE_STEP;
        if (fee > MAX_STEP_FEE) fee = MAX_STEP_FEE;
        fee = clampFee(fee);
        return (fee, fee);
    }

    function getName() external pure override returns (string memory) {
        return "Escalating_v3c";
    }
}
