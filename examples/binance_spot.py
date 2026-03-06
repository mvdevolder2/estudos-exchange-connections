#!/usr/bin/env python3
"""
Exemplo de uso do BinanceConnection (Python)
"""
import os
from binance_connection import BinanceConnection

# Exemplo de callbacks
def on_connected():
    print("✅ Conectado ao Binance WebSocket")

def on_disconnected():
    print("❌ Desconectado do Binance WebSocket")

def on_error(error_code, message):
    print(f"❌ Erro [{error_code}]: {message}")

def on_order_update(order):
    print(f"📦 Ordem atualizada: {order}")

def on_balance_update(balance):
    print(f"💰 Saldo atualizado: {balance}")

async def on_message(message):
    print(f"📡 Mensagem do stream: {message}")

# Criar conexão Spot (testnet)
conn_spot_testnet = BinanceConnection(
    api_key=os.getenv('BINANCE_API_KEY_TEST'),
    secret_key=os.getenv('BINANCE_API_SECRET_TEST'),
    testnet=True,
    callbacks={
        'on_connected': on_connected,
        'on_disconnected': on_disconnected,
        'on_error': on_error,
        'on_order_update': on_order_update,
        'on_balance_update': on_balance_update
    }
)

# Criar conexão Spot (mainnet)
conn_spot_mainnet = BinanceConnection(
    api_key=os.getenv('BINANCE_API_KEY'),
    secret_key=os.getenv('BINANCE_API_SECRET'),
    testnet=False
)

# Criar conexão Futures (testnet)
conn_futures_testnet = BinanceConnection(
    api_key=os.getenv('BINANCE_API_KEY_TEST'),
    secret_key=os.getenv('BINANCE_API_SECRET_TEST'),
    testnet=True
)

# Criar conexão Futures (mainnet)
conn_futures_mainnet = BinanceConnection(
    api_key=os.getenv('BINANCE_API_KEY'),
    secret_key=os.getenv('BINANCE_API_SECRET'),
    testnet=False
)

# Exemplo de uso
if __name__ == "__main__":
    print("="*80)
    print("Exemplo de Uso - BinanceConnection (Python)")
    print("="*80)
    print()

    # Buscar saldo Spot (testnet)
    try:
        balances = conn_spot_testnet.get_balance(asset='USDT')
        print("💰 Saldo USDT Spot (testnet):")
        for balance in balances:
            print(f"   {balance['asset']}: {balance['free']}")
    except Exception as e:
        print(f"❌ Erro ao buscar saldo: {e}")

    # Buscar saldo Futures (testnet)
    try:
        balances = conn_futures_testnet.get_balance(asset='USDT')
        print("\n💰 Saldo USDT Futures (testnet):")
        for balance in balances:
            print(f"   {balance['asset']}: {balance['free']}")
    except Exception as e:
        print(f"❌ Erro ao buscar saldo futures: {e}")

    # Buscar book de ofertas
    try:
        order_book = conn_spot_testnet.get_order_book(symbol='BTCUSDT', limit=5)
        print("\n📊 Order Book BTCUSDT (testnet):")
        print(f"   Best Ask: {order_book['asks'][0] if order_book.get('asks') else 'N/A'}")
        print(f"   Best Bid: {order_book['bids'][0] if order_book.get('bids') else 'N/A'}")
    except Exception as e:
        print(f"❌ Erro ao buscar order book: {e}")

    # Criar ordem Spot (testnet)
    try:
        order = conn_spot_testnet.place_order(
            symbol='BTCUSDT',
            side='BUY',
            type='MARKET',
            quantity='0.001'
        )
        print(f"\n✅ Ordem criada (testnet): {order.get('orderId', order.get('orderId', 'N/A'))}")
    except Exception as e:
        print(f"❌ Erro ao criar ordem: {e}")

    # Buscar ordens abertas
    try:
        orders = conn_spot_testnet.get_open_orders(symbol='BTCUSDT')
        print(f"\n📋 Ordens abertas (testnet): {len(orders) if orders else 0}")
        for order in orders[:5]:
            print(f"   {order.get('symbol')}: {order.get('orderId', order.get('orderId'))} - {order.get('side')} @ {order.get('price', order.get('origQty'))}")
    except Exception as e:
        print(f"❌ Erro ao buscar ordens abertas: {e}")

    # Buscar histórico de trades
    try:
        trades = conn_spot_testnet.get_order_history(symbol='BTCUSDT', limit=10)
        print(f"\n📊 Histórico de trades (testnet): {len(trades) if trades else 0}")
        for trade in trades[:5]:
            print(f"   {trade.get('time')} - {trade.get('symbol')}: {trade.get('orderId', trade.get('orderId'))} - {trade.get('price', trade.get('origQty'))}")
    except Exception as e:
        print(f"❌ Erro ao buscar histórico: {e}")

    # Buscar posição Futures (testnet)
    try:
        position = conn_futures_testnet.get_position(symbol='BTCUSDTUSDT')
        print(f"\n📦 Posição BTCUSDTUSDT (testnet):")
        if position:
            print(f"   Quantity: {position.get('positionAmt', position.get('positionAmt'))}")
            print(f"   Entry Price: {position.get('entryPrice')}")
            print(f"   Mark Price: {position.get('markPrice')}")
            print(f"   Unrealized PnL: {position.get('unRealizedProfit')}")
        else:
            print("   Nenhuma posição aberta")
    except Exception as e:
        print(f"❌ Erro ao buscar posição: {e}")

    # Buscar todas as posições Futures
    try:
        positions = conn_futures_testnet.get_all_positions()
        print(f"\n📦 Todas as posições (testnet): {len(positions) if positions else 0}")
        for position in positions[:5]:
            print(f"   {position.get('symbol')}: {position.get('positionAmt', position.get('positionAmt'))}")
    except Exception as e:
        print(f"❌ Erro ao buscar posições: {e}")

    # Conectar WebSocket
    try:
        print("\n🔌 Conectando ao WebSocket...")
        if conn_spot_testnet.connect():
            print("✅ Conectado!")
        else:
            print("❌ Falha na conexão")
    except Exception as e:
        print(f"❌ Erro ao conectar: {e}")

    # Iniciar stream
    try:
        print("\n📡 Iniciando stream...")
        conn_spot_testnet.start_stream(
            streams=['btcusdt@ticker'],
            on_message=on_message
        )
        print("✅ Stream iniciado!")
    except Exception as e:
        print(f"❌ Erro ao iniciar stream: {e}")

    print("\n✅ Exemplo concluído!")
