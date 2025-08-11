"""
Module for checking the status of a token's bonding curve on the Solana network using
the Pump.fun program. It allows querying the bonding curve state and completion status.

Note: creator fee upgrade introduced updates in bonding curve structure.
https://github.com/pump-fun/pump-public-docs/blob/main/docs/PUMP_CREATOR_FEE_README.md
"""

import argparse
import asyncio
import os
import struct
from typing import Final

from construct import Bytes, Flag, Int64ul, Struct
from dotenv import load_dotenv
from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey

load_dotenv()

RPC_ENDPOINT = os.environ.get("SOLANA_NODE_RPC_ENDPOINT")

# Change to token you want to query
TOKEN_MINT = "..."

# Constants
PUMP_PROGRAM_ID: Final[Pubkey] = Pubkey.from_string(
    "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
)
EXPECTED_DISCRIMINATOR: Final[bytes] = struct.pack("<Q", 6966180631402821399)


class BondingCurveState:
    """
    Represents the state of a bonding curve account.

    Attributes:
        virtual_token_reserves: Virtual token reserves in the curve
        virtual_sol_reserves: Virtual SOL reserves in the curve
        real_token_reserves: Real token reserves in the curve
        real_sol_reserves: Real SOL reserves in the curve
        token_total_supply: Total token supply in the curve
        complete: Whether the curve has completed and liquidity migrated
    """

    _STRUCT_1 = Struct(
        "virtual_token_reserves" / Int64ul,
        "virtual_sol_reserves" / Int64ul,
        "real_token_reserves" / Int64ul,
        "real_sol_reserves" / Int64ul,
        "token_total_supply" / Int64ul,
        "complete" / Flag,
    )

    # Struct after creator fee update has been introduced
    # https://github.com/pump-fun/pump-public-docs/blob/main/docs/PUMP_CREATOR_FEE_README.md
    _STRUCT_2 = Struct(
        "virtual_token_reserves" / Int64ul,
        "virtual_sol_reserves" / Int64ul,
        "real_token_reserves" / Int64ul,
        "real_sol_reserves" / Int64ul,
        "token_total_supply" / Int64ul,
        "complete" / Flag,
        "creator" / Bytes(32),  # Added new creator field - 32 bytes for Pubkey
    )

    def __init__(self, data: bytes) -> None:
        """Parse bonding curve data."""
        if data[:8] != EXPECTED_DISCRIMINATOR:
            raise ValueError("Invalid curve state discriminator")

        if len(data) < 150:
            parsed = self._STRUCT_1.parse(data[8:])
            self.__dict__.update(parsed)

        else:
            parsed = self._STRUCT_2.parse(data[8:])
            self.__dict__.update(parsed)
            # Convert raw bytes to Pubkey for creator field
            if hasattr(self, "creator") and isinstance(self.creator, bytes):
                self.creator = Pubkey.from_bytes(self.creator)


def get_associated_bonding_curve_address(
    mint: Pubkey, program_id: Pubkey
) -> tuple[Pubkey, int]:
    """
    Derives the associated bonding curve address for a given mint.

    Args:
        mint: The token mint address
        program_id: The program ID for the bonding curve

    Returns:
        Tuple of (bonding curve address, bump seed)
    """
    return Pubkey.find_program_address([b"bonding-curve", bytes(mint)], program_id)


async def get_bonding_curve_state(
    conn: AsyncClient, curve_address: Pubkey
) -> BondingCurveState:
    """
    Fetches and validates the state of a bonding curve account.

    Args:
        conn: AsyncClient connection to Solana RPC
        curve_address: Address of the bonding curve account

    Returns:
        BondingCurveState object containing parsed account data

    Raises:
        ValueError: If account data is invalid or missing
    """
    response = await conn.get_account_info(curve_address, encoding="base64")
    if not response.value or not response.value.data:
        raise ValueError("Invalid curve state: No data")

    data = response.value.data
    if data[:8] != EXPECTED_DISCRIMINATOR:
        raise ValueError("Invalid curve state discriminator")

    return BondingCurveState(data)


async def check_token_status(mint_address: str) -> None:
    """
    Checks and prints the status of a token and its bonding curve.

    Args:
        mint_address: The token mint address as a string
    """
    try:
        mint = Pubkey.from_string(mint_address)

        # Get the associated bonding curve address
        bonding_curve_address, bump = get_associated_bonding_curve_address(
            mint, PUMP_PROGRAM_ID
        )

        print("\nToken status:")
        print("-" * 50)
        print(f"Token mint:              {mint}")
        print(f"Associated bonding curve: {bonding_curve_address}")
        print(f"Bump seed:               {bump}")
        print("-" * 50)

        # Check completion status
        async with AsyncClient(RPC_ENDPOINT) as client:
            try:
                curve_state = await get_bonding_curve_state(
                    client, bonding_curve_address
                )

                print("\nBonding curve status:")
                print("-" * 50)
                print(
                    f"Completion status: {'Completed' if curve_state.complete else 'Not completed'}"
                )
                if curve_state.complete:
                    print(
                        "\nNote: This bonding curve has completed and liquidity has been migrated to PumpSwap."
                    )
                print("-" * 50)

            except ValueError as e:
                print(f"\nError accessing bonding curve: {e}")

    except ValueError as e:
        print(f"\nError: Invalid address format - {e}")
    except Exception as e:
        print(f"\nUnexpected error: {e}")


def main() -> None:
    """Main entry point for the token status checker."""
    parser = argparse.ArgumentParser(description="Check token bonding curve status")
    parser.add_argument(
        "mint_address", nargs="?", help="The token mint address", default=TOKEN_MINT
    )
    args = parser.parse_args()

    asyncio.run(check_token_status(args.mint_address))


if __name__ == "__main__":
    main()
