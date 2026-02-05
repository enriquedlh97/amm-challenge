"""Order router with optimal splitting across multiple AMMs."""

import math
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from amm_competition.core.amm import AMM
from amm_competition.core.trade import TradeInfo
from amm_competition.market.retail import RetailOrder


@dataclass
class RoutedTrade:
    """Result of routing a trade to an AMM."""
    amm: AMM
    trade_info: TradeInfo
    amount_y: Decimal  # Y spent (buy) or received (sell)


class OrderRouter:
    """Routes retail orders optimally across AMMs.

    Implements optimal order splitting so that the marginal price is equal
    across all AMMs after the trade. This maximizes execution quality for
    the trader and creates fair competition between AMMs based on their fees.

    For constant product AMMs (xy=k), the optimal split can be computed
    analytically rather than using numerical methods.
    """

    def compute_optimal_split_buy(
        self, amms: list[AMM], total_y: Decimal
    ) -> list[tuple[AMM, Decimal]]:
        """Compute optimal Y split for buying X across multiple AMMs.

        For a trader spending Y to buy X, split the order so that marginal
        prices are equal after execution.

        Uses Uniswap v2 fee-on-input model with γ = 1 - f:
        - Net Y added to reserves: γ * Y_in
        - Output: Δx = x * γ * Δy / (y + γ * Δy)
        - Marginal output: dΔx/dΔy = x * γ * y / (y + γ * Δy)²

        For 2 AMMs, solve for equal marginal prices:
        A_i = sqrt(x_i * γ_i * y_i), r = A_1/A_2
        Δy_1* = (r * (y_2 + γ_2 * Y) - y_1) / (γ_1 + r * γ_2)

        Args:
            amms: List of AMMs to split across
            total_y: Total Y amount to spend

        Returns:
            List of (AMM, Y_amount) tuples for each AMM
        """
        if len(amms) == 0:
            return []

        if len(amms) == 1:
            return [(amms[0], total_y)]

        if len(amms) == 2:
            return self._split_buy_two_amms(amms[0], amms[1], total_y)

        # For >2 AMMs, use iterative pairwise splitting
        # (This is a simplification - true optimal would require solving simultaneously)
        remaining = total_y
        splits = []
        for i, amm in enumerate(amms[:-1]):
            # Split between this AMM and "the rest" (approximated by next AMM)
            pair_split = self._split_buy_two_amms(amm, amms[i + 1], remaining)
            splits.append(pair_split[0])
            remaining = pair_split[1][1]
        splits.append((amms[-1], remaining))
        return splits

    def _split_buy_two_amms(
        self, amm1: AMM, amm2: AMM, total_y: Decimal
    ) -> list[tuple[AMM, Decimal]]:
        """Compute optimal Y split between exactly two AMMs for buying X.

        Uses float internally for performance (sqrt, division are 10-50x faster).
        """
        # Convert to float for fast math
        x1, y1 = float(amm1.reserve_x), float(amm1.reserve_y)
        x2, y2 = float(amm2.reserve_x), float(amm2.reserve_y)
        f1 = float(amm1.current_fees.ask_fee)
        f2 = float(amm2.current_fees.ask_fee)
        Y = float(total_y)

        # γ = 1 - f
        gamma1 = 1.0 - f1
        gamma2 = 1.0 - f2

        # A_i = sqrt(x_i * γ_i * y_i)
        A1 = math.sqrt(x1 * gamma1 * y1)
        A2 = math.sqrt(x2 * gamma2 * y2)

        if A2 == 0:
            return [(amm1, total_y), (amm2, Decimal("0"))]

        # r = A_1 / A_2
        r = A1 / A2

        # Δy_1* = (r * (y_2 + γ_2 * Y) - y_1) / (γ_1 + r * γ_2)
        numerator = r * (y2 + gamma2 * Y) - y1
        denominator = gamma1 + r * gamma2

        if denominator == 0:
            y1_amount = Y / 2.0
        else:
            y1_amount = numerator / denominator

        # Clamp to valid range [0, Y]
        y1_amount = max(0.0, min(Y, y1_amount))
        y2_amount = Y - y1_amount

        return [(amm1, Decimal(str(y1_amount))), (amm2, Decimal(str(y2_amount)))]

    def compute_optimal_split_sell(
        self, amms: list[AMM], total_x: Decimal
    ) -> list[tuple[AMM, Decimal]]:
        """Compute optimal X split for selling X across multiple AMMs.

        For a trader selling X to receive Y, split the order so that marginal
        prices are equal after execution.

        Uses Uniswap v2 fee-on-input model with γ = 1 - f:
        - Net X added to reserves: γ * X_in
        - Output: Δy = y * γ * Δx / (x + γ * Δx)
        - Marginal output: dΔy/dΔx = y * γ * x / (x + γ * Δx)²

        For 2 AMMs, solve for equal marginal prices:
        B_i = sqrt(y_i * γ_i * x_i), r = B_1/B_2
        Δx_1* = (r * (x_2 + γ_2 * X) - x_1) / (γ_1 + r * γ_2)

        Args:
            amms: List of AMMs to split across
            total_x: Total X amount to sell

        Returns:
            List of (AMM, X_amount) tuples for each AMM
        """
        if len(amms) == 0:
            return []

        if len(amms) == 1:
            return [(amms[0], total_x)]

        if len(amms) == 2:
            return self._split_sell_two_amms(amms[0], amms[1], total_x)

        # For >2 AMMs, use iterative pairwise splitting
        remaining = total_x
        splits = []
        for i, amm in enumerate(amms[:-1]):
            pair_split = self._split_sell_two_amms(amm, amms[i + 1], remaining)
            splits.append(pair_split[0])
            remaining = pair_split[1][1]
        splits.append((amms[-1], remaining))
        return splits

    def _split_sell_two_amms(
        self, amm1: AMM, amm2: AMM, total_x: Decimal
    ) -> list[tuple[AMM, Decimal]]:
        """Compute optimal X split between exactly two AMMs for selling X.

        Uses float internally for performance (sqrt, division are 10-50x faster).
        """
        # Convert to float for fast math
        x1, y1 = float(amm1.reserve_x), float(amm1.reserve_y)
        x2, y2 = float(amm2.reserve_x), float(amm2.reserve_y)
        f1 = float(amm1.current_fees.bid_fee)
        f2 = float(amm2.current_fees.bid_fee)
        X = float(total_x)

        # γ = 1 - f
        gamma1 = 1.0 - f1
        gamma2 = 1.0 - f2

        # B_i = sqrt(y_i * γ_i * x_i)
        B1 = math.sqrt(y1 * gamma1 * x1)
        B2 = math.sqrt(y2 * gamma2 * x2)

        if B2 == 0:
            return [(amm1, total_x), (amm2, Decimal("0"))]

        # r = B_1 / B_2
        r = B1 / B2

        # Δx_1* = (r * (x_2 + γ_2 * X) - x_1) / (γ_1 + r * γ_2)
        numerator = r * (x2 + gamma2 * X) - x1
        denominator = gamma1 + r * gamma2

        if denominator == 0:
            x1_amount = X / 2.0
        else:
            x1_amount = numerator / denominator

        # Clamp to valid range [0, X]
        x1_amount = max(0.0, min(X, x1_amount))
        x2_amount = X - x1_amount

        return [(amm1, Decimal(str(x1_amount))), (amm2, Decimal(str(x2_amount)))]

    def route_order(
        self,
        order: RetailOrder,
        amms: list[AMM],
        fair_price: Decimal,
        timestamp: int,
    ) -> list[RoutedTrade]:
        """Route a retail order optimally across AMMs.

        Splits the order to equalize marginal prices across all AMMs,
        giving the trader the best possible execution.
        """
        trades = []

        if order.side == "buy":
            # Trader wants to buy X, spending Y
            total_y = order.size
            splits = self.compute_optimal_split_buy(amms, total_y)

            for amm, y_amount in splits:
                if float(y_amount) <= 0.0001:  # Skip tiny amounts
                    continue

                trade_info = amm.execute_buy_x_with_y(y_amount, timestamp)
                if trade_info is not None:
                    trades.append(RoutedTrade(
                        amm=amm,
                        trade_info=trade_info,
                        amount_y=y_amount,
                    ))

        else:
            # Trader wants to sell X, receiving Y
            # Convert Y-denominated size to X using fair price
            total_x = order.size / fair_price
            splits = self.compute_optimal_split_sell(amms, total_x)

            for amm, x_amount in splits:
                if float(x_amount) <= 0.0001:  # Skip tiny amounts
                    continue

                trade_info = amm.execute_buy_x(x_amount, timestamp)
                if trade_info is not None:
                    trades.append(RoutedTrade(
                        amm=amm,
                        trade_info=trade_info,
                        amount_y=trade_info.amount_y,
                    ))

        return trades

    def route_orders(
        self,
        orders: list[RetailOrder],
        amms: list[AMM],
        fair_price: Decimal,
        timestamp: int,
    ) -> list[RoutedTrade]:
        """Route multiple orders to AMMs with optimal splitting.

        Args:
            orders: List of retail orders
            amms: List of AMMs to route to
            fair_price: Current fair price
            timestamp: Current simulation step

        Returns:
            List of all executed trades across all orders
        """
        all_trades = []
        for order in orders:
            trades = self.route_order(order, amms, fair_price, timestamp)
            all_trades.extend(trades)
        return all_trades
