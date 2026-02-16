// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AMMStrategyBase} from "./AMMStrategyBase.sol";
import {TradeInfo} from "./IAMMStrategy.sol";

/// @title ImpactReactive v1 — Dynamic Fee Strategy
/// @notice Bumps fees after large trades (likely arbs), decays toward optimal base.
/// @dev Simple "bump and decay" regime: spike to SPIKE_FEE on large impact,
///      then linearly decay DECAY_AMOUNT per afterSwap call back to BASE_FEE.
///
/// Rationale:
///   - Static fee sweep showed 80 bps as optimal (edge 380 vs 344 at 30 bps).
///   - At 80 bps, arbs are rare (no-arb band is ~±0.8%, requiring ~8.5σ moves).
///   - Dynamic value comes from protecting during rare volatility spikes.
///   - Trade impact (amountY / reserveY) distinguishes large trades from retail.
///
/// Storage layout:
///   slots[0] = currentFee    (WAD) — current symmetric fee
///   slots[1] = lastTimestamp        — last observed trade timestamp
///   slots[2..31]                    — reserved for future iterations
contract Strategy is AMMStrategyBase {
    // ── Constants ────────────────────────────────────────────────────────

    /// @notice Base fee: optimal static fee from sweep (80 bps)
    uint256 internal constant BASE_FEE = 80 * BPS;

    /// @notice Spike fee after detecting a large trade (150 bps)
    uint256 internal constant SPIKE_FEE = 150 * BPS;

    /// @notice Trade is "large" if amountY > 0.5% of reserveY
    uint256 internal constant IMPACT_THRESHOLD = WAD / 200;

    /// @notice Fee decays by 3 bps per afterSwap call
    uint256 internal constant DECAY_AMOUNT = 3 * BPS;

    // ── Interface ────────────────────────────────────────────────────────

    function afterInitialize(uint256, uint256)
        external override returns (uint256 bidFee, uint256 askFee)
    {
        slots[0] = BASE_FEE;
        return (BASE_FEE, BASE_FEE);
    }

    function afterSwap(TradeInfo calldata trade)
        external override returns (uint256 bidFee, uint256 askFee)
    {
        uint256 fee = slots[0];

        // Measure trade impact: amountY relative to post-trade reserveY.
        // Safe: reserveY is always > 0 after a valid trade.
        uint256 impact = wdiv(trade.amountY, trade.reserveY);

        if (impact > IMPACT_THRESHOLD) {
            // Large trade detected (likely arb or large informed flow).
            // Spike fee to protect against continued adverse selection.
            if (SPIKE_FEE > fee) {
                fee = SPIKE_FEE;
            }
        } else {
            // Small trade (likely retail). Decay toward base fee.
            if (fee > BASE_FEE + DECAY_AMOUNT) {
                fee = fee - DECAY_AMOUNT;
            } else if (fee > BASE_FEE) {
                fee = BASE_FEE;
            }
        }

        slots[0] = fee;
        slots[1] = trade.timestamp;

        fee = clampFee(fee);
        return (fee, fee);
    }

    function getName() external pure override returns (string memory) {
        return "ImpactReactive_v1";
    }
}
