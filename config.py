"""
Configuration for the pump.fun trading bot.
"""

from typing import Final

import os

from dotenv import load_dotenv
from solders.pubkey import Pubkey

load_dotenv()

# System & pump.fun addresses
PUMP_PROGRAM: Final[Pubkey] = Pubkey.from_string(
    "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
)
PUMP_GLOBAL: Final[Pubkey] = Pubkey.from_string(
    "4wTV1YmiEkRvAtNtsSGPtUrqRYQMe5SKy2uB4Jjaxnjf"
)
PUMP_EVENT_AUTHORITY: Final[Pubkey] = Pubkey.from_string(
    "Ce6TQqeHC9p8KetsN6JsjHK7UTZk7nasjjnr7XxXp9F1"
)
PUMP_FEE: Final[Pubkey] = Pubkey.from_string(
    "CebN5WGQ4jvEPvsVU4EoHEpgzq1VV7AbicfhtW4xC9iM"
)
PUMP_LIQUIDITY_MIGRATOR: Final[Pubkey] = Pubkey.from_string(
    "39azUYFWPz3VHgKCf3VChUwbpURdCHRxjWVowf5jUJjg"
)
SYSTEM_PROGRAM: Final[Pubkey] = Pubkey.from_string("11111111111111111111111111111111")
SYSTEM_TOKEN_PROGRAM: Final[Pubkey] = Pubkey.from_string(
    "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
)
SYSTEM_ASSOCIATED_TOKEN_ACCOUNT_PROGRAM: Final[Pubkey] = Pubkey.from_string(
    "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL"
)
SYSTEM_RENT: Final[Pubkey] = Pubkey.from_string(
    "SysvarRent111111111111111111111111111111111"
)
SOL: Final[Pubkey] = Pubkey.from_string("So11111111111111111111111111111111111111112")
LAMPORTS_PER_SOL: Final[int] = 1_000_000_000

# Trading parameters
BUY_AMOUNT = 0.0001  # Amount of SOL to spend when buying
BUY_SLIPPAGE = 0.2  # 20% slippage tolerance for buying
SELL_SLIPPAGE = 0.2  # 20% slippage tolerance for selling
ENABLE_DYNAMIC_PRIORITY_FEE = (
    True  # getRecentPriorityFee is used to get current priority fee
)
EXTRA_PRIORITY_FEE = 0.1  # 10% increase in dynamic priority fee

TOKEN_DECIMALS: Final[int] = 6
MAX_RETRIES: int = 5
WAIT_TIME_AFTER_BUY: int = 20
WAIT_TIME_BEFORE_NEW_TOKEN: int = 5
WAIT_TIME_AFTER_CREATION: int = 15

# RPS of your node to avoid rate limit errors
# You can also get a trader node https://docs.chainstack.com/docs/solana-trader-nodes
MAX_RPS = 25
