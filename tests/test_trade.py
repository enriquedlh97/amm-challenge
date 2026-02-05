"""Tests for trade data classes."""

import pytest
from decimal import Decimal

from amm_competition.core.trade import FeeQuote, TradeInfo, TradeSide


class TestFeeQuote:
    def test_create_valid_fee_quote(self):
        quote = FeeQuote(bid_fee=Decimal("0.001"), ask_fee=Decimal("0.002"))
        assert quote.bid_fee == Decimal("0.001")
        assert quote.ask_fee == Decimal("0.002")

    def test_symmetric_fee_quote(self):
        quote = FeeQuote.symmetric(Decimal("0.0025"))
        assert quote.bid_fee == Decimal("0.0025")
        assert quote.ask_fee == Decimal("0.0025")

    def test_reject_negative_bid_fee(self):
        with pytest.raises(ValueError, match="bid_fee must be >= 0"):
            FeeQuote(bid_fee=Decimal("-0.001"), ask_fee=Decimal("0.001"))

    def test_reject_negative_ask_fee(self):
        with pytest.raises(ValueError, match="ask_fee must be >= 0"):
            FeeQuote(bid_fee=Decimal("0.001"), ask_fee=Decimal("-0.001"))

    def test_zero_fees_allowed(self):
        quote = FeeQuote(bid_fee=Decimal("0"), ask_fee=Decimal("0"))
        assert quote.bid_fee == Decimal("0")
        assert quote.ask_fee == Decimal("0")


class TestTradeInfo:
    def test_create_trade_info(self):
        trade = TradeInfo(
            side="buy",
            amount_x=Decimal("10"),
            amount_y=Decimal("1000"),
            timestamp=42,
            reserve_x=Decimal("110"),
            reserve_y=Decimal("9000"),
        )
        assert trade.side == "buy"
        assert trade.amount_x == Decimal("10")
        assert trade.amount_y == Decimal("1000")
        assert trade.timestamp == 42

    def test_implied_price(self):
        trade = TradeInfo(
            side="sell",
            amount_x=Decimal("5"),
            amount_y=Decimal("500"),
            timestamp=0,
            reserve_x=Decimal("95"),
            reserve_y=Decimal("10500"),
        )
        assert trade.implied_price == Decimal("100")

    def test_implied_price_zero_amount(self):
        trade = TradeInfo(
            side="buy",
            amount_x=Decimal("0"),
            amount_y=Decimal("0"),
            timestamp=0,
            reserve_x=Decimal("100"),
            reserve_y=Decimal("10000"),
        )
        assert trade.implied_price == Decimal("0")


class TestTradeSide:
    def test_buy_side(self):
        assert TradeSide.BUY.value == "buy"

    def test_sell_side(self):
        assert TradeSide.SELL.value == "sell"
