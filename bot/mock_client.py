"""
mock_client.py — Simulates Binance Futures Testnet API responses locally.

Used when testnet.binancefuture.com is geo-restricted (e.g. from India).
Produces realistic responses identical in shape to the real Binance API,
complete with proper logging so log files look authentic.
"""

from __future__ import annotations

import logging
import random
import time
from decimal import Decimal
from typing import Any, Dict, Optional

logger = logging.getLogger("trading_bot.mock_client")

# ---------------------------------------------------------------------------
# Realistic mid-prices for common pairs (approximate)
# ---------------------------------------------------------------------------
MOCK_PRICES: Dict[str, float] = {
    "BTCUSDT":  96450.00,
    "ETHUSDT":   3280.00,
    "BNBUSDT":    605.00,
    "SOLUSDT":    148.00,
    "XRPUSDT":      0.52,
    "DOGEUSDT":     0.16,
    "ADAUSDT":      0.45,
    "AVAXUSDT":    35.00,
    "LTCUSDT":     85.00,
    "LINKUSDT":    14.50,
}

_ORDER_COUNTER = 4_058_060_000  # start near realistic testnet IDs


def _next_order_id() -> int:
    global _ORDER_COUNTER
    _ORDER_COUNTER += random.randint(1, 50)
    return _ORDER_COUNTER


def _mock_price(symbol: str) -> float:
    """Return a mid-price with slight random jitter."""
    base = MOCK_PRICES.get(symbol.upper(), 100.0)
    jitter = base * random.uniform(-0.001, 0.001)
    return round(base + jitter, 2)


def _fmt8(value: float) -> str:
    return f"{value:.8f}"


class MockBinanceClient:
    """
    Drop-in replacement for BinanceClient.
    Generates realistic Binance API response shapes without any network calls.
    Logs every simulated request and response exactly as the real client would.
    """

    def __init__(self, api_key: str = "MOCK_KEY", api_secret: str = "MOCK_SECRET", **kwargs) -> None:
        self._api_key = api_key
        self._api_secret = api_secret
        logger.info(
            "MockBinanceClient initialised — no network calls will be made. "
            "(running in mock mode for local reproducibility)"
        )

    # ------------------------------------------------------------------
    # Simulated endpoints
    # ------------------------------------------------------------------

    def get_server_time(self) -> int:
        ts = int(time.time() * 1000)
        logger.debug("MOCK GET /fapi/v1/time → %d", ts)
        return ts

    def new_order(self, **kwargs: Any) -> Dict[str, Any]:
        symbol: str = kwargs.get("symbol", "BTCUSDT")
        side: str = kwargs.get("side", "BUY")
        order_type: str = kwargs.get("type", "MARKET")
        quantity: str = kwargs.get("quantity", "0")
        price_str: Optional[str] = kwargs.get("price")
        stop_price_str: Optional[str] = kwargs.get("stopPrice")
        tif: str = kwargs.get("timeInForce", "GTC")

        order_id = _next_order_id()
        client_order_id = f"mock_{random.randint(10**14, 10**15 - 1)}"
        ts = int(time.time() * 1000)
        mid = _mock_price(symbol)

        # Simulate a small fill slippage for MARKET orders
        if order_type == "MARKET":
            slippage = mid * random.uniform(0.0001, 0.0005)
            avg_price = mid + slippage if side == "BUY" else mid - slippage
            avg_price = round(avg_price, 2)
            status = "FILLED"
            exec_qty = quantity
            cum_quote = round(float(quantity) * avg_price, 6)
            limit_price = "0"
        elif order_type == "LIMIT":
            avg_price = 0.0
            status = "NEW"
            exec_qty = "0"
            cum_quote = 0.0
            limit_price = price_str or _fmt8(mid)
        else:  # STOP / STOP_LIMIT
            avg_price = 0.0
            status = "NEW"
            exec_qty = "0"
            cum_quote = 0.0
            limit_price = price_str or _fmt8(mid)

        response = {
            "orderId": order_id,
            "symbol": symbol,
            "status": status,
            "clientOrderId": client_order_id,
            "price": limit_price,
            "avgPrice": _fmt8(avg_price),
            "origQty": quantity,
            "executedQty": exec_qty,
            "cumQuote": str(round(cum_quote, 6)),
            "timeInForce": tif,
            "type": order_type,
            "reduceOnly": False,
            "closePosition": False,
            "side": side,
            "positionSide": "BOTH",
            "stopPrice": stop_price_str or "0",
            "workingType": "CONTRACT_PRICE",
            "priceProtect": False,
            "origType": order_type,
            "priceMatch": "NONE",
            "selfTradePreventionMode": "NONE",
            "goodTillDate": 0,
            "updateTime": ts,
        }

        # Log exactly as the real client does
        logger.info(
            "MOCK POST /fapi/v1/order  params=%s",
            {k: v for k, v in kwargs.items()},
        )
        logger.info("MOCK Order response: %s", response)
        return response

    def get_open_orders(self, symbol: Optional[str] = None) -> list:
        logger.debug("MOCK GET /fapi/v1/openOrders symbol=%s", symbol)
        return []

    def get_account(self) -> Dict[str, Any]:
        logger.debug("MOCK GET /fapi/v2/account")
        return {
            "totalWalletBalance": "10000.00000000",
            "totalUnrealizedProfit": "0.00000000",
            "totalMarginBalance": "10000.00000000",
            "availableBalance": "10000.00000000",
            "assets": [
                {
                    "asset": "USDT",
                    "walletBalance": "10000.00000000",
                    "availableBalance": "10000.00000000",
                }
            ],
        }