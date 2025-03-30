import asyncio
import os
import struct

import base58
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed
from solana.rpc.types import MemcmpOpts, TxOpts
from solders.compute_budget import set_compute_unit_limit, set_compute_unit_price
from solders.instruction import AccountMeta, Instruction
from solders.keypair import Keypair
from solders.message import Message
from solders.pubkey import Pubkey
from solders.transaction import VersionedTransaction
from spl.token.instructions import get_associated_token_address

RPC_ENDPOINT = os.environ.get("SOLANA_NODE_RPC_ENDPOINT")
TOKEN_MINT = Pubkey.from_string("35ySx7Rt3RqeTp75QB81FgRvPT5yDY2m5BupsUYDpump")
PRIVATE_KEY = base58.b58decode(os.environ.get("SOLANA_PRIVATE_KEY"))
PAYER = Keypair.from_bytes(PRIVATE_KEY)
SLIPPAGE = 0.25  # Slippage tolerance

TOKEN_DECIMALS = 6
SELL_DISCRIMINATOR = struct.pack("<Q", 3739823480024040365)

SOL = Pubkey.from_string("So11111111111111111111111111111111111111112")
PUMP_AMM_PROGRAM_ID = Pubkey.from_string("pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA")
PUMP_SWAP_GLOBAL_CONFIG = Pubkey.from_string("ADyA8hdefvWN2dbGGWFotbzWxrAvLW83WG6QCVXvJKqw")
PUMP_PROTOCOL_FEE_RECIPIENT = Pubkey.from_string("7VtfL8fvgNfhz17qKRMjzQEXgbdpnHHHQRh54R9jP2RJ")
PUMP_PROTOCOL_FEE_RECIPIENT_TOKEN_ACCOUNT = Pubkey.from_string("7GFUN3bWzJMKMRZ34JLsvcqdssDbXnp589SiE33KVwcC")
SYSTEM_TOKEN_PROGRAM = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
SYSTEM_PROGRAM = Pubkey.from_string("11111111111111111111111111111111")
SYSTEM_ASSOCIATED_TOKEN_ACCOUNT_PROGRAM = Pubkey.from_string("ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL")
PUMP_SWAP_EVENT_AUTHORITY = Pubkey.from_string("GS4CU59F31iL7aR2Q8zVS8DRrcRnXX1yjQ66TqNVQnaR")


async def get_market_address_by_base_mint(client: AsyncClient, base_mint_address: Pubkey, amm_program_id: Pubkey) -> Pubkey:
    base_mint_bytes = bytes(base_mint_address)
    offset = 43  # This should be calculated based on the fields before the base_mint field
    filters = [
        MemcmpOpts(offset=offset, bytes=base_mint_bytes)
    ]
        
    response = await client.get_program_accounts(
        amm_program_id,
        encoding="jsonParsed",
        filters=filters
    )

    market_address = [account.pubkey for account in response.value][0]
    return market_address
    
async def get_market_data(client: AsyncClient, market_address: Pubkey):
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

async def get_token_price_from_pool(client: AsyncClient, pool_base_token_account: Pubkey, pool_quote_token_account: Pubkey) -> float:
    base_balance_resp = await client.get_token_account_balance(pool_base_token_account)
    quote_balance_resp = await client.get_token_account_balance(pool_quote_token_account)
        
    base_amount = float(base_balance_resp.value.ui_amount)
    quote_amount = float(quote_balance_resp.value.ui_amount)
    token_price = base_amount / quote_amount
    
    return token_price, base_amount, quote_amount

async def calculate_sol_amount_from_token(client: AsyncClient, token_amount: float, pool_base_token_account: Pubkey, pool_quote_token_account: Pubkey) -> float:
    _, base_amount, quote_amount = await get_token_price_from_pool(client, pool_base_token_account, pool_quote_token_account)
    
    k = base_amount * quote_amount
    new_base_amount = base_amount + token_amount
    new_quote_amount = k / new_base_amount
    sol_amount = quote_amount - new_quote_amount
        
    sol_received = sol_amount * (1 - 0.25 / 100)

    return sol_received

def create_ata_idempotent_ix(payer_pubkey, owner_pubkey):
    """
    Create an instruction to create an Associated Token Account for WSOL in an idempotent way.
    """
    associated_token_address = get_associated_token_address(owner_pubkey, SOL)
    instruction_accounts = [
        AccountMeta(pubkey=payer_pubkey, is_signer=True, is_writable=True),
        AccountMeta(pubkey=associated_token_address, is_signer=False, is_writable=True),
        AccountMeta(pubkey=owner_pubkey, is_signer=False, is_writable=False),
        AccountMeta(pubkey=SOL, is_signer=False, is_writable=False),
        AccountMeta(pubkey=SYSTEM_PROGRAM, is_signer=False, is_writable=False),
        AccountMeta(pubkey=SYSTEM_TOKEN_PROGRAM, is_signer=False, is_writable=False),
    ]
    data = bytes([1])
    return Instruction(SYSTEM_ASSOCIATED_TOKEN_ACCOUNT_PROGRAM, data, instruction_accounts)

async def sell_pump_swap(client: AsyncClient, pump_fun_amm_pool: Pubkey, payer: Keypair,
                          base_mint: Pubkey, user_base_token_account: Pubkey, 
                          user_quote_token_account: Pubkey, pool_base_token_account: Pubkey, 
                          pool_quote_token_account: Pubkey, slippage: float = 0.25):
    
    token_balance = await client.get_token_account_balance(user_quote_token_account)
    token_balance_decimal = token_balance / 10**TOKEN_DECIMALS
    print(f"Token balance: {token_balance_decimal}")
    if token_balance == 0:
        print("No tokens to sell.")
        return

    token_price, base_amount, quote_amount = await get_token_price_from_pool(client, pool_base_token_account, pool_quote_token_account)
    
    k = base_amount * quote_amount
    new_quote_amount = quote_amount + token_balance_decimal
    new_base_amount = k / new_quote_amount
    expected_sol_amount = base_amount - new_base_amount
    
    expected_sol_after_fee = expected_sol_amount * (1 - 0.25 / 100)
    min_sol_output_float = expected_sol_after_fee * (1 - slippage)
    min_sol_output = min(int(min_sol_output_float * 10**9), 18_446_744_073_709_551_615)
    
    print(f"Selling {token_balance_decimal} tokens")
    print(f"Expected SOL: {expected_sol_after_fee:.9f}")
    print(f"Min SOL with {slippage*100}% slippage: {min_sol_output/10**9:.9f}")

    print(f"Token balance to sell (raw): {token_balance}")
    print(f"Min SOL output (raw): {min_sol_output}")

    data = SELL_DISCRIMINATOR + struct.pack("<Q", token_balance) + struct.pack("<Q", min_sol_output)

    accounts = [
            AccountMeta(pubkey=pump_fun_amm_pool, is_signer=False, is_writable=False),
            AccountMeta(pubkey=payer.pubkey(), is_signer=True, is_writable=True),
            AccountMeta(pubkey=PUMP_SWAP_GLOBAL_CONFIG, is_signer=False, is_writable=False),
            AccountMeta(pubkey=base_mint, is_signer=False, is_writable=False),
            AccountMeta(pubkey=SOL, is_signer=False, is_writable=False),
            AccountMeta(pubkey=user_base_token_account, is_signer=False, is_writable=True),
            AccountMeta(pubkey=user_quote_token_account, is_signer=False, is_writable=True),
            AccountMeta(pubkey=pool_base_token_account, is_signer=False, is_writable=True),
            AccountMeta(pubkey=pool_quote_token_account, is_signer=False, is_writable=True),
            AccountMeta(pubkey=PUMP_PROTOCOL_FEE_RECIPIENT, is_signer=False, is_writable=False),
            AccountMeta(pubkey=PUMP_PROTOCOL_FEE_RECIPIENT_TOKEN_ACCOUNT, is_signer=False, is_writable=True),
            AccountMeta(pubkey=SYSTEM_TOKEN_PROGRAM, is_signer=False, is_writable=False),
            AccountMeta(pubkey=SYSTEM_TOKEN_PROGRAM, is_signer=False, is_writable=False),
            AccountMeta(pubkey=SYSTEM_PROGRAM, is_signer=False, is_writable=False),
            AccountMeta(pubkey=SYSTEM_ASSOCIATED_TOKEN_ACCOUNT_PROGRAM, is_signer=False, is_writable=False),
            AccountMeta(pubkey=PUMP_SWAP_EVENT_AUTHORITY, is_signer=False, is_writable=False),
            AccountMeta(pubkey=PUMP_AMM_PROGRAM_ID, is_signer=False, is_writable=False),
    ]
    
    compute_limit_ix = set_compute_unit_limit(87_122)
    compute_price_ix = set_compute_unit_price(10_000)
    create_ata_ix = create_ata_idempotent_ix(
        payer_pubkey=payer.pubkey(),
        owner_pubkey=payer.pubkey()
    )
    
    sell_ix = Instruction(PUMP_AMM_PROGRAM_ID, data, accounts)
    
    blockhash_resp = await client.get_latest_blockhash()
    recent_blockhash = blockhash_resp.value.blockhash
    
    msg = Message.new_with_blockhash(
        [compute_limit_ix, compute_price_ix, create_ata_ix, sell_ix],
        payer.pubkey(),
        recent_blockhash
    )
    
    tx_sell = VersionedTransaction(
        message=msg,
        keypairs=[payer]
    )
    
    try:
        tx_sig = await client.send_transaction(
            tx_sell,
            opts=TxOpts(skip_preflight=True, preflight_commitment=Confirmed),
        )
        
        tx_hash = tx_sig.value
        print(f"Transaction sent: https://explorer.solana.com/tx/{tx_hash}")
        await client.confirm_transaction(tx_hash, commitment="confirmed")
        print("Transaction confirmed")
        return tx_hash
    except Exception as e:
        print(f"Error sending transaction: {e!s}")
        return None


async def main():
    async with AsyncClient(RPC_ENDPOINT) as client:
        market_address = await get_market_address_by_base_mint(client, TOKEN_MINT)
        market_data = await get_market_data(client, market_address)
        
        await sell_pump_swap(
            client,
            PUMP_AMM_PROGRAM_ID,
            PAYER,
            Pubkey.from_string(TOKEN_MINT),
            await get_associated_token_address(PAYER, TOKEN_MINT),
            await get_associated_token_address(PAYER, SOL),
            market_data["pool_base_token_account"],
            market_data["pool_quote_token_account"],
            SLIPPAGE
        )

if __name__ == "__main__":
    asyncio.run(main())
