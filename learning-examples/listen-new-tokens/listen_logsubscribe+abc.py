"""
Listens for new Pump.fun token creations via Solana WebSocket.
Monitors logs for 'Create' instructions, decodes and prints token details (name, symbol, mint, etc.).
Additionally, calculates an associated bonding curve address for each token.

It is usually faster than blockSubscribe, but slower than Geyser.
"""

import asyncio
import base64
import json
import os
import struct

import base58
import websockets
from dotenv import load_dotenv
from solders.pubkey import Pubkey

load_dotenv()

WSS_ENDPOINT = os.environ.get("SOLANA_NODE_WSS_ENDPOINT")
PUMP_PROGRAM_ID = Pubkey.from_string("6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P")
TOKEN_PROGRAM_ID = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
ASSOCIATED_TOKEN_PROGRAM_ID = Pubkey.from_string("ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL")

def find_associated_bonding_curve(mint: Pubkey, bonding_curve: Pubkey) -> Pubkey:
    """
    Find the associated bonding curve for a given mint and bonding curve.
    This uses the standard ATA derivation.
    """
    derived_address, _ = Pubkey.find_program_address(
        [
            bytes(bonding_curve),
            bytes(TOKEN_PROGRAM_ID),
            bytes(mint),
        ],
        ASSOCIATED_TOKEN_PROGRAM_ID,
    )
    return derived_address


def parse_create_instruction(data):
    if len(data) < 8:
        return None
    offset = 8
    parsed_data = {}

    # Parse fields based on CreateEvent structure
    fields = [
        ("name", "string"),
        ("symbol", "string"),
        ("uri", "string"),
        ("mint", "publicKey"),
        ("bondingCurve", "publicKey"),
        ("user", "publicKey"),
        ("creator", "publicKey"),
    ]

    try:
        for field_name, field_type in fields:
            if field_type == "string":
                length = struct.unpack("<I", data[offset : offset + 4])[0]
                offset += 4
                value = data[offset : offset + length].decode("utf-8")
                offset += length
            elif field_type == "publicKey":
                value = base58.b58encode(data[offset : offset + 32]).decode("utf-8")
                offset += 32

            parsed_data[field_name] = value

        return parsed_data
    except:
        return None


async def listen_for_new_tokens():
    while True:
        try:
            async with websockets.connect(WSS_ENDPOINT) as websocket:
                subscription_message = json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "logsSubscribe",
                        "params": [
                            {"mentions": [str(PUMP_PROGRAM_ID)]},
                            {"commitment": "processed"},
                        ],
                    }
                )
                await websocket.send(subscription_message)
                print(
                    f"Listening for new token creations from program: {PUMP_PROGRAM_ID}"
                )

                # Wait for subscription confirmation
                response = await websocket.recv()
                print(f"Subscription response: {response}")

                while True:
                    try:
                        response = await websocket.recv()
                        data = json.loads(response)

                        if "method" in data and data["method"] == "logsNotification":
                            log_data = data["params"]["result"]["value"]
                            logs = log_data.get("logs", [])

                            if any(
                                "Program log: Instruction: Create" in log
                                for log in logs
                            ):
                                for log in logs:
                                    if "Program data:" in log:
                                        try:
                                            encoded_data = log.split(": ")[1]
                                            decoded_data = base64.b64decode(
                                                encoded_data
                                            )
                                            parsed_data = parse_create_instruction(
                                                decoded_data
                                            )
                                            if parsed_data and "name" in parsed_data:
                                                print(
                                                    "Signature:",
                                                    log_data.get("signature"),
                                                )
                                                for key, value in parsed_data.items():
                                                    print(f"{key}: {value}")

                                                # Calculate associated bonding curve
                                                mint = Pubkey.from_string(
                                                    parsed_data["mint"]
                                                )
                                                bonding_curve = Pubkey.from_string(
                                                    parsed_data["bondingCurve"]
                                                )
                                                associated_curve = (
                                                    find_associated_bonding_curve(
                                                        mint, bonding_curve
                                                    )
                                                )
                                                print(
                                                    f"Associated Bonding Curve: {associated_curve}"
                                                )
                                                print(
                                                    "##########################################################################################"
                                                )
                                        except Exception as e:
                                            print(f"Failed to decode: {log}")
                                            print(f"Error: {e!s}")

                    except Exception as e:
                        print(f"An error occurred while processing message: {e}")
                        break

        except Exception as e:
            print(f"Connection error: {e}")
            print("Reconnecting in 5 seconds...")
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(listen_for_new_tokens())
