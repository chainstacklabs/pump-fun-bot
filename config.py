"""
Configuration for the pump.fun trading bot.
"""

# Trading parameters
BUY_AMOUNT: float = 0.000001  # Amount of SOL to spend when buying
BUY_SLIPPAGE: float = 0.4  # 40% slippage tolerance for buying
SELL_SLIPPAGE: float = 0.4  # 40% slippage tolerance for selling

# Configuration for priority fee settings
ENABLE_DYNAMIC_PRIORITY_FEE: bool = True  # Enable dynamic priority fee calculation
ENABLE_FIXED_PRIORITY_FEE: bool = True  # Enable fixed priority fee
FIXED_PRIORITY_FEE: int = 200000  # Fixed priority fee in lamports (0 means no fee)
EXTRA_PRIORITY_FEE: float = (
    0.1  # Percentage increase applied to priority fee (0.1 = 10%)
)
HARD_CAP_PRIOR_FEE: int = 1000000  # Maximum allowed priority fee in lamports (hard cap)

# Retries and timeouts
MAX_RETRIES: int = 2
WAIT_TIME_AFTER_BUY: int = 15
WAIT_TIME_BEFORE_NEW_TOKEN: int = 30
WAIT_TIME_AFTER_CREATION: int = 15

# Maximum age (in seconds) for a token to be considered "fresh" and eligible for processing.
# This threshold is checked before processing starts - tokens older than this are skipped
# since they likely contain outdated information from the websocket stream
MAX_TOKEN_AGE: float = 0.1

# Node provier configuration
# You can also get a trader node https://docs.chainstack.com/docs/solana-trader-nodes
MAX_RPS: int = 25  # TODO: not implemented. Max RPS to avoid rate limit errors
PUBLIC_RPC_ENDPOINT = "https://api.mainnet-beta.solana.com"
PUBLIC_WSS_ENDPOINT = "wss://api.mainnet-beta.solana.com"


def validate_priority_fee_config() -> None:
    """Validate priority fee configuration values."""
    if not isinstance(ENABLE_DYNAMIC_PRIORITY_FEE, bool):
        raise ValueError("ENABLE_DYNAMIC_PRIORITY_FEE must be a boolean")
    if not isinstance(ENABLE_FIXED_PRIORITY_FEE, bool):
        raise ValueError("ENABLE_FIXED_PRIORITY_FEE must be a boolean")
    if not isinstance(FIXED_PRIORITY_FEE, int) or FIXED_PRIORITY_FEE < 0:
        raise ValueError("FIXED_PRIORITY_FEE must be a non-negative integer")
    if not isinstance(EXTRA_PRIORITY_FEE, float) or EXTRA_PRIORITY_FEE < 0:
        raise ValueError("EXTRA_PRIORITY_FEE must be a non-negative float")
    if not isinstance(HARD_CAP_PRIOR_FEE, int) or HARD_CAP_PRIOR_FEE < 0:
        raise ValueError("HARD_CAP_PRIOR_FEE must be a non-negative integer")


# Validate config on import
validate_priority_fee_config()
