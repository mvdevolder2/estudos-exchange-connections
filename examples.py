# exemplos de uso da BinanceConnection
import os
from binance_connection import BinanceConnection

API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")

if not API_KEY or not API_SECRET:
    raise ValueError("API_KEY e API_SECRET devem ser definidos em variáveis de ambiente")

# Conexão Spot
spot = BinanceConnection(API_KEY, API_SECRET)
print("Saldo Spot:")
print(spot.get_account())

# Criação de ordem Spot (exemplo limbo)
# order = spot.create_order(symbol="BTCUSDT", side="BUY", type="LIMIT", timeInForce="GTC", quantity="0.001", price="30000")
# print("Ordem criada:", order)

# Ordens abertas Spot
print("Ordens abertas Spot:")
print(spot.get_open_orders())

# Histórico de trades Spot
print("Trades em BTCUSDT:")
print(spot.get_my_trades("BTCUSDT"))

# Conexão Futures USDT-M
futures = BinanceConnection(API_KEY, API_SECRET, tld="us")  # tld='us' ou ''
print("Posições Futures:")
print(futures.futures_account())

# Criação de ordem Futures (exemplo)
# fut_order = futures.futures_create_order(symbol="BTCUSDT", side="BUY", type="LIMIT", timeInForce="GTC", quantity="0.01", price="30000")
# print("Ordem Futures criada:", fut_order)

# Ordens abertas Futures
print("Ordens abertas Futures:")
print(futures.futures_open_orders())

# Histórico de trades Futures
print("Trades Futures em BTCUSDT:")
print(futures.futures_my_trades("BTCUSDT"))
