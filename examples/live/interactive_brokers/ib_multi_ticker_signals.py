# -------------------------------------------------------------------------------------------------
#  Copyright (C) 2015-2026 Nautech Systems Pty Ltd. All rights reserved.
#  https://nautechsystems.io
#
#  Licensed under the GNU Lesser General Public License Version 3.0 (the "License");
#  You may not use this file except in compliance with the License.
#  You may obtain a copy of the License at https://www.gnu.org/licenses/lgpl-3.0.en.html
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
# -------------------------------------------------------------------------------------------------
"""
Multi-ticker EMA crossover signal strategy for Interactive Brokers live data.

Each ticker keeps its own indicators and state. Indicators are warmed up from historical
bars, and signals are generated only from live bars. Orders are sent only when
`SEND_ORDERS` is enabled.

"""

from __future__ import annotations

import datetime as dt
import os
from dataclasses import dataclass
from dataclasses import field
from typing import Any

from nautilus_trader.indicators import ExponentialMovingAverage
from nautilus_trader.model import BarType
from nautilus_trader.model import ClientId
from nautilus_trader.model import InstrumentId
from nautilus_trader.model import OrderSide
from nautilus_trader.model import Quantity
from nautilus_trader.model import StrategyId
from nautilus_trader.model import TimeInForce
from nautilus_trader.trading import Strategy
from nautilus_trader.trading import StrategyConfig


TICKERS = ["AAPL.XNAS", "MSFT.XNAS", "TSLA.XNAS"]
BAR_SPEC = "1-MINUTE-LAST-EXTERNAL"
FAST_PERIOD = 10
SLOW_PERIOD = 30
WARMUP_DAYS = 3
TRADE_SIZE = "10"
SEND_ORDERS = os.getenv("SEND_ORDERS", "0").lower() in {"1", "true", "yes", "y"}
IB = ClientId.from_str("IB")


@dataclass
class TickerState:
    bar_type: BarType
    fast: ExponentialMovingAverage = field(
        default_factory=lambda: ExponentialMovingAverage(FAST_PERIOD),
    )
    slow: ExponentialMovingAverage = field(
        default_factory=lambda: ExponentialMovingAverage(SLOW_PERIOD),
    )
    last_ts: int = 0
    prev_diff: float | None = None


class MultiTickerSignalStrategy(Strategy):
    """
    EMA crossover signals for several tickers over one IB connection.
    """

    def __init__(self) -> None:
        super().__init__(
            StrategyConfig(strategy_id=StrategyId.from_str("MULTI-SIGNALS-001")),
        )
        self.states: dict[InstrumentId, TickerState] = {}
        for ticker in TICKERS:
            instrument_id = InstrumentId.from_str(ticker)
            self.states[instrument_id] = TickerState(
                bar_type=BarType.from_str(f"{instrument_id}-{BAR_SPEC}"),
            )

    def on_start(self) -> None:
        for instrument_id in self.states:
            self.request_instrument(instrument_id, client_id=IB)

    def on_instrument(self, instrument: Any) -> None:
        state = self.states.get(instrument.id)
        if state is None:
            return

        start = dt.datetime.now(dt.UTC) - dt.timedelta(days=WARMUP_DAYS)
        self.request_bars(state.bar_type, start=start, client_id=IB)
        self.subscribe_bars(state.bar_type, client_id=IB)

    def on_historical_bars(self, bars: Any) -> None:
        for bar in bars:
            self._update(bar, live=False)

    def on_bar(self, bar: Any) -> None:
        self._update(bar, live=True)

    def _update(self, bar: Any, live: bool) -> None:
        instrument_id = bar.bar_type.instrument_id
        state = self.states.get(instrument_id)

        # Warm-up and live streams can overlap, so process each bar once per ticker
        if state is None or bar.ts_event <= state.last_ts:
            return

        state.last_ts = bar.ts_event
        state.fast.handle_bar(bar)
        state.slow.handle_bar(bar)

        signal = self._signal(state)
        if signal is not None and live:
            self._on_signal(instrument_id, signal, bar)

    def _signal(self, state: TickerState) -> OrderSide | None:
        if not (state.fast.initialized and state.slow.initialized):
            return None

        diff = state.fast.value - state.slow.value
        prev = state.prev_diff
        state.prev_diff = diff

        if prev is None:
            return None
        if prev <= 0 < diff:
            return OrderSide.BUY
        if prev >= 0 > diff:
            return OrderSide.SELL
        return None

    def _on_signal(self, instrument_id: InstrumentId, side: OrderSide, bar: Any) -> None:
        self.log.info(f"SIGNAL {side} {instrument_id} close={bar.close}")

        if not SEND_ORDERS:
            return
        if side == OrderSide.BUY and self.portfolio.is_net_long(instrument_id):
            return
        if side == OrderSide.SELL and self.portfolio.is_net_short(instrument_id):
            return

        order = self.order_factory.market(
            instrument_id=instrument_id,
            order_side=side,
            quantity=Quantity.from_str(TRADE_SIZE),
            time_in_force=TimeInForce.DAY,
        )
        self.submit_order(order, client_id=IB)

    def on_stop(self) -> None:
        for instrument_id in self.states:
            self.cancel_all_orders(instrument_id)
