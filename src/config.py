"""
Configuration for the pump.fun trading bot.
"""

# Trading parameters
BUY_AMOUNT: int | float = 0.000_001  # Amount of SOL to spend when buying
BUY_SLIPPAGE: float = 0.4  # 40% slippage tolerance for buying
SELL_SLIPPAGE: float = 0.4  # 40% slippage tolerance for selling


# Configuration for priority fee settings
ENABLE_DYNAMIC_PRIORITY_FEE: bool = False  # Enable dynamic priority fee calculation
ENABLE_FIXED_PRIORITY_FEE: bool = True  # Enable fixed priority fee
FIXED_PRIORITY_FEE: int = 2_000  # Fixed priority fee in microlamports
EXTRA_PRIORITY_FEE: float = (
    0.0  # Percentage increase applied to priority fee (0.1 = 10%)
)
HARD_CAP_PRIOR_FEE: int = (
    200_000  # Maximum allowed priority fee in microlamports (hard cap)
)


# Listener configuration
LISTENER_TYPE = "block"  # Options: "block" or "logs"


# Retries and timeouts
MAX_RETRIES: int = 10  # Number of retries for transaction sending
# TODO: waiting times will be replaced with retries to shorten delays
WAIT_TIME_AFTER_CREATION: int | float = (
    15  # Time to wait after token creation (in seconds)
    # Too short a delay may cause the RPC node to be unaware of the bonding curve account
)
WAIT_TIME_AFTER_BUY: int | float = (
    15  # Time to wait after a buy transaction is confirmed (in seconds)
    # Acts as a simple holding period
    # Too short delay may cause the RPC node to be unaware of account balance
)
WAIT_TIME_BEFORE_NEW_TOKEN: int | float = (
    5  # Time to wait after a sell transaction is confirmed (in seconds)
    # Provides a pause between completed trades, can be set to 0
)


# Maximum age (in seconds) for a token to be considered "fresh" and eligible for processing.
# This threshold is checked before processing starts - tokens older than this are skipped
# since they likely contain outdated information from the websocket stream
MAX_TOKEN_AGE: int | float = 0.1


# Node provider configuration
# Tested with Chainstack nodes (https://console.chainstack.com), but you can use any node provider
# You can get a trader node https://docs.chainstack.com/docs/solana-trader-nodes
MAX_RPS: int = 25  # TODO: not implemented. Max RPS to avoid rate limit errors


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
