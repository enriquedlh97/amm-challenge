// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AMMStrategyBase} from "./AMMStrategyBase.sol";
import {TradeInfo} from "./IAMMStrategy.sol";

/// @title Static Fee Strategy
/// @notice Fixed symmetric fee — used as baseline for comparison
contract Strategy is AMMStrategyBase {
    function afterInitialize(uint256, uint256) external override returns (uint256 bidFee, uint256 askFee) {
        uint256 fee = bpsToWad(30);
        return (fee, fee);
    }

    function afterSwap(TradeInfo calldata) external override returns (uint256 bidFee, uint256 askFee) {
        uint256 fee = bpsToWad(30);
        return (fee, fee);
    }

    function getName() external pure override returns (string memory) {
        return "Static 30 bps";
    }
}
