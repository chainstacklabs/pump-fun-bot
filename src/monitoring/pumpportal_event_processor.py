"""
Event processing for pump.fun tokens using PumpPortal data.
"""

from solders.pubkey import Pubkey

from core.pubkeys import PumpAddresses, SystemAddresses
from trading.base import TokenInfo
from utils.logger import get_logger

logger = get_logger(__name__)


class PumpPortalEventProcessor:
    """Processes token creation events from PumpPortal WebSocket."""

    def __init__(self, pump_program: Pubkey):
        """Initialize event processor.

        Args:
            pump_program: Pump.fun program address
        """
        self.pump_program = pump_program

    def process_token_data(self, token_data: dict) -> TokenInfo | None:
        """Process token data from PumpPortal and extract token creation info.

        Args:
            token_data: Token data from PumpPortal WebSocket

        Returns:
            TokenInfo if token creation found, None otherwise
        """
        try:
            # Extract required fields
            name = token_data.get("name", "")
            symbol = token_data.get("symbol", "")
            mint_str = token_data.get("mint")
            bonding_curve_str = token_data.get("bondingCurveKey")
            creator_str = token_data.get("traderPublicKey")  # Maps to user field
            uri = token_data.get("uri", "")

            # Additional fields available from PumpPortal but not used:
            # - initialBuy: Initial buy amount in SOL
            # - marketCapSol: Market cap in SOL
            # - vSolInBondingCurve: Virtual SOL in bonding curve
            # - vTokensInBondingCurve: Virtual tokens in bonding curve
            # - signature: Transaction signature

            if not all([name, symbol, mint_str, bonding_curve_str, creator_str]):
                logger.warning("Missing required fields in PumpPortal token data")
                return None

            # Convert string addresses to Pubkey objects
            mint = Pubkey.from_string(mint_str)
            bonding_curve = Pubkey.from_string(bonding_curve_str)
            user = Pubkey.from_string(creator_str)
            
            # For PumpPortal, we assume the creator is the same as the user
            # since PumpPortal doesn't distinguish between them
            creator = user

            # Calculate derived addresses
            associated_bonding_curve = self._find_associated_bonding_curve(
                mint, bonding_curve
            )
            creator_vault = self._find_creator_vault(creator)

            return TokenInfo(
                name=name,
                symbol=symbol,
                uri=uri,
                mint=mint,
                bonding_curve=bonding_curve,
                associated_bonding_curve=associated_bonding_curve,
                user=user,
                creator=creator,
                creator_vault=creator_vault,
            )

        except Exception as e:
            logger.error(f"Failed to process PumpPortal token data: {e}")
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
            [
                b"creator-vault",
                bytes(creator)
            ],
            PumpAddresses.PROGRAM,
        )
        return derived_address