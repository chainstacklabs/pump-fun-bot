from solders.pubkey import Pubkey

# Global constants
PUMP_PROGRAM = Pubkey.from_string("6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P")
SYSTEM_TOKEN_PROGRAM = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
SYSTEM_ASSOCIATED_TOKEN_ACCOUNT_PROGRAM = Pubkey.from_string(
    "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL"
)

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
            bytes(SYSTEM_TOKEN_PROGRAM),
            bytes(mint),
        ],
        SYSTEM_ASSOCIATED_TOKEN_ACCOUNT_PROGRAM,
    )
    return derived_address


def main():
    mint_address = input("Enter the token mint address: ")

    try:
        mint = Pubkey.from_string(mint_address)

        bonding_curve_address, bump = get_bonding_curve_address(
            mint, PUMP_PROGRAM
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
        print(f"Error: Invalid address format - {e!s}")


if __name__ == "__main__":
    main()
