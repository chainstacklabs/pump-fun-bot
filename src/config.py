"""
Configuration for the pump.fun trading bot.

This file defines comprehensive parameters and settings for the trading bot.
Carefully review and adjust values to match your trading strategy and risk tolerance.
"""

# Trading parameters
# Control trade execution: amount of SOL per trade and acceptable price deviation
BUY_AMOUNT: int | float = 0.000_001  # Minimal SOL amount to prevent dust transactions
BUY_SLIPPAGE: float = 0.4  # Maximum acceptable price deviation (0.4 = 40%)
SELL_SLIPPAGE: float = 0.4  # Consistent slippage tolerance to maintain trading strategy


# Priority fee configuration
# Manage transaction speed and cost on the Solana network
ENABLE_DYNAMIC_PRIORITY_FEE: bool = False  # Adaptive fee calculation
ENABLE_FIXED_PRIORITY_FEE: bool = True  # Use consistent, predictable fee
FIXED_PRIORITY_FEE: int = 2_000  # Base fee in microlamports
EXTRA_PRIORITY_FEE: float = 0.0  # Percentage increase on base priority fee (0.1 = 10%)
HARD_CAP_PRIOR_FEE: int = 200_000  # Maximum allowable fee to prevent excessive spending in microlamports


# Listener configuration
# Choose method for detecting new tokens on the network
# "logs": Recommended for more stable token detection
# "blocks": Unstable method, potentially less reliable
LISTENER_TYPE = "logs"


# Retry and timeout settings
# Control bot resilience and transaction handling
MAX_RETRIES: int = 10  # Number of attempts for transaction submission

# Waiting periods in seconds between actions (TODO: to be replaced with retry mechanism)
WAIT_TIME_AFTER_CREATION: int | float = 15  # Seconds to wait after token creation
WAIT_TIME_AFTER_BUY: int | float = 15  # Holding period after buy transaction
WAIT_TIME_BEFORE_NEW_TOKEN: int | float = 15  # Pause between token trades


# Token and account management
# Control token processing and account cleanup strategies
MAX_TOKEN_AGE: int | float = 0.1  # Maximum token age in seconds for processing

# Cleanup mode determines when to manage token accounts. Options:
# "disabled": No cleanup will occur.
# "on_fail": Only clean up if a buy transaction fails.
# "after_sell": Clean up after selling, but only if the balance is zero.
# "post_session": Clean up all empty accounts after a trading session ends.
CLEANUP_MODE: str = "disabled"
CLEANUP_FORCE_CLOSE_WITH_BURN: bool = False  # Burn remaining tokens before closing account, else skip ATA with non-zero balances
CLEANUP_WITH_PRIORITY_FEE: bool = False  # Use priority fees for cleanup transactions


# Node provider configuration (TODO: to be implemented)
# Manage RPC node interaction to prevent rate limiting
MAX_RPS: int = 25  # Maximum requests per second


def validate_configuration() -> None:
    """
    Comprehensive validation of bot configuration.
    
    Checks:
    - Type correctness
    - Value ranges
    - Logical consistency of settings
    """
    # Configuration validation checks
    config_checks = [
        # (value, type, min_value, max_value, error_message)
        (BUY_AMOUNT, (int, float), 0, float('inf'), "BUY_AMOUNT must be a positive number"),
        (BUY_SLIPPAGE, float, 0, 1, "BUY_SLIPPAGE must be between 0 and 1"),
        (SELL_SLIPPAGE, float, 0, 1, "SELL_SLIPPAGE must be between 0 and 1"),
        (FIXED_PRIORITY_FEE, int, 0, float('inf'), "FIXED_PRIORITY_FEE must be a non-negative integer"),
        (EXTRA_PRIORITY_FEE, float, 0, 1, "EXTRA_PRIORITY_FEE must be between 0 and 1"),
        (HARD_CAP_PRIOR_FEE, int, 0, float('inf'), "HARD_CAP_PRIOR_FEE must be a non-negative integer"),
        (MAX_RETRIES, int, 0, 100, "MAX_RETRIES must be between 0 and 100")
    ]

    for value, expected_type, min_val, max_val, error_msg in config_checks:
        if not isinstance(value, expected_type):
            raise ValueError(f"Type error: {error_msg}")
        
        if isinstance(value, (int, float)) and not (min_val <= value <= max_val):
            raise ValueError(f"Range error: {error_msg}")

    # Logical consistency checks
    if ENABLE_DYNAMIC_PRIORITY_FEE and ENABLE_FIXED_PRIORITY_FEE:
        raise ValueError("Cannot enable both dynamic and fixed priority fees simultaneously")

    # Validate listener type
    if LISTENER_TYPE not in ["logs", "blocks"]:
        raise ValueError("LISTENER_TYPE must be either 'logs' or 'blocks'")

    # Validate cleanup mode
    valid_cleanup_modes = ["disabled", "on_fail", "after_sell", "post_session"]
    if CLEANUP_MODE not in valid_cleanup_modes:
        raise ValueError(f"CLEANUP_MODE must be one of {valid_cleanup_modes}")


# Validate configuration on import
validate_configuration()