import base64
import json
import struct

from construct import Bytes, Flag, Int64ul, Struct
from solders.pubkey import Pubkey

LAMPORTS_PER_SOL = 1_000_000_000
TOKEN_DECIMALS = 6
EXPECTED_DISCRIMINATOR = struct.pack("<Q", 6966180631402821399)


class BondingCurveState:
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


def calculate_bonding_curve_price(curve_state: BondingCurveState) -> float:
    if curve_state.virtual_token_reserves <= 0 or curve_state.virtual_sol_reserves <= 0:
        raise ValueError("Invalid reserve state")

    return (curve_state.virtual_sol_reserves / LAMPORTS_PER_SOL) / (
        curve_state.virtual_token_reserves / 10**TOKEN_DECIMALS
    )


def decode_bonding_curve_data(raw_data: str) -> BondingCurveState:
    decoded_data = base64.b64decode(raw_data)
    if decoded_data[:8] != EXPECTED_DISCRIMINATOR:
        raise ValueError("Invalid curve state discriminator")
    return BondingCurveState(decoded_data)


# Load the JSON data
with open("learning-examples/raw_bondingCurve_from_getAccountInfo.json") as file:
    json_data = json.load(file)

# Extract the base64 encoded data
encoded_data = json_data["result"]["value"]["data"][0]

# Decode the data
bonding_curve_state = decode_bonding_curve_data(encoded_data)

# Calculate and print the token price
token_price_sol = calculate_bonding_curve_price(bonding_curve_state)

print("Bonding Curve State:")
print(f"  Virtual Token Reserves: {bonding_curve_state.virtual_token_reserves}")
print(f"  Virtual SOL Reserves: {bonding_curve_state.virtual_sol_reserves}")
print(f"  Real Token Reserves: {bonding_curve_state.real_token_reserves}")
print(f"  Real SOL Reserves: {bonding_curve_state.real_sol_reserves}")
print(f"  Token Total Supply: {bonding_curve_state.token_total_supply}")
print(f"  Complete: {bonding_curve_state.complete}")
print(f"\nToken Price: {token_price_sol:.10f} SOL")
