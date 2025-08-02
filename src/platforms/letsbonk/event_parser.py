"""
LetsBonk implementation of EventParser interface.

This module parses LetsBonk-specific token creation events from various sources
by implementing the EventParser interface.
"""

import struct
from time import monotonic
from typing import Any, Final

from solders.pubkey import Pubkey

from interfaces.core import EventParser, Platform, TokenInfo
from platforms.letsbonk.address_provider import LetsBonkAddressProvider
from utils.logger import get_logger

logger = get_logger(__name__)


class LetsBonkEventParser(EventParser):
    """LetsBonk implementation of EventParser interface."""
    
    # Discriminator for initialize instruction from IDL
    INITIALIZE_DISCRIMINATOR: Final[bytes] = bytes([175, 175, 109, 31, 13, 152, 155, 237])
    INITIALIZE_DISCRIMINATOR_INT: Final[int] = struct.unpack("<Q", INITIALIZE_DISCRIMINATOR)[0]
    
    def __init__(self):
        """Initialize LetsBonk event parser."""
        self.address_provider = LetsBonkAddressProvider()
    
    @property
    def platform(self) -> Platform:
        """Get the platform this parser serves."""
        return Platform.LETS_BONK
    
    def parse_token_creation_from_logs(
        self,
        logs: list[str],
        signature: str
    ) -> TokenInfo | None:
        """Parse token creation from LetsBonk transaction logs.
        
        Args:
            logs: List of log strings from transaction
            signature: Transaction signature
            
        Returns:
            TokenInfo if token creation found, None otherwise
        """
        # LetsBonk doesn't emit specific logs for token creation like pump.fun
        # Token creation is identified through instruction parsing
        return None
    
    def parse_token_creation_from_instruction(
        self,
        instruction_data: bytes,
        accounts: list[int],
        account_keys: list[bytes]
    ) -> TokenInfo | None:
        """Parse token creation from LetsBonk instruction data.
        
        Args:
            instruction_data: Raw instruction data
            accounts: List of account indices
            account_keys: List of account public keys
            
        Returns:
            TokenInfo if token creation found, None otherwise
        """
        if not instruction_data.startswith(self.INITIALIZE_DISCRIMINATOR):
            return None

        try:
            # Helper to get account key
            def get_account_key(index):
                if index >= len(accounts):
                    return None
                account_index = accounts[index]
                if account_index >= len(account_keys):
                    return None
                return Pubkey.from_bytes(account_keys[account_index])

            # Parse instruction data
            token_data = self._parse_initialize_instruction_data(instruction_data)
            if not token_data:
                return None

            # Extract account information based on IDL account order
            creator = get_account_key(1)  # creator account
            pool_state = get_account_key(5)  # pool_state account
            base_mint = get_account_key(6)  # base_mint account
            base_vault = get_account_key(8)  # base_vault account
            quote_vault = get_account_key(9)  # quote_vault account

            if not all([creator, pool_state, base_mint, base_vault, quote_vault]):
                return None

            return TokenInfo(
                name=token_data["name"],
                symbol=token_data["symbol"],
                uri=token_data["uri"],
                mint=base_mint,
                platform=Platform.LETS_BONK,
                pool_state=pool_state,
                base_vault=base_vault,
                quote_vault=quote_vault,
                user=creator,
                creator=creator,
                creation_timestamp=monotonic(),
            )

        except Exception:
            return None
    
    def parse_token_creation_from_geyser(
        self,
        transaction_info: Any
    ) -> TokenInfo | None:
        """Parse token creation from Geyser transaction data.
        
        Args:
            transaction_info: Geyser transaction information
            
        Returns:
            TokenInfo if token creation found, None otherwise
        """
        try:
            if not hasattr(transaction_info, 'transaction'):
                return None

            tx = transaction_info.transaction.transaction.transaction
            msg = getattr(tx, "message", None)
            if msg is None:
                return None

            for ix in msg.instructions:
                # Skip non-LetsBonk program instructions
                program_idx = ix.program_id_index
                if program_idx >= len(msg.account_keys):
                    continue

                program_id = msg.account_keys[program_idx]
                if bytes(program_id) != bytes(self.get_program_id()):
                    continue

                # Check if it's the LetsBonk platform config account
                has_platform_config = False
                for acc_idx in ix.accounts:
                    if acc_idx < len(msg.account_keys):
                        acc_key = msg.account_keys[acc_idx]
                        if bytes(acc_key) == bytes(self.address_provider.LETSBONK_PLATFORM_CONFIG):
                            has_platform_config = True
                            break
                
                if not has_platform_config:
                    continue

                # Process instruction data
                token_info = self.parse_token_creation_from_instruction(
                    ix.data, ix.accounts, msg.account_keys
                )
                if token_info:
                    return token_info

            return None

        except Exception:
            return None
    
    def get_program_id(self) -> Pubkey:
        """Get the Raydium LaunchLab program ID this parser monitors.
        
        Returns:
            Raydium LaunchLab program ID
        """
        return self.address_provider.RAYDIUM_LAUNCHLAB_PROGRAM_ID
    
    def get_instruction_discriminators(self) -> list[bytes]:
        """Get instruction discriminators for token creation.
        
        Returns:
            List of discriminator bytes to match
        """
        return [self.INITIALIZE_DISCRIMINATOR]
    
    def _parse_initialize_instruction_data(self, data: bytes) -> dict | None:
        """Parse the initialize instruction data from LetsBonk.
        
        Args:
            data: Raw instruction data
            
        Returns:
            Dictionary of parsed data or None if parsing fails
        """
        if len(data) < 8:
            return None

        # Check discriminator
        discriminator = struct.unpack("<Q", data[:8])[0]
        if discriminator != self.INITIALIZE_DISCRIMINATOR_INT:
            return None

        offset = 8
        parsed_data = {}

        try:
            # Helper functions for reading data
            def read_string():
                nonlocal offset
                if offset + 4 > len(data):
                    raise ValueError("Not enough data for string length")
                length = struct.unpack_from("<I", data, offset)[0]
                offset += 4
                if offset + length > len(data):
                    raise ValueError("Not enough data for string")
                value = data[offset:offset + length].decode('utf-8')
                offset += length
                return value
            
            def read_u8():
                nonlocal offset
                if offset + 1 > len(data):
                    raise ValueError("Not enough data for u8")
                value = struct.unpack_from("<B", data, offset)[0]
                offset += 1
                return value
            
            # Parse MintParams struct
            decimals = read_u8()
            name = read_string()
            symbol = read_string()
            uri = read_string()
            
            parsed_data["name"] = name
            parsed_data["symbol"] = symbol
            parsed_data["uri"] = uri
            parsed_data["decimals"] = decimals
            
            return parsed_data
            
        except Exception:
            return None
    
    def parse_token_creation_from_block(self, block_data: dict) -> list[TokenInfo]:
        """Parse token creations from block data (for block listener).
        
        Args:
            block_data: Block data from WebSocket
            
        Returns:
            List of TokenInfo for any token creations found
        """
        tokens = []
        
        try:
            if "transactions" not in block_data:
                return tokens

            for tx in block_data["transactions"]:
                if not isinstance(tx, dict) or "transaction" not in tx:
                    continue

                # Process transaction (implementation would be similar to pump.fun)
                # This is a simplified version - full implementation would decode
                # the transaction and check for LetsBonk initialize instructions
                pass

            return tokens

        except Exception:
            return tokens