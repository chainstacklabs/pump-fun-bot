"""
Main trading coordinator for pump.fun tokens.
Refactored PumpTrader to only process fresh tokens from WebSocket.
"""

import asyncio
import json
import os
from datetime import datetime

import config
from core.client import SolanaClient
from core.curve import BondingCurveManager
from core.priority_fee.manager import PriorityFeeManager
from core.pubkeys import PumpAddresses
from core.wallet import Wallet
from monitoring.block_listener import BlockListener
from monitoring.logs_listener import LogsListener
from trading.base import TokenInfo, TradeResult
from trading.buyer import TokenBuyer
from trading.seller import TokenSeller
from utils.logger import get_logger

logger = get_logger(__name__)


class PumpTrader:
    """Coordinates trading operations for pump.fun tokens with focus on freshness."""

    def __init__(
        self,
        rpc_endpoint: str,
        wss_endpoint: str,
        private_key: str,
        buy_amount: float,
        buy_slippage: float,
        sell_slippage: float,
        max_retries: int = 5,
        listener_type: str = "block",  # Add this parameter
    ):
        """Initialize the pump trader.

        Args:
            rpc_endpoint: RPC endpoint URL
            wss_endpoint: WebSocket endpoint URL
            private_key: Wallet private key
            buy_amount: Amount of SOL to spend on buys
            buy_slippage: Slippage tolerance for buys
            sell_slippage: Slippage tolerance for sells
            max_retries: Maximum number of retry attempts
            listener_type: Type of listener to use ('block' or 'logs')
        """
        self.solana_client = SolanaClient(rpc_endpoint)
        self.wallet = Wallet(private_key)
        self.curve_manager = BondingCurveManager(self.solana_client)

        self.priority_fee_manager = PriorityFeeManager(
            client=self.solana_client,
            enable_dynamic_fee=config.ENABLE_DYNAMIC_PRIORITY_FEE,
            enable_fixed_fee=config.ENABLE_FIXED_PRIORITY_FEE,
            fixed_fee=config.FIXED_PRIORITY_FEE,
            extra_fee=config.EXTRA_PRIORITY_FEE,
            hard_cap=config.HARD_CAP_PRIOR_FEE,
        )

        self.buyer = TokenBuyer(
            self.solana_client,
            self.wallet,
            self.curve_manager,
            self.priority_fee_manager,
            buy_amount,
            buy_slippage,
            max_retries,
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
        if listener_type.lower() == "logs":
            self.token_listener = LogsListener(wss_endpoint, PumpAddresses.PROGRAM)
            logger.info("Using logsSubscribe listener for token monitoring")
        else:
            self.token_listener = BlockListener(wss_endpoint, PumpAddresses.PROGRAM)
            logger.info("Using blockSubscribe listener for token monitoring")

        self.buy_amount = buy_amount
        self.buy_slippage = buy_slippage
        self.sell_slippage = sell_slippage
        self.max_retries = max_retries
        self.max_token_age = config.MAX_TOKEN_AGE

        # Token processing state
        self.token_queue = asyncio.Queue()
        self.processing = False
        self.processed_tokens: set[str] = set()
        self.token_timestamps: dict[str, float] = {}
        
    async def start(
        self,
        match_string: str | None = None,
        bro_address: str | None = None,
        marry_mode: bool = False,
        yolo_mode: bool = False,
    ) -> None:
        """Start the trading bot.

        Args:
            match_string: Optional string to match in token name/symbol
            bro_address: Optional creator address to filter by
            marry_mode: If True, only buy tokens and skip selling
            yolo_mode: If True, trade continuously
        """
        logger.info("Starting pump.fun trader")
        logger.info(f"Match filter: {match_string if match_string else 'None'}")
        logger.info(f"Creator filter: {bro_address if bro_address else 'None'}")
        logger.info(f"Marry mode: {marry_mode}")
        logger.info(f"YOLO mode: {yolo_mode}")
        logger.info(f"Max token age: {self.max_token_age} seconds")

        # Start processor task
        processor_task = asyncio.create_task(
            self._process_token_queue(marry_mode, yolo_mode)
        )

        try:
            await self.token_listener.listen_for_tokens(
                lambda token: self._queue_token(token),
                match_string,
                bro_address,
            )

        except Exception as e:
            logger.error(f"Trading stopped due to error: {e!s}")
            processor_task.cancel()
            await self.solana_client.close()

    async def _queue_token(self, token_info: TokenInfo) -> None:
        """Queue a token for processing if not already processed."""
        token_key = str(token_info.mint)

        if token_key in self.processed_tokens:
            logger.debug(f"Token {token_info.symbol} already processed. Skipping...")
            return

        # Record timestamp when token was discovered
        self.token_timestamps[token_key] = asyncio.get_event_loop().time()

        await self.token_queue.put(token_info)
        logger.info(f"Queued new token: {token_info.symbol} ({token_info.mint})")

    async def _process_token_queue(self, marry_mode: bool, yolo_mode: bool) -> None:
        """Continuously process tokens from the queue, only if they're fresh."""
        while True:
            token_info = await self.token_queue.get()
            token_key = str(token_info.mint)

            # Check if token is still "fresh"
            current_time = asyncio.get_event_loop().time()
            token_age = current_time - self.token_timestamps.get(
                token_key, current_time
            )

            if token_age > self.max_token_age:
                logger.info(
                    f"Skipping token {token_info.symbol} - too old ({token_age:.1f}s > {self.max_token_age}s)"
                )
                self.token_queue.task_done()
                continue

            self.processed_tokens.add(token_key)

            logger.info(
                f"Processing fresh token: {token_info.symbol} (age: {token_age:.1f}s)"
            )
            await self._handle_token(token_info, marry_mode, yolo_mode)

            self.token_queue.task_done()

    async def _handle_token(
        self, token_info: TokenInfo, marry_mode: bool, yolo_mode: bool
    ) -> None:
        """Handle a new token creation event.

        Args:
            token_info: Token information
            marry_mode: If True, only buy tokens and skip selling
            yolo_mode: If True, continue trading after this token
        """
        try:
            await self._save_token_info(token_info)

            logger.info(
                f"Waiting for {config.WAIT_TIME_AFTER_CREATION} seconds for the bonding curve to stabilize..."
            )
            await asyncio.sleep(config.WAIT_TIME_AFTER_CREATION)

            logger.info(
                f"Buying {self.buy_amount:.6f} SOL worth of {token_info.symbol}..."
            )
            buy_result: TradeResult = await self.buyer.execute(token_info)

            if buy_result.success:
                logger.info(f"Successfully bought {token_info.symbol}")
                self._log_trade(
                    "buy",
                    token_info,
                    buy_result.price,  # type: ignore
                    buy_result.amount,  # type: ignore
                    buy_result.tx_signature,
                )
            else:
                logger.error(
                    f"Failed to buy {token_info.symbol}: {buy_result.error_message}"
                )

            # Sell token if not in marry mode
            if not marry_mode and buy_result.success:
                logger.info(
                    f"Waiting for {config.WAIT_TIME_AFTER_BUY} seconds before selling..."
                )
                await asyncio.sleep(config.WAIT_TIME_AFTER_BUY)

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
                else:
                    logger.error(
                        f"Failed to sell {token_info.symbol}: {sell_result.error_message}"
                    )
            elif marry_mode:
                logger.info("Marry mode enabled. Skipping sell operation.")

            # Wait before looking for the next token
            if yolo_mode:
                logger.info(
                    f"YOLO mode enabled. Waiting {config.WAIT_TIME_BEFORE_NEW_TOKEN} seconds before looking for next token..."
                )
            await asyncio.sleep(config.WAIT_TIME_BEFORE_NEW_TOKEN)

        except Exception as e:
            logger.error(f"Error handling token {token_info.symbol}: {e!s}")

    async def _save_token_info(self, token_info: TokenInfo) -> None:
        """Save token information to a file.

        Args:
            token_info: Token information
        """
        os.makedirs("trades", exist_ok=True)
        file_name = os.path.join("trades", f"{token_info.mint}.txt")

        with open(file_name, "w") as file:
            file.write(json.dumps(token_info.to_dict(), indent=2))

        logger.info(f"Token information saved to {file_name}")

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
            action: Trade action (buy/sell)
            token_info: Token information
            price: Token price in SOL
            amount: Trade amount in SOL
            tx_hash: Transaction hash
        """
        os.makedirs("trades", exist_ok=True)

        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "action": action,
            "token_address": str(token_info.mint),
            "symbol": token_info.symbol,
            "price": price,
            "amount": amount,
            "tx_hash": str(tx_hash),
        }

        with open("trades/trades.log", "a") as log_file:
            log_file.write(json.dumps(log_entry) + "\n")
