"""
Solana client abstraction for blockchain operations.
"""

import asyncio
from typing import Any, Dict, List, Optional, Tuple, Union

from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed
from solana.rpc.types import TxOpts
from solana.transaction import Transaction
from solders.instruction import Instruction
from solders.keypair import Keypair
from solders.pubkey import Pubkey

from src.utils.logger import get_logger

logger = get_logger(__name__)


class SolanaClient:
    """Abstraction for Solana RPC client operations."""

    def __init__(self, rpc_endpoint: str):
        """Initialize Solana client with RPC endpoint.

        Args:
            rpc_endpoint: URL of the Solana RPC endpoint
        """
        self.rpc_endpoint = rpc_endpoint
        self._client = None

    async def get_client(self) -> AsyncClient:
        """Get or create the AsyncClient instance.

        Returns:
            AsyncClient instance
        """
        if self._client is None:
            self._client = AsyncClient(self.rpc_endpoint)
        return self._client

    async def close(self):
        """Close the client connection if open."""
        if self._client:
            await self._client.close()
            self._client = None

    async def get_account_info(self, pubkey: Pubkey) -> Dict[str, Any]:
        """Get account info from the blockchain.

        Args:
            pubkey: Public key of the account

        Returns:
            Account info response

        Raises:
            ValueError: If account doesn't exist or has no data
        """
        client = await self.get_client()
        response = await client.get_account_info(pubkey)
        if not response.value:
            raise ValueError(f"Account {pubkey} not found")
        return response.value

    async def get_token_account_balance(self, token_account: Pubkey) -> int:
        """Get token balance for an account.

        Args:
            token_account: Token account address

        Returns:
            Token balance as integer
        """
        client = await self.get_client()
        response = await client.get_token_account_balance(token_account)
        if response.value:
            return int(response.value.amount)
        return 0

    async def get_latest_blockhash(self) -> str:
        """Get the latest blockhash.

        Returns:
            Recent blockhash as string
        """
        client = await self.get_client()
        response = await client.get_latest_blockhash()
        return response.value.blockhash

    async def send_transaction(
        self,
        transaction: Transaction,
        signer: Keypair,
        skip_preflight: bool = True,
        max_retries: int = 3,
    ) -> str:
        """Send a transaction to the network.

        Args:
            transaction: Prepared transaction
            signer: Transaction signer
            skip_preflight: Whether to skip preflight checks
            max_retries: Maximum number of sending attempts

        Returns:
            Transaction signature

        Raises:
            Exception: If transaction fails after all retries
        """
        client = await self.get_client()

        # Ensure transaction has a recent blockhash
        if not transaction.recent_blockhash:
            blockhash = await self.get_latest_blockhash()
            transaction.recent_blockhash = blockhash

        # Attempt to send with retries
        for attempt in range(max_retries):
            try:
                tx_opts = TxOpts(
                    skip_preflight=skip_preflight, preflight_commitment=Confirmed
                )
                response = await client.send_transaction(
                    transaction, signer, opts=tx_opts
                )
                return response.value

            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(
                        f"Failed to send transaction after {max_retries} attempts"
                    )
                    raise

                wait_time = 2**attempt
                logger.warning(
                    f"Transaction attempt {attempt + 1} failed: {str(e)}, retrying in {wait_time}s"
                )
                await asyncio.sleep(wait_time)

    async def confirm_transaction(
        self, signature: str, commitment: str = "confirmed"
    ) -> bool:
        """Wait for transaction confirmation.

        Args:
            signature: Transaction signature
            commitment: Confirmation commitment level

        Returns:
            Whether transaction was confirmed
        """
        client = await self.get_client()
        try:
            await client.confirm_transaction(signature, commitment=commitment)
            return True
        except Exception as e:
            logger.error(f"Failed to confirm transaction {signature}: {str(e)}")
            return False
