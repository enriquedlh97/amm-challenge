"""Retail trader simulation with Poisson arrivals."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

import numpy as np


@dataclass
class RetailOrder:
    """A retail order to be routed to AMMs."""
    side: str  # "buy" or "sell" (from trader's perspective, re: X)
    size: Decimal  # Size in Y terms (how much Y willing to spend/receive)


class RetailTrader:
    """Generates retail trading flow with Poisson arrivals.

    Retail traders arrive according to a Poisson process and
    submit orders of random size. They are uninformed and
    trade randomly (buy or sell with equal probability by default).
    """

    def __init__(
        self,
        arrival_rate: float = 1.0,
        mean_size: float = 1.0,
        size_sigma: float = 1.2,
        buy_prob: float = 0.5,
        seed: Optional[int] = None,
    ):
        """
        Args:
            arrival_rate: Expected number of trades per time step (lambda)
            mean_size: Mean trade size (in Y terms)
            size_sigma: Lognormal sigma (log-space)
            buy_prob: Probability of a buy order
            seed: Random seed for reproducibility
        """
        self.arrival_rate = arrival_rate
        self.mean_size = mean_size
        self.size_sigma = size_sigma
        self.buy_prob = buy_prob
        self._rng = np.random.default_rng(seed)

    def reset(self, seed: Optional[int] = None) -> None:
        """Reset the random state."""
        if seed is not None:
            self._rng = np.random.default_rng(seed)

    def generate_orders(self) -> list[RetailOrder]:
        """Generate retail orders for one time step.

        Returns:
            List of retail orders (may be empty if no arrivals)
        """
        # Number of arrivals follows Poisson distribution
        n_arrivals = self._rng.poisson(self.arrival_rate)

        if n_arrivals == 0:
            return []

        orders = []
        for _ in range(n_arrivals):
            # Lognormally distributed sizes with mean = mean_size
            sigma = max(self.size_sigma, 0.01)
            mean = max(self.mean_size, 0.01)
            mu = float(np.log(mean) - 0.5 * sigma * sigma)
            size = Decimal(str(self._rng.lognormal(mu, sigma)))

            # Random side
            if self._rng.random() < self.buy_prob:
                side = "buy"  # Trader wants to buy X
            else:
                side = "sell"  # Trader wants to sell X

            orders.append(RetailOrder(side=side, size=size))

        return orders
