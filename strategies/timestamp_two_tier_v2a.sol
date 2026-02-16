// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AMMStrategyBase} from "./AMMStrategyBase.sol";
import {TradeInfo} from "./IAMMStrategy.sol";

/// @title TimestampTwoTier v2a — Dynamic Fee Strategy
/// @notice Exploits within-step timing: arbs trade first, then retail arrives.
/// @dev After a timestamp change (new simulation step), the first trade is
///      likely the arb correcting price. Set LOW fee afterward to attract
///      retail flow in the same step. On subsequent same-step trades (retail),
///      raise fee back to HIGH for the next step's arb.
///
/// Rationale:
///   - Simulation loop per step: price moves → arb trades → retail arrives.
///   - afterSwap fires after each trade. The fee returned applies to the NEXT trade.
///   - After the arb corrects price, lowering the fee captures retail that would
///     otherwise route to the normalizer (which charges fixed 30 bps).
///   - We undercut the normalizer (29 bps < 30 bps) only in the retail window,
///     then raise back to 80 bps before the next step's arb.
///
/// Storage layout:
///   slots[0] = lastTimestamp — last observed trade timestamp
contract Strategy is AMMStrategyBase {
    // ── Constants ────────────────────────────────────────────────────────

    /// @notice Low fee set after first trade of a new step (undercut normalizer)
    uint256 internal constant LOW_FEE = 29 * BPS;

    /// @notice High fee set after retail trades (protect against next step's arb)
    uint256 internal constant HIGH_FEE = 80 * BPS;

    // ── Interface ────────────────────────────────────────────────────────

    function afterInitialize(uint256, uint256)
        external override returns (uint256 bidFee, uint256 askFee)
    {
        // Start with HIGH_FEE — first trade of step 1 will be an arb.
        return (HIGH_FEE, HIGH_FEE);
    }

    function afterSwap(TradeInfo calldata trade)
        external override returns (uint256 bidFee, uint256 askFee)
    {
        uint256 lastTimestamp = slots[0];

        uint256 fee;
        if (trade.timestamp > lastTimestamp) {
            // New step — this trade was the first of the step (likely arb).
            // Set LOW fee to attract retail that follows in this same step.
            fee = LOW_FEE;
        } else {
            // Same step — this trade was retail (or additional arb).
            // Set HIGH fee for the next step's arb.
            fee = HIGH_FEE;
        }

        slots[0] = trade.timestamp;

        fee = clampFee(fee);
        return (fee, fee);
    }

    function getName() external pure override returns (string memory) {
        return "TimestampTwoTier_v2a";
    }
}
