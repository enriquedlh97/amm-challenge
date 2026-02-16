// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import {AMMStrategyBase} from "./AMMStrategyBase.sol";
import {TradeInfo} from "./IAMMStrategy.sol";
contract Strategy is AMMStrategyBase {
    uint256 internal constant FEE = 82 * BPS;
    function afterInitialize(uint256, uint256) external override returns (uint256 bidFee, uint256 askFee) { return (FEE, FEE); }
    function afterSwap(TradeInfo calldata) external override returns (uint256 bidFee, uint256 askFee) { return (FEE, FEE); }
    function getName() external pure override returns (string memory) { return "Static"; }
}
