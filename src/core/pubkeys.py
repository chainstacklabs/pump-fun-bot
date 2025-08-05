"""
System addresses and constants for Solana blockchain operations.
This module contains only system-level addresses that are shared across all platforms.
Platform-specific addresses are handled by their respective AddressProvider implementations.
"""

from typing import Final

from solders.pubkey import Pubkey

# Constants
LAMPORTS_PER_SOL: Final[int] = 1_000_000_000
TOKEN_DECIMALS: Final[int] = 6

# Core system programs
SYSTEM_PROGRAM: Final[Pubkey] = Pubkey.from_string("11111111111111111111111111111111")
TOKEN_PROGRAM: Final[Pubkey] = Pubkey.from_string(
    "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
)
ASSOCIATED_TOKEN_PROGRAM: Final[Pubkey] = Pubkey.from_string(
    "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL"
)

# System accounts
RENT: Final[Pubkey] = Pubkey.from_string(
    "SysvarRent111111111111111111111111111111111"
)

# Native SOL token
SOL_MINT: Final[Pubkey] = Pubkey.from_string(
    "So11111111111111111111111111111111111111112"
)


class SystemAddresses:
    """System-level Solana addresses shared across all platforms."""
    
    # Reference the module-level constants
    SYSTEM_PROGRAM = SYSTEM_PROGRAM
    TOKEN_PROGRAM = TOKEN_PROGRAM
    ASSOCIATED_TOKEN_PROGRAM = ASSOCIATED_TOKEN_PROGRAM
    RENT = RENT
    SOL_MINT = SOL_MINT
    
    @classmethod
    def get_all_system_addresses(cls) -> dict[str, Pubkey]:
        """Get all system addresses as a dictionary.
        
        Returns:
            Dictionary mapping address names to Pubkey objects
        """
        return {
            "system_program": cls.SYSTEM_PROGRAM,
            "token_program": cls.TOKEN_PROGRAM,
            "associated_token_program": cls.ASSOCIATED_TOKEN_PROGRAM,
            "rent": cls.RENT,
            "sol_mint": cls.SOL_MINT,
        }