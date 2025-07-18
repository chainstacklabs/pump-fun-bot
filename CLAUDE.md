# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Environment Setup
```bash
# Create virtual environment and install dependencies
uv sync --extra dev

# Activate virtual environment
source .venv/bin/activate  # Unix/macOS
.venv\Scripts\activate     # Windows
```

### Running the Bot
```bash
# Run bot with all configurations in bots/ directory
pump_bot

# Run bot directly
uv run src/bot_runner.py
```

### Development Tools
```bash
# Run linting
uv run ruff check src/

# Run formatting
uv run ruff format src/
```

### Testing
```bash
# Run individual test files
uv run tests/test_block_listener.py
uv run tests/test_geyser_listener.py
uv run tests/test_logs_listener.py
```

## Architecture Overview

This is a Solana-based trading bot for pump.fun tokens with a modular architecture:

### Core Components

- **`src/bot_runner.py`**: Main entry point that loads configurations and starts trading bots
- **`src/config_loader.py`**: Handles YAML configuration loading, validation, and environment variable resolution
- **`src/trading/trader.py`**: `PumpTrader` class - main trading coordinator that orchestrates token detection, buying, and selling
- **`src/core/client.py`**: `SolanaClient` - abstraction for Solana RPC operations with background blockhash caching
- **`src/core/wallet.py`**: Wallet management for signing transactions
- **`src/core/curve.py`**: Bonding curve calculations for pump.fun tokens

### Trading System

- **`src/trading/buyer.py`**: `TokenBuyer` - handles token purchase logic with slippage and retry support
- **`src/trading/seller.py`**: `TokenSeller` - handles token sale logic 
- **`src/trading/position.py`**: `Position` - tracks positions with take-profit/stop-loss functionality
- **`src/trading/base.py`**: Common trading data structures (`TokenInfo`, `TradeResult`)

### Token Detection (Monitoring)

Multiple listener implementations for detecting new tokens:
- **`src/monitoring/logs_listener.py`**: Uses `logsSubscribe` WebSocket method
- **`src/monitoring/block_listener.py`**: Uses `blockSubscribe` WebSocket method  
- **`src/monitoring/geyser_listener.py`**: Uses Geyser gRPC streaming (fastest)
- **`src/monitoring/pumpportal_listener.py`**: Uses PumpPortal WebSocket API
- **`src/monitoring/base_listener.py`**: Abstract base class for all listeners

### Priority Fees

- **`src/core/priority_fee/manager.py`**: Manages priority fee calculation
- **`src/core/priority_fee/dynamic_fee.py`**: Dynamic fee calculation based on network conditions
- **`src/core/priority_fee/fixed_fee.py`**: Fixed fee implementation

### Configuration System

Bot configurations are stored in `bots/*.yaml` files. Each bot can run independently with its own settings for:
- Connection endpoints (RPC, WSS, Geyser)
- Trading parameters (buy amount, slippage, exit strategy)
- Priority fees (dynamic vs fixed)
- Token filters (match string, creator address)
- Cleanup modes for token accounts

### Key Features

1. **Multiple Listener Types**: Supports logs, blocks, Geyser, and PumpPortal for token detection
2. **Exit Strategies**: Time-based, take-profit/stop-loss, or manual
3. **Extreme Fast Mode**: Skips stabilization wait and price checks for faster execution
4. **Priority Fee Management**: Dynamic or fixed fee calculation
5. **Account Cleanup**: Automatic cleanup of empty token accounts
6. **Multi-bot Support**: Run multiple bots with different configurations simultaneously

### Trading Modes

- **Single Token Mode** (`yolo_mode: false`): Process one token and exit
- **Continuous Mode** (`yolo_mode: true`): Continuously process tokens
- **Marry Mode** (`marry_mode: true`): Only buy tokens, skip selling

## Environment Configuration

Create `.env` file with:
```
SOLANA_NODE_RPC_ENDPOINT=your_rpc_endpoint
SOLANA_NODE_WSS_ENDPOINT=your_wss_endpoint
SOLANA_PRIVATE_KEY=your_private_key
GEYSER_ENDPOINT=your_geyser_endpoint
GEYSER_API_TOKEN=your_geyser_token
```

## Important Notes

- This is educational/learning code - not for production use
- The bot trades on pump.fun bonding curves and handles migrations to PumpSwap
- Geyser listener provides fastest token detection
- All configurations support environment variable substitution with `${VAR}` syntax
- Bot logs are stored in `logs/` directory with timestamps
- Trade logs are written to `trades/trades.log`