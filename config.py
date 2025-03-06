"""
Configuration for the pump.fun trading bot.
"""

# Trading parameters
BUY_AMOUNT = 0.0001  # Amount of SOL to spend when buying
BUY_SLIPPAGE = 0.2  # 20% slippage tolerance for buying
SELL_SLIPPAGE = 0.2  # 20% slippage tolerance for selling
ENABLE_DYNAMIC_PRIORITY_FEE = True  # TODO: not implemented. getRecentPriorityFee is used to get current priority fee
EXTRA_PRIORITY_FEE = 0.1  # TODO: not implemented. 10% increase in dynamic priority fee

# Retries and timeouts
MAX_RETRIES: int = 5
WAIT_TIME_AFTER_BUY: int = 5
WAIT_TIME_BEFORE_NEW_TOKEN: int = 5
WAIT_TIME_AFTER_CREATION: int = 5

# Node provier configuration
# You can also get a trader node https://docs.chainstack.com/docs/solana-trader-nodes
MAX_RPS = 25  # TODO: not implemented. Max RPS to avoid rate limit errors
PUBLIC_RPC_ENDPOINT = "https://api.mainnet-beta.solana.com"
PUBLIC_WSS_ENDPOINT = "wss://api.mainnet-beta.solana.com"
