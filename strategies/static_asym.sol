// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AMMStrategyBase} from "./AMMStrategyBase.sol";
import {TradeInfo} from "./IAMMStrategy.sol";

/// @title Static Asymmetric Fee Strategy (A1 variant)
/// @notice Fixed asymmetric bid/ask fees — tests whether mild asymmetry
///         around the 80 bps optimum can capture additional edge.
///
/// Rationale:
///   - Static 80 bps is the best symmetric fee (edge 380.06).
///   - Retail flow may have a directional bias we can exploit.
///   - By charging slightly more on one side, we may improve
///     revenue without losing meaningful routing share.
///
/// Storage: none needed (stateless)
contract Strategy is AMMStrategyBase {
    /// @notice Bid fee: charged when AMM buys X (82 bps)
    uint256 internal constant BID_FEE = 82 * BPS;

    /// @notice Ask fee: charged when AMM sells X (78 bps)
    uint256 internal constant ASK_FEE = 78 * BPS;

    function afterInitialize(uint256, uint256)
        external override returns (uint256 bidFee, uint256 askFee)
    {
        return (clampFee(BID_FEE), clampFee(ASK_FEE));
    }

    function afterSwap(TradeInfo calldata)
        external override returns (uint256 bidFee, uint256 askFee)
    {
        return (clampFee(BID_FEE), clampFee(ASK_FEE));
    }

    function getName() external pure override returns (string memory) {
        return "StaticAsym_82_78";
    }
}
