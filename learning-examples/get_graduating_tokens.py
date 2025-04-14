import asyncio
import os
import struct

from dotenv import load_dotenv
from solana.rpc.async_api import AsyncClient
from solana.rpc.types import MemcmpOpts, TokenAccountOpts
from solders.pubkey import Pubkey

load_dotenv()

RPC_ENDPOINT = os.environ.get("SOLANA_NODE_RPC_ENDPOINT1")
PUMP_PROGRAM_ID = Pubkey.from_string("6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P")
TOKEN_PROGRAM_ID = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")

# The 8-byte discriminator for bonding curve accounts in Pump.fun
# Used to identify account types in getProgramAccounts requests
BONDING_CURVE_DISCRIMINATOR_BYTES = bytes.fromhex("17b7f83760d8ac60")


async def get_bonding_curves_by_reserves(client: AsyncClient | None = None) -> list:
    """
    Fetch bonding curve accounts from the Pump.fun program that have real_token_reserves
    below a defined threshold and are not marked as complete (i.e., not migrated).
    
    Args:
        client: Optional AsyncClient instance. If None, a new one will be created.
        
    Returns:
        List of bonding curve accounts matching the criteria
    """
    # Define the reserve threshold we're interested in
    # 100 trillion (in token base units)
    threshold = 100_000_000_000_000
    
    # Convert the threshold into 8-byte little-endian format (as stored on-chain)
    threshold_bytes = threshold.to_bytes(8, 'little')
    
    # Extract the 2 most significant bytes to pre-filter values less than 2^48 (~281T)
    # This optimization reduces the number of accounts returned by the RPC
    msb_prefix = threshold_bytes[6:]

    should_close_client = client is None
    try:
        if should_close_client:
            client = AsyncClient(RPC_ENDPOINT, commitment="processed", timeout=120)
            await client.is_connected()
            
        # Define on-chain filters for getProgramAccounts
        filters = [
            # Match only bonding curve accounts
            MemcmpOpts(offset=0, bytes=BONDING_CURVE_DISCRIMINATOR_BYTES),
            # Real token reserves MSB bytes (pre-filter)
            MemcmpOpts(offset=30, bytes=msb_prefix),
            # Complete flag is False (not migrated)
            MemcmpOpts(offset=48, bytes=b'\x00'),
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

            # Parse account data according to the Pump.fun bonding curve layout:
            # [8] discriminator
            # [8] virtual_token_reserves (u64)
            # [8] virtual_sol_reserves (u64)
            # [8] real_token_reserves (u64)
            # [8] real_sol_reserves (u64)
            # [8] token_total_supply (u64)
            # [1] complete (bool)
            
            # Skip to real_token_reserves field (8 + 8 + 8 = 24 bytes offset)
            offset = 24
            
            # Extract real_token_reserves (u64 = 8 bytes, little-endian)
            real_token_reserves = struct.unpack("<Q", raw[offset:offset + 8])[0]

            # Post-filter: ensure value is really below the defined threshold
            if real_token_reserves < threshold:
                print(f"Pubkey: {acc.pubkey}")
                print(f"Real token reserves: {real_token_reserves / 10**6} tokens")
                print("="*50)
                result.append(acc)

        return result
    finally:
        if should_close_client and client:
            await client.close()


async def find_associated_bonding_curve(bonding_curve_address: str, client: AsyncClient | None = None):
    """
    Find the SPL token account owned by a bonding curve.
    
    A bonding curve typically owns exactly one SPL token account that represents
    the token being traded through the curve.
    
    Args:
        bonding_curve_address: The bonding curve public key (as a string)
        client: Optional AsyncClient instance. If None, a new one will be created.
        
    Returns:
        The associated SPL token account data or None if not found
    """
    should_close_client = client is None
    try:
        if should_close_client:
            client = AsyncClient(RPC_ENDPOINT)
            await client.is_connected()
            
        response = await client.get_token_accounts_by_owner(
            Pubkey.from_string(bonding_curve_address),
            TokenAccountOpts(program_id=TOKEN_PROGRAM_ID)
        )
            
        if response.value and len(response.value) > 0:
            return response.value[0].account
        else:
            print(f"No token accounts found for {bonding_curve_address}")
            return None
    except Exception as e:
        print(f"Error finding associated token account: {e}")
        return None
    finally:
        if should_close_client and client:
            await client.close()


def get_mint_address(data: bytes) -> str:
    """
    Extract the mint address from SPL token account data.
    
    In SPL token account data, the mint address is stored in the first 32 bytes.
    
    Args:
        data: The token account data as bytes
        
    Returns:
        The mint address as a base58-encoded string
    """
    # The mint address is stored in the first 32 bytes
    mint_bytes = data[:32]
    return str(Pubkey(mint_bytes))


async def main():
    async with AsyncClient(RPC_ENDPOINT, commitment="processed", timeout=120) as client:
        await client.is_connected()
        
        bonding_curves = await get_bonding_curves_by_reserves(client)
        print(f"Total matches: {len(bonding_curves)}")
        print("="*50)

        for bonding_curve in bonding_curves:
            # Find the SPL token account owned by the bonding curve
            associated_token_account = await find_associated_bonding_curve(
                str(bonding_curve.pubkey), client
            )
            
            if associated_token_account:
                mint_address = get_mint_address(associated_token_account.data)
                print(f"Bonding curve: {bonding_curve.pubkey}")
                print(f"Mint address: {mint_address}")
                print("="*50)
            
            # For demonstration, only process the first curve
            break


if __name__ == "__main__":
    asyncio.run(main())
