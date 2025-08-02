"""
Pump.Fun implementation of EventParser interface.

This module parses pump.fun-specific token creation events from various sources
by implementing the EventParser interface with IDL-based parsing.
"""

import base64
import struct
from time import monotonic
from typing import Any

from solders.pubkey import Pubkey
from solders.transaction import VersionedTransaction

from core.pubkeys import SystemAddresses
from interfaces.core import EventParser, Platform, TokenInfo
from platforms.pumpfun.address_provider import PumpFunAddresses
from utils.idl_parser import IDLParser
from utils.logger import get_logger

logger = get_logger(__name__)


class PumpFunEventParser(EventParser):
    """Pump.Fun implementation of EventParser interface with IDL-based parsing."""
    
    def __init__(self, idl_parser: IDLParser):
        """Initialize pump.fun event parser with injected IDL parser.
        
        Args:
            idl_parser: Pre-loaded IDL parser for pump.fun platform
        """
        self._idl_parser = idl_parser
        
        # Get discriminators from injected IDL parser
        discriminators = self._idl_parser.get_instruction_discriminators()
        self._create_discriminator_bytes = discriminators["create"]
        self._create_discriminator = struct.unpack("<Q", self._create_discriminator_bytes)[0]
        
        logger.info("Pump.Fun event parser initialized with injected IDL parser")
    
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
        """Parse token creation from pump.fun instruction data using injected IDL parser.
        
        Args:
            instruction_data: Raw instruction data
            accounts: List of account indices
            account_keys: List of account public keys
            
        Returns:
            TokenInfo if token creation found, None otherwise
        """
        if not instruction_data.startswith(self._create_discriminator_bytes):
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

            # Parse instruction data using injected IDL parser
            decoded = self._idl_parser.decode_instruction(instruction_data, account_keys, accounts)
            if not decoded or decoded['instruction_name'] != 'create':
                return None
            
            args = decoded.get('args', {})
            
            # Extract account information based on IDL account order
            mint = get_account_key(0)
            bonding_curve = get_account_key(2)
            associated_bonding_curve = get_account_key(3)
            user = get_account_key(7)

            if not all([mint, bonding_curve, associated_bonding_curve, user]):
                return None

            # Create creator vault
            creator = Pubkey.from_string(args.get("creator", str(user))) if args.get("creator") else user
            creator_vault = self._derive_creator_vault(creator)

            return TokenInfo(
                name=args.get("name", ""),
                symbol=args.get("symbol", ""),
                uri=args.get("uri", ""),
                mint=mint,
                platform=Platform.PUMP_FUN,
                bonding_curve=bonding_curve,
                associated_bonding_curve=associated_bonding_curve,
                user=user,
                creator=creator,
                creator_vault=creator_vault,
                creation_timestamp=monotonic(),
            )

        except Exception as e:
            logger.debug(f"Failed to parse create instruction: {e}")
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

        except Exception as e:
            logger.debug(f"Failed to parse geyser transaction: {e}")
            return None
    
    def get_program_id(self) -> Pubkey:
        """Get the pump.fun program ID this parser monitors.
        
        Returns:
            Pump.fun program ID
        """
        return PumpFunAddresses.PROGRAM
    
    def get_instruction_discriminators(self) -> list[bytes]:
        """Get instruction discriminators for token creation.
        
        Returns:
            List of discriminator bytes to match
        """
        return [self._create_discriminator_bytes]
    
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

                # Decode base64 transaction data if needed
                tx_data = tx["transaction"]
                if isinstance(tx_data, list) and len(tx_data) > 0:
                    try:
                        tx_data_encoded = tx_data[0]
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
                                
                                if discriminator == self._create_discriminator:
                                    # Token creation should have substantial data and many accounts
                                    if len(ix_data) <= 8 or len(ix.accounts) < 10:
                                        continue

                                    account_keys_bytes = [
                                        bytes(key)
                                        for key in transaction.message.account_keys
                                    ]
                                    
                                    # Parse the instruction
                                    token_info = self.parse_token_creation_from_instruction(
                                        ix_data, ix.accounts, account_keys_bytes
                                    )
                                    if token_info:
                                        return token_info
                                        
                    except Exception as e:
                        logger.debug(f"Failed to parse block transaction: {e}")
                        continue
                
                # Handle already decoded transaction data
                elif isinstance(tx_data, dict) and "message" in tx_data:
                    try:
                        message = tx_data["message"]
                        if "instructions" not in message or "accountKeys" not in message:
                            continue
                            
                        for ix in message["instructions"]:
                            if "programIdIndex" not in ix or "accounts" not in ix or "data" not in ix:
                                continue
                                
                            program_idx = ix["programIdIndex"]
                            if program_idx >= len(message["accountKeys"]):
                                continue
                                
                            program_id_str = message["accountKeys"][program_idx]
                            if program_id_str != str(self.get_program_id()):
                                continue
                            
                            # Decode instruction data
                            ix_data = base64.b64decode(ix["data"])
                            
                            if len(ix_data) >= 8:
                                discriminator = struct.unpack("<Q", ix_data[:8])[0]
                                
                                if discriminator == self._create_discriminator:
                                    if len(ix_data) <= 8 or len(ix["accounts"]) < 10:
                                        continue
                                    
                                    # Convert account keys to bytes for parsing
                                    account_keys_bytes = [
                                        Pubkey.from_string(key).to_bytes() 
                                        for key in message["accountKeys"]
                                    ]
                                    
                                    token_info = self.parse_token_creation_from_instruction(
                                        ix_data, ix["accounts"], account_keys_bytes
                                    )
                                    if token_info:
                                        return token_info
                                        
                    except Exception as e:
                        logger.debug(f"Failed to parse decoded block transaction: {e}")
                        continue

            return None

        except Exception as e:
            logger.debug(f"Failed to parse block data: {e}")
            return None
    
    def _parse_create_instruction_data(self, data: bytes) -> dict | None:
        """Parse the create instruction data from pump.fun using injected IDL parser.
        
        Args:
            data: Raw instruction data
            
        Returns:
            Dictionary of parsed data or None if parsing fails
        """
        if len(data) < 8:
            return None

        # Check for the correct instruction discriminator
        discriminator = struct.unpack("<Q", data[:8])[0]
        if discriminator != self._create_discriminator:
            return None

        try:
            # Use IDL parser to decode the instruction data
            # For log data parsing, we need to create dummy account info
            dummy_accounts = list(range(20))  # Assume enough accounts
            dummy_account_keys = [b'\x00' * 32] * 20  # Dummy keys
            
            decoded = self._idl_parser.decode_instruction(data, dummy_account_keys, dummy_accounts)
            if not decoded or decoded['instruction_name'] != 'create':
                return None
            
            # Extract the arguments
            args = decoded.get('args', {})
            return {
                "name": args.get("name", ""),
                "symbol": args.get("symbol", ""),
                "uri": args.get("uri", ""),
                "creator": args.get("creator", ""),
            }
            
        except Exception as e:
            logger.debug(f"Failed to parse instruction data with IDL: {e}")
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
            PumpFunAddresses.PROGRAM,
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