# OKX API Guide

This guide provides a complete reference for implementing connections to the OKX exchange (Spot and Futures). It covers REST endpoints, WebSocket streams, authentication, rate limits, permissions, and example code. The guide is tailored for the **`estudos-exchange-connections`** project.

## Table of Contents
1. [REST API Overview](#rest-api-overview)
2. [WebSocket Overview](#websocket-overview)
3. [SDK Python](#sdk-python)
4. [Authentication](#authentication)
5. [Rate Limits](#rate-limits)
6. [Permissions Matrix](#permissions-matrix)
7. [Key Endpoints](#key-endpoints)
8. [Python Class: OKXConnection](#python-class-okxconnection)
9. [Sample Code Snippets](#sample-code-snippets)
10. [Security & Key Management](#security--key-management)

---

## REST API Overview

The official OKX REST API v5 exposes separate namespaces for Spot and Futures:

- **Base URL**: `https://www.okx.com` (HTTPS only)
- **Spot**: `/api/v5/spot/…`
- **Futures**: `/api/v5/future/…`
- **Spot Futures (BTC‑USD, USD‑Ⓢ‑M)** also use `/api/v5/future/…` but with distinct contract pairs.
- Use **API version v5**; older v3 endpoints are deprecated.

The API is stateless; each call includes required authentication headers.

## WebSocket Overview

OKX WebSocket provides real‑time market data and account updates.

- **Base Endpoint**: `wss://ws.okx.com:8443/ws/v5/public` for public market streams.
- **Private**: `wss://ws.okx.com:8443/ws/v5/trade` or `wss://ws.okx.com:8443/ws/v5/private` depending on the use‑case.
- Authentication over WebSocket uses the same headers as REST but requires an additional **`Signature`** created from `timestamp + method(POST) + requestPath + body` (usually `wss://ws.okx.com:8443/ws/v5/private`).
- Connection count limit: **100 concurrent connections per IP**.
- Rate limit: **60 requests/second** for login, subscribe, and unsubscribe actions.

## SDK Python

OKX provides an **official SDK** (`okx-sdk` on PyPI). It handles signing, retries, and typing.

```bash
pip install okx-sdk
```

Example import:

```python
from okx.sdk import OKX
```

SDK can operate in **async** or **sync** mode. Use the sync client for quick scripts.

## Authentication

All authenticated endpoints (including WebSocket login) require the following HTTP headers:

| Header | Description |
|--------|-------------|
| `OK-ACCESS-KEY` | Your API key |
| `OK-ACCESS-SIGN` | HMAC‑SHA256 of `timestamp + method + requestPath + body`, base64‑encoded |
| `OK-ACCESS-TIMESTAMP` | ISO‑8601 UTC timestamp, e.g. `2023-12-31T23:59:59Z` |
| `OK-ACCESS-PASSPHRASE` | Passphrase created when generating the key |

**Signature formula** (pseudocode):

```python
message = f"{timestamp}{method}{request_path}{body}".encode()
sign = base64.b64encode(hmac.new(secret.encode(), message, hashlib.sha256).digest()).decode()
```

All private calls use an **HTTP method** (`GET`, `POST`, `DELETE`). For POST, include `body` as a JSON string; for GET, `body=''`.

## Rate Limits

| Category | Limit | Notes |
|----------|-------|-------|
| Spot REST | 120 requests/second (1200/min) | Per IP. Exceeding triggers `429`.
| Futures REST | 60 requests/second (600/min) | Per IP.
| WebSocket (login/subscribe) | 60 per second | Per IP.
|
Keep a local counter or use SDK’s built‑in rate‑limit handling. Exponential back‑off on `429`.

## Permissions Matrix

| Operation | Spot | Futures | Read‑only | Streaming |
|-----------|------|---------|-----------|-----------|
| Get Balance | ✅ | ✅ | ❌ | ❌ |
| Create Order | ✅ | ✅ | ❌ | ❌ |
| Get Open Orders | ✅ | ✅ | ❌ | ❌ |
| Get Trade History | ✅ | ✅ | ❌ | ❌ |
| Get Positions | ❌ | ✅ | ❌ | ❌ |
| Set Leverage | ❌ | ✅ | ❌ | ❌ |
| Subscribe Tick | ❌ | ❌ | ✅ | ✅ |
| Subscribe Trade | ❌ | ❌ | ✅ | ✅ |
|
**Read‑only key**: can only call `GET` endpoints and subscribe. **Trading key**: add `order` and `trade` permissions.

## Key Endpoints

Below are the most often used endpoints. The request path is the exact string used in the signature.

### Spot
| Purpose | Endpoint | Method |
|---------|----------|--------|
| Get balance | `/api/v5/account/balance` | `GET` |
| Place order | `/api/v5/trade/order` | `POST` |
| Cancel order | `/api/v5/trade/cancel-order` | `POST` |
| Open orders | `/api/v5/trade/open-orders` | `GET` |
| Trade history | `/api/v5/trade/fills` | `GET` |

### Futures
| Purpose | Endpoint | Method |
|---------|----------|--------|
| Get positions | `/api/v5/trade/positions` | `GET` |
| Get positions history | `/api/v5/trade/positions/history` | `GET` |
| Set leverage | `/api/v5/trade/leverage` | `POST` |
| Get max order qty | `/api/v5/trade/max-order-quantity` | `GET` |

### WebSocket Streams
- **Public Tick**: `wss://ws.okx.com:8443/ws/v5/public?...` – `book5.<symbol>`
- **Public Trade**: `trade.<symbol>`
- **Private Account Updates**: `account.<account-id>` after login.

## Python Class: `OKXConnection`

The following class encapsulates common patterns for REST and WebSocket operations.

```python
import time
import hmac
import hashlib
import base64
import json
import requests
import websocket
from typing import Dict, Any

class OKXConnection:
    BASE_URL = "https://www.okx.com"
    WS_PUBLIC = "wss://ws.okx.com:8443/ws/v5/public"
    WS_PRIVATE = "wss://ws.okx.com:8443/ws/v5/private"

    def __init__(self, key: str, secret: str, passphrase: str, use_futures: bool = False):
        self.key = key
        self.secret = secret
        self.passphrase = passphrase
        self.use_futures = use_futures
        self.session = requests.Session()

    def _timestamp(self) -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%S.%fZ", time.gmtime())

    def _sign(self, timestamp: str, method: str, request_path: str, body: str) -> str:
        message = f"{timestamp}{method}{request_path}{body}".encode()
        signature = hmac.new(self.secret.encode(), message, hashlib.sha256).digest()
        return base64.b64encode(signature).decode()

    def _headers(self, method: str, request_path: str, body: str = "") -> Dict[str, str]:
        timestamp = self._timestamp()
        sign = self._sign(timestamp, method, request_path, body)
        return {
            "OK-ACCESS-KEY": self.key,
            "OK-ACCESS-SIGN": sign,
            "OK-ACCESS-TIMESTAMP": timestamp,
            "OK-ACCESS-PASSPHRASE": self.passphrase,
            "Content-Type": "application/json",
        }

    # ----------------- REST -----------------
    def get_balance(self, account_type: str = "spot") -> Dict[str, Any]:
        path = "/api/v5/account/balance"
        headers = self._headers("GET", path)
        resp = self.session.get(self.BASE_URL + path, headers=headers)
        resp.raise_for_status()
        return resp.json()

    def place_order(self, side: str, symbol: str, order_type: str, price: float, size: float, **kwargs) -> Dict[str, Any]:
        path = "/api/v5/trade/order"
        payload = {
            "side": side,
            "symbol": symbol,
            "type": order_type,
            "price": str(price),
            "size": str(size),
            **kwargs,
        }
        body = json.dumps(payload)
        headers = self._headers("POST", path, body)
        resp = self.session.post(self.BASE_URL + path, headers=headers, data=body)
        resp.raise_for_status()
        return resp.json()

    # --------------------------------------------------
    # WebSocket – public subscribe
    def ws_public_subscribe(self, channel: str, params: Dict[str, Any] = None, on_message=None):
        ws = websocket.WebSocketApp(self.WS_PUBLIC,
                                    on_message=on_message,
                                    on_error=lambda ws, e: print("WS error", e),
                                    on_close=lambda ws: print("WS closed"))
        # Build subscribe payload
        msg = {"op": "subscribe", "args": [channel]} if not params else {"op": "subscribe", "args": [params]}
        ws.send(json.dumps(msg))
        ws.run_forever()

    # WebSocket – private login
    def ws_private_login(self, on_message=None):
        # Build login payload with auth
        timestamp = self._timestamp()
        sign = self._sign(timestamp, "POST", "/ws/v5/private", "")
        data = {
            "op": "login",
            "args": [{
                "APIKey": self.key,
                "Passphrase": self.passphrase,
                "Signature": sign,
                "Timestamp": timestamp,
                "recvWindow": 5000
            }]
        }
        ws = websocket.WebSocketApp(self.WS_PRIVATE, on_message=on_message)
        ws.send(json.dumps(data))
        ws.run_forever()
```

> **Tip**: For production, wrap the WebSocket in a thread or async task and implement reconnect logic.

## Sample Code Snippets

### Spot: Get balance
```python
conn = OKXConnection(key, secret, passphrase)
print(conn.get_balance())
```

### Spot: Place a market order
```python
order_resp = conn.place_order(
    side="buy",
    symbol="BTC-USDT",
    order_type="market",
    price=0,        # price ignored for market
    size=0.001,
    orderIv=0,      # optional
)
print(order_resp)
```

### Futures: Get positions
```python
conn = OKXConnection(key, secret, passphrase)
print(conn.session.get(conn.BASE_URL + "/api/v5/trade/positions", headers=conn._headers("GET", "/api/v5/trade/positions")).json())
```

### WebSocket: Subscribe to BTC‑USDT trades (public)
```python
def on_msg(ws, msg):
    print("Trade:", msg)

conn.ws_public_subscribe("trade.BTC-USDT", on_message=on_msg)
```

### WebSocket: Private account updates
```python
def on_msg(ws, msg):
    print("Account update:", msg)

conn.ws_private_login(on_message=on_msg)
```

## Security & Key Management

1. Store API keys in a secrets manager or encrypted file. Example using environment variables:
   ```bash
   export OKX_API_KEY=xxxxxxxx
   export OKX_SECRET=xxxxxxxx
   export OKX_PASSPHRASE=xxxxxx
   ```
2. Never commit keys to source control.
3. Rotate keys regularly and monitor for abuse via the OKX dashboard.
4. Use **read‑only** API keys for scripts that only fetch data.

---

## Summary

- **Base URLs**: `https://www.okx.com` for REST, `wss://ws.okx.com:8443` for WS.
- **Auth**: HMAC‑SHA256 derived headers.
- **Rate limits**: 120 rps for Spot, 60 rps for Futures, 60 rps for WS.
- **Permissions**: Separate key scopes.
- **Key endpoints**: Balance, orders, positions, leverage, trade history.
- **Python**: `OKXConnection` class demonstrates common usage.

Feel free to adapt the snippets to your project structure.
