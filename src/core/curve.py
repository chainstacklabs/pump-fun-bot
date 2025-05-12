"""
Bonding curve operations for pump.fun tokens.
"""

import struct
from typing import Final

from construct import Bytes, Flag, Int64ul, Struct
from solders.pubkey import Pubkey

from core.client import SolanaClient
from core.pubkeys import LAMPORTS_PER_SOL, TOKEN_DECIMALS
from utils.logger import get_logger

logger = get_logger(__name__)

# Discriminator for the bonding curve account
EXPECTED_DISCRIMINATOR: Final[bytes] = struct.pack("<Q", 6966180631402821399)


class BondingCurveState:
    """Represents the state of a pump.fun bonding curve."""

    _STRUCT = Struct(
        "virtual_token_reserves" / Int64ul,
        "virtual_sol_reserves" / Int64ul,
        "real_token_reserves" / Int64ul,
        "real_sol_reserves" / Int64ul,
        "token_total_supply" / Int64ul,
        "complete" / Flag,
        "creator" / Bytes(32),  # Added new creator field - 32 bytes for Pubkey
    )

    def __init__(self, data: bytes) -> None:
        """Parse bonding curve data.

        Args:
            data: Raw account data

        Raises:
            ValueError: If data cannot be parsed
        """
        if data[:8] != EXPECTED_DISCRIMINATOR:
            raise ValueError("Invalid curve state discriminator")

        parsed = self._STRUCT.parse(data[8:])
        self.__dict__.update(parsed)
        
        # Convert raw bytes to Pubkey for creator field
        if hasattr(self, 'creator') and isinstance(self.creator, bytes):
            self.creator = Pubkey.from_bytes(self.creator)

    def calculate_price(self) -> float:
        """Calculate token price in SOL.

        Returns:
            Token price in SOL

        Raises:
            ValueError: If reserve state is invalid
        """
        if self.virtual_token_reserves <= 0 or self.virtual_sol_reserves <= 0:
            raise ValueError("Invalid reserve state")

        return (self.virtual_sol_reserves / LAMPORTS_PER_SOL) / (
            self.virtual_token_reserves / 10**TOKEN_DECIMALS
        )

    @property
    def token_reserves(self) -> float:
        """Get token reserves in decimal form."""
        return self.virtual_token_reserves / 10**TOKEN_DECIMALS

    @property
    def sol_reserves(self) -> float:
        """Get SOL reserves in decimal form."""
        return self.virtual_sol_reserves / LAMPORTS_PER_SOL


class BondingCurveManager:
    """Manager for bonding curve operations."""

    def __init__(self, client: SolanaClient):
        """Initialize with Solana client.

        Args:
            client: Solana client for RPC calls
        """
        self.client = client

    async def get_curve_state(self, curve_address: Pubkey) -> BondingCurveState:
        """Get the state of a bonding curve.

        Args:
            curve_address: Address of the bonding curve account

        Returns:
            Bonding curve state

        Raises:
            ValueError: If curve data is invalid
        """
        try:
            account = await self.client.get_account_info(curve_address)
            if not account.data:
                raise ValueError(f"No data in bonding curve account {curve_address}")

            return BondingCurveState(account.data)

        except Exception as e:
            logger.error(f"Failed to get curve state: {e!s}")
            raise ValueError(f"Invalid curve state: {e!s}")

    async def calculate_price(self, curve_address: Pubkey) -> float:
        """Calculate the current price of a token.

        Args:
            curve_address: Address of the bonding curve account

        Returns:
            Token price in SOL
        """
        curve_state = await self.get_curve_state(curve_address)
        return curve_state.calculate_price()

    async def calculate_expected_tokens(
        self, curve_address: Pubkey, sol_amount: float
    ) -> float:
        """Calculate the expected token amount for a given SOL input.

        Args:
            curve_address: Address of the bonding curve account
            sol_amount: Amount of SOL to spend

        Returns:
            Expected token amount
        """
        curve_state = await self.get_curve_state(curve_address)
        price = curve_state.calculate_price()
        return sol_amount / price
