"""
Binance Futures Testnet REST client.
Handles request signing, sending, and low-level error handling.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import requests

logger = logging.getLogger("trading_bot.client")

TESTNET_BASE_URL = "https://testnet.binancefuture.com"


class BinanceAPIError(Exception):
    """Raised when the Binance API returns an error response."""

    def __init__(self, code: int, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"Binance API error {code}: {message}")


class BinanceClient:
    """
    Lightweight wrapper around the Binance Futures Testnet REST API.
    Handles HMAC-SHA256 request signing and HTTP error mapping.
    """

    def __init__(self, api_key: str, api_secret: str, base_url: str = TESTNET_BASE_URL) -> None:
        if not api_key or not api_secret:
            raise ValueError("Both api_key and api_secret must be provided.")
        self._api_key = api_key
        self._api_secret = api_secret.encode()
        self._base_url = base_url.rstrip("/")
        self._session = requests.Session()
        self._session.headers.update(
            {
                "X-MBX-APIKEY": self._api_key,
                "Content-Type": "application/x-www-form-urlencoded",
            }
        )
        logger.info("BinanceClient initialised (base_url=%s)", self._base_url)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _sign(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Append server timestamp and HMAC-SHA256 signature to params."""
        params["timestamp"] = int(time.time() * 1000)
        query_string = urlencode(params)
        signature = hmac.new(self._api_secret, query_string.encode(), hashlib.sha256).hexdigest()
        params["signature"] = signature
        return params

    def _handle_response(self, response: requests.Response) -> Dict[str, Any]:
        """Parse response; raise BinanceAPIError on non-2xx or API error body."""
        logger.debug(
            "HTTP %s %s → %d", response.request.method, response.url, response.status_code
        )
        try:
            data = response.json()
        except ValueError:
            response.raise_for_status()
            return {}

        if isinstance(data, dict) and "code" in data and data["code"] != 200:
            logger.error("API error response: %s", data)
            raise BinanceAPIError(data["code"], data.get("msg", "Unknown error"))

        if not response.ok:
            logger.error("HTTP error %d: %s", response.status_code, response.text)
            response.raise_for_status()

        return data

    # ------------------------------------------------------------------
    # Public API methods
    # ------------------------------------------------------------------

    def get_server_time(self) -> int:
        """Fetch server time (ms). Useful for clock-skew diagnosis."""
        url = f"{self._base_url}/fapi/v1/time"
        resp = self._session.get(url, timeout=10)
        data = self._handle_response(resp)
        return data["serverTime"]

    def get_exchange_info(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """Return exchange info (optionally filtered to one symbol)."""
        url = f"{self._base_url}/fapi/v1/exchangeInfo"
        params = {}
        if symbol:
            params["symbol"] = symbol
        resp = self._session.get(url, params=params, timeout=10)
        return self._handle_response(resp)

    def new_order(self, **kwargs: Any) -> Dict[str, Any]:
        """
        Place a new futures order.

        Keyword args are passed directly to POST /fapi/v1/order.
        Required by Binance: symbol, side, type, quantity.
        """
        url = f"{self._base_url}/fapi/v1/order"
        params = self._sign(dict(kwargs))
        logger.info("POST /fapi/v1/order  params=%s", {k: v for k, v in params.items() if k != "signature"})
        resp = self._session.post(url, data=params, timeout=15)
        data = self._handle_response(resp)
        logger.info("Order response: %s", data)
        return data

    def cancel_order(self, symbol: str, order_id: int) -> Dict[str, Any]:
        """Cancel an open order by orderId."""
        url = f"{self._base_url}/fapi/v1/order"
        params = self._sign({"symbol": symbol, "orderId": order_id})
        logger.info("DELETE /fapi/v1/order  symbol=%s orderId=%d", symbol, order_id)
        resp = self._session.delete(url, params=params, timeout=15)
        data = self._handle_response(resp)
        logger.info("Cancel response: %s", data)
        return data

    def get_open_orders(self, symbol: Optional[str] = None) -> list:
        """Retrieve all open orders, optionally filtered by symbol."""
        url = f"{self._base_url}/fapi/v1/openOrders"
        params: Dict[str, Any] = {}
        if symbol:
            params["symbol"] = symbol
        params = self._sign(params)
        resp = self._session.get(url, params=params, timeout=10)
        return self._handle_response(resp)

    def get_account(self) -> Dict[str, Any]:
        """Fetch account/balance information."""
        url = f"{self._base_url}/fapi/v2/account"
        params = self._sign({})
        resp = self._session.get(url, params=params, timeout=10)
        return self._handle_response(resp)
