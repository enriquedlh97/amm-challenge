// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import {AMMStrategyBase} from "./AMMStrategyBase.sol";
import {TradeInfo} from "./IAMMStrategy.sol";
contract Strategy is AMMStrategyBase {
    uint256 internal constant BID_FEE = 120 * BPS;
    uint256 internal constant ASK_FEE = 40 * BPS;
    function afterInitialize(uint256, uint256) external override returns (uint256 bidFee, uint256 askFee) { return (BID_FEE, ASK_FEE); }
    function afterSwap(TradeInfo calldata) external override returns (uint256 bidFee, uint256 askFee) { return (BID_FEE, ASK_FEE); }
    function getName() external pure override returns (string memory) { return "Asym_120_40"; }
}
