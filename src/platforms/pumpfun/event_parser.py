"""
Pump.Fun implementation of EventParser interface.

This module parses pump.fun-specific token creation events from various sources
by implementing the EventParser interface.
"""

import base64
import struct
from time import monotonic
from typing import Any, Final

import base58
from solders.pubkey import Pubkey
from solders.transaction import VersionedTransaction

from core.pubkeys import PumpAddresses, SystemAddresses
from interfaces.core import EventParser, Platform, TokenInfo


class PumpFunEventParser(EventParser):
    """Pump.Fun implementation of EventParser interface."""
    
    # Discriminators for pump.fun instructions
    CREATE_DISCRIMINATOR: Final[int] = 8576854823835016728
    CREATE_DISCRIMINATOR_BYTES: Final[bytes] = struct.pack("<Q", CREATE_DISCRIMINATOR)
    
    # Discriminator for program logs
    LOGS_CREATE_DISCRIMINATOR: Final[int] = 8530921459188068891
    
    @property
    def platform(self) -> Platform:
        """Get the platform this parser serves."""
        return Platform.PUMP_FUN
    
    def parse_token_creation_from_logs(
        self,
        logs: list[str],
        signature: str
    ) -> TokenInfo | None:
        """Parse token creation from pump.fun transaction logs.
        
        Args:
            logs: List of log strings from transaction
            signature: Transaction signature
            
        Returns:
            TokenInfo if token creation found, None otherwise
        """
        # Check if this is a token creation
        if not any("Program log: Instruction: Create" in log for log in logs):
            return None

        # Skip swaps and other operations
        if any("Program log: Instruction: CreateTokenAccount" in log for log in logs):
            return None

        # Find and process program data
        for log in logs:
            if "Program data:" in log:
                try:
                    encoded_data = log.split(": ")[1]
                    decoded_data = base64.b64decode(encoded_data)
                    return self._parse_create_instruction_data(decoded_data)
                except Exception:
                    continue
        
        return None
    
    def parse_token_creation_from_instruction(
        self,
        instruction_data: bytes,
        accounts: list[int],
        account_keys: list[bytes]
    ) -> TokenInfo | None:
        """Parse token creation from pump.fun instruction data.
        
        Args:
            instruction_data: Raw instruction data
            accounts: List of account indices
            account_keys: List of account public keys
            
        Returns:
            TokenInfo if token creation found, None otherwise
        """
        if not instruction_data.startswith(self.CREATE_DISCRIMINATOR_BYTES):
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
            token_data = self._parse_create_instruction_data(instruction_data)
            if not token_data:
                return None

            # Extract account information
            mint = get_account_key(0)
            bonding_curve = get_account_key(2)
            associated_bonding_curve = get_account_key(3)
            user = get_account_key(7)

            if not all([mint, bonding_curve, associated_bonding_curve, user]):
                return None

            # Create creator vault
            creator = Pubkey.from_string(token_data["creator"]) if token_data.get("creator") else user
            creator_vault = self._derive_creator_vault(creator)

            return TokenInfo(
                name=token_data["name"],
                symbol=token_data["symbol"],
                uri=token_data["uri"],
                mint=mint,
                platform=Platform.PUMP_FUN,
                bonding_curve=bonding_curve,
                associated_bonding_curve=associated_bonding_curve,
                user=user,
                creator=creator,
                creator_vault=creator_vault,
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
                # Skip non-pump.fun program instructions
                program_idx = ix.program_id_index
                if program_idx >= len(msg.account_keys):
                    continue

                program_id = msg.account_keys[program_idx]
                if bytes(program_id) != bytes(self.get_program_id()):
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
        """Get the pump.fun program ID this parser monitors.
        
        Returns:
            Pump.fun program ID
        """
        return PumpAddresses.PROGRAM
    
    def get_instruction_discriminators(self) -> list[bytes]:
        """Get instruction discriminators for token creation.
        
        Returns:
            List of discriminator bytes to match
        """
        return [self.CREATE_DISCRIMINATOR_BYTES]
    
    def parse_token_creation_from_block(self, block_data: dict) -> TokenInfo | None:
        """Parse token creation from block data (for block listener).
        
        Args:
            block_data: Block data from WebSocket
            
        Returns:
            TokenInfo if token creation found, None otherwise
        """
        try:
            if "transactions" not in block_data:
                return None

            for tx in block_data["transactions"]:
                if not isinstance(tx, dict) or "transaction" not in tx:
                    continue

                # Decode base64 transaction data
                tx_data_encoded = tx["transaction"][0]
                tx_data_decoded = base64.b64decode(tx_data_encoded)
                transaction = VersionedTransaction.from_bytes(tx_data_decoded)

                for ix in transaction.message.instructions:
                    program_id = transaction.message.account_keys[ix.program_id_index]
                    
                    # Check if instruction is from pump.fun program
                    if str(program_id) != str(self.get_program_id()):
                        continue

                    ix_data = bytes(ix.data)
                    
                    # Check for create discriminator
                    if len(ix_data) >= 8:
                        discriminator = struct.unpack("<Q", ix_data[:8])[0]
                        
                        if discriminator == self.CREATE_DISCRIMINATOR:
                            # Token creation should have substantial data and many accounts
                            if len(ix_data) <= 8 or len(ix.accounts) < 10:
                                continue
                            
                            # Parse the instruction
                            token_info = self.parse_token_creation_from_instruction(
                                ix_data, ix.accounts, transaction.message.account_keys
                            )
                            if token_info:
                                return token_info

            return None

        except Exception:
            return None
    
    def _parse_create_instruction_data(self, data: bytes) -> dict | None:
        """Parse the create instruction data from pump.fun.
        
        Args:
            data: Raw instruction data
            
        Returns:
            Dictionary of parsed data or None if parsing fails
        """
        if len(data) < 8:
            return None

        # Check for the correct instruction discriminator
        discriminator = struct.unpack("<Q", data[:8])[0]
        if discriminator not in [self.CREATE_DISCRIMINATOR, self.LOGS_CREATE_DISCRIMINATOR]:
            return None

        offset = 8
        parsed_data = {}

        try:
            # Parse fields based on CreateEvent structure
            fields = [
                ("name", "string"),
                ("symbol", "string"),
                ("uri", "string"),
            ]
            
            # For instruction data, we also have creator info
            if discriminator == self.CREATE_DISCRIMINATOR:
                fields.extend([
                    ("creator", "publicKey"),
                ])

            for field_name, field_type in fields:
                if field_type == "string":
                    if offset + 4 > len(data):
                        return None
                    length = struct.unpack("<I", data[offset : offset + 4])[0]
                    offset += 4
                    if offset + length > len(data):
                        return None
                    value = data[offset : offset + length].decode("utf-8")
                    offset += length
                elif field_type == "publicKey":
                    if offset + 32 > len(data):
                        return None
                    value = base58.b58encode(data[offset : offset + 32]).decode("utf-8")
                    offset += 32

                parsed_data[field_name] = value

            return parsed_data
            
        except Exception:
            return None
    
    def _derive_creator_vault(self, creator: Pubkey) -> Pubkey:
        """Derive the creator vault for a creator.
        
        Args:
            creator: Creator address
            
        Returns:
            Creator vault address
        """
        derived_address, _ = Pubkey.find_program_address(
            [b"creator-vault", bytes(creator)],
            PumpAddresses.PROGRAM,
        )
        return derived_address
    
    def _derive_associated_bonding_curve(self, mint: Pubkey, bonding_curve: Pubkey) -> Pubkey:
        """Derive the associated bonding curve (ATA of bonding curve for the token).
        
        Args:
            mint: Token mint address
            bonding_curve: Bonding curve address
            
        Returns:
            Associated bonding curve address
        """
        derived_address, _ = Pubkey.find_program_address(
            [
                bytes(bonding_curve),
                bytes(SystemAddresses.TOKEN_PROGRAM),
                bytes(mint),
            ],
            SystemAddresses.ASSOCIATED_TOKEN_PROGRAM,
        )
        return derived_address