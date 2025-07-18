"""
Event processing for pump.fun tokens.
"""

import base64
import json
import struct
from typing import Any

import base58
from solders.pubkey import Pubkey
from solders.transaction import VersionedTransaction

from core.pubkeys import PumpAddresses
from trading.base import TokenInfo
from utils.logger import get_logger

logger = get_logger(__name__)


class PumpEventProcessor:
    """Processes events from pump.fun program."""

    # Discriminator for create instruction
    CREATE_DISCRIMINATOR = 8576854823835016728

    def __init__(self, pump_program: Pubkey):
        """Initialize event processor.

        Args:
            pump_program: Pump.fun program address
        """
        self.pump_program = pump_program
        self._idl = self._load_idl()

    def _load_idl(self) -> dict[str, Any]:
        """Load IDL from file.

        Returns:
            IDL as dictionary
        """
        try:
            with open("idl/pump_fun_idl.json") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load IDL: {e!s}")
            # Create a minimal IDL with just what we need
            return {
                "instructions": [
                    {
                        "name": "create",
                        "args": [
                            {"name": "name", "type": "string"},
                            {"name": "symbol", "type": "string"},
                            {"name": "uri", "type": "string"},
                        ],
                    }
                ]
            }

    def process_transaction(self, tx_data: str) -> TokenInfo | None:
        """Process a transaction and extract token info.

        Args:
            tx_data: Base64 encoded transaction data

        Returns:
            TokenInfo if a token creation is found, None otherwise
        """
        try:
            tx_data_decoded = base64.b64decode(tx_data)
            transaction = VersionedTransaction.from_bytes(tx_data_decoded)

            for ix in transaction.message.instructions:
                # Check if instruction is from pump.fun program
                program_id_index = ix.program_id_index
                if program_id_index >= len(transaction.message.account_keys):
                    continue

                program_id = transaction.message.account_keys[program_id_index]

                if str(program_id) != str(self.pump_program):
                    continue

                ix_data = bytes(ix.data)

                # Check if it's a create instruction
                if len(ix_data) < 8:
                    continue

                discriminator = struct.unpack("<Q", ix_data[:8])[0]
                if discriminator != self.CREATE_DISCRIMINATOR:
                    continue

                # Found a create instruction, decode it
                create_ix = next(
                    (
                        instr
                        for instr in self._idl["instructions"]
                        if instr["name"] == "create"
                    ),
                    None,
                )
                if not create_ix:
                    continue

                # Get account keys for this instruction
                account_keys = [
                    transaction.message.account_keys[index] for index in ix.accounts
                ]

                # Decode instruction arguments
                decoded_args = self._decode_create_instruction(
                    ix_data, create_ix, account_keys
                )
                creator = Pubkey.from_string(decoded_args["creator"])
                creator_vault = self._find_creator_vault(creator)

                return TokenInfo(
                    name=decoded_args["name"],
                    symbol=decoded_args["symbol"],
                    uri=decoded_args["uri"],
                    mint=Pubkey.from_string(decoded_args["mint"]),
                    bonding_curve=Pubkey.from_string(decoded_args["bondingCurve"]),
                    associated_bonding_curve=Pubkey.from_string(
                        decoded_args["associatedBondingCurve"]
                    ),
                    user=Pubkey.from_string(decoded_args["user"]),
                    creator=creator,
                    creator_vault=creator_vault,
                )

        except Exception as e:
            logger.error(f"Error processing transaction: {e!s}")

        return None

    def _decode_create_instruction(
        self, ix_data: bytes, ix_def: dict[str, Any], accounts: list[Pubkey]
    ) -> dict[str, Any]:
        """Decode create instruction data.

        Args:
            ix_data: Instruction data bytes
            ix_def: Instruction definition from IDL
            accounts: List of account pubkeys

        Returns:
            Decoded instruction arguments
        """
        args = {}
        offset = 8  # Skip 8-byte discriminator

        for arg in ix_def["args"]:
            if arg["type"] == "string":
                length = struct.unpack_from("<I", ix_data, offset)[0]
                offset += 4
                value = ix_data[offset : offset + length].decode("utf-8")
                offset += length
            elif arg["type"] == "pubkey":
                value = base58.b58encode(ix_data[offset : offset + 32]).decode("utf-8")
                offset += 32
            else:
                logger.warning(f"Unsupported type: {arg['type']}")
                value = None

            args[arg["name"]] = value

        args["mint"] = str(accounts[0])
        args["bondingCurve"] = str(accounts[2])
        args["associatedBondingCurve"] = str(accounts[3])
        args["user"] = str(accounts[7])

        return args

    def _find_creator_vault(self, creator: Pubkey) -> Pubkey:
        """
        Find the creator vault for a creator.

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
