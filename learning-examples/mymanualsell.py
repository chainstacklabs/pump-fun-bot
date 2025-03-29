from solders.instruction import Instruction, AccountMeta
from solders.pubkey import Pubkey
from solana.rpc.async_api import AsyncClient
from solana.rpc.types import MemcmpOpts
from spl.token.instructions import get_associated_token_address
from solders.keypair import Keypair
import sys
import os
import asyncio
import base58
import struct
from solana.transaction import Transaction, Message
from solders.transaction import VersionedTransaction
from solana.rpc.types import TxOpts
from solana.rpc.commitment import Confirmed
from solders.compute_budget import set_compute_unit_price, set_compute_unit_limit


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import SELL_DISCRIMINATOR, PUMP_AMM_PROGRAM_ID, PUMP_SWAP_GLOBAL, SOL, PUMP_PROTOCOL_FEE_5, PUMP_PROTOCOL_FEE_5_TA, SYSTEM_TOKEN_PROGRAM, SYSTEM_PROGRAM, SYSTEM_ASSOCIATED_TOKEN_ACCOUNT_PROGRAM, PUMP_SWAP_EVENT_AUTHORITY
TOKEN_DECIMALS = 6

EXPECTED_DISCRIMINATOR = struct.pack('8B', *SELL_DISCRIMINATOR)

COMPUTE_UNIT_PRICE = 1_000_000  # Default compute unit price (micro-lamports)
COMPUTE_UNIT_LIMIT = 87_122     # Default compute unit limit from successful transaction

rpc_url = "" #RPC URL
token_mint_address = "" #Token mint address
private_key = base58.b58decode("") #your private key
payer = Keypair.from_bytes(private_key)
slippage = 0.25


async def get_pools_with_base_mint(mint_address:Pubkey):
    async with AsyncClient(rpc_url) as client:
        mint_bytes = str(mint_address)
        filters = [
        211, 
        MemcmpOpts(offset=43, bytes=mint_bytes) 
        ]
        response = await client.get_program_accounts(
            PUMP_AMM_PROGRAM_ID,
            encoding="base64",
            filters=filters
        )
        mapped_pools = []
        for account in response.value:        
            mapped_pools.append({
                "address": account.pubkey,
                "is_native_base": False,
            })
        if len(mapped_pools) == 1:
            return mapped_pools[0]["address"]
        elif len(mapped_pools) > 1:
            print(f"Found {len(mapped_pools)} pools:")
            for i, pool in enumerate(mapped_pools):
                print(f"{i+1}: {pool['address']}")
            while True:
                try:
                    selection = int(input(f"Select a pool (1-{len(mapped_pools)}): "))
                    if 1 <= selection <= len(mapped_pools):
                        return mapped_pools[selection-1]["address"]
                    else:
                        print(f"Please enter a number between 1 and {len(mapped_pools)}")
                except ValueError:
                    print("Please enter a valid number")
        else:
            return None

def get_associated_token_account(wallet_address: Pubkey, mint_address: Pubkey):
    associated_token_account = get_associated_token_address(
        wallet_address, 
        mint_address
    )
    
    return associated_token_account

async def get_token_price_from_pool(client: AsyncClient, pool_base_token_account: Pubkey, pool_quote_token_account: Pubkey) -> float:
    try:
        base_balance_resp = await client.get_token_account_balance(pool_base_token_account)
        quote_balance_resp = await client.get_token_account_balance(pool_quote_token_account)
        
        base_amount = float(base_balance_resp.value.ui_amount)
        quote_amount = float(quote_balance_resp.value.ui_amount)
        
        print(f"Base token amount: {base_amount:,.2f}")
        print(f"Quote token amount: {quote_amount:,.2f} tokens")
        
    
        token_price = base_amount / quote_amount
        
        print(f"Current price: {token_price:,.10f} SOL per token")
        
        return token_price, base_amount, quote_amount
    
    except Exception as e:
        print(f"Error getting token price: {str(e)}")
        return 0, 0, 0

async def calculate_sol_amount_from_token(client: AsyncClient, token_amount: float, pool_base_token_account: Pubkey, pool_quote_token_account: Pubkey) -> float:
    try:
        _, base_amount, quote_amount = await get_token_price_from_pool(client, pool_base_token_account, pool_quote_token_account)
        
        k = base_amount * quote_amount
        new_base_amount = base_amount + token_amount
        new_quote_amount = k / new_base_amount
        sol_amount = quote_amount - new_quote_amount
        
        sol_received = sol_amount * (1 - 0.25 / 100)
        
        return sol_received
    except Exception as e:
        print(f"Error calculating SOL amount: {str(e)}")
        return 0

async def get_token_balance(conn: AsyncClient, associated_token_account: Pubkey):
    try:
        response = await conn.get_token_account_balance(associated_token_account)
        if hasattr(response, 'value') and response.value:
            return int(response.value.amount)
        return 0
    except Exception as e:
        print(f"Error getting token balance for {associated_token_account}: {str(e)}")
        return 0

def create_associated_token_account_idempotent_ix(payer_pubkey, owner_pubkey):
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
    
    token_balance = await get_token_balance(client, user_quote_token_account)
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

    discriminator = EXPECTED_DISCRIMINATOR
    print(f"Token balance to sell (raw): {token_balance}")
    print(f"Min SOL output (raw): {min_sol_output}")
    
    
    data = discriminator + struct.pack("<Q", token_balance) + struct.pack("<Q", min_sol_output)

    accounts = [
            AccountMeta(pubkey=pump_fun_amm_pool, is_signer=False, is_writable=False),
            AccountMeta(pubkey=payer.pubkey(), is_signer=True, is_writable=True),
            AccountMeta(pubkey=PUMP_SWAP_GLOBAL, is_signer=False, is_writable=False),
            AccountMeta(pubkey=base_mint, is_signer=False, is_writable=False),
            AccountMeta(pubkey=SOL, is_signer=False, is_writable=False),
            AccountMeta(pubkey=user_quote_token_account, is_signer=False, is_writable=True),
            AccountMeta(pubkey=user_base_token_account, is_signer=False, is_writable=True),
            AccountMeta(pubkey=pool_quote_token_account, is_signer=False, is_writable=True),
            AccountMeta(pubkey=pool_base_token_account, is_signer=False, is_writable=True),
            AccountMeta(pubkey=PUMP_PROTOCOL_FEE_5, is_signer=False, is_writable=False),
            AccountMeta(pubkey=PUMP_PROTOCOL_FEE_5_TA, is_signer=False, is_writable=True),
            AccountMeta(pubkey=SYSTEM_TOKEN_PROGRAM, is_signer=False, is_writable=False),
            AccountMeta(pubkey=SYSTEM_TOKEN_PROGRAM, is_signer=False, is_writable=False),
            AccountMeta(pubkey=SYSTEM_PROGRAM, is_signer=False, is_writable=False),
            AccountMeta(pubkey=SYSTEM_ASSOCIATED_TOKEN_ACCOUNT_PROGRAM, is_signer=False, is_writable=False),
            AccountMeta(pubkey=PUMP_SWAP_EVENT_AUTHORITY, is_signer=False, is_writable=False),
            AccountMeta(pubkey=PUMP_AMM_PROGRAM_ID, is_signer=False, is_writable=False),
    ]
    
    compute_limit_ix = set_compute_unit_limit(COMPUTE_UNIT_LIMIT)
    
    compute_price_ix = set_compute_unit_price(COMPUTE_UNIT_PRICE)
    
    create_ata_ix = create_associated_token_account_idempotent_ix(
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
        print(f"Transaction confirmed")
        return tx_hash
    except Exception as e:
        print(f"Error sending transaction: {str(e)}")
        return None

async def main():
    pooldata = await get_pools_with_base_mint(Pubkey.from_string(token_mint_address))
    

    user_base_token_account = get_associated_token_account(payer.pubkey(), SOL)
    user_quote_token_account = get_associated_token_account(payer.pubkey(), Pubkey.from_string(token_mint_address))
    pool_base_token_account = get_associated_token_account(pooldata, SOL)
    pool_quote_token_account = get_associated_token_account(pooldata, Pubkey.from_string(token_mint_address))

    print(f"User SOL token account: {user_base_token_account}")
    print(f"User token account: {user_quote_token_account}")
    print(f"Pool SOL token account: {pool_base_token_account}")
    print(f"Pool token account: {pool_quote_token_account}")

    async with AsyncClient(rpc_url) as client:
        price, _, _ = await get_token_price_from_pool(client, pool_base_token_account, pool_quote_token_account)
        print(f"Current token price: {price} SOL")
        
        await sell_pump_swap(
            client,
            pooldata,
            payer,
            Pubkey.from_string(token_mint_address),
            user_base_token_account,
            user_quote_token_account,
            pool_base_token_account,
            pool_quote_token_account,
            slippage
        )

if __name__ == "__main__":
    asyncio.run(main())
