import os
import sys

from solders.pubkey import Pubkey

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.pubkeys import PumpAddresses, SystemAddresses


def get_bonding_curve_address(mint: Pubkey, program_id: Pubkey) -> tuple[Pubkey, int]:
    """
    Derives the bonding curve address for a given mint
    """
    return Pubkey.find_program_address([b"bonding-curve", bytes(mint)], program_id)


def find_associated_bonding_curve(mint: Pubkey, bonding_curve: Pubkey) -> Pubkey:
    """
    Find the associated bonding curve for a given mint and bonding curve.
    This uses the standard ATA derivation.
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


def main():
    mint_address = input("Enter the token mint address: ")

    try:
        mint = Pubkey.from_string(mint_address)

        bonding_curve_address, bump = get_bonding_curve_address(
            mint, PumpAddresses.PROGRAM
        )

        # Calculate the associated bonding curve
        associated_bonding_curve = find_associated_bonding_curve(
            mint, bonding_curve_address
        )

        print("\nResults:")
        print("-" * 50)
        print(f"Token Mint:              {mint}")
        print(f"Bonding Curve:           {bonding_curve_address}")
        print(f"Associated Bonding Curve: {associated_bonding_curve}")
        print(f"Bonding Curve Bump:      {bump}")
        print("-" * 50)

    except ValueError as e:
        print(f"Error: Invalid address format - {str(e)}")


if __name__ == "__main__":
    main()
