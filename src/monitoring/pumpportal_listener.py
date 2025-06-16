"""
PumpPortal monitoring for pump.fun tokens.
"""

import asyncio
import json
from collections.abc import Awaitable, Callable

import websockets
from solders.pubkey import Pubkey

from monitoring.base_listener import BaseTokenListener
from monitoring.pumpportal_event_processor import PumpPortalEventProcessor
from trading.base import TokenInfo
from utils.logger import get_logger

logger = get_logger(__name__)


class PumpPortalListener(BaseTokenListener):
    """PumpPortal listener for pump.fun token creation events."""

    def __init__(self, pump_program: Pubkey, pumpportal_url: str = "wss://pumpportal.fun/api/data"):
        """Initialize token listener.

        Args:
            pump_program: Pump.fun program address
            pumpportal_url: PumpPortal WebSocket URL
        """
        self.pump_program = pump_program
        self.pumpportal_url = pumpportal_url
        self.event_processor = PumpPortalEventProcessor(pump_program)
        self.ping_interval = 20  # seconds

    async def listen_for_tokens(
        self,
        token_callback: Callable[[TokenInfo], Awaitable[None]],
        match_string: str | None = None,
        creator_address: str | None = None,
    ) -> None:
        """Listen for new token creations using PumpPortal WebSocket.

        Args:
            token_callback: Callback function for new tokens
            match_string: Optional string to match in token name/symbol
            creator_address: Optional creator address to filter by
        """
        while True:
            try:
                async with websockets.connect(self.pumpportal_url) as websocket:
                    await self._subscribe_to_new_tokens(websocket)
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
                        logger.warning("PumpPortal WebSocket connection closed. Reconnecting...")
                    finally:
                        ping_task.cancel()
                        try:
                            await ping_task
                        except asyncio.CancelledError:
                            pass

            except Exception:
                logger.exception("PumpPortal WebSocket connection error")
                logger.info("Reconnecting in 5 seconds...")
                await asyncio.sleep(5)
    async def _subscribe_to_new_tokens(self, websocket) -> None:
        """Subscribe to new token events from PumpPortal.

        Args:
            websocket: Active WebSocket connection
        """
        subscription_message = json.dumps({
            "method": "subscribeNewToken",
            "params": []
        })

        await websocket.send(subscription_message)
        logger.info("Subscribed to PumpPortal new token events")

    async def _ping_loop(self, websocket) -> None:
        """Keep connection alive with pings.

        Args:
            websocket: Active WebSocket connection
        """
        try:
            while True:
                await asyncio.sleep(self.ping_interval)
                try:
                    pong_waiter = await websocket.ping()
                    await asyncio.wait_for(pong_waiter, timeout=10)
                except TimeoutError:
                    logger.warning("Ping timeout - PumpPortal server not responding")
                    # Force reconnection
                    await websocket.close()
                    return
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Ping error: {e}")

    async def _wait_for_token_creation(self, websocket) -> TokenInfo | None:
        """Wait for token creation event from PumpPortal.

        Args:
            websocket: Active WebSocket connection

        Returns:
            TokenInfo if a token creation is found, None otherwise
        """
        try:
            response = await asyncio.wait_for(websocket.recv(), timeout=30)
            data = json.loads(response)

            # Handle different message formats from PumpPortal
            token_info = None
            if "method" in data and data["method"] == "newToken":
                # Standard newToken method format
                params = data.get("params", [])
                if params and len(params) > 0:
                    token_data = params[0]
                    token_info = self.event_processor.process_token_data(token_data)
            elif "signature" in data and "mint" in data:
                # Direct token data format
                token_info = self.event_processor.process_token_data(data)

            return token_info

        except TimeoutError:
            logger.debug("No data received from PumpPortal for 30 seconds")
        except websockets.exceptions.ConnectionClosed:
            logger.warning("PumpPortal WebSocket connection closed")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode PumpPortal message: {e}")
        except Exception as e:
            logger.error(f"Error processing PumpPortal WebSocket message: {e}")

        return None