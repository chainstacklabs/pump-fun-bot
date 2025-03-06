"""
Main trading coordinator for pump.fun tokens.
"""

import asyncio
import json
import os
from datetime import datetime

import config
from src.core.client import SolanaClient
from src.core.curve import BondingCurveManager
from src.core.pubkeys import PumpAddresses
from src.core.wallet import Wallet
from src.monitoring.listener import PumpTokenListener
from src.trading.base import TokenInfo, TradeResult
from src.trading.buyer import TokenBuyer
from src.trading.seller import TokenSeller
from src.utils.logger import get_logger

logger = get_logger(__name__)


class PumpTrader:
    """Coordinates trading operations for pump.fun tokens."""

    def __init__(
        self,
        rpc_endpoint: str,
        wss_endpoint: str,
        private_key: str,
        buy_amount: float,
        buy_slippage: float,
        sell_slippage: float,
        max_retries: int = 5,
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
        """
        self.solana_client = SolanaClient(rpc_endpoint)
        self.wallet = Wallet(private_key)
        self.curve_manager = BondingCurveManager(self.solana_client)

        self.buyer = TokenBuyer(
            self.solana_client,
            self.wallet,
            self.curve_manager,
            buy_amount,
            buy_slippage,
            max_retries,
        )

        self.seller = TokenSeller(
            self.solana_client,
            self.wallet,
            self.curve_manager,
            sell_slippage,
            max_retries,
        )

        self.token_listener = PumpTokenListener(wss_endpoint, PumpAddresses.PROGRAM)

        self.buy_amount = buy_amount
        self.buy_slippage = buy_slippage
        self.sell_slippage = sell_slippage
        self.max_retries = max_retries

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

        try:
            await self.token_listener.listen_for_tokens(
                lambda token: self._handle_new_token(token, marry_mode, yolo_mode),
                match_string,
                bro_address,
            )

        except Exception as e:
            logger.error(f"Trading stopped due to error: {str(e)}")
            await self.solana_client.close()

    async def _handle_new_token(
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
            logger.error(f"Error handling token {token_info.symbol}: {str(e)}")

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
            "tx_hash": tx_hash,
        }

        with open("trades/trades.log", "a") as log_file:
            log_file.write(json.dumps(log_entry) + "\n")
