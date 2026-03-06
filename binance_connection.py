# binance_connection.py
import time
import hmac
import hashlib
from urllib.parse import urlencode
import requests

class BinanceConnection:
    BASE_SPOT = "https://api.binance.com"
    BASE_FUTURES = "https://fapi.binance.com"

    def __init__(self, api_key: str, secret_key: str, tld: str = "", passphrase: str | None = None, recv_window: int = 5000):
        self.api_key = api_key
        self.secret_key = secret_key
        self.passphrase = passphrase
        self.recv_window = recv_window
        self.tld = tld

    def _sign(self, query: str) -> str:
        return hmac.new(self.secret_key.encode(), query.encode(), hashlib.sha256).hexdigest()

    def _build_params(self, params: dict):
        if params is None:
            params = {}
        ts = str(int(time.time() * 1000))
        params["timestamp"] = ts
        params["recvWindow"] = self.recv_window
        return params

    def _request(self, method: str, endpoint: str, params: dict = None, private: bool = False, futures: bool = False):
        url = f"{self.BASE_FUTURES if futures else self.BASE_SPOT}{endpoint}"
        headers = {}
        if private:
            headers["X-MBX-APIKEY"] = self.api_key
        if params is None:
            params = {}
        if private:
            params = self._build_params(params)
            query = urlencode(params, True)
            signature = self._sign(query)
            params["signature"] = signature
        if futures and self.tld:
            # For Futures custom TLD, adjust host
            url = url.replace("fapi", f"{self.tld}api")
        if self.passphrase:
            params["passphrase"] = self.passphrase
        if method.upper() == "GET":
            resp = requests.get(url, headers=headers, params=params, timeout=10)
        elif method.upper() == "POST":
            resp = requests.post(url, headers=headers, params=params, timeout=10)
        else:
            raise ValueError("Unsupported HTTP method")
        try:
            resp.raise_for_status()
        except requests.HTTPError as e:
            raise Exception(f"HTTP {resp.status_code}: {resp.text}") from e
        return resp.json()

    # Spot methods
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

    # Futures methods
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

# End of file
