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
Data-only actor that forwards Interactive Brokers live data to a pluggable sink.
"""

from __future__ import annotations

from typing import Any
from typing import Protocol

from nautilus_trader.common import DataActor
from nautilus_trader.common import DataActorConfig
from nautilus_trader.model import ActorId
from nautilus_trader.model import BarType
from nautilus_trader.model import ClientId
from nautilus_trader.model import InstrumentId


TICKERS = ["AAPL.XNAS", "MSFT.XNAS", "TSLA.XNAS"]
BAR_SPEC = "1-MINUTE-LAST-EXTERNAL"
IB = ClientId.from_str("IB")


class DataSink(Protocol):
    def write_quote(self, **row: Any) -> None: ...
    def write_trade(self, **row: Any) -> None: ...
    def write_bar(self, **row: Any) -> None: ...


class PrintSink:
    """
    Print rows to stdout; replace with a real data layer writer.
    """

    def write_quote(self, **row: Any) -> None:
        print("QUOTE", row, flush=True)

    def write_trade(self, **row: Any) -> None:
        print("TRADE", row, flush=True)

    def write_bar(self, **row: Any) -> None:
        print("BAR", row, flush=True)


class IbDataFeed(DataActor):
    """
    Subscribe to quotes, trades and bars for several tickers and forward them to a sink.

    Callbacks run on the node event loop, so a real sink should enqueue rows and write
    them from a separate thread or process. Prices and sizes are passed as strings to
    preserve exact values.

    """

    def __init__(self, sink: DataSink) -> None:
        super().__init__(DataActorConfig(actor_id=ActorId.from_str("IB-DATA-FEED-001")))
        self.sink = sink
        self.instrument_ids = [InstrumentId.from_str(ticker) for ticker in TICKERS]

    def on_start(self) -> None:
        for instrument_id in self.instrument_ids:
            self.request_instrument(instrument_id, client_id=IB)

    def on_instrument(self, instrument: Any) -> None:
        if instrument.id not in self.instrument_ids:
            return

        self.subscribe_quotes(instrument.id, client_id=IB)
        self.subscribe_trades(instrument.id, client_id=IB)
        self.subscribe_bars(BarType.from_str(f"{instrument.id}-{BAR_SPEC}"), client_id=IB)

    def on_quote(self, quote: Any) -> None:
        self.sink.write_quote(
            instrument_id=str(quote.instrument_id),
            bid=str(quote.bid_price),
            ask=str(quote.ask_price),
            bid_size=str(quote.bid_size),
            ask_size=str(quote.ask_size),
            ts_event=quote.ts_event,
        )

    def on_trade(self, trade: Any) -> None:
        self.sink.write_trade(
            instrument_id=str(trade.instrument_id),
            price=str(trade.price),
            size=str(trade.size),
            aggressor_side=str(trade.aggressor_side),
            ts_event=trade.ts_event,
        )

    def on_bar(self, bar: Any) -> None:
        self.sink.write_bar(
            bar_type=str(bar.bar_type),
            open=str(bar.open),
            high=str(bar.high),
            low=str(bar.low),
            close=str(bar.close),
            volume=str(bar.volume),
            ts_event=bar.ts_event,
        )
