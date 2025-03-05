"""
Buy operations for pump.fun tokens.
"""

import asyncio
import struct
from typing import List, Optional

import spl.token.instructions as spl_token
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed
from solana.rpc.types import TxOpts
from solders.instruction import AccountMeta, Instruction
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.system_program import TransferParams, transfer
from solders.transaction import Transaction
from spl.token.instructions import get_associated_token_address

from src.core.client import SolanaClient
from src.core.curve import BondingCurveManager
from src.core.pubkeys import (
    LAMPORTS_PER_SOL,
    TOKEN_DECIMALS,
    PumpAddresses,
    SystemAddresses,
)
from src.core.wallet import Wallet
from src.trading.base import TokenInfo, Trader, TradeResult
from src.utils.logger import get_logger

logger = get_logger(__name__)


class TokenBuyer(Trader):
    """Handles buying tokens on pump.fun."""

    def __init__(
        self,
        client: SolanaClient,
        wallet: Wallet,
        curve_manager: BondingCurveManager,
        amount: float,
        slippage: float = 0.01,
        max_retries: int = 5,
    ):
        """Initialize token buyer.

        Args:
            client: Solana client for RPC calls
            wallet: Wallet for signing transactions
            curve_manager: Bonding curve manager
            amount: Amount of SOL to spend
            slippage: Slippage tolerance (0.01 = 1%)
            max_retries: Maximum number of retry attempts
        """
        self.client = client
        self.wallet = wallet
        self.curve_manager = curve_manager
        self.amount = amount
        self.slippage = slippage
        self.max_retries = max_retries

    async def execute(self, token_info: TokenInfo, *args, **kwargs) -> TradeResult:
        """Execute buy operation.

        Args:
            token_info: Token information

        Returns:
            TradeResult with buy outcome
        """
        try:
            # Extract token info
            mint = token_info.mint
            bonding_curve = token_info.bonding_curve
            associated_bonding_curve = token_info.associated_bonding_curve

            # Convert amount to lamports
            amount_lamports = int(self.amount * LAMPORTS_PER_SOL)

            # Fetch token price
            curve_state = await self.curve_manager.get_curve_state(bonding_curve)
            token_price_sol = curve_state.calculate_price()
            token_amount = self.amount / token_price_sol

            # Calculate maximum SOL to spend with slippage
            max_amount_lamports = int(amount_lamports * (1 + self.slippage))

            logger.info(
                f"Buying {token_amount:.6f} tokens at {token_price_sol:.8f} SOL per token"
            )
            logger.info(
                f"Total cost: {self.amount:.6f} SOL (max: {max_amount_lamports / LAMPORTS_PER_SOL:.6f} SOL)"
            )

            associated_token_account = self.wallet.get_associated_token_address(mint)

            await self._ensure_associated_token_account(mint, associated_token_account)

            tx_signature = await self._send_buy_transaction(
                mint,
                bonding_curve,
                associated_bonding_curve,
                associated_token_account,
                token_amount,
                max_amount_lamports,
            )

            success = await self.client.confirm_transaction(tx_signature)

            if success:
                logger.info(f"Buy transaction confirmed: {tx_signature}")
                return TradeResult(
                    success=True,
                    tx_signature=tx_signature,
                    amount=token_amount,
                    price=token_price_sol,
                )
            else:
                return TradeResult(
                    success=False,
                    error_message=f"Transaction failed to confirm: {tx_signature}",
                )

        except Exception as e:
            logger.error(f"Buy operation failed: {str(e)}")
            return TradeResult(success=False, error_message=str(e))

    async def _ensure_associated_token_account(
        self, mint: Pubkey, associated_token_account: Pubkey
    ) -> None:
        """Ensure associated token account exists.

        Args:
            mint: Token mint
            associated_token_account: Associated token account address
        """
        try:
            solana_client = await self.client.get_client()
            account_info = await solana_client.get_account_info(
                associated_token_account
            )

            if account_info.value is None:
                logger.info(f"Creating associated token account for {mint}...")

                create_ata_ix = spl_token.create_associated_token_account(
                    payer=self.wallet.pubkey, owner=self.wallet.pubkey, mint=mint
                )

                create_ata_tx = Transaction()
                create_ata_tx.add(create_ata_ix)
                blockhash = await self.client.get_latest_blockhash()
                create_ata_tx.recent_blockhash = blockhash

                tx_sig = await self.client.send_transaction(
                    create_ata_tx, self.wallet.keypair
                )

                await self.client.confirm_transaction(tx_sig)
                logger.info(
                    f"Associated token account created: {associated_token_account}"
                )
            else:
                logger.info(
                    f"Associated token account already exists: {associated_token_account}"
                )

        except Exception as e:
            logger.error(f"Error creating associated token account: {str(e)}")
            raise

    async def _send_buy_transaction(
        self,
        mint: Pubkey,
        bonding_curve: Pubkey,
        associated_bonding_curve: Pubkey,
        associated_token_account: Pubkey,
        token_amount: float,
        max_amount_lamports: int,
    ) -> str:
        """Send buy transaction.

        Args:
            mint: Token mint
            bonding_curve: Bonding curve address
            associated_bonding_curve: Associated bonding curve address
            associated_token_account: User's token account
            token_amount: Amount of tokens to buy
            max_amount_lamports: Maximum SOL to spend in lamports

        Returns:
            Transaction signature

        Raises:
            Exception: If transaction fails after all retries
        """
        accounts = [
            AccountMeta(
                pubkey=PumpAddresses.GLOBAL, is_signer=False, is_writable=False
            ),
            AccountMeta(pubkey=PumpAddresses.FEE, is_signer=False, is_writable=True),
            AccountMeta(pubkey=mint, is_signer=False, is_writable=False),
            AccountMeta(pubkey=bonding_curve, is_signer=False, is_writable=True),
            AccountMeta(
                pubkey=associated_bonding_curve, is_signer=False, is_writable=True
            ),
            AccountMeta(
                pubkey=associated_token_account, is_signer=False, is_writable=True
            ),
            AccountMeta(pubkey=self.wallet.pubkey, is_signer=True, is_writable=True),
            AccountMeta(
                pubkey=SystemAddresses.PROGRAM, is_signer=False, is_writable=False
            ),
            AccountMeta(
                pubkey=SystemAddresses.TOKEN_PROGRAM, is_signer=False, is_writable=False
            ),
            AccountMeta(
                pubkey=SystemAddresses.RENT, is_signer=False, is_writable=False
            ),
            AccountMeta(
                pubkey=PumpAddresses.EVENT_AUTHORITY, is_signer=False, is_writable=False
            ),
            AccountMeta(
                pubkey=PumpAddresses.PROGRAM, is_signer=False, is_writable=False
            ),
        ]

        # Prepare buy instruction data
        # Discriminator for buy instruction
        discriminator = struct.pack("<Q", 16927863322537952870)
        token_amount_raw = int(token_amount * 10**TOKEN_DECIMALS)
        data = (
            discriminator
            + struct.pack("<Q", token_amount_raw)
            + struct.pack("<Q", max_amount_lamports)
        )
        buy_ix = Instruction(PumpAddresses.PROGRAM, data, accounts)

        transaction = Transaction()
        transaction.add(buy_ix)

        try:
            return await self.client.send_transaction(
                transaction,
                self.wallet.keypair,
                skip_preflight=True,
                max_retries=self.max_retries,
            )
        except Exception as e:
            logger.error(f"Buy transaction failed: {str(e)}")
            raise
