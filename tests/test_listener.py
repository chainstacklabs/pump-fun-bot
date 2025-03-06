"""
Test script for PumpTokenListener
Tests websocket monitoring for new pump.fun tokens
"""

import asyncio
import logging
import os
from core.pubkeys import PumpAddresses
from monitoring.listener import PumpTokenListener
from trading.base import TokenInfo

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("token-listener-test")


class TestTokenCallback:
    def __init__(self):
        self.detected_tokens = []

    async def on_token_created(self, token_info: TokenInfo) -> None:
        """Process detected token"""
        logger.info(f"New token detected: {token_info.name} ({token_info.symbol})")
        logger.info(f"Mint: {token_info.mint}")
        self.detected_tokens.append(token_info)
        print(f"\n{'=' * 50}")
        print(f"NEW TOKEN: {token_info.name}")
        print(f"Symbol: {token_info.symbol}")
        print(f"Mint: {token_info.mint}")
        print(f"URI: {token_info.uri}")
        print(f"Creator: {token_info.user}")
        print(f"Bonding Curve: {token_info.bonding_curve}")
        print(f"Associated Bonding Curve: {token_info.associated_bonding_curve}")
        print(f"{'=' * 50}\n")


async def test_pump_token_listener(
    match_string: str | None = None,
    creator_address: str | None = None,
    test_duration: int = 60,
):
    """Test the token listener functionality"""
    wss_endpoint = os.environ.get(
        "SOLANA_NODE_WSS_ENDPOINT", "wss://api.mainnet-beta.solana.com"
    )
    logger.info(f"Connecting to WebSocket: {wss_endpoint}")
    listener = PumpTokenListener(wss_endpoint, PumpAddresses.PROGRAM)
    callback = TestTokenCallback()

    if match_string:
        logger.info(f"Filtering tokens matching: {match_string}")
    if creator_address:
        logger.info(f"Filtering tokens by creator: {creator_address}")

    listen_task = asyncio.create_task(
        listener.listen_for_tokens(
            callback.on_token_created,
            match_string=match_string,
            creator_address=creator_address,
        )
    )

    logger.info(f"Listening for {test_duration} seconds...")
    try:
        await asyncio.sleep(test_duration)
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    finally:
        listen_task.cancel()
        try:
            await listen_task
        except asyncio.CancelledError:
            pass

    logger.info(f"Detected {len(callback.detected_tokens)} tokens")
    for token in callback.detected_tokens:
        logger.info(f"  - 🪙 {token.name} ({token.symbol}): {token.mint}")

    return callback.detected_tokens


if __name__ == "__main__":
    match_string = None  # Update if you want to filter tokens by name/symbol
    creator_address = None  # Update if you want to filter tokens by creator address
    test_duration = 60
    logger.info("Starting token listener test")
    asyncio.run(test_pump_token_listener(match_string, creator_address, test_duration))
