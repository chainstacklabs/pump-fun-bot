"""
Listens to Solana blocks for Pump.fun 'create' instructions via WebSocket.
Decodes transaction data to extract mint, bonding curve, and user details.

It is usually slower than other listeners.
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
from solders.transaction import VersionedTransaction

load_dotenv()

WSS_ENDPOINT = os.environ.get("SOLANA_NODE_WSS_ENDPOINT")
PUMP_PROGRAM_ID = Pubkey.from_string("6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P")


def load_idl(file_path):
    with open(file_path) as f:
        return json.load(f)


def decode_create_instruction(ix_data, ix_def, accounts):
    args = {}
    offset = 8  # Skip 8-byte discriminator

    for arg in ix_def["args"]:
        if arg["type"] == "string":
            length = struct.unpack_from("<I", ix_data, offset)[0]
            offset += 4
            value = ix_data[offset : offset + length].decode("utf-8")
            offset += length
        elif arg["type"] == "pubkey":
            value = base58.b58encode(ix_data[offset : offset + 32]).decode("utf-8")
            offset += 32
        else:
            raise ValueError(f"Unsupported type: {arg['type']}")

        args[arg["name"]] = value

    # Add accounts
    args["mint"] = str(accounts[0])
    args["bondingCurve"] = str(accounts[2])
    args["associatedBondingCurve"] = str(accounts[3])
    args["user"] = str(accounts[7])

    return args


# Here and later all the discriminators are precalculated. See learning-examples/discriminator.py
async def listen_and_decode_create():
    idl = load_idl("idl/pump_fun_idl.json")
    create_discriminator = 8576854823835016728

    async with websockets.connect(WSS_ENDPOINT) as websocket:
        subscription_message = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "blockSubscribe",
                "params": [
                    {"mentionsAccountOrProgram": str(PUMP_PROGRAM_ID)},
                    {
                        "commitment": "confirmed",
                        "encoding": "base64",
                        "showRewards": False,
                        "transactionDetails": "full",
                        "maxSupportedTransactionVersion": 0,
                    },
                ],
            }
        )
        await websocket.send(subscription_message)
        print(f"Subscribed to blocks mentioning program: {PUMP_PROGRAM_ID}")

        while True:
            try:
                response = await websocket.recv()
                data = json.loads(response)

                if "method" in data and data["method"] == "blockNotification":
                    if "params" in data and "result" in data["params"]:
                        block_data = data["params"]["result"]
                        if "value" in block_data and "block" in block_data["value"]:
                            block = block_data["value"]["block"]
                            if "transactions" in block:
                                for tx in block["transactions"]:
                                    if isinstance(tx, dict) and "transaction" in tx:
                                        tx_data_decoded = base64.b64decode(
                                            tx["transaction"][0]
                                        )
                                        transaction = VersionedTransaction.from_bytes(
                                            tx_data_decoded
                                        )

                                        for ix in transaction.message.instructions:
                                            if str(
                                                transaction.message.account_keys[
                                                    ix.program_id_index
                                                ]
                                            ) == str(PUMP_PROGRAM_ID):
                                                ix_data = bytes(ix.data)
                                                discriminator = struct.unpack(
                                                    "<Q", ix_data[:8]
                                                )[0]

                                                if (
                                                    discriminator
                                                    == create_discriminator
                                                ):
                                                    create_ix = next(
                                                        instr
                                                        for instr in idl["instructions"]
                                                        if instr["name"] == "create"
                                                    )
                                                    account_keys = [
                                                        str(
                                                            transaction.message.account_keys[
                                                                index
                                                            ]
                                                        )
                                                        for index in ix.accounts
                                                    ]
                                                    decoded_args = (
                                                        decode_create_instruction(
                                                            ix_data,
                                                            create_ix,
                                                            account_keys,
                                                        )
                                                    )
                                                    print(
                                                        json.dumps(
                                                            decoded_args, indent=2
                                                        )
                                                    )
                                                    print("--------------------")
                elif "result" in data:
                    print("Subscription confirmed")
                else:
                    print(
                        f"Received unexpected message type: {data.get('method', 'Unknown')}"
                    )
            except Exception as e:
                print(f"An error occurred: {e!s}")
                print(f"Error details: {type(e).__name__}")
                import traceback

                traceback.print_exc()

    print("WebSocket connection closed.")


if __name__ == "__main__":
    asyncio.run(listen_and_decode_create())
