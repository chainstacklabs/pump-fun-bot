import asyncio
import os
import struct

import base58
from solana.rpc.async_api import AsyncClient
from solana.rpc.types import MemcmpOpts
from solders.pubkey import Pubkey

RPC_ENDPOINT = os.environ.get("SOLANA_NODE_RPC_ENDPOINT")
PUMP_AMM_PROGRAM_ID = Pubkey.from_string("pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA")
TOKEN_MINT = Pubkey.from_string("35ySx7Rt3RqeTp75QB81FgRvPT5yDY2m5BupsUYDpump")


async def get_market_address_by_base_mint(base_mint_address: Pubkey, amm_program_id: Pubkey):
    async with AsyncClient(RPC_ENDPOINT) as client:
        base_mint_bytes = bytes(base_mint_address)
        
        # Define the offset for base_mint field
        offset = 43
        
        # Create the filter to match the base_mint
        filters = [
            MemcmpOpts(offset=offset, bytes=base_mint_bytes)
        ]
        
        # Retrieve the accounts that match the filter
        response = await client.get_program_accounts(
            amm_program_id,  # AMM program ID
            encoding="jsonParsed",
            filters=filters
        )

        pool_addresses = [account.pubkey for account in response.value]
        return pool_addresses[0]
    
async def get_market_data(market_address: Pubkey):
    async with AsyncClient(RPC_ENDPOINT) as client:
        response = await client.get_account_info_json_parsed(market_address)
        data = response.value.data
        parsed_data = {}

        offset = 8
        fields = [
            ("pool_bump", "u8"),
            ("index", "u16"),
            ("creator", "pubkey"),
            ("base_mint", "pubkey"),
            ("quote_mint", "pubkey"),
            ("lp_mint", "pubkey"),
            ("pool_base_token_account", "pubkey"),
            ("pool_quote_token_account", "pubkey"),
            ("lp_supply", "u64"),
        ]

        for field_name, field_type in fields:
            if field_type == "pubkey":
                value = data[offset:offset + 32]
                parsed_data[field_name] = base58.b58encode(value).decode("utf-8")
                offset += 32
            elif field_type in {"u64", "i64"}:
                value = struct.unpack("<Q", data[offset:offset + 8])[0] if field_type == "u64" else struct.unpack("<q", data[offset:offset + 8])[0]
                parsed_data[field_name] = value
                offset += 8
            elif field_type == "u16":
                value = struct.unpack("<H", data[offset:offset + 2])[0]
                parsed_data[field_name] = value
                offset += 2
            elif field_type == "u8":
                value = data[offset]
                parsed_data[field_name] = value
                offset += 1

        return parsed_data

    
async def main():
    market_address = await get_market_address_by_base_mint(TOKEN_MINT, PUMP_AMM_PROGRAM_ID)
    print(market_address)

    market_data = await get_market_data(market_address)
    print(market_data)


if __name__ == "__main__":
    asyncio.run(main())
