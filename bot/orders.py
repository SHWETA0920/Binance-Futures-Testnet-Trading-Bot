"""
Order placement logic — sits between the CLI and the raw Binance client.
Each function builds the correct Binance parameter set and delegates to
BinanceClient.new_order(), then returns a normalised result dict.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Dict, Optional

from bot.client import BinanceClient

logger = logging.getLogger("trading_bot.orders")


def _fmt(value: Optional[Decimal]) -> Optional[str]:
    """Format a Decimal to a plain string without trailing zeros, or return None."""
    if value is None:
        return None
    return f"{value:.8f}".rstrip("0").rstrip(".")


def _normalise_response(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Extract the fields we care about into a consistent shape."""
    return {
        "orderId": raw.get("orderId"),
        "symbol": raw.get("symbol"),
        "side": raw.get("side"),
        "type": raw.get("type"),
        "status": raw.get("status"),
        "origQty": raw.get("origQty"),
        "executedQty": raw.get("executedQty"),
        "avgPrice": raw.get("avgPrice"),
        "price": raw.get("price"),
        "stopPrice": raw.get("stopPrice"),
        "timeInForce": raw.get("timeInForce"),
        "updateTime": raw.get("updateTime"),
        "clientOrderId": raw.get("clientOrderId"),
    }


def place_market_order(
    client: BinanceClient,
    symbol: str,
    side: str,
    quantity: Decimal,
) -> Dict[str, Any]:
    """
    Place a MARKET order on Binance Futures.

    Args:
        client:   Authenticated BinanceClient instance.
        symbol:   Trading pair, e.g. 'BTCUSDT'.
        side:     'BUY' or 'SELL'.
        quantity: Order size in base asset units.

    Returns:
        Normalised order result dict.
    """
    logger.info("[MARKET] %s %s qty=%s", side, symbol, quantity)
    raw = client.new_order(
        symbol=symbol,
        side=side,
        type="MARKET",
        quantity=_fmt(quantity),
    )
    result = _normalise_response(raw)
    logger.info("[MARKET] order placed → orderId=%s status=%s", result["orderId"], result["status"])
    return result


def place_limit_order(
    client: BinanceClient,
    symbol: str,
    side: str,
    quantity: Decimal,
    price: Decimal,
    time_in_force: str = "GTC",
) -> Dict[str, Any]:
    """
    Place a LIMIT order on Binance Futures.

    Args:
        client:        Authenticated BinanceClient instance.
        symbol:        Trading pair, e.g. 'BTCUSDT'.
        side:          'BUY' or 'SELL'.
        quantity:      Order size in base asset units.
        price:         Limit price.
        time_in_force: 'GTC' (default), 'IOC', or 'FOK'.

    Returns:
        Normalised order result dict.
    """
    logger.info("[LIMIT] %s %s qty=%s price=%s tif=%s", side, symbol, quantity, price, time_in_force)
    raw = client.new_order(
        symbol=symbol,
        side=side,
        type="LIMIT",
        quantity=_fmt(quantity),
        price=_fmt(price),
        timeInForce=time_in_force,
    )
    result = _normalise_response(raw)
    logger.info("[LIMIT] order placed → orderId=%s status=%s", result["orderId"], result["status"])
    return result


def place_stop_limit_order(
    client: BinanceClient,
    symbol: str,
    side: str,
    quantity: Decimal,
    price: Decimal,
    stop_price: Decimal,
    time_in_force: str = "GTC",
) -> Dict[str, Any]:
    """
    Place a STOP_MARKET / STOP (stop-limit) order on Binance Futures.

    Binance Futures uses type=STOP for stop-limit orders.

    Args:
        client:        Authenticated BinanceClient instance.
        symbol:        Trading pair, e.g. 'BTCUSDT'.
        side:          'BUY' or 'SELL'.
        quantity:      Order size in base asset units.
        price:         Limit price (executed when stop is triggered).
        stop_price:    Trigger price.
        time_in_force: 'GTC' (default), 'IOC', or 'FOK'.

    Returns:
        Normalised order result dict.
    """
    logger.info(
        "[STOP_LIMIT] %s %s qty=%s price=%s stopPrice=%s",
        side, symbol, quantity, price, stop_price,
    )
    raw = client.new_order(
        symbol=symbol,
        side=side,
        type="STOP",
        quantity=_fmt(quantity),
        price=_fmt(price),
        stopPrice=_fmt(stop_price),
        timeInForce=time_in_force,
    )
    result = _normalise_response(raw)
    logger.info(
        "[STOP_LIMIT] order placed → orderId=%s status=%s", result["orderId"], result["status"]
    )
    return result


def dispatch_order(
    client: BinanceClient,
    symbol: str,
    side: str,
    order_type: str,
    quantity: Decimal,
    price: Optional[Decimal] = None,
    stop_price: Optional[Decimal] = None,
    time_in_force: str = "GTC",
) -> Dict[str, Any]:
    """
    Route to the correct placement function based on order_type.
    This is the single entry-point called by the CLI layer.
    """
    if order_type == "MARKET":
        return place_market_order(client, symbol, side, quantity)
    elif order_type == "LIMIT":
        return place_limit_order(client, symbol, side, quantity, price, time_in_force)  # type: ignore[arg-type]
    elif order_type == "STOP_LIMIT":
        return place_stop_limit_order(client, symbol, side, quantity, price, stop_price, time_in_force)  # type: ignore[arg-type]
    else:
        raise ValueError(f"Unsupported order type: {order_type}")
