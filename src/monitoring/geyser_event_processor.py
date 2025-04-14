"""
Event processing for pump.fun tokens using Geyser data.
"""

import struct
from typing import Final

from solders.pubkey import Pubkey

from trading.base import TokenInfo
from utils.logger import get_logger

logger = get_logger(__name__)


class GeyserEventProcessor:
    """Processes token creation events from Geyser stream."""

    CREATE_DISCRIMINATOR: Final[bytes] = struct.pack("<Q", 8576854823835016728)

    def __init__(self, pump_program: Pubkey):
        """Initialize event processor.

        Args:
            pump_program: Pump.fun program address
        """
        self.pump_program = pump_program

    def process_transaction_data(self, instruction_data: bytes, accounts: list, keys: list) -> TokenInfo | None:
        """Process transaction data and extract token creation info.

        Args:
            instruction_data: Raw instruction data
            accounts: List of account indices
            keys: List of account public keys

        Returns:
            TokenInfo if token creation found, None otherwise
        """
        if not instruction_data.startswith(self.CREATE_DISCRIMINATOR):
            return None

        try:
            # Skip past the 8-byte discriminator
            offset = 8
            
            # Helper to read strings (prefixed with length)
            def read_string():
                nonlocal offset
                # Get string length (4-byte uint)
                length = struct.unpack_from("<I", instruction_data, offset)[0]
                offset += 4
                # Extract and decode the string
                value = instruction_data[offset:offset + length].decode("utf-8")
                offset += length
                return value
            
            # Helper to get account key
            def get_account_key(index):
                if index >= len(accounts):
                    return None
                account_index = accounts[index]
                if account_index >= len(keys):
                    return None
                return Pubkey.from_bytes(keys[account_index])
            
            name = read_string()
            symbol = read_string()
            uri = read_string()

            mint = get_account_key(0)
            bonding_curve = get_account_key(2)
            associated_bonding_curve = get_account_key(3)
            user = get_account_key(7)
            
            if not all([mint, bonding_curve, associated_bonding_curve, user]):
                logger.warning("Missing required account keys in token creation")
                return None
            
            return TokenInfo(
                name=name,
                symbol=symbol,
                uri=uri,
                mint=mint,
                bonding_curve=bonding_curve,
                associated_bonding_curve=associated_bonding_curve,
                user=user,
            )
            
        except Exception as e:
            logger.error(f"Failed to process transaction data: {e}")
            return None
