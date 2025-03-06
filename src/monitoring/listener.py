"""
WebSocket monitoring for pump.fun tokens.
"""

import asyncio
import json
from typing import Awaitable, Callable, Optional

import websockets
from solders.pubkey import Pubkey

from monitoring.events import PumpEventProcessor
from trading.base import TokenInfo
from utils.logger import get_logger

logger = get_logger(__name__)


class PumpTokenListener:
    """WebSocket listener for pump.fun token creation events."""

    def __init__(self, wss_endpoint: str, pump_program: Pubkey):
        """Initialize token listener.

        Args:
            wss_endpoint: WebSocket endpoint URL
            pump_program: Pump.fun program address
        """
        self.wss_endpoint = wss_endpoint
        self.pump_program = pump_program
        self.event_processor = PumpEventProcessor(pump_program)
        self.ping_interval = 20  # seconds

    async def listen_for_tokens(
        self,
        token_callback: Callable[[TokenInfo], Awaitable[None]],
        match_string: str | None = None,
        creator_address: str | None = None,
    ) -> None:
        """Listen for new token creations.

        Args:
            token_callback: Callback function for new tokens
            match_string: Optional string to match in token name/symbol
            creator_address: Optional creator address to filter by
        """
        while True:
            try:
                async with websockets.connect(self.wss_endpoint) as websocket:
                    await self._subscribe_to_program(websocket)
                    ping_task = asyncio.create_task(self._ping_loop(websocket))

                    try:
                        while True:
                            token_info = await self._wait_for_token_creation(websocket)
                            if not token_info:
                                continue

                            logger.info(
                                f"New token detected: {token_info.name} ({token_info.symbol})"
                            )

                            if match_string and not (
                                match_string.lower() in token_info.name.lower()
                                or match_string.lower() in token_info.symbol.lower()
                            ):
                                logger.info(
                                    f"Token does not match filter '{match_string}'. Skipping..."
                                )
                                continue

                            if (
                                creator_address
                                and str(token_info.user) != creator_address
                            ):
                                logger.info(
                                    f"Token not created by {creator_address}. Skipping..."
                                )
                                continue

                            await token_callback(token_info)

                    except websockets.exceptions.ConnectionClosed:
                        logger.warning("WebSocket connection closed. Reconnecting...")
                        ping_task.cancel()

            except Exception as e:
                logger.error(f"WebSocket connection error: {str(e)}")
                logger.info("Reconnecting in 5 seconds...")
                await asyncio.sleep(5)

    async def _subscribe_to_program(self, websocket) -> None:
        """Subscribe to blocks mentioning the pump.fun program.

        Args:
            websocket: Active WebSocket connection
        """
        subscription_message = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "blockSubscribe",
                "params": [
                    {"mentionsAccountOrProgram": str(self.pump_program)},
                    {
                        "commitment": "confirmed",
                        "encoding": "base64",
                        "showRewards": False,
                        "transactionDetails": "full",
                        "maxSupportedTransactionVersion": 0,
                    },
                ],
            }
        )

        await websocket.send(subscription_message)
        logger.info(f"Subscribed to blocks mentioning program: {self.pump_program}")

    async def _ping_loop(self, websocket) -> None:
        """Keep connection alive with pings.

        Args:
            websocket: Active WebSocket connection
        """
        try:
            while True:
                await asyncio.sleep(self.ping_interval)
                await websocket.ping()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Ping error: {str(e)}")

    async def _wait_for_token_creation(self, websocket) -> Optional[TokenInfo]:
        """Wait for token creation event.

        Args:
            websocket: Active WebSocket connection

        Returns:
            TokenInfo if a token creation is found, None otherwise
        """
        try:
            response = await asyncio.wait_for(websocket.recv(), timeout=30)
            data = json.loads(response)

            if "method" not in data or data["method"] != "blockNotification":
                return None

            if "params" not in data or "result" not in data["params"]:
                return None

            block_data = data["params"]["result"]
            if "value" not in block_data or "block" not in block_data["value"]:
                return None

            block = block_data["value"]["block"]
            if "transactions" not in block:
                return None

            for tx in block["transactions"]:
                if not isinstance(tx, dict) or "transaction" not in tx:
                    continue

                token_info = self.event_processor.process_transaction(
                    tx["transaction"][0]
                )
                if token_info:
                    return token_info

        except asyncio.TimeoutError:
            logger.debug("No data received for 30 seconds")
        except websockets.exceptions.ConnectionClosed:
            logger.warning("WebSocket connection closed")
            raise
        except Exception as e:
            logger.error(f"Error processing WebSocket message: {str(e)}")

        return None
