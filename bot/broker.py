"""Alpaca paper-trading wrapper.

Entries are OTO orders (market buy that, once filled, places the stop-loss) —
Alpaca brackets/OTO require whole shares, which risk.target_qty guarantees.
client_order_id is derived from (symbol, date), so re-running the bot on the
same day cannot double-enter: Alpaca rejects the duplicate id.
"""
import os
from datetime import date


class DuplicateOrder(Exception):
    """Entry for this (symbol, day) was already submitted."""


class PaperBroker:
    def __init__(self):
        from alpaca.trading.client import TradingClient

        self.client = TradingClient(
            os.environ["ALPACA_API_KEY"], os.environ["ALPACA_SECRET_KEY"], paper=True
        )

    def equity(self) -> float:
        return float(self.client.get_account().equity)

    def position(self, symbol: str) -> tuple[int, float]:
        """(qty, avg_entry_price); (0, 0.0) when flat."""
        from alpaca.common.exceptions import APIError

        try:
            pos = self.client.get_open_position(symbol)
        except APIError:
            return 0, 0.0
        return int(float(pos.qty)), float(pos.avg_entry_price)

    def submit_entry(self, symbol: str, qty: int, stop: float):
        from alpaca.common.exceptions import APIError
        from alpaca.trading.enums import OrderClass, OrderSide, TimeInForce
        from alpaca.trading.requests import MarketOrderRequest, StopLossRequest

        req = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=OrderSide.BUY,
            time_in_force=TimeInForce.DAY,
            order_class=OrderClass.OTO,
            stop_loss=StopLossRequest(stop_price=stop),
            client_order_id=f"spyqqq-{symbol}-{date.today().isoformat()}",
        )
        try:
            return self.client.submit_order(req)
        except APIError as e:
            if "client_order_id must be unique" in str(e):
                raise DuplicateOrder(symbol) from e
            raise

    def exit_position(self, symbol: str):
        """Cancel the resting stop first, then close at market."""
        from alpaca.trading.enums import QueryOrderStatus
        from alpaca.trading.requests import GetOrdersRequest

        open_orders = self.client.get_orders(
            GetOrdersRequest(status=QueryOrderStatus.OPEN, symbols=[symbol])
        )
        for order in open_orders:
            self.client.cancel_order_by_id(order.id)
        return self.client.close_position(symbol)
