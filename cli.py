#!/usr/bin/env python3
"""
Command-line interface for the pump.fun trading bot.
"""

import argparse
import asyncio
import os
import sys
from typing import Any, Dict

import config
from src.trading.trader import PumpTrader
from src.utils.logger import get_logger, setup_file_logging

logger = get_logger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments.

    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(description="Trade tokens on pump.fun.")
    parser.add_argument(
        "--yolo", action="store_true", help="Run in YOLO mode (continuous trading)"
    )
    parser.add_argument(
        "--match",
        type=str,
        help="Only trade tokens with names or symbols matching this string",
    )
    parser.add_argument(
        "--bro", type=str, help="Only trade tokens created by this user address"
    )
    parser.add_argument(
        "--marry", action="store_true", help="Only buy tokens, skip selling"
    )
    parser.add_argument(
        "--amount",
        type=float,
        help=f"Amount of SOL to spend on each buy (default: {config.BUY_AMOUNT})",
    )
    parser.add_argument(
        "--buy-slippage",
        type=float,
        help=f"Buy slippage tolerance (default: {config.BUY_SLIPPAGE})",
    )
    parser.add_argument(
        "--sell-slippage",
        type=float,
        help=f"Sell slippage tolerance (default: {config.SELL_SLIPPAGE})",
    )
    parser.add_argument("--rpc", type=str, help="Solana RPC endpoint")
    parser.add_argument("--wss", type=str, help="Solana WebSocket endpoint")

    parser.add_argument("--wss", type=str, help="Solana WebSocket endpoint")
    parser.add_argument(
        "--key",
        type=str,
        help="Solana private key (better to use environment variable)",
    )
    parser.add_argument("--log", type=str, help="Log file path")
    return parser.parse_args()


async def main() -> None:
    """Main entry point for the CLI."""
    setup_file_logging("pump_trading.log")

    args = parse_args()

    # Get configuration values, preferring command line args over config.py
    rpc_endpoint: str | None = args.rpc or os.environ.get("SOLANA_NODE_RPC_ENDPOINT")
    wss_endpoint: str | None = args.wss or os.environ.get("SOLANA_NODE_WSS_ENDPOINT")
    private_key: str | None = args.key or os.environ.get("SOLANA_PRIVATE_KEY")

    if not rpc_endpoint or rpc_endpoint.startswith(("http://", "https://")):
        logger.error("Invalid RPC endpoint. Must start with http:// or https://")
        sys.exit(1)

    if not wss_endpoint or wss_endpoint.startswith(("ws://", "wss://")):
        logger.error("Invalid WebSocket endpoint. Must start with ws:// or wss://")
        sys.exit(1)

    if not private_key or len(private_key) < 80:
        logger.error("Invalid private key. Key appears to be missing or too short")
        sys.exit(1)

    buy_amount: float = args.amount if args.amount is not None else config.BUY_AMOUNT
    buy_slippage: float = (
        args.buy_slippage if args.buy_slippage is not None else config.BUY_SLIPPAGE
    )
    sell_slippage: float = (
        args.sell_slippage if args.sell_slippage is not None else config.SELL_SLIPPAGE
    )

    trader: PumpTrader = PumpTrader(
        rpc_endpoint=rpc_endpoint,  # type: ignore
        wss_endpoint=wss_endpoint,  # type: ignore
        private_key=private_key,
        buy_amount=buy_amount,
        buy_slippage=buy_slippage,
        sell_slippage=sell_slippage,
        max_retries=config.MAX_RETRIES,
    )

    try:
        await trader.start(
            match_string=args.match,
            bro_address=args.bro,
            marry_mode=args.marry,
            yolo_mode=args.yolo,
        )
    except KeyboardInterrupt:
        logger.info("Trading stopped by user")
    except Exception as e:
        logger.error(f"Trading stopped due to error: {str(e)}")
    finally:
        try:
            await trader.solana_client.close()
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())
