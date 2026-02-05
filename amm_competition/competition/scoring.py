"""PNL scoring for AMM competition."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class AMMState:
    """Snapshot of an AMM's state for scoring."""
    name: str
    reserve_x: Decimal
    reserve_y: Decimal
    spot_price: Decimal


def calculate_pnl(
    initial_state: AMMState,
    final_state: AMMState,
    initial_fair_price: Decimal,
    final_fair_price: Decimal,
) -> Decimal:
    """Calculate PNL for an AMM.

    PNL = (X_final * fair_price_final + Y_final) - (X_initial * fair_price_initial + Y_initial)

    This measures the total value change, accounting for:
    - Changes in reserves
    - Changes in the fair price

    Args:
        initial_state: AMM state at start of simulation
        final_state: AMM state at end of simulation
        initial_fair_price: Fair price at start
        final_fair_price: Fair price at end

    Returns:
        PNL in Y terms
    """
    initial_value = (
        initial_state.reserve_x * initial_fair_price + initial_state.reserve_y
    )
    final_value = (
        final_state.reserve_x * final_fair_price + final_state.reserve_y
    )
    return final_value - initial_value


def calculate_return(pnl: Decimal, initial_value: Decimal) -> Decimal:
    """Calculate percentage return.

    Args:
        pnl: Absolute PNL
        initial_value: Initial portfolio value

    Returns:
        Return as a decimal (0.1 = 10%)
    """
    if initial_value == 0:
        return Decimal("0")
    return pnl / initial_value
