"""
Configuration for the pump.fun trading bot.
"""

# Trading parameters
BUY_AMOUNT = 0.0001  # Amount of SOL to spend when buying
BUY_SLIPPAGE = 0.2  # 20% slippage tolerance for buying
SELL_SLIPPAGE = 0.2  # 20% slippage tolerance for selling
ENABLE_DYNAMIC_PRIORITY_FEE = (
    True  # TODO: getRecentPriorityFee is used to get current priority fee
)
EXTRA_PRIORITY_FEE = 0.1  # TODO: 10% increase in dynamic priority fee

TOKEN_DECIMALS: int = 6
MAX_RETRIES: int = 5
WAIT_TIME_AFTER_BUY: int = 20
WAIT_TIME_BEFORE_NEW_TOKEN: int = 5
WAIT_TIME_AFTER_CREATION: int = 15

# TODO: RPS of your node to avoid rate limit errors
# You can also get a trader node https://docs.chainstack.com/docs/solana-trader-nodes
MAX_RPS = 25

PUBLIC_RPC_ENDPOINT = "https://api.mainnet-beta.solana.com"
PUBLIC_WSS_ENDPOINT = "wss://api.mainnet-beta.solana.com"
