import asyncio
import os
import struct

from dotenv import load_dotenv
from solana.rpc.async_api import AsyncClient
from solana.rpc.types import MemcmpOpts
from solders.pubkey import Pubkey

load_dotenv()

RPC_ENDPOINT = os.environ.get("SOLANA_NODE_RPC_ENDPOINT1")
PUMP_PROGRAM_ID = Pubkey.from_string("6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P")
# Known 8-byte discriminator for bonding curve accounts
# This ensures we're only fetching bonding curve accounts
BONDING_CURVE_DISCRIMINATOR_BYTES = bytes.fromhex("17b7f83760d8ac60")


async def get_bonding_curves_by_reserves():
    """
    Fetch bonding curve accounts from the Pump.fun program that have real_token_reserves
    below a defined threshold and are not marked as complete (i.e., not migrated).
    """

    # Define the reserve threshold we're interested in
    # 100 trillion (in token base units)
    threshold = 100_000_000_000_000
    
    # Convert the threshold into 8-byte little-endian format (as stored on-chain)
    threshold_bytes = threshold.to_bytes(8, 'little')
    
    # Extract the 2 most significant bytes (bytes 6 and 7 in little-endian)
    # This helps us pre-filter for values less than 2^48 (~281T)
    msb_prefix = threshold_bytes[6:]

    async with AsyncClient(RPC_ENDPOINT, commitment="processed", timeout=120) as client:
        # Define on-chain filters for getProgramAccounts
        filters = [
            MemcmpOpts(offset=0, bytes=BONDING_CURVE_DISCRIMINATOR_BYTES),  # only bonding curve accounts
            MemcmpOpts(offset=30, bytes=msb_prefix),          # real_token_reserves < ~281T
            MemcmpOpts(offset=48, bytes=b'\x00'),             # complete == False (not migrated)
        ]

        # Query accounts matching filters
        response = await client.get_program_accounts(
            PUMP_PROGRAM_ID,
            encoding="base64",
            filters=filters
        )

        result = []
        for acc in response.value:
            raw = acc.account.data

            # Parse the account layout according to known struct (49 bytes):
            # [discriminator][virtual_token_reserves][virtual_sol_reserves]
            # [real_token_reserves][real_sol_reserves][token_total_supply][complete]
            # Example: https://solscan.io/account/ASwuqjAGjWVhojrdot9yrnXTV4hMdTEryAWkGn4UUJma#anchorData

            offset = 8  # skip 8-byte discriminator
            offset += 8  # skip virtual_token_reserves
            offset += 8  # skip virtual_sol_reserves

            # Extract real_token_reserves (u64 = 8 bytes, little-endian)
            real_token_reserves = struct.unpack("<Q", raw[offset:offset + 8])[0]
            offset += 8

            # Post-filter: ensure value is really below the defined threshold
            if real_token_reserves < threshold:
                print(f"Pubkey: {acc.pubkey}")
                print(f"Real token reserves: {real_token_reserves / 10**6} tokens")
                print("="*50)
                result.append(acc)

        return result


async def main():
    bonding_curves_response = await get_bonding_curves_by_reserves()
    print(f"Total matches: {len(bonding_curves_response)}")


if __name__ == "__main__":
    asyncio.run(main())
