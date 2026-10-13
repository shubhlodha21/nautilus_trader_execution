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
Run a data-only node that streams IB Gateway live data for several tickers.

No execution client is added, so no orders can be placed.

"""

from __future__ import annotations

import os

from _common import build_ib_live_node
from _common import env_int
from _common import instrument_provider_config
from ib_data_feed import TICKERS
from ib_data_feed import IbDataFeed
from ib_data_feed import PrintSink


DEFAULT_GATEWAY_PORT = 4002
DEFAULT_CLIENT_ID = 21


def main() -> None:
    """
    Run the example.
    """
    host = os.getenv("IB_V2_HOST", "127.0.0.1")
    port = env_int("IB_V2_PORT", DEFAULT_GATEWAY_PORT)
    client_id = env_int("IB_V2_CLIENT_ID", DEFAULT_CLIENT_ID)

    node = build_ib_live_node(
        name="IB-DATA-FEED",
        trader_id="DATA-001",
        host=host,
        port=port,
        data_client_id=client_id,
        account_id=None,
        provider_config=instrument_provider_config(load_ids=TICKERS),
    )
    node.add_actor(IbDataFeed(sink=PrintSink()))

    print(f"Streaming IB data from {host}:{port}; press Ctrl+C to stop.", flush=True)
    node.run()


if __name__ == "__main__":
    main()
