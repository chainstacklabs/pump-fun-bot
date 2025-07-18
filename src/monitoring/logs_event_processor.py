"""
Event processing for pump.fun tokens using logsSubscribe data.
"""

import base64
import struct
from typing import Final

import base58
from solders.pubkey import Pubkey

from core.pubkeys import PumpAddresses, SystemAddresses
from trading.base import TokenInfo
from utils.logger import get_logger

logger = get_logger(__name__)


class LogsEventProcessor:
    """Processes events from pump.fun program logs."""

    # Discriminator for create instruction to avoid non-create transactions
    CREATE_DISCRIMINATOR: Final[int] = 8530921459188068891

    def __init__(self, pump_program: Pubkey):
        """Initialize event processor.

        Args:
            pump_program: Pump.fun program address
        """
        self.pump_program = pump_program

    def process_program_logs(self, logs: list[str], signature: str) -> TokenInfo | None:
        """Process program logs and extract token info.

        Args:
            logs: List of log strings from the notification
            signature: Transaction signature

        Returns:
            TokenInfo if a token creation is found, None otherwise
        """
        # Check if this is a token creation
        if not any("Program log: Instruction: Create" in log for log in logs):
            return None

        # Skip swaps as the first condition may pass them
        if any("Program log: Instruction: CreateTokenAccount" in log for log in logs):
            return None

        # Find and process program data
        for log in logs:
            if "Program data:" in log:
                try:
                    encoded_data = log.split(": ")[1]
                    decoded_data = base64.b64decode(encoded_data)
                    parsed_data = self._parse_create_instruction(decoded_data)

                    if parsed_data and "name" in parsed_data:
                        mint = Pubkey.from_string(parsed_data["mint"])
                        bonding_curve = Pubkey.from_string(parsed_data["bondingCurve"])
                        associated_curve = self._find_associated_bonding_curve(
                            mint, bonding_curve
                        )
                        creator = Pubkey.from_string(parsed_data["creator"])
                        creator_vault = self._find_creator_vault(creator)

                        return TokenInfo(
                            name=parsed_data["name"],
                            symbol=parsed_data["symbol"],
                            uri=parsed_data["uri"],
                            mint=mint,
                            bonding_curve=bonding_curve,
                            associated_bonding_curve=associated_curve,
                            user=Pubkey.from_string(parsed_data["user"]),
                            creator=creator,
                            creator_vault=creator_vault,
                        )
                except Exception as e:
                    logger.error(f"Failed to process log data: {e}")

        return None

    def _parse_create_instruction(self, data: bytes) -> dict | None:
        """Parse the create instruction data.

        Args:
            data: Raw instruction data

        Returns:
            Dictionary of parsed data or None if parsing fails
        """
        if len(data) < 8:
            return None

        # Check for the correct instruction discriminator
        discriminator = struct.unpack("<Q", data[:8])[0]
        if discriminator != self.CREATE_DISCRIMINATOR:
            logger.info(
                f"Skipping non-Create instruction with discriminator: {discriminator}"
            )
            return None

        offset = 8
        parsed_data = {}

        # Parse fields based on CreateEvent structure
        fields = [
            ("name", "string"),
            ("symbol", "string"),
            ("uri", "string"),
            ("mint", "publicKey"),
            ("bondingCurve", "publicKey"),
            ("user", "publicKey"),
            ("creator", "publicKey"),
        ]

        try:
            for field_name, field_type in fields:
                if field_type == "string":
                    length = struct.unpack("<I", data[offset : offset + 4])[0]
                    offset += 4
                    value = data[offset : offset + length].decode("utf-8")
                    offset += length
                elif field_type == "publicKey":
                    value = base58.b58encode(data[offset : offset + 32]).decode("utf-8")
                    offset += 32

                parsed_data[field_name] = value

            return parsed_data
        except Exception as e:
            logger.error(f"Failed to parse create instruction: {e}")
            return None

    def _find_associated_bonding_curve(
        self, mint: Pubkey, bonding_curve: Pubkey
    ) -> Pubkey:
        """
        Find the associated bonding curve for a given mint and bonding curve.
        This uses the standard ATA derivation.

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
