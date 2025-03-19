"""
Test script to compare BlockListener and LogsListener
Runs both listeners simultaneously to compare their performance
"""

import asyncio
import logging
import os
import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent / "src"))

from core.pubkeys import PumpAddresses
from monitoring.block_listener import BlockListener
from monitoring.logs_listener import LogsListener
from trading.base import TokenInfo

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("listener-comparison")


class TimingTokenCallback:
    def __init__(self, name: str):
        self.name = name
        self.detected_tokens = []
        self.detection_times = {}

    async def on_token_created(self, token_info: TokenInfo) -> None:
        """Process detected token with timing information"""
        token_key = str(token_info.mint)
        detection_time = time.time()
        
        self.detected_tokens.append(token_info)
        self.detection_times[token_key] = detection_time
        
        logger.info(f"[{self.name}] Detected: {token_info.name} ({token_info.symbol})")
        print(f"\n{'=' * 50}")
        print(f"[{self.name}] NEW TOKEN: {token_info.name}")
        print(f"Symbol: {token_info.symbol}")
        print(f"Mint: {token_info.mint}")
        print(f"Detection time: {detection_time}")
        print(f"{'=' * 50}\n")


async def run_comparison(test_duration: int = 300):
    """Run both listeners and compare their performance"""
    wss_endpoint = os.environ.get("SOLANA_NODE_WSS_ENDPOINT")
    if not wss_endpoint:
        logger.error("SOLANA_NODE_WSS_ENDPOINT environment variable is not set")
        return
    
    logger.info(f"Connecting to WebSocket: {wss_endpoint}")
    
    block_listener = BlockListener(wss_endpoint, PumpAddresses.PROGRAM)
    logs_listener = LogsListener(wss_endpoint, PumpAddresses.PROGRAM)
    
    block_callback = TimingTokenCallback("BlockListener")
    logs_callback = TimingTokenCallback("LogsListener")

    logger.info("Starting both listeners...")
    block_task = asyncio.create_task(
        block_listener.listen_for_tokens(block_callback.on_token_created)
    )
    logs_task = asyncio.create_task(
        logs_listener.listen_for_tokens(logs_callback.on_token_created)
    )

    logger.info(f"Comparison running for {test_duration} seconds...")
    try:
        await asyncio.sleep(test_duration)
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    finally:
        block_task.cancel()
        logs_task.cancel()
        try:
            await asyncio.gather(block_task, logs_task, return_exceptions=True)
        except asyncio.CancelledError:
            pass

    logger.info(f"BlockListener detected {len(block_callback.detected_tokens)} tokens")
    logger.info(f"LogsListener detected {len(logs_callback.detected_tokens)} tokens")
    
    # Find tokens detected by both listeners
    block_mints = {str(token.mint) for token in block_callback.detected_tokens}
    logs_mints = {str(token.mint) for token in logs_callback.detected_tokens}
    common_mints = block_mints.intersection(logs_mints)
    
    logger.info(f"Tokens detected by both listeners: {len(common_mints)}")
    
    # Compare detection times for common tokens
    if common_mints:
        logger.info("\nPerformance comparison for tokens detected by both listeners:")
        logger.info("Token Mint | BlockListener Time | LogsListener Time | Difference (ms)")
        logger.info("-" * 80)
        
        for mint in common_mints:
            block_time = block_callback.detection_times.get(mint)
            logs_time = logs_callback.detection_times.get(mint)
            
            if block_time and logs_time:
                diff_ms = abs(block_time - logs_time) * 1000  # Convert to milliseconds
                faster = "BlockListener" if block_time < logs_time else "LogsListener"
                
                logger.info(f"{mint[:10]}... | {block_time:.6f} | {logs_time:.6f} | {diff_ms:.2f}ms ({faster} faster)")
    
    # Report tokens only detected by one listener
    block_only = block_mints - logs_mints
    logs_only = logs_mints - block_mints
    
    if block_only:
        logger.info(f"\nTokens only detected by BlockListener: {len(block_only)}")
        for mint in block_only:
            logger.info(f"  - {mint}")
    
    if logs_only:
        logger.info(f"\nTokens only detected by LogsListener: {len(logs_only)}")
        for mint in logs_only:
            logger.info(f"  - {mint}")


if __name__ == "__main__":
    test_duration = 30  # seconds

    if len(sys.argv) > 1:
        try:
            test_duration = int(sys.argv[1])
        except ValueError:
            logger.error(f"Invalid test duration: {sys.argv[1]}. Using default of {test_duration} seconds.")

    logger.info("Starting listener comparison test")
    logger.info(f"Will run for {test_duration} seconds")
    asyncio.run(run_comparison(test_duration))
