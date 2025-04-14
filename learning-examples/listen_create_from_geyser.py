import asyncio
import os
import struct

import base58
import grpc
from dotenv import load_dotenv
from generated import geyser_pb2, geyser_pb2_grpc

load_dotenv()


GEYSER_ENDPOINT = os.getenv("GEYSER_ENDPOINT")
GEYSER_API_TOKEN = os.getenv("GEYSER_API_TOKEN")

PUMP_PROGRAM = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
PUMP_CREATE_PREFIX = struct.pack("<Q", 8576854823835016728)


async def create_geyser_connection():
    """Establish a secure connection to the Geyser endpoint."""
    auth = grpc.metadata_call_credentials(
        lambda context, callback: callback((("authorization", f"Basic {GEYSER_API_TOKEN}"),), None)
    )
    creds = grpc.composite_channel_credentials(grpc.ssl_channel_credentials(), auth)
    channel = grpc.aio.secure_channel(GEYSER_ENDPOINT, creds)
    return geyser_pb2_grpc.GeyserStub(channel)


def create_subscription_request():
    """Create a subscription request for Pump.fun transactions."""
    request = geyser_pb2.SubscribeRequest()
    request.transactions["pump_filter"].account_include.append(PUMP_PROGRAM)
    request.transactions["pump_filter"].failed = False
    request.commitment = geyser_pb2.CommitmentLevel.PROCESSED
    return request


def decode_create_instruction(ix_data: bytes, keys, accounts) -> dict:
    """Decode a create instruction from transaction data."""
    # Skip past the 8-byte discriminator prefix
    offset = 8
    
    # Extract account keys in base58 format
    def get_account_key(index):
        if index >= len(accounts):
            return "N/A"
        account_index = accounts[index]
        return base58.b58encode(keys[account_index]).decode()
    
    # Read string fields (prefixed with length)
    def read_string():
        nonlocal offset
        # Get string length (4-byte uint)
        length = struct.unpack_from("<I", ix_data, offset)[0]
        offset += 4
        # Extract and decode the string
        value = ix_data[offset:offset + length].decode()
        offset += length
        return value
    
    name = read_string()
    symbol = read_string()
    uri = read_string()
    
    token_info = {
        "name": name,
        "symbol": symbol,
        "uri": uri,
        "mint": get_account_key(0),
        "metadata": get_account_key(1),
        "bonding_curve": get_account_key(2),
        "associated_bonding_curve": get_account_key(3),
        "token_program": get_account_key(4),
        "system_program": get_account_key(5),
        "rent": get_account_key(6),
        "user": get_account_key(7),
    }
        
    return token_info


def print_token_info(info, signature):
    """Print formatted token information."""
    print("\n🎯 New Pump.fun token detected!")
    print(f"Name: {info['name']} | Symbol: {info['symbol']}")
    print(f"Mint: {info['mint']}")
    print(f"Bonding curve: {info['bonding_curve']}")
    print(f"Associated bonding curve: {info['associated_bonding_curve']}")
    print(f"Signature: {signature}")


async def monitor_pump():
    """Monitor Solana blockchain for new Pump.fun token creations."""
    stub = await create_geyser_connection()
    request = create_subscription_request()
    
    async for update in stub.Subscribe(iter([request])):
        # Skip non-transaction updates
        if not update.HasField("transaction"):
            continue
        
        tx = update.transaction.transaction.transaction
        msg = getattr(tx, "message", None)
        if msg is None:
            continue
        
        # Check each instruction in the transaction
        for ix in msg.instructions:
            if not ix.data.startswith(PUMP_CREATE_PREFIX):
                continue

            info = decode_create_instruction(ix.data, msg.account_keys, ix.accounts)
            signature = base58.b58encode(bytes(update.transaction.transaction.signature)).decode()
            print_token_info(info, signature)


if __name__ == "__main__":
    asyncio.run(monitor_pump())