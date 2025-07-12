"""
Main trading coordinator for pump.fun tokens.
Refactored PumpTrader to only process fresh tokens from WebSocket.
"""

import asyncio
import json
import os
import signal
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from time import monotonic
from typing import Dict, List, Optional, Set

import uvloop
from solders.pubkey import Pubkey

from cleanup.modes import (
    handle_cleanup_after_failure,
    handle_cleanup_after_sell,
    handle_cleanup_post_session,
)
from core.client import SolanaClient
from core.curve import BondingCurveManager
from core.priority_fee.manager import PriorityFeeManager
from core.pubkeys import PumpAddresses
from core.wallet import Wallet
from monitoring.block_listener import BlockListener
from monitoring.geyser_listener import GeyserListener
from monitoring.logs_listener import LogsListener
from monitoring.pumpportal_listener import PumpPortalListener
from trading.base import TokenInfo, TradeResult
from trading.buyer import TokenBuyer
from trading.position import Position, ExitReason
from trading.seller import TokenSeller
from utils.logger import get_logger

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

logger = get_logger(__name__)


class PumpTrader:
    """Coordinates trading operations for pump.fun tokens with focus on freshness and concurrency."""
    def __init__(
        self,
        rpc_endpoint: str,
        wss_endpoint: str,
        private_key: str,
        buy_amount: float,
        buy_slippage: float,
        sell_slippage: float,
        listener_type: str = "logs",
        geyser_endpoint: str | None = None,
        geyser_api_token: str | None = None,
        geyser_auth_type: str = "x-token",
        pumpportal_url: str = "wss://pumpportal.fun/api/data",

        extreme_fast_mode: bool = False,
        extreme_fast_token_amount: int = 30,
        
        # Exit strategy configuration
        exit_strategy: str = "time_based",
        take_profit_percentage: float | None = None,
        stop_loss_percentage: float | None = None,
        max_hold_time: int | None = None,
        price_check_interval: int = 10,
        
        # Priority fee configuration
        enable_dynamic_priority_fee: bool = False,
        enable_fixed_priority_fee: bool = True,
        fixed_priority_fee: int = 200_000,
        extra_priority_fee: float = 0.0,
        hard_cap_prior_fee: int = 200_000,
        
        # Retry and timeout settings
        max_retries: int = 3,
        wait_time_after_creation: int = 15, # here and further - seconds
        wait_time_after_buy: int = 15,
        wait_time_before_new_token: int = 15,
        max_token_age: int | float = 0.001,
        token_wait_timeout: int = 30,
        
        # Cleanup settings
        cleanup_mode: str = "disabled",
        cleanup_force_close_with_burn: bool = False,
        cleanup_with_priority_fee: bool = False,
        
        # Trading filters
        match_string: str | None = None,
        bro_address: str | None = None,
        marry_mode: bool = False,
        yolo_mode: bool = False,
        
        # Concurrency settings
        max_concurrent_positions: int = 5,
        max_concurrent_trades: int = 3,
    ):
        """Initialize the pump trader.
        Args:
            rpc_endpoint: RPC endpoint URL
            wss_endpoint: WebSocket endpoint URL
            private_key: Wallet private key
            buy_amount: Amount of SOL to spend on buys
            buy_slippage: Slippage tolerance for buys
            sell_slippage: Slippage tolerance for sells

            listener_type: Type of listener to use ('logs', 'blocks', 'geyser', or 'pumpportal')
            geyser_endpoint: Geyser endpoint URL (required for geyser listener)
            geyser_api_token: Geyser API token (required for geyser listener)
            geyser_auth_type: Geyser authentication type ('x-token' or 'basic')
            pumpportal_url: PumpPortal WebSocket URL (default: wss://pumpportal.fun/api/data)

            extreme_fast_mode: Whether to enable extreme fast mode
            extreme_fast_token_amount: Maximum token amount for extreme fast mode

            exit_strategy: Exit strategy ("time_based", "tp_sl", or "manual")
            take_profit_percentage: Take profit percentage (0.5 = 50% profit)
            stop_loss_percentage: Stop loss percentage (0.2 = 20% loss)
            max_hold_time: Maximum hold time in seconds
            price_check_interval: How often to check price for TP/SL (seconds)

            enable_dynamic_priority_fee: Whether to enable dynamic priority fees
            enable_fixed_priority_fee: Whether to enable fixed priority fees
            fixed_priority_fee: Fixed priority fee amount
            extra_priority_fee: Extra percentage for priority fees
            hard_cap_prior_fee: Hard cap for priority fees

            max_retries: Maximum number of retry attempts
            wait_time_after_creation: Time to wait after token creation (seconds)
            wait_time_after_buy: Time to wait after buying a token (seconds)
            wait_time_before_new_token: Time to wait before processing a new token (seconds)
            max_token_age: Maximum age of token to process (seconds)
            token_wait_timeout: Timeout for waiting for a token in single-token mode (seconds)

            cleanup_mode: Cleanup mode ("disabled", "auto", or "manual")
            cleanup_force_close_with_burn: Whether to force close with burn during cleanup
            cleanup_with_priority_fee: Whether to use priority fees during cleanup
            
            match_string: Optional string to match in token name/symbol
            bro_address: Optional creator address to filter by
            marry_mode: If True, only buy tokens and skip selling
            yolo_mode: If True, trade continuously
            
            max_concurrent_positions: Maximum number of concurrent positions to monitor
            max_concurrent_trades: Maximum number of concurrent trades to execute
        """
        self.solana_client = SolanaClient(rpc_endpoint)
        self.wallet = Wallet(private_key)
        self.curve_manager = BondingCurveManager(self.solana_client)
        self.priority_fee_manager = PriorityFeeManager(
            client=self.solana_client,
            enable_dynamic_fee=enable_dynamic_priority_fee,
            enable_fixed_fee=enable_fixed_priority_fee,
            fixed_fee=fixed_priority_fee,
            extra_fee=extra_priority_fee,
            hard_cap=hard_cap_prior_fee,
        )
        self.buyer = TokenBuyer(
            self.solana_client,
            self.wallet,
            self.curve_manager,
            self.priority_fee_manager,
            buy_amount,
            buy_slippage,
            max_retries,
            extreme_fast_token_amount,
            extreme_fast_mode
        )
        self.seller = TokenSeller(
            self.solana_client,
            self.wallet,
            self.curve_manager,
            self.priority_fee_manager,
            sell_slippage,
            max_retries,
        )
        
        # Initialize the appropriate listener type
        listener_type = listener_type.lower()
        if listener_type == "geyser":
            if not geyser_endpoint or not geyser_api_token:
                raise ValueError("Geyser endpoint and API token are required for geyser listener")
                
            self.token_listener = GeyserListener(
                geyser_endpoint, 
                geyser_api_token,
                geyser_auth_type, 
                PumpAddresses.PROGRAM
            )
            logger.info("Using Geyser listener for token monitoring")
        elif listener_type == "logs":
            self.token_listener = LogsListener(wss_endpoint, PumpAddresses.PROGRAM)
            logger.info("Using logsSubscribe listener for token monitoring")
        elif listener_type == "pumpportal":
            self.token_listener = PumpPortalListener(PumpAddresses.PROGRAM, pumpportal_url)
            logger.info("Using PumpPortal listener for token monitoring")
        else:
            self.token_listener = BlockListener(wss_endpoint, PumpAddresses.PROGRAM)
            logger.info("Using blockSubscribe listener for token monitoring")
            
        # Trading parameters
        self.buy_amount = buy_amount
        self.buy_slippage = buy_slippage
        self.sell_slippage = sell_slippage
        self.max_retries = max_retries
        self.extreme_fast_mode = extreme_fast_mode
        self.extreme_fast_token_amount = extreme_fast_token_amount
        
        # Exit strategy parameters
        self.exit_strategy = exit_strategy.lower()
        self.take_profit_percentage = take_profit_percentage
        self.stop_loss_percentage = stop_loss_percentage
        self.max_hold_time = max_hold_time
        self.price_check_interval = price_check_interval
        
        # Timing parameters
        self.wait_time_after_creation = wait_time_after_creation
        self.wait_time_after_buy = wait_time_after_buy
        self.wait_time_before_new_token = wait_time_before_new_token
        self.max_token_age = max_token_age
        self.token_wait_timeout = token_wait_timeout
        
        # Cleanup parameters
        self.cleanup_mode = cleanup_mode
        self.cleanup_force_close_with_burn = cleanup_force_close_with_burn
        self.cleanup_with_priority_fee = cleanup_with_priority_fee

        # Trading filters/modes
        self.match_string = match_string
        self.bro_address = bro_address
        self.marry_mode = marry_mode
        self.yolo_mode = yolo_mode
        
        # Concurrency parameters
        self.max_concurrent_positions = max_concurrent_positions
        self.max_concurrent_trades = max_concurrent_trades
        
        # State tracking
        self.traded_mints: Set[Pubkey] = set()
        self.active_positions: Dict[str, Position] = {}
        self.token_queue: asyncio.Queue = asyncio.Queue()
        self.processing: bool = False
        self.processed_tokens: Set[str] = set()
        self.token_timestamps: Dict[str, float] = {}
        
        # Concurrency control
        self.trade_semaphore = asyncio.Semaphore(max_concurrent_trades)
        self.position_semaphore = asyncio.Semaphore(max_concurrent_positions)
        self.shutdown_event = asyncio.Event()
        
        # Task tracking for cleanup
        self.active_tasks: Set[asyncio.Task] = set()
        self.monitoring_tasks: Dict[str, asyncio.Task] = {}
        
        # Setup signal handlers
        self._setup_signal_handlers()
        
    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}. Initiating graceful shutdown...")
            self.shutdown_event.set()
            
        # Handle SIGINT (Ctrl+C) and SIGTERM
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
    @asynccontextmanager
    async def _task_tracker(self, task_name: str):
        """Context manager to track async tasks for proper cleanup."""
        task = None
        try:
            yield
        except asyncio.CancelledError:
            logger.debug(f"Task {task_name} was cancelled")
            raise
        except Exception as e:
            logger.error(f"Error in task {task_name}: {e}")
            raise
        finally:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                    
    async def _emergency_shutdown(self) -> None:
        """Emergency shutdown that immediately sells all positions and cleans up."""
        logger.critical("EMERGENCY SHUTDOWN: Selling all positions immediately...")
        
        # Sell all active positions concurrently
        sell_tasks = []
        position_map = {}  # Map task to position for tracking failures
        
        for mint_str, position in self.active_positions.items():
            if position.is_active:
                logger.info(f"Emergency selling position: {position.symbol}")
                task = asyncio.create_task(self._emergency_sell_position(mint_str, position))
                sell_tasks.append(task)
                position_map[task] = (mint_str, position)
        
        failed_positions = []
        
        if sell_tasks:
            results = await asyncio.gather(*sell_tasks, return_exceptions=True)
            
            # Track failed sell attempts
            for task, result in zip(sell_tasks, results):
                if isinstance(result, Exception):
                    mint_str, position = position_map[task]
                    failed_positions.append({
                        'mint': str(position.mint),
                        'symbol': position.symbol,
                        'entry_price': position.entry_price,
                        'quantity': position.quantity,
                        'entry_time': position.entry_time.isoformat(),
                        'failed_at': datetime.utcnow().isoformat(),
                        'error': str(result)
                    })
                    logger.error(f"Failed to emergency sell {position.symbol}: {result}")
            
            # Write failed positions to file for retry on next startup
            if failed_positions:
                await self._save_failed_sells(failed_positions)
                
        # Force cleanup of all traded mints
        if self.traded_mints:
            logger.info("Performing emergency cleanup of all traded tokens...")
            try:
                await asyncio.wait_for(
                    handle_cleanup_post_session(
                        self.solana_client, 
                        self.wallet, 
                        list(self.traded_mints), 
                        self.priority_fee_manager,
                        self.cleanup_mode,
                        self.cleanup_with_priority_fee,
                        self.cleanup_force_close_with_burn
                    ),
                    timeout=30.0  # Emergency cleanup timeout
                )
            except asyncio.TimeoutError:
                logger.warning("Emergency cleanup timed out")
            except Exception as e:
                logger.error(f"Emergency cleanup failed: {e}")
        
        logger.info("Emergency shutdown completed")
        
    async def _emergency_sell_position(self, mint_str: str, position: Position) -> None:
        """Emergency sell a specific position."""
        try:
            # Create TokenInfo for selling
            token_info = TokenInfo(
                mint=position.mint,
                symbol=position.symbol,
                name=position.symbol,
                bonding_curve=None,  # Will be resolved in seller
                associated_bonding_curve=None,
                virtual_token_reserves=0,
                virtual_sol_reserves=0,
                real_token_reserves=0,
                real_sol_reserves=0,
                token_total_supply=0,
                complete=False,
                timestamp=datetime.utcnow()
            )
            
            # Sell with timeout
            sell_result = await asyncio.wait_for(
                self.seller.execute(token_info), 
                timeout=15.0  # Emergency sell timeout
            )
            
            if sell_result.success:
                logger.info(f"Emergency sell successful for {position.symbol}")
                position.close_position(sell_result.price, ExitReason.EMERGENCY_STOP)
                self._log_trade(
                    "emergency_sell",
                    token_info,
                    sell_result.price,
                    sell_result.amount,
                    sell_result.tx_signature,
                )
            else:
                logger.error(f"Emergency sell failed for {position.symbol}: {sell_result.error_message}")
                
        except asyncio.TimeoutError:
            logger.warning(f"Emergency sell timed out for {position.symbol}")
        except Exception as e:
            logger.error(f"Emergency sell error for {position.symbol}: {e}")
            
    async def _save_failed_sells(self, failed_positions: List[Dict]) -> None:
        """Save failed sell positions to file for retry on next startup."""
        try:
            os.makedirs("emergency", exist_ok=True)
            failed_sells_file = "emergency/failed_sells.json"
            
            with open(failed_sells_file, 'w') as f:
                json.dump(failed_positions, f, indent=2)
            
            logger.critical(f"Saved {len(failed_positions)} failed sell(s) to {failed_sells_file}")
        except Exception as e:
            logger.error(f"Failed to save failed sells to file: {e}")
    
    async def _load_and_process_failed_sells(self) -> None:
        """Load and process failed sells from previous emergency shutdown."""
        failed_sells_file = "emergency/failed_sells.json"
        
        if not os.path.exists(failed_sells_file):
            return
            
        try:
            with open(failed_sells_file, 'r') as f:
                failed_positions = json.load(f)
            
            if not failed_positions:
                return
                
            logger.warning(f"Found {len(failed_positions)} failed sell(s) from previous shutdown. Processing...")
            
            # Process failed sells concurrently
            retry_tasks = []
            for pos_data in failed_positions:
                logger.info(f"Retrying emergency sell for {pos_data['symbol']} ({pos_data['mint']})")
                task = asyncio.create_task(self._retry_failed_sell(pos_data))
                retry_tasks.append(task)
            
            if retry_tasks:
                results = await asyncio.gather(*retry_tasks, return_exceptions=True)
                
                # Check for any remaining failures
                still_failed = []
                for pos_data, result in zip(failed_positions, results):
                    if isinstance(result, Exception):
                        # Update failure information
                        pos_data['retry_failed_at'] = datetime.utcnow().isoformat()
                        pos_data['retry_error'] = str(result)
                        still_failed.append(pos_data)
                        logger.error(f"Retry failed for {pos_data['symbol']}: {result}")
                    else:
                        logger.info(f"Successfully retried emergency sell for {pos_data['symbol']}")
                
                # Update file with remaining failures or remove if all succeeded
                if still_failed:
                    with open(failed_sells_file, 'w') as f:
                        json.dump(still_failed, f, indent=2)
                    logger.warning(f"{len(still_failed)} sell(s) still failed after retry")
                else:
                    os.remove(failed_sells_file)
                    logger.info("All failed sells successfully retried and processed")
                    
        except Exception as e:
            logger.error(f"Error processing failed sells: {e}")
    
    async def _retry_failed_sell(self, pos_data: Dict) -> None:
        """Retry selling a position that failed during emergency shutdown."""
        try:
            # Recreate TokenInfo from stored data
            token_info = TokenInfo(
                mint=Pubkey.from_string(pos_data['mint']),
                symbol=pos_data['symbol'],
                name=pos_data['symbol'],
                bonding_curve=None,  # Will be resolved in seller
                associated_bonding_curve=None,
                virtual_token_reserves=0,
                virtual_sol_reserves=0,
                real_token_reserves=0,
                real_sol_reserves=0,
                token_total_supply=0,
                complete=False,
                timestamp=datetime.utcnow()
            )
            
            # Attempt to sell with timeout
            sell_result = await asyncio.wait_for(
                self.seller.execute(token_info),
                timeout=30.0  # Longer timeout for retry
            )
            
            if sell_result.success:
                logger.info(f"Retry sell successful for {pos_data['symbol']}")
                self._log_trade(
                    "emergency_sell_retry",
                    token_info,
                    sell_result.price,
                    sell_result.amount,
                    sell_result.tx_signature,
                )
                
                # Perform cleanup after successful sell
                await handle_cleanup_after_sell(
                    self.solana_client,
                    self.wallet,
                    token_info.mint,
                    self.priority_fee_manager,
                    self.cleanup_mode,
                    self.cleanup_with_priority_fee,
                    self.cleanup_force_close_with_burn
                )
            else:
                raise Exception(f"Sell failed: {sell_result.error_message}")
                
        except Exception as e:
            logger.error(f"Retry sell failed for {pos_data['symbol']}: {e}")
            raise
            
    async def start(self) -> None:
        """Start the trading bot and listen for new tokens."""
        logger.info("Starting pump.fun trader with enhanced concurrency")
        logger.info(f"Max concurrent positions: {self.max_concurrent_positions}")
        logger.info(f"Max concurrent trades: {self.max_concurrent_trades}")
        logger.info(f"Match filter: {self.match_string if self.match_string else 'None'}")
        logger.info(f"Creator filter: {self.bro_address if self.bro_address else 'None'}")
        logger.info(f"Marry mode: {self.marry_mode}")
        logger.info(f"YOLO mode: {self.yolo_mode}")
        logger.info(f"Exit strategy: {self.exit_strategy}")
        if self.exit_strategy == "tp_sl":
            logger.info(f"Take profit: {self.take_profit_percentage * 100 if self.take_profit_percentage else 'None'}%")
            logger.info(f"Stop loss: {self.stop_loss_percentage * 100 if self.stop_loss_percentage else 'None'}%")
            logger.info(f"Max hold time: {self.max_hold_time if self.max_hold_time else 'None'} seconds")
        logger.info(f"Max token age: {self.max_token_age} seconds")

        try:
            health_resp = await self.solana_client.get_health()
            logger.info(f"RPC warm-up successful (getHealth passed: {health_resp})")
        except Exception as e:
            logger.warning(f"RPC warm-up failed: {e!s}")

        # Process any failed sells from previous emergency shutdown
        await self._load_and_process_failed_sells()

        main_task = None
        try:
            # Choose operating mode based on yolo_mode
            if not self.yolo_mode:
                # Single token mode: process one token and exit
                logger.info("Running in single token mode - will process one token and exit")
                main_task = asyncio.create_task(self._run_single_token_mode())
            else:
                # Continuous mode: process tokens until interrupted
                logger.info("Running in continuous mode - will process tokens until interrupted")
                main_task = asyncio.create_task(self._run_continuous_mode())
                
            # Wait for main task or shutdown signal
            done, pending = await asyncio.wait(
                [main_task, asyncio.create_task(self.shutdown_event.wait())],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Cancel pending tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            
            # Check if shutdown was requested
            if self.shutdown_event.is_set():
                logger.info("Shutdown requested - performing emergency shutdown...")
                await self._emergency_shutdown()
        
        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt received - performing emergency shutdown...")
            await self._emergency_shutdown()
        except Exception as e:
            logger.error(f"Trading stopped due to error: {e!s}")
            await self._emergency_shutdown()
        
        finally:
            await self._cleanup_resources()
            logger.info("Pump trader has shut down")

    async def _run_single_token_mode(self) -> None:
        """Run in single token mode."""
        token_info = await self._wait_for_token()
        if token_info:
            await self._handle_token(token_info)
            logger.info("Finished processing single token. Exiting...")
        else:
            logger.info(f"No suitable token found within timeout period ({self.token_wait_timeout}s). Exiting...")

    async def _run_continuous_mode(self) -> None:
        """Run in continuous mode."""
        processor_task = asyncio.create_task(self._process_token_queue())
        self.active_tasks.add(processor_task)

        try:
            await self.token_listener.listen_for_tokens(
                lambda token: self._queue_token(token),
                self.match_string,
                self.bro_address,
            )
        finally:
            processor_task.cancel()
            if processor_task in self.active_tasks:
                self.active_tasks.remove(processor_task)
            try:
                await processor_task
            except asyncio.CancelledError:
                pass

    async def _wait_for_token(self) -> TokenInfo | None:
        """Wait for a single token to be detected.
        
        Returns:
            TokenInfo or None if timeout occurs
        """
        # Create a one-time event to signal when a token is found
        token_found = asyncio.Event()
        found_token = None
        
        async def token_callback(token: TokenInfo) -> None:
            nonlocal found_token
            token_key = str(token.mint)
            
            # Only process if not already processed and fresh
            if token_key not in self.processed_tokens:
                # Record when the token was discovered
                self.token_timestamps[token_key] = monotonic()
                found_token = token
                self.processed_tokens.add(token_key)
                token_found.set()
        
        listener_task = asyncio.create_task(
            self.token_listener.listen_for_tokens(
                token_callback,
                self.match_string,
                self.bro_address,
            )
        )
        self.active_tasks.add(listener_task)
        
        # Wait for a token with a timeout
        try:
            logger.info(f"Waiting for a suitable token (timeout: {self.token_wait_timeout}s)...")
            await asyncio.wait_for(token_found.wait(), timeout=self.token_wait_timeout)
            logger.info(f"Found token: {found_token.symbol} ({found_token.mint})")
            return found_token
        except TimeoutError:
            logger.info(f"Timed out after waiting {self.token_wait_timeout}s for a token")
            return None
        finally:
            listener_task.cancel()
            if listener_task in self.active_tasks:
                self.active_tasks.remove(listener_task)
            try:
                await listener_task
            except asyncio.CancelledError:
                pass

    async def _cleanup_resources(self) -> None:
        """Perform cleanup operations before shutting down."""
        logger.info("Starting resource cleanup...")
        
        # Cancel all active tasks
        if self.active_tasks:
            logger.info(f"Cancelling {len(self.active_tasks)} active tasks...")
            for task in self.active_tasks:
                if not task.done():
                    task.cancel()
            
            # Wait for tasks to complete cancellation
            await asyncio.gather(*self.active_tasks, return_exceptions=True)
            self.active_tasks.clear()
            
        # Cancel all monitoring tasks
        if self.monitoring_tasks:
            logger.info(f"Cancelling {len(self.monitoring_tasks)} monitoring tasks...")
            for task in self.monitoring_tasks.values():
                if not task.done():
                    task.cancel()
            
            await asyncio.gather(*self.monitoring_tasks.values(), return_exceptions=True)
            self.monitoring_tasks.clear()
        
        # Final cleanup of traded mints
        if self.traded_mints:
            try:
                logger.info(f"Final cleanup of {len(self.traded_mints)} traded token(s)...")
                await handle_cleanup_post_session(
                    self.solana_client, 
                    self.wallet, 
                    list(self.traded_mints), 
                    self.priority_fee_manager,
                    self.cleanup_mode,
                    self.cleanup_with_priority_fee,
                    self.cleanup_force_close_with_burn
                )
            except Exception as e:
                logger.error(f"Error during final cleanup: {e!s}")
                
        # Clear state tracking
        old_keys = {k for k in self.token_timestamps if k not in self.processed_tokens}
        for key in old_keys:
            self.token_timestamps.pop(key, None)
        
        self.active_positions.clear()
        
        # Close client connection
        await self.solana_client.close()
        logger.info("Resource cleanup completed")

    async def _queue_token(
        self, token_info: TokenInfo
    ) -> None:
        """Queue a token for processing if not already processed.
        
        Args:
            token_info: Token information to queue
        """
        if self.shutdown_event.is_set():
            return
            
        token_key = str(token_info.mint)

        if token_key in self.processed_tokens:
            logger.debug(f"Token {token_info.symbol} already processed. Skipping...")
            return

        # Record timestamp when token was discovered
        self.token_timestamps[token_key] = monotonic()

        try:
            await asyncio.wait_for(self.token_queue.put(token_info), timeout=1.0)
            logger.info(f"Queued new token: {token_info.symbol} ({token_info.mint})")
        except asyncio.TimeoutError:
            logger.warning(f"Token queue full, dropping token: {token_info.symbol}")

    async def _process_token_queue(self) -> None:
        """Continuously process tokens from the queue, only if they're fresh."""
        while not self.shutdown_event.is_set():
            try:
                # Check for tokens with timeout to allow shutdown checking
                token_info = await asyncio.wait_for(
                    self.token_queue.get(), 
                    timeout=1.0
                )
                
                token_key = str(token_info.mint)

                # Check if token is still "fresh"
                current_time = monotonic()
                token_age = current_time - self.token_timestamps.get(
                    token_key, current_time
                )

                if token_age > self.max_token_age:
                    logger.info(
                        f"Skipping token {token_info.symbol} - too old ({token_age:.1f}s > {self.max_token_age}s)"
                    )
                    continue

                self.processed_tokens.add(token_key)

                logger.info(
                    f"Processing fresh token: {token_info.symbol} (age: {token_age:.1f}s)"
                )
                
                # Process token with concurrency control
                task = asyncio.create_task(self._handle_token(token_info))
                self.active_tasks.add(task)
                
                # Clean up completed tasks
                task.add_done_callback(lambda t: self.active_tasks.discard(t))

            except asyncio.TimeoutError:
                # Timeout is expected, continue loop to check shutdown
                continue
            except asyncio.CancelledError:
                # Handle cancellation gracefully
                logger.info("Token queue processor was cancelled")
                break
            except Exception as e:
                logger.error(f"Error in token queue processor: {e!s}")
                await asyncio.sleep(1.0)  # Brief pause before retrying
            finally:
                try:
                    self.token_queue.task_done()
                except ValueError:
                    # task_done() called more times than there were items
                    pass

    async def _handle_token(
        self, token_info: TokenInfo
    ) -> None:
        """Handle a new token creation event with concurrency control.

        Args:
            token_info: Token information
        """
        async with self.trade_semaphore:
            if self.shutdown_event.is_set():
                return
                
            try:
                # Wait for bonding curve to stabilize (unless in extreme fast mode)
                if not self.extreme_fast_mode:
                    logger.info(
                        f"Waiting for {self.wait_time_after_creation} seconds for the bonding curve to stabilize..."
                    )
                    await asyncio.sleep(self.wait_time_after_creation)

                # Check shutdown again after wait
                if self.shutdown_event.is_set():
                    return

                # Buy token
                logger.info(
                    f"Buying {self.buy_amount:.6f} SOL worth of {token_info.symbol}..."
                )
                buy_result: TradeResult = await self.buyer.execute(token_info)

                if buy_result.success:
                    await self._handle_successful_buy(token_info, buy_result)
                else:
                    await self._handle_failed_buy(token_info, buy_result)

                # Only wait for next token in yolo mode
                if self.yolo_mode and not self.shutdown_event.is_set():
                    logger.info(
                        f"YOLO mode enabled. Waiting {self.wait_time_before_new_token} seconds before looking for next token..."
                    )
                    await asyncio.sleep(self.wait_time_before_new_token)

            except asyncio.CancelledError:
                logger.info(f"Token handling cancelled for {token_info.symbol}")
                raise
            except Exception as e:
                logger.error(f"Error handling token {token_info.symbol}: {e!s}")

    async def _handle_successful_buy(
        self, token_info: TokenInfo, buy_result: TradeResult
    ) -> None:
        """Handle successful token purchase.
        
        Args:
            token_info: Token information
            buy_result: The result of the buy operation
        """
        logger.info(f"Successfully bought {token_info.symbol}")
        self._log_trade(
            "buy",
            token_info,
            buy_result.price,  # type: ignore
            buy_result.amount,  # type: ignore
            buy_result.tx_signature,
        )
        self.traded_mints.add(token_info.mint)
        
        # Choose exit strategy
        if not self.marry_mode:
            if self.exit_strategy == "tp_sl":
                await self._handle_tp_sl_exit(token_info, buy_result)
            elif self.exit_strategy == "time_based":
                await self._handle_time_based_exit(token_info)
            elif self.exit_strategy == "manual":
                logger.info("Manual exit strategy - position will remain open")
        else:
            logger.info("Marry mode enabled. Skipping sell operation.")

    async def _handle_failed_buy(
        self, token_info: TokenInfo, buy_result: TradeResult
    ) -> None:
        """Handle failed token purchase.
        
        Args:
            token_info: Token information
            buy_result: The result of the buy operation
        """
        logger.error(
            f"Failed to buy {token_info.symbol}: {buy_result.error_message}"
        )
        # Close ATA if enabled
        await handle_cleanup_after_failure(
            self.solana_client, 
            self.wallet, 
            token_info.mint, 
            self.priority_fee_manager,
            self.cleanup_mode,
            self.cleanup_with_priority_fee,
            self.cleanup_force_close_with_burn
        )

    async def _handle_tp_sl_exit(self, token_info: TokenInfo, buy_result: TradeResult) -> None:
        """Handle take profit/stop loss exit strategy with concurrent monitoring.
        
        Args:
            token_info: Token information
            buy_result: Result from the buy operation
        """
        # Use semaphore to limit concurrent position monitoring
        async with self.position_semaphore:
            # Create position
            position = Position.create_from_buy_result(
                mint=token_info.mint,
                symbol=token_info.symbol,
                entry_price=buy_result.price,  # type: ignore
                quantity=buy_result.amount,    # type: ignore
                take_profit_percentage=self.take_profit_percentage,
                stop_loss_percentage=self.stop_loss_percentage,
                max_hold_time=self.max_hold_time,
            )
            
            # Store position
            position_key = str(token_info.mint)
            self.active_positions[position_key] = position
            
            logger.info(f"Created position: {position}")
            if position.take_profit_price:
                logger.info(f"Take profit target: {position.take_profit_price:.8f} SOL")
            if position.stop_loss_price:
                logger.info(f"Stop loss target: {position.stop_loss_price:.8f} SOL")
            
            # Start monitoring task
            monitor_task = asyncio.create_task(
                self._monitor_position_until_exit(token_info, position)
            )
            self.monitoring_tasks[position_key] = monitor_task
            
            # Clean up completed monitoring tasks
            monitor_task.add_done_callback(
                lambda t: self.monitoring_tasks.pop(position_key, None)
            )

    async def _handle_time_based_exit(self, token_info: TokenInfo) -> None:
        """Handle legacy time-based exit strategy.
        
        Args:
            token_info: Token information
        """
        logger.info(
            f"Waiting for {self.wait_time_after_buy} seconds before selling..."
        )
        
        # Wait with shutdown check
        try:
            await asyncio.wait_for(
                self.shutdown_event.wait(), 
                timeout=self.wait_time_after_buy
            )
            # If shutdown event was set, don't proceed with selling
            logger.info("Shutdown requested during wait, skipping sell")
            return
        except asyncio.TimeoutError:
            # Normal timeout, proceed with selling
            pass

        if self.shutdown_event.is_set():
            return

        logger.info(f"Selling {token_info.symbol}...")
        sell_result: TradeResult = await self.seller.execute(token_info)

        if sell_result.success:
            logger.info(f"Successfully sold {token_info.symbol}")
            self._log_trade(
                "sell",
                token_info,
                sell_result.price,  # type: ignore
                sell_result.amount,  # type: ignore
                sell_result.tx_signature,
            )
            # Close ATA if enabled
            await handle_cleanup_after_sell(
                self.solana_client, 
                self.wallet, 
                token_info.mint, 
                self.priority_fee_manager,
                self.cleanup_mode,
                self.cleanup_with_priority_fee,
                self.cleanup_force_close_with_burn
            )
        else:
            logger.error(
                f"Failed to sell {token_info.symbol}: {sell_result.error_message}"
            )

    async def _monitor_position_until_exit(self, token_info: TokenInfo, position: Position) -> None:
        """Monitor a position until exit conditions are met.
        
        Args:
            token_info: Token information
            position: Position to monitor
        """
        logger.info(f"Starting position monitoring (check interval: {self.price_check_interval}s)")
        position_key = str(token_info.mint)
        
        try:
            while position.is_active and not self.shutdown_event.is_set():
                try:
                    # Get current price from bonding curve
                    current_price = await self.curve_manager.calculate_price(token_info.bonding_curve)
                    
                    # Check if position should be exited
                    should_exit, exit_reason = position.should_exit(current_price)
                    
                    if should_exit and exit_reason:
                        logger.info(f"Exit condition met: {exit_reason.value}")
                        logger.info(f"Current price: {current_price:.8f} SOL")
                        
                        # Log PnL before exit
                        pnl = position.get_pnl(current_price)
                        logger.info(f"Position PnL: {pnl['price_change_pct']:.2f}% ({pnl['unrealized_pnl_sol']:.6f} SOL)")
                        
                        # Execute sell
                        sell_result = await self.seller.execute(token_info)
                        
                        if sell_result.success:
                            # Close position with actual exit price
                            position.close_position(sell_result.price, exit_reason)  # type: ignore
                            
                            logger.info(f"Successfully exited position: {exit_reason.value}")
                            self._log_trade(
                                "sell",
                                token_info,
                                sell_result.price,  # type: ignore
                                sell_result.amount,  # type: ignore
                                sell_result.tx_signature,
                            )
                            
                            # Log final PnL
                            final_pnl = position.get_pnl()
                            logger.info(f"Final PnL: {final_pnl['price_change_pct']:.2f}% ({final_pnl['unrealized_pnl_sol']:.6f} SOL)")
                            
                            # Close ATA if enabled
                            await handle_cleanup_after_sell(
                                self.solana_client, 
                                self.wallet, 
                                token_info.mint, 
                                self.priority_fee_manager,
                                self.cleanup_mode,
                                self.cleanup_with_priority_fee,
                                self.cleanup_force_close_with_burn
                            )
                        else:
                            logger.error(f"Failed to exit position: {sell_result.error_message}")
                            # Keep monitoring in case sell can be retried
                            
                        break
                    else:
                        # Log current status
                        pnl = position.get_pnl(current_price)
                        logger.debug(f"Position status: {current_price:.8f} SOL ({pnl['price_change_pct']:+.2f}%)")
                    
                    # Wait before next price check with shutdown awareness
                    try:
                        await asyncio.wait_for(
                            self.shutdown_event.wait(), 
                            timeout=self.price_check_interval
                        )
                        # If shutdown event was set, exit monitoring
                        break
                    except asyncio.TimeoutError:
                        # Normal timeout, continue monitoring
                        continue
                    
                except Exception as e:
                    logger.error(f"Error monitoring position: {e}")
                    await asyncio.sleep(self.price_check_interval)  # Continue monitoring despite errors
                    
        except asyncio.CancelledError:
            logger.info(f"Position monitoring cancelled for {position.symbol}")
            raise
        finally:
            # Clean up position tracking
            self.active_positions.pop(position_key, None)
            logger.info(f"Position monitoring ended for {position.symbol}")

    async def _save_token_info(
        self, token_info: TokenInfo
    ) -> None:
        """Save token information to a file.

        Args:
            token_info: Token information
        """
        try:
            os.makedirs("trades", exist_ok=True)
            file_name = os.path.join("trades", f"{token_info.mint}.txt")

            with open(file_name, "w") as file:
                file.write(json.dumps(token_info.to_dict(), indent=2))

            logger.info(f"Token information saved to {file_name}")
        except Exception as e:
            logger.error(f"Failed to save token information: {e!s}")

    def _log_trade(
        self,
        action: str,
        token_info: TokenInfo,
        price: float,
        amount: float,
        tx_hash: str | None,
    ) -> None:
        """Log trade information.

        Args:
            action: Trade action (buy/sell/emergency_sell/emergency_sell_retry)
            token_info: Token information
            price: Token price in SOL
            amount: Trade amount in SOL
            tx_hash: Transaction hash
        """
        try:
            os.makedirs("trades", exist_ok=True)

            log_entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "action": action,
                "token_address": str(token_info.mint),
                "symbol": token_info.symbol,
                "price": price,
                "amount": amount,
                "tx_hash": str(tx_hash) if tx_hash else None,
            }

            with open("trades/trades.log", "a") as log_file:
                log_file.write(json.dumps(log_entry) + "\n")
        except Exception as e:
            logger.error(f"Failed to log trade information: {e!s}")