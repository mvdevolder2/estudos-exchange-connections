# Binance API Guia de Conexão

Este documento descreve passo a passo como integrar a API da Binance (Spot e Futures) em projetos Python. Ele cobre:

1. Visão geral da documentação REST oficial.
2. Guia WebSocket.
3. Utilização do SDK Python oficial.
4. Autenticação (API Key, Secret Key, Passphrase).
5. Rate limits e boas práticas.
6. Permissões de endpoints.
7. Endpoints principais e exemplos de uso.
8. Implementação da classe de conexão `BinanceConnection`.

## 1. Documentação REST oficial

- **Spot**: https://developers.binance.com/docs/binance-spot-api-docs
- **Futures**: https://developers.binance.com/docs/derivatives

A documentação está estruturada por **grupos de endpoints** (ex.: `Account`, `Order`, `Market Data`). Cada endpoint tem:
- URL relativa (ex.: `/api/v3/account`)
- Método HTTP (GET/POST/DELETE)
- Parâmetros obrigatórios/extra
- Resposta JSON

**Observação**: a Binance mantém o mesmo prefixo `/api/v3/` para Spot e `/fapi/v1/` (USDⓈ-M) ou `/dapi/v1/` (COIN-M). No caso de APIs públicas, nem todos os endpoints exigem autenticação.

## 2. WebSocket

- **Spot**: `wss://stream.binance.com:9443/ws` (streams separadas como `ticker@arr`, `depth@100ms`)
- **USDT-M Futures**: `wss://fstream.binance.com/stream`
- **COIN-M Futures**: `wss://dstream.binance.com/stream`

* Streams podem ser concatenados por `stream?streams=trade@ticker1/aggTrade@ticker2`*.

Para dados de conta (stream de balance, openOrders etc.) use o WebSocket `private` disponível apenas com uma assinatura via JWT.

## 3. SDK Python oficial

Pacote: `pip install python-binance`.

````python
from binance.client import Client
client = Client(api_key, api_secret)
# Spot balance
print(client.get_account())
````

Para futures use `client = Client(api_key, api_secret, tld='us')` para USDT-M, ou `tld='d'` para COIN-M.

O SDK gera automaticamente cabeçalhos `X-MBX-APIKEY` e `X-MBX-SIGNATURE` quando necessário.

## 4. Autenticação

1. **API Key** e **Secret Key** são obrigatórios para qualquer operação privada.
2. Para *Futures USDT-M* e *COIN-M*, a assinatura é HMAC‑SHA256 do string de query concatenado com `&timestamp=<ts>`, onde `ts` é timestamp em ms.
3. Algumas APIs exigem um campo opcional `recvWindow` (padrão 5000 ms).
4. **Passphrase** é usado em alguns endpoints de Binance US (ex.: `sapi/v1/withdrawHistory`). Para esses, inclua `passphrase=` no query.
5. **Exemplo de assinatura**:

````python
import hmac, hashlib, time
query = 'symbol=BTCUSDT&side=BUY&type=LIMIT&timeInForce=GTC&quantity=0.1&price=50000'
timestamp = str(int(time.time() * 1000))
payload = query + f'&timestamp={timestamp}'
signature = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
````

## 5. Rate Limits

| Escopo | Limite | Comentários |
|--------|--------|-------------|
| Spot    | 1200/recurso a 1 min | 10 requisições/segundo max |
| Futures | 1200/recurso a 1 min | 10 requisições/segundo max |
| WebSocket | 20 conexões simultâneas por IP | Reconnect imediatamente em caso de *`PONG` timeout* |

**Boas práticas**:
- Use “leaky bucket” (ex.: bucket de 1200 tokens, decrementa a cada request).
- Em caso de 429, espere `retry‑after` ou aumente `recvWindow`.
- Para streams, limite de mensagens por segunda não se aplica (o limite é nas requisições HTTP).

## 6. Permissões de endpoint

| Tipo de operação | Permissão requerida |
|--------------------|-------------------|
| Leitura Spot | `spot` (Read) |
| Order Spot | `spot` (Trade) |
| Leitura Futures | `futures` (Read) |
| Order Futures | `futures` (Trade) |
| Transfer / Withdrawal | `spot`/`futures` (Trade + Withdraw) |

As permissões são definidas na página de API Key na Binance.

## 7. Endpoints principais

```mermaid
flowchart TD
    BAL[GET /api/v3/account] -->|Spot account balance| B1
    ORD[POST /api/v3/order] -->|Place order| B2
    OORD[GET /api/v3/openOrders] -->|Open orders| B3
    HIST[GET /api/v3/myTrades] -->|Trade history| B4
    POS[GET /fapi/v2/account] -->|Open positions (USDT‑M)| B5
```

### 7.1 Saldo da conta
````python
balance = client.get_account()
# balance['balances'] contém lista de {asset, free, locked}
````

### 7.2 Criação de ordem
````python
order = client.create_order(
    symbol='BTCUSDT',
    side='BUY',
    type='LIMIT',
    timeInForce='GTC',
    quantity=0.001,
    price=30000
)
````

### 7.3 Ordens abertas
````python
open_ord = client.get_open_orders(symbol='BTCUSDT')
````

### 7.4 Histórico de trades
````python
trades = client.get_my_trades(symbol='BTCUSDT')
````

### 7.5 Posições abertas (USDT‑M Futures)
````python
positions = client.futures_account()
# Cada posição contém asset, positionAmt, entryPrice, unrealizedProfit
````

## 8. Implementação da Classe de Conexão

```python
# /home/claw/.openclaw/workspace-crypto/estudos-exchange-connections/binance_connection.py

import time
import hmac
import hashlib
from urllib.parse import urlencode
import requests

class BinanceConnection:
    BASE_SPOT = "https://api.binance.com"  # Spot base URL
    BASE_FUTURES = "https://fapi.binance.com"  # USDT‑M Futures

    def __init__(self, api_key: str, secret_key: str, tld: str = "", passphrase: str | None = None, recv_window: int = 5000):
        self.api_key = api_key
        self.secret_key = secret_key
        self.passphrase = passphrase
        self.recv_window = recv_window
        self.tld = tld  # "us" for USDT‑M, "d" for COIN‑M

    def _sign(self, query: str) -> str:
        return hmac.new(self.secret_key.encode(), query.encode(), hashlib.sha256).hexdigest()

    def _request(self, method: str, endpoint: str, params: dict = None, private: bool = False, futures: bool = False):
        url = f"{self.BASE_FUTURES if futures else self.BASE_SPOT}{endpoint}"
        headers = {}
        if private:
            headers["X-MBX-APIKEY"] = self.api_key
        if params is None:
            params = {}
        if private:
            ts = str(int(time.time() * 1000))
            params["timestamp"] = ts
            params["recvWindow"] = self.recv_window
            param_str = urlencode(params, True)
            signature = self._sign(param_str)
            params["signature"] = signature
        if futures and self.tld:
            # For Futures with custom TLD, adjust host
            url = url.replace("fapi", f"{self.tld}api")
        if self.passphrase:
            params["passphrase"] = self.passphrase
        if method.upper() == "GET":
            resp = requests.get(url, headers=headers, params=params, timeout=10)
        elif method.upper() == "POST":
            resp = requests.post(url, headers=headers, params=params, timeout=10)
        else:
            raise ValueError("Unsupported HTTP method")
        resp.raise_for_status()
        return resp.json()

    # --- Spot ---
    def get_account(self):
        return self._request("GET", "/api/v3/account", private=True)

    def create_order(self, **kwargs):
        return self._request("POST", "/api/v3/order", params=kwargs, private=True)

    def get_open_orders(self, symbol=None):
        params = {}
        if symbol:
            params["symbol"] = symbol
        return self._request("GET", "/api/v3/openOrders", params=params, private=True)

    def get_my_trades(self, symbol):
        return self._request("GET", "/api/v3/myTrades", params={"symbol": symbol}, private=True)

    # --- Futures ---
    def futures_account(self):
        return self._request("GET", "/fapi/v2/account", private=True, futures=True)

    def futures_create_order(self, **kwargs):
        return self._request("POST", "/fapi/v1/order", params=kwargs, private=True, futures=True)

    def futures_open_orders(self, symbol=None):
        params = {}
        if symbol:
            params["symbol"] = symbol
        return self._request("GET", "/fapi/v1/openOrders", params=params, private=True, futures=True)

    def futures_my_trades(self, symbol):
        return self._request("GET", "/fapi/v1/myTrades", params={"symbol": symbol}, private=True, futures=True)

# Exemplo de uso
if __name__ == "__main__":
    api_key = "YOUR_API_KEY"
    secret = "YOUR_SECRET"
    conn = BinanceConnection(api_key, secret)
    print(conn.get_account())
```

## 9. Armazenamento seguro de chaves

- Mantenha `api_key` e `secret_key` fora do código-fonte (ex.: variáveis de ambiente, GCP Secret Manager, Vault).
- No GitHub, ignore arquivos `.env` e `.secrets.yml` via `.gitignore`.
- Em projetos locais, use `python-dotenv` para carregar `.env`.

## 10. Exemplos de código completo

Crie o arquivo `examples.py` com chamadas demonstrando cada endpoint usando a classe acima.

---

> **Nota**: Este guia está em português (Brasil). Para mais detalhes, consulte a [documentação oficial](https://developers.binance.com/docs/)."
