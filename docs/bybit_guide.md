# Bybit Exchange Connection Guide

> **Project:** `estudos-exchange-connections`
> **Author:** Data (Crypto Lead)
> **Date:** 2026‑03‑06

---

## Overview
This document provides a **complete** reference for connecting to the Bybit exchange, covering:

1. **REST API (Spot & Futures)** – Endpoints, authentication, and rate‑limits.
2. **WebSocket API** – Public/secret channels, authentication, and reconnection strategy.
3. **Official Python SDK** – When to use it, and how to integrate it with custom logic.
4. **Security** – Safe key storage and handling.
5. **Concrete Python examples** for each operation.
6. **How to respect rate‑limits** and build a robust client.
7. **Spot vs Futures** – A side‑by‑side table for quick reference.

Feel free to copy‑paste the snippets and adapt them to your own experiments or production scripts.

---

## 1. REST API

| Layer | Base URL | Public endp. | Private endp.
|-------|----------|--------------|-------------|
| **Spot** | `https://api.bybit.com/spot/v1/` | `/public/*` | `/private/*`
| **Futures** | `https://api.bybit.com/futures/` | `/public/*` | `/private/*`

### 1.1 Authentication

Bybit uses an **HMAC‑SHA256** signature that is **MD5‑hashed**.

> **Signature formula** (for v2):
> ```text
>  sign = MD5( HMAC_SHA256(secretKey, queryString) )
> ```
>
> * `queryString` – the URL‑encoded request parameters **excluding** `api_key` and `sign`.
> * The `api_key`, `sign`, and, optionally, `recvWindow` (default 3000 ms) are passed as query parameters.
>
> **Example (Python)**
> ```python
> import time, hashlib, hmac, urllib.parse
> api_key = "YOUR_API_KEY"
> secret_key = "YOUR_SECRET_KEY"
> params = {
>     "symbol": "BTCUSDT",
>     "timestamp": int(time.time() * 1000),
>     "recvWindow": 5000,
> }
> # 1. Sort and encode
> query = urllib.parse.urlencode(sorted(params.items()))
> # 2. Compute HMAC‑SHA256
> mac = hmac.new(secret_key.encode(), query.encode(), hashlib.sha256).digest()
> # 3. MD5 hash the binary
> sign = hashlib.md5(mac).hexdigest()
> params["api_key"] = api_key
> params["sign"] = sign
> ```
>
> Send the signed `params` as query string or POST body depending on the endpoint.
>
> **Tip** – Keep the clock in sync with NTP; a drift greater than `recvWindow` will cause signature errors.

### 1.2 Rate Limits

| Scope | Limit | Notes |
|-------|-------|-------|
| **Spot Private** | 20 req/s (≈ 1 000 req/min) | Apply an exponential back‑off on `429`.
| **Spot Public**  | 20 req/s | No key required, but still respect the limit.
| **Futures Private** | 60 req/s (≈ 3 000 req/min) | Some endpoints (order placement) are *double* rate‑limited – avoid flooding.
| **Futures Public** | 20 req/s | Same as spot public.

> **Implementation tip** – Wrap every request in a `@rate_limited` decorator (e.g., `ratelimit` or custom semaphore). Log any 429 responses and wait `timeout`.

### 1.3 Spot Endpoint Summary

| Operation | HTTP | Path | Example URL | Reference |
|-----------|------|------|-------------|-----------|
| **Account Balance** | GET | `/private/account` | `?symbol=BTCUSDT` | Retrieve wallet balances per asset.
| **Create Order** | POST | `/private/order` | `?symbol=BTCUSDT&type=limit&side=buy&size=1&price=30000` |
| **Active Orders** | GET | `/private/active-order/list` | `?symbol=BTCUSDT` |
| **Trade History** | GET | `/private/account/withdraw-history` |  (spot trades are in `/private/order/list` with `order_status=done`) |
| **Open Positions** | GET | `/private/open-position/list` |  (spot supports leveraged trading, returns open leveraged orders) |
| **Closed Positions** | GET | `/private/open-position/list` |  filter `closed=true` |
| **Leverage** | POST | `/private/account/set-leverage` | `?symbol=BTCUSDT&leverage=10` |

### 1.4 Futures Endpoint Summary

| Operation | HTTP | Path | Example URL | Reference |
|-----------|------|------|-------------|-----------|
| **Account Balance** | GET | `/private/linear/position/list` (USDT‑m futures) | `?symbol=BTCUSDT` |
| **Create Order** | POST | `/private/linear/order/create` | `?symbol=BTCUSDT&type=Limit&side=Buy&qty=1&price=30000&time_in_force=GoodTillCancel` |
| **Open Orders** | GET | `/private/linear/order/list` | `?symbol=BTCUSDT` |
| **Trade History** | GET | `/private/linear/settlement/list` | `?symbol=BTCUSDT` |
| **Open Positions** | GET | `/private/linear/position/list` | `?symbol=BTCUSDT` |
| **Closed Positions** | GET | `/private/linear/position/list` | `?symbol=BTCUSDT&closed=true` |
| **Leverage** | POST | `/private/linear/position/leverage/save` | `?symbol=BTCUSDT&leverage=10` |

> **Note** – “Linear” endpoints refer to USDT‑m futures. There are separate *Inverse* endpoints for BTC‑m futures; paths are similar but under `/private/inverse/...`.

---

## 2. WebSocket API

Bybit provides a unified WebSocket stream at:

- **Public**: `wss://stream.bybit.com/v2/public/{spot|futures}`
- **Private**: `wss://stream.bybit.com/v2/private/{spot|futures}`

### 2.1 Authentication for Private Streams

> **Headers** – The socket does **not** use query string parameters.
> ```text
>  api_key: YOUR_API_KEY
>  sign:     <MD5 HMAC‑SHA256(secret_key, timestamp)>
>  timestamp: <millis since Unix epoch>
> ```
> The signature is computed over the timestamp string alone.
>
> **Example in Python** (using `websockets`):
> ```python
> import asyncio, hashlib, hmac, time
> import websockets
>
> async def run():
>     api_key = "<API_KEY>"
>     secret = "<SECRET>"
>     ts = str(int(time.time() * 1000))
>     sign = hashlib.md5(hmac.new(secret.encode(), ts.encode(), hashlib.sha256).digest()).hexdigest()
>     headers = {
>         "api_key": api_key,
>         "sign": sign,
>         "timestamp": ts,
>     }
>     async with websockets.connect("wss://stream.bybit.com/v2/private/spot", extra_headers=headers) as ws:
>         await ws.send("{\"op\":\"subscribe\",\"args\":\"spot.account\"}")
>         async for msg in ws:
>             print(msg)
>
> asyncio.run(run())
> ```
>
> For public streams, no auth headers are needed.

### 2.2 Reconnection Strategy

- Detect `close` events and attempt reconnection after an exponential back‑off (10 s → 20 s → 40 s).
- Resubscribe to subscribed topics using the same JSON `op: subscribe` message.
- Keep a counter of missed heartbeats (If‑None‑Receive time) and close the socket if timeout > 30 s.

### 2.3 Sample Topics

| Spot | Futures |
|------|---------|
| `spot.account` | `futures.account` |
| `spot.order` | `futures.order` |
| `spot.trade` | `futures.trade` |
| `spot.depth.{symbol}` | `futures.depth.{symbol}` |

---

## 3. Official Python SDK

> **Installation** – `pip install bybit`.
> Provides `bybit.bybit` class.

```python
from bybit import bybit
client = bybit(test=True, api_key=KEY, api_secret=SECRET, category='spot')  # category: spot/inverse/linear
```

### 3.1 Spot

```python
# Get account balances
result = client.private_wallet_get_balances().result()  # spot

# Place a limit buy order
order = client.private_order_create(side='Buy', symbol='BTCUSDT', qty='1', order_type='Limit', price='30000', time_in_force='GoodTillCancel').result()
```

### 3.2 Futures (Linear)

```python
client = bybit(test=True, api_key=KEY, api_secret=SECRET, category='linear')
# Set leverage
client.private_position_leverage_save(symbol='BTCUSDT', leverage='10').result()
# Get open positions
pos = client.private_position_list().result()
```

> **Tip** – The SDK automatically signs and retries on 429 internally but does not enforce rate limit; combine with your own `rate_limited` decorator for safety.

---

## 4. Secure Key Storage

### 4.1 Environment Variables

```bash
export BYBIT_API_KEY="xxxx"
export BYBIT_SECRET="yyyy"
```

### 4.2 .env File (for local dev only)

```dotenv
# .env
BYBIT_API_KEY=xxxx
BYBIT_SECRET=yyyy
```

```python
from dotenv import load_dotenv
import os
load_dotenv()
api_key = os.getenv("BYBIT_API_KEY")
secret = os.getenv("BYBIT_SECRET")
```

> **Do not commit** the `.env` or any file containing keys into version control.

---

## 5. Python Template – `BybitConnection`

Below is a minimal but extensible client that covers the requested operations.

```python
# src/bybit_connection.py
import time
import hashlib
import hmac
import urllib.parse
import requests

BASE_URL = {
    "spot": "https://api.bybit.com/spot/v1/",
    "futures": "https://api.bybit.com/futures/",  # public; private under /private/
}

class BybitConnection:
    def __init__(self, api_key: str, secret: str, category: str = "spot", testnet: bool = False):
        self.api_key = api_key
        self.secret = secret
        self.category = category  # spot, linear, inverse
        self.base = BASE_URL[category]
        if testnet:
            self.base = self.base.replace("api.bybit.com", "testnet‑api.bybit.com")

    def _sign(self, params: dict) -> dict:
        ts = str(int(time.time() * 1000))
        params = {k: v for k, v in params.items() if v is not None}
        params.update({"api_key": self.api_key, "recvWindow": 5000, "timestamp": ts})
        query = urllib.parse.urlencode(sorted(params.items()))
        mac = hmac.new(self.secret.encode(), query.encode(), hashlib.sha256).digest()
        sign = hashlib.md5(mac).hexdigest()
        params["sign"] = sign
        return params

    def _request(self, method: str, endpoint: str, params: dict = None, private: bool = False):
        if params is None:
            params = {}
        url = self.base + endpoint
        if private:
            params = self._sign(params)
        else:
            ts = str(int(time.time() * 1000))
            params.update({"timestamp": ts})
            query = urllib.parse.urlencode(sorted(params.items()))
            url += "?" + query
        try:
            resp = requests.request(method, url, params=params if method == "GET" else None,
                                    data=params if method == "POST" else None,
                                    timeout=10)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            print("Request error:", e)
            return None

    # Spot Endpoints
    def get_spot_balance(self, symbol: str):
        return self._request("GET", "private/account", {"symbol": symbol}, private=True)

    def place_spot_order(self, symbol: str, side: str, qty: str, price: str, order_type: str = "Limit"):
        payload = {
            "symbol": symbol,
            "side": side,
            "order_type": order_type,
            "qty": qty,
            "price": price,
        }
        return self._request("POST", "private/order", payload, private=True)

    def get_spot_open_orders(self, symbol: str):
        return self._request("GET", "private/active-order/list", {"symbol": symbol}, private=True)

    def get_spot_trade_history(self, symbol: str):
        return self._request("GET", "private/account/withdraw-history", {"symbol": symbol}, private=True)

    # Futures Endpoints (Linear)
    def get_futures_balance(self, symbol: str):
        return self._request("GET", "private/linear/position/list", {"symbol": symbol}, private=True)

    def place_futures_order(self, symbol: str, side: str, qty: str, price: str, order_type: str = "Limit"):
        payload = {
            "symbol": symbol,
            "side": side,
            "order_type": order_type,
            "qty": qty,
            "price": price,
            "time_in_force": "GoodTillCancel",
        }
        return self._request("POST", "private/linear/order/create", payload, private=True)

    def get_futures_open_orders(self, symbol: str):
        return self._request("GET", "private/linear/order/list", {"symbol": symbol}, private=True)

    def get_futures_trade_history(self, symbol: str):
        return self._request("GET", "private/linear/settlement/list", {"symbol": symbol}, private=True)

    def get_futures_positions(self, symbol: str, closed: bool = False):
        params = {"symbol": symbol}
        if closed:
            params["closed"] = "true"
        return self._request("GET", "private/linear/position/list", params, private=True)

    def set_leverage(self, symbol: str, leverage: int):
        payload = {"symbol": symbol, "leverage": str(leverage)}
        return self._request("POST", "private/linear/position/leverage/save", payload, private=True)
```

> **Usage** – Import `BybitConnection` and instantiate with your API keys.

---

## 6. Rate‑Limit Handling (Illustrated in Python)

```python
from ratelimit import limits, sleep_and_retry

CALLS = 20  # per second for spot
PERIOD = 1

@sleep_and_retry
@limits(calls=CALLS, period=PERIOD)
def safe_request(...):
    return client.get_spot_balance(symbol)
```

If a request returns status `429`, pause for `timeout` seconds and retry.

---

## 7. Spot vs Futures Quick Reference

| Feature | Spot | Futures (Linear) |
|---------|-------|-----------------|
| **Leverage** | Optional up to 125× | Up to 125× (configurable per contract) |
| **Funding Rate** | None | Yes, per contract |
| **Position Types** | Spot balances, limited margin | Long/Short positions, isolated/cross margin |
| **Fee Structure** | Maker/Taker ~0.075% | Maker/Taker ~0.04% (maker) / ~0.04% (taker) |
| **Data Streams** | Spot depth, trades, account | Additional futures depth, mark price, funding info |
| **Order Types** | Market, Limit, Stop, OCO | Market, Limit, Stop, OCO, Trail, Stop Limit |
| **API Key Scopes** | `spot` | `futures` (or `inverse`/`linear`) |

---

## 8. Next Steps for the Team

1. **Setup** – Create `.env` with your Bybit keys.
2. **Run** – Import `BybitConnection` and try the sample scripts.
3. **Extend** – Add caching for balances, use websocket streams for low‑latency order status.
4. **Monitor** – Log all requests and responses; watch for 429s.
5. **CI** – Add unit tests for signing and endpoint wrappers.

---

> **Disclaimer:** This guide is based on the public Bybit API as of 2026‑03‑06. APIs may evolve; always refer to the official docs for the latest changes.

