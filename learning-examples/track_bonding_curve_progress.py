"""
Track bonding curve progress for a pump.fun token by mint address.
"""

import asyncio
import os
import struct

from dotenv import load_dotenv
from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey

# Import pump.fun program address
from core.pubkeys import PumpAddresses

load_dotenv()

RPC_URL = os.getenv("SOLANA_NODE_RPC_ENDPOINT")
TOKEN_MINT = "xWrzYY4c1LnbSkLrd2LDUg9vw7YtVyJhGmw7MABpump"

LAMPORTS_PER_SOL = 1_000_000_000
TOKEN_DECIMALS = 6
EXPECTED_DISCRIMINATOR = struct.pack("<Q", 6966180631402821399)  # pump.fun bonding curve discriminator
POLL_INTERVAL = 5  # seconds between each status check


def get_associated_bonding_curve_address(mint: Pubkey, program_id: Pubkey) -> Pubkey:
    """Derive the bonding curve PDA address from mint."""
    return Pubkey.find_program_address([b"bonding-curve", bytes(mint)], program_id)[0]


async def get_account_data(client: AsyncClient, pubkey: Pubkey) -> bytes:
    """Fetch raw account data for a given public key."""
    resp = await client.get_account_info(pubkey, encoding="base64")
    if not resp.value or not resp.value.data:
        raise ValueError(f"Account {pubkey} not found or has no data")

    return resp.value.data


def parse_curve_state(data: bytes) -> dict:
    """Decode bonding curve account data."""
    if data[:8] != EXPECTED_DISCRIMINATOR:
        raise ValueError("Invalid discriminator for bonding curve")

    fields = struct.unpack_from("<QQQQQ?", data, 8)
    return {
        "virtual_token_reserves": fields[0] / 10**TOKEN_DECIMALS,
        "virtual_sol_reserves": fields[1] / LAMPORTS_PER_SOL,
        "real_token_reserves": fields[2] / 10**TOKEN_DECIMALS,
        "real_sol_reserves": fields[3] / LAMPORTS_PER_SOL,
        "token_total_supply": fields[4] / 10**TOKEN_DECIMALS,
        "complete": fields[5],
    }


def print_curve_status(state: dict):
    """Print current bonding curve status."""
    progress = 0
    if state["token_total_supply"]:
        progress = 100 - (100 * state["real_token_reserves"] / state["token_total_supply"])

    print("==============================")
    print(f"Complete: {'✅' if state['complete'] else '❌'}")
    print(f"Progress: {progress:.2f}%")
    print(f"Token Reserves: {state['real_token_reserves']:.4f}")
    print(f"SOL Reserves:   {state['real_sol_reserves']:.4f}")
    print("==============================\n")


async def track_curve():
    """Main loop to track bonding curve state."""
    if not RPC_URL or not TOKEN_MINT:
        print("❌ Set SOLANA_NODE_RPC_ENDPOINT and TOKEN_MINT in .env")
        return

    mint_pubkey = Pubkey.from_string(TOKEN_MINT)
    curve_pubkey = get_associated_bonding_curve_address(mint_pubkey, PumpAddresses.PROGRAM)

    print("Tracking bonding curve for:", mint_pubkey)
    print("Curve address:", curve_pubkey, "\n")

    async with AsyncClient(RPC_URL) as client:
        while True:
            try:
                data = await get_account_data(client, curve_pubkey)
                state = parse_curve_state(data)
                print_curve_status(state)
            except Exception as e:
                print(f"⚠️ Error: {e}")

            await asyncio.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    asyncio.run(track_curve())