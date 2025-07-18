"""
Test script to compare BlockListener, LogsListener, and GeyserListener
Runs all listeners simultaneously to compare their performance
"""

import asyncio
import logging
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

sys.path.append(str(Path(__file__).parent.parent / "src"))

from core.pubkeys import PumpAddresses
from monitoring.block_listener import BlockListener
from monitoring.geyser_listener import GeyserListener
from monitoring.logs_listener import LogsListener
from trading.base import TokenInfo

load_dotenv()

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


async def listen_with_timeout(listener, callback, timeout):
    """Run a listener for a specified duration"""
    try:
        listen_task = asyncio.create_task(
            listener.listen_for_tokens(callback.on_token_created)
        )
        
        await asyncio.sleep(timeout)

        listen_task.cancel()
        try:
            await listen_task
        except asyncio.CancelledError:
            pass
    except Exception as e:
        logger.error(f"Error in listener {callback.name}: {e}")


async def run_comparison(test_duration: int = 300):
    """Run all listeners and compare their performance"""
    wss_endpoint = os.environ.get("SOLANA_NODE_WSS_ENDPOINT")
    geyser_endpoint = os.environ.get("GEYSER_ENDPOINT")
    geyser_api_token = os.environ.get("GEYSER_API_TOKEN")
    geyser_auth_type = os.environ.get("GEYSER_AUTH_TYPE", "x-token")
    
    if not wss_endpoint:
        logger.error("SOLANA_NODE_WSS_ENDPOINT environment variable is not set")
        return
    
    logger.info(f"Connecting to WebSocket: {wss_endpoint}")
    
    block_listener = BlockListener(wss_endpoint, PumpAddresses.PROGRAM)
    logs_listener = LogsListener(wss_endpoint, PumpAddresses.PROGRAM)

    block_callback = TimingTokenCallback("BlockListener")
    logs_callback = TimingTokenCallback("LogsListener")

    listener_tasks = [
        listen_with_timeout(block_listener, block_callback, test_duration),
        listen_with_timeout(logs_listener, logs_callback, test_duration)
    ]
    
    callbacks = [block_callback, logs_callback]
    listener_names = ["BlockListener", "LogsListener"]
    
    # Initialize Geyser listener if credentials are available
    if geyser_endpoint and geyser_api_token:
        logger.info(f"Connecting to Geyser API: {geyser_endpoint}")
        geyser_listener = GeyserListener(geyser_endpoint, geyser_api_token, geyser_auth_type, PumpAddresses.PROGRAM)
        geyser_callback = TimingTokenCallback("GeyserListener")
        
        listener_tasks.append(
            listen_with_timeout(geyser_listener, geyser_callback, test_duration)
        )
        
        callbacks.append(geyser_callback)
        listener_names.append("GeyserListener")
    else:
        logger.warning("Geyser API credentials not found. Running without Geyser listener.")

    logger.info("Starting all listeners simultaneously...")
    logger.info(f"Comparison running for {test_duration} seconds...")
    
    try:
        # Start all listeners at the same time
        start_time = time.time()
        await asyncio.gather(*listener_tasks)
        end_time = time.time()
        
        logger.info(f"Test completed in {end_time - start_time:.2f} seconds")
        
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
        # No need for explicit cancellation as gather() will be interrupted

    for i, callback in enumerate(callbacks):
        logger.info(f"{listener_names[i]} detected {len(callback.detected_tokens)} tokens")
    
    # Find tokens detected by multiple listeners
    all_mints = {}
    for i, callback in enumerate(callbacks):
        mints = {str(token.mint) for token in callback.detected_tokens}
        all_mints[listener_names[i]] = mints
    
    # Analyze common detections between all listeners
    if len(callbacks) > 1:
        logger.info("\nAnalyzing token detection across listeners:")
        
        # Find tokens detected by all listeners
        if len(callbacks) > 2:  # If we have all 3 listeners
            common_to_all = set.intersection(*all_mints.values())
            logger.info(f"Tokens detected by all listeners: {len(common_to_all)}")
        
        # Compare pairs of listeners
        listeners = list(all_mints.keys())
        for i in range(len(listeners)):
            for j in range(i+1, len(listeners)):
                listener1 = listeners[i]
                listener2 = listeners[j]
                common = all_mints[listener1].intersection(all_mints[listener2])
                logger.info(f"Tokens detected by both {listener1} and {listener2}: {len(common)}")
                
                unique1 = all_mints[listener1] - all_mints[listener2]
                unique2 = all_mints[listener2] - all_mints[listener1]
                logger.info(f"Tokens unique to {listener1}: {len(unique1)}")
                logger.info(f"Tokens unique to {listener2}: {len(unique2)}")
        
        # Find tokens detected by at least one listener
        all_detected = set.union(*all_mints.values())
        logger.info(f"Total unique tokens detected by any listener: {len(all_detected)}")
    
    logger.info("\nDetection speed comparison:")
    
    # Collect all tokens detected by at least two listeners
    detection_comparisons = []
    for mint in set.union(*all_mints.values()):
        detections = {}
        for i, callback in enumerate(callbacks):
            if mint in callback.detection_times:
                detections[listener_names[i]] = callback.detection_times[mint]
        
        if len(detections) > 1:  # Only consider tokens detected by multiple listeners
            detection_comparisons.append((mint, detections))
    
    if detection_comparisons:
        logger.info("Token | " + " | ".join(listener_names) + " | Fastest")
        logger.info("-" * 80)
        
        for mint, detections in detection_comparisons:
            # Create row with detection times or "N/A" if not detected
            times = []
            for name in listener_names:
                time_str = f"{detections.get(name, 0):.6f}" if name in detections else "N/A"
                times.append(time_str)
            
            # Determine fastest listener
            valid_times = {name: time for name, time in detections.items() if time > 0}
            fastest = min(valid_times.items(), key=lambda x: x[1])[0] if valid_times else "N/A"
            
            logger.info(f"{mint[:10]}... | " + " | ".join(times) + f" | {fastest}")
    else:
        logger.info("No tokens were detected by multiple listeners for timing comparison")


if __name__ == "__main__":
    test_duration = 60  # seconds

    if len(sys.argv) > 1:
        try:
            test_duration = int(sys.argv[1])
        except ValueError:
            logger.error(f"Invalid test duration: {sys.argv[1]}. Using default of {test_duration} seconds.")

    logger.info("Starting listener comparison test")
    logger.info(f"Will run for {test_duration} seconds")
    asyncio.run(run_comparison(test_duration))
