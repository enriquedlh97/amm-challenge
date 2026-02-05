// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AMMStrategyBase} from "../AMMStrategyBase.sol";
import {IAMMStrategy, TradeInfo} from "../IAMMStrategy.sol";

/// @title Adaptive Strategy
/// @notice Adjusts fees based on recent trade flow imbalance
/// @dev Higher fees when flow is one-sided, lower when balanced
contract Strategy is AMMStrategyBase {
    // Storage slot indices
    uint256 constant SLOT_BUY_VOLUME = 0;   // Cumulative buy volume (WAD)
    uint256 constant SLOT_SELL_VOLUME = 1;  // Cumulative sell volume (WAD)
    uint256 constant SLOT_DECAY_FACTOR = 2; // Volume decay factor (WAD, e.g., 0.95)
    uint256 constant SLOT_BASE_FEE = 3;     // Base fee in WAD

    /// @notice Default base fee: 20 bps
    uint256 constant DEFAULT_BASE_FEE = 20 * BPS;

    /// @notice Decay factor: 95% (volumes decay each trade)
    uint256 constant DEFAULT_DECAY = 95e16; // 0.95 WAD

    /// @notice Maximum fee multiplier: 3x base fee
    uint256 constant MAX_MULTIPLIER = 3 * WAD;

    /// @inheritdoc IAMMStrategy
    function initialize(uint256, uint256) external override returns (uint256 bidFee, uint256 askFee) {
        // Initialize storage
        slots[SLOT_BUY_VOLUME] = 0;
        slots[SLOT_SELL_VOLUME] = 0;
        slots[SLOT_DECAY_FACTOR] = DEFAULT_DECAY;
        slots[SLOT_BASE_FEE] = DEFAULT_BASE_FEE;

        // Start with symmetric base fees
        return (DEFAULT_BASE_FEE, DEFAULT_BASE_FEE);
    }

    /// @inheritdoc IAMMStrategy
    function onTrade(TradeInfo calldata trade) external override returns (uint256 bidFee, uint256 askFee) {
        // Load state
        uint256 buyVol = slots[SLOT_BUY_VOLUME];
        uint256 sellVol = slots[SLOT_SELL_VOLUME];
        uint256 decay = slots[SLOT_DECAY_FACTOR];
        uint256 baseFee = slots[SLOT_BASE_FEE];

        // Decay existing volumes
        buyVol = wmul(buyVol, decay);
        sellVol = wmul(sellVol, decay);

        // Add new trade volume
        if (trade.isBuy) {
            buyVol += trade.amountX;
        } else {
            sellVol += trade.amountX;
        }

        // Store updated volumes
        slots[SLOT_BUY_VOLUME] = buyVol;
        slots[SLOT_SELL_VOLUME] = sellVol;

        // Calculate imbalance ratio
        uint256 totalVol = buyVol + sellVol;
        if (totalVol == 0) {
            return (baseFee, baseFee);
        }

        // Calculate directional imbalance (0 to 1 WAD)
        // 0.5 WAD = perfectly balanced, 0 or 1 = completely one-sided
        uint256 buyRatio = wdiv(buyVol, totalVol);
        uint256 sellRatio = WAD - buyRatio;

        // Fee multiplier increases with imbalance
        // Formula: 1 + 2 * |ratio - 0.5| (ranges from 1x to 2x)
        uint256 imbalance = absDiff(buyRatio, WAD / 2);
        uint256 multiplier = WAD + wmul(imbalance, 2 * WAD);

        // Clamp multiplier
        if (multiplier > MAX_MULTIPLIER) {
            multiplier = MAX_MULTIPLIER;
        }

        // Apply asymmetric fees based on direction
        // Higher fee on the dominant side to discourage further imbalance
        uint256 adjustedFee = wmul(baseFee, multiplier);

        if (buyRatio > sellRatio) {
            // More buys than sells - increase bid fee (when AMM buys more X)
            bidFee = clampFee(adjustedFee);
            askFee = clampFee(baseFee);
        } else {
            // More sells than buys - increase ask fee
            bidFee = clampFee(baseFee);
            askFee = clampFee(adjustedFee);
        }

        return (bidFee, askFee);
    }

    /// @inheritdoc IAMMStrategy
    function getName() external pure override returns (string memory) {
        return "Adaptive";
    }
}
