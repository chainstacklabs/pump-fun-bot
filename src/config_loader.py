import os
from typing import Any

import yaml
from dotenv import load_dotenv

REQUIRED_FIELDS = [
    "name", "rpc_endpoint", "wss_endpoint", "private_key",
    "trade.buy_amount", "trade.buy_slippage", "trade.sell_slippage",
    "filters.listener_type", "filters.max_token_age"
]

CONFIG_VALIDATION_RULES = [
    # (path, type, min_value, max_value, error_message)
    ("trade.buy_amount", (int, float), 0, float('inf'), "trade.buy_amount must be a positive number"),
    ("trade.buy_slippage", float, 0, 1, "trade.buy_slippage must be between 0 and 1"),
    ("trade.sell_slippage", float, 0, 1, "trade.sell_slippage must be between 0 and 1"),
    ("priority_fees.fixed_amount", int, 0, float('inf'), "priority_fees.fixed_amount must be a non-negative integer"),
    ("priority_fees.extra_percentage", float, 0, 1, "priority_fees.extra_percentage must be between 0 and 1"),
    ("priority_fees.hard_cap", int, 0, float('inf'), "priority_fees.hard_cap must be a non-negative integer"),
    ("retries.max_attempts", int, 0, 100, "retries.max_attempts must be between 0 and 100"),
    ("filters.max_token_age", (int, float), 0, float('inf'), "filters.max_token_age must be a non-negative number")
]

# Valid values for enum-like fields
VALID_VALUES = {
    "filters.listener_type": ["logs", "blocks", "geyser", "pumpportal"],
    "cleanup.mode": ["disabled", "on_fail", "after_sell", "post_session"],
    "trade.exit_strategy": ["time_based", "tp_sl", "manual"]
}


def load_bot_config(path: str) -> dict:
    """
    Load and validate a bot configuration from a YAML file.
    
    Args:
        path: Path to the YAML configuration file (relative or absolute)
        
    Returns:
        Validated configuration dictionary
        
    Raises:
        FileNotFoundError: If the configuration file doesn't exist
        ValueError: If the configuration is invalid
    """
    with open(path) as f:
        config = yaml.safe_load(f)
    
    env_file = config.get("env_file")
    if env_file:
        env_path = os.path.join(os.path.dirname(path), env_file)
        if os.path.exists(env_path):
            load_dotenv(env_path, override=True)
        else:
            # If not found relative to config, try relative to current working directory
            load_dotenv(env_file, override=True)
    
    resolve_env_vars(config)
    validate_config(config)
    
    return config

def resolve_env_vars(config: dict) -> None:
    """
    Recursively resolve environment variables in the configuration.
    
    Args:
        config: Configuration dictionary to process
    """
    def resolve_env(value):
        if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
            env_var = value[2:-1]
            env_value = os.getenv(env_var)
            if env_value is None:
                raise ValueError(f"Environment variable '{env_var}' not found")
            return env_value
        return value
    
    def resolve_all(d):
        for k, v in d.items():
            if isinstance(v, dict):
                resolve_all(v)
            else:
                d[k] = resolve_env(v)
    
    resolve_all(config)

def get_nested_value(config: dict, path: str) -> Any:
    """
    Get a nested value from the configuration using dot notation.
    
    Args:
        config: Configuration dictionary
        path: Path to the value using dot notation (e.g., "trade.buy_amount")
        
    Returns:
        The value at the specified path
        
    Raises:
        ValueError: If the path doesn't exist in the configuration
    """
    keys = path.split(".")
    value = config
    for key in keys:
        if not isinstance(value, dict) or key not in value:
            raise ValueError(f"Missing required config key: {path}")
        value = value[key]
    return value

def validate_config(config: dict) -> None:
    """
    Validate the configuration against defined rules.
    
    Args:
        config: Configuration dictionary to validate
        
    Raises:
        ValueError: If the configuration is invalid
    """
    for field in REQUIRED_FIELDS:
        get_nested_value(config, field)
    
    for path, expected_type, min_val, max_val, error_msg in CONFIG_VALIDATION_RULES:
        try:
            value = get_nested_value(config, path)
            
            if not isinstance(value, expected_type):
                raise ValueError(f"Type error: {error_msg}")
            
            if isinstance(value, (int, float)) and not (min_val <= value <= max_val):
                raise ValueError(f"Range error: {error_msg}")
                
        except ValueError as e:
            # Re-raise if it's our own error
            if str(e).startswith(("Type error:", "Range error:")):
                raise
            # Otherwise, the field might be missing
            continue
    
    # Validate enum-like fields
    for path, valid_values in VALID_VALUES.items():
        try:
            value = get_nested_value(config, path)
            if value not in valid_values:
                raise ValueError(f"{path} must be one of {valid_values}")
        except ValueError:
            # Skip if the field is missing
            continue
    
    # Cannot enable both dynamic and fixed priority fees
    try:
        dynamic = get_nested_value(config, "priority_fees.enable_dynamic")
        fixed = get_nested_value(config, "priority_fees.enable_fixed")
        if dynamic and fixed:
            raise ValueError("Cannot enable both dynamic and fixed priority fees simultaneously")
    except ValueError:
        # Skip if one of the fields is missing
        pass

def print_config_summary(config: dict) -> None:
    """
    Print a summary of the loaded configuration.
    
    Args:
        config: Configuration dictionary
    """
    print(f"Bot name: {config.get('name', 'unnamed')}")
    print(f"Listener type: {config.get('filters', {}).get('listener_type', 'not configured')}")
    
    trade = config.get('trade', {})
    print("Trade settings:")
    print(f"  - Buy amount: {trade.get('buy_amount', 'not configured')} SOL")
    print(f"  - Buy slippage: {trade.get('buy_slippage', 'not configured') * 100}%")
    print(f"  - Extreme fast mode: {'enabled' if trade.get('extreme_fast_mode') else 'disabled'}")
    
    fees = config.get('priority_fees', {})
    print("Priority fees:")
    if fees.get('enable_dynamic'):
        print("  - Dynamic fees enabled")
    elif fees.get('enable_fixed'):
        print(f"  - Fixed fee: {fees.get('fixed_amount', 'not configured')} microlamports")
    
    print("Configuration loaded successfully!")


if __name__ == "__main__":
    config = load_bot_config("bots/bot-sniper.yaml")
    print_config_summary(config)