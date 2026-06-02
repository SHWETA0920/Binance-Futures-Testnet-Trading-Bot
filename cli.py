#!/usr/bin/env python3
"""
cli.py – Command-line entry point for the Binance Futures Testnet Trading Bot.

Usage examples:
  # Real testnet (requires API credentials):
  python cli.py --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001

  # Mock mode (no credentials, no internet — works everywhere):
  python cli.py --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001 --mock
  python cli.py --symbol BTCUSDT --side SELL --type LIMIT --quantity 0.001 --price 100000 --mock
  python cli.py --symbol BTCUSDT --side BUY --type STOP_LIMIT --quantity 0.001 --price 79000 --stop-price 79500 --mock
  python cli.py --interactive --mock
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import Optional

from bot.logging_config import setup_logging
from bot.orders import dispatch_order
from bot.validators import validate_all
from bot.client import BinanceAPIError

# ---------------------------------------------------------------------------
# ANSI colours
# ---------------------------------------------------------------------------
BOLD   = "\033[1m"
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
DIM    = "\033[2m"
RESET  = "\033[0m"

def _c(text: str, code: str) -> str:
    return f"{code}{text}{RESET}" if sys.stdout.isatty() else text


# ---------------------------------------------------------------------------
# Print helpers
# ---------------------------------------------------------------------------

def _banner(mock: bool) -> None:
    mode_tag = _c("  ⚠  MOCK MODE — no real orders placed", YELLOW) if mock else ""
    print(_c(
        "\n  ╔══════════════════════════════════════════════╗\n"
        "  ║   Binance Futures Testnet  •  Trading Bot    ║\n"
        "  ╚══════════════════════════════════════════════╝",
        CYAN + BOLD,
    ))
    if mode_tag:
        print(mode_tag)


def _print_summary(params: dict) -> None:
    print()
    print(_c("  ── Order Request ──────────────────────────", DIM))
    for key, value in params.items():
        if value is not None:
            print(f"  {_c(key.ljust(16), BOLD)}: {value}")
    print(_c("  ────────────────────────────────────────────", DIM))


def _print_result(result: dict, success: bool, mock: bool) -> None:
    print()
    if success:
        label = "✔  Order simulated successfully! (mock)" if mock else "✔  Order placed successfully!"
        print(_c(f"  {label}", GREEN + BOLD))
    else:
        print(_c("  ✘  Order failed.", RED + BOLD))

    print(_c("  ── Order Response ──────────────────────────", DIM))
    display_keys = [
        ("orderId",      "Order ID"),
        ("symbol",       "Symbol"),
        ("side",         "Side"),
        ("type",         "Type"),
        ("status",       "Status"),
        ("origQty",      "Orig Qty"),
        ("executedQty",  "Executed Qty"),
        ("avgPrice",     "Avg Price"),
        ("price",        "Limit Price"),
        ("stopPrice",    "Stop Price"),
        ("timeInForce",  "Time-in-Force"),
    ]
    for key, label in display_keys:
        value = result.get(key)
        if value not in (None, "", "0", "0.00000000"):
            print(f"  {_c(label.ljust(16), BOLD)}: {value}")
    print(_c("  ────────────────────────────────────────────", DIM))
    print()


# ---------------------------------------------------------------------------
# Client factory
# ---------------------------------------------------------------------------

def _build_client(mock: bool):
    if mock:
        from bot.mock_client import MockBinanceClient
        logging.getLogger("trading_bot.cli").info(
            "Running in MOCK mode — simulated responses, no network calls."
        )
        return MockBinanceClient()

    api_key    = os.getenv("BINANCE_TESTNET_API_KEY", "")
    api_secret = os.getenv("BINANCE_TESTNET_API_SECRET", "")

    if not api_key or not api_secret:
        print(_c(
            "\n  ERROR: Credentials not found.\n"
            "  Set BINANCE_TESTNET_API_KEY and BINANCE_TESTNET_API_SECRET,\n"
            "  or use --mock to run without credentials.\n",
            RED + BOLD,
        ))
        sys.exit(1)

    from bot.client import BinanceClient
    return BinanceClient(api_key=api_key, api_secret=api_secret)


# ---------------------------------------------------------------------------
# Core execution
# ---------------------------------------------------------------------------

def _execute(
    client,
    symbol: str,
    side: str,
    order_type: str,
    quantity: str,
    price: Optional[str],
    stop_price: Optional[str],
    time_in_force: str,
    mock: bool,
) -> None:
    logger = logging.getLogger("trading_bot.cli")

    # Validate inputs
    try:
        params = validate_all(
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
        )
    except ValueError as exc:
        print(_c(f"\n  ✘  Validation error: {exc}\n", RED + BOLD))
        logger.error("Validation failed: %s", exc)
        sys.exit(2)

    _print_summary({
        "Symbol":        params["symbol"],
        "Side":          params["side"],
        "Order Type":    params["order_type"],
        "Quantity":      str(params["quantity"]),
        "Price":         str(params["price"]) if params["price"] else "—",
        "Stop Price":    str(params["stop_price"]) if params["stop_price"] else "—",
        "Time-in-Force": time_in_force if params["order_type"] != "MARKET" else "—",
        "Mode":          _c("MOCK (simulated)", YELLOW) if mock else "LIVE (testnet)",
    })

    # Place / simulate order
    try:
        result = dispatch_order(
            client=client,
            symbol=params["symbol"],
            side=params["side"],
            order_type=params["order_type"],
            quantity=params["quantity"],
            price=params["price"],
            stop_price=params["stop_price"],
            time_in_force=time_in_force,
        )
        _print_result(result, success=True, mock=mock)

    except BinanceAPIError as exc:
        print(_c(f"\n  ✘  Binance API error [{exc.code}]: {exc.message}\n", RED + BOLD))
        logger.error("BinanceAPIError: code=%s msg=%s", exc.code, exc.message)
        sys.exit(3)

    except Exception as exc:
        print(_c(f"\n  ✘  Unexpected error: {exc}\n", RED + BOLD))
        logger.exception("Unexpected error during order placement")
        sys.exit(4)


# ---------------------------------------------------------------------------
# Interactive mode
# ---------------------------------------------------------------------------

def _prompt(label: str, default: Optional[str] = None) -> str:
    suffix = f" [{default}]" if default else ""
    while True:
        value = input(f"  {_c(label + suffix + ': ', CYAN)}")
        if value.strip():
            return value.strip()
        if default is not None:
            return default
        print(_c("  ⚠  This field is required.", YELLOW))


def _interactive_mode(client, mock: bool) -> None:
    _banner(mock)
    print(_c("\n  Interactive order entry\n", BOLD))
    symbol     = _prompt("Symbol (e.g. BTCUSDT)", default="BTCUSDT")
    side       = _prompt("Side [BUY/SELL]")
    order_type = _prompt("Order type [MARKET/LIMIT/STOP_LIMIT]")

    price: Optional[str]      = None
    stop_price: Optional[str] = None

    if order_type.upper() in ("LIMIT", "STOP_LIMIT"):
        price = _prompt("Limit price")
    if order_type.upper() == "STOP_LIMIT":
        stop_price = _prompt("Stop/trigger price")

    quantity = _prompt("Quantity (base asset)")
    tif = "GTC"
    if order_type.upper() in ("LIMIT", "STOP_LIMIT"):
        tif = _prompt("Time-in-force", default="GTC")

    _execute(
        client=client,
        symbol=symbol,
        side=side,
        order_type=order_type,
        quantity=quantity,
        price=price,
        stop_price=stop_price,
        time_in_force=tif,
        mock=mock,
    )


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trading_bot",
        description="Binance Futures Trading Bot  (testnet + mock mode)",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""
examples (mock mode — no credentials needed):
  python cli.py --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001 --mock
  python cli.py --symbol ETHUSDT --side SELL --type LIMIT --quantity 0.01 --price 3000 --mock
  python cli.py --symbol BTCUSDT --side BUY --type STOP_LIMIT \\
      --quantity 0.001 --price 79000 --stop-price 79500 --mock
  python cli.py --interactive --mock

examples (live testnet — requires API credentials):
  python cli.py --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001
""",
    )
    parser.add_argument("--symbol",     help="Trading pair (e.g. BTCUSDT)")
    parser.add_argument("--side",       choices=["BUY", "SELL"], help="Order side")
    parser.add_argument("--type",       dest="order_type",
                        choices=["MARKET", "LIMIT", "STOP_LIMIT"], help="Order type")
    parser.add_argument("--quantity",   help="Order quantity in base asset units")
    parser.add_argument("--price",      help="Limit price (required for LIMIT/STOP_LIMIT)")
    parser.add_argument("--stop-price", dest="stop_price",
                        help="Stop/trigger price (STOP_LIMIT only)")
    parser.add_argument("--tif",        dest="time_in_force", default="GTC",
                        choices=["GTC", "IOC", "FOK"],
                        help="Time-in-force (default: GTC)")
    parser.add_argument("--mock", "-m", action="store_true",
                        help="Run in mock mode — simulates API locally, no credentials needed")
    parser.add_argument("--interactive", "-i", action="store_true",
                        help="Launch interactive guided order entry")
    parser.add_argument("--log-level",  default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    parser.add_argument("--log-dir",    default="logs",
                        help="Log file directory (default: logs/)")
    return parser


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = _build_parser()
    args   = parser.parse_args()

    setup_logging(log_dir=args.log_dir, log_level=args.log_level)
    client = _build_client(mock=args.mock)

    if args.interactive:
        _interactive_mode(client, mock=args.mock)
        return

    missing = [f for f in ("symbol", "side", "order_type", "quantity")
               if not getattr(args, f, None)]
    if missing:
        parser.print_help()
        print(_c(
            f"\n  ✘  Missing required arguments: {', '.join(missing)}\n"
            "  Tip: use --interactive for a guided prompt, or --mock to run without credentials.\n",
            RED + BOLD,
        ))
        sys.exit(2)

    _banner(mock=args.mock)
    _execute(
        client=client,
        symbol=args.symbol,
        side=args.side,
        order_type=args.order_type,
        quantity=args.quantity,
        price=args.price,
        stop_price=args.stop_price,
        time_in_force=args.time_in_force,
        mock=args.mock,
    )


if __name__ == "__main__":
    main()
