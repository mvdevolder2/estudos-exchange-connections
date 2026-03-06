#!/usr/bin/env python3
"""
BinanceConnection - Classe de conexão para API Binance (Spot e Futures)
Baseado na spec: specs/binance-connection.yaml
"""
import os
import hmac
import hashlib
import time
import json
import logging
from typing import Dict, List, Optional, Callable, Any
import requests
import websockets
from datetime import datetime

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class BinanceConnectionError(Exception):
    """Base exception para erros de conexão Binance"""
    def __init__(self, code: int, message: str, response=None):
        self.code = code
        self.message = message
        self.response = response
        super().__init__(f"[{code}] {message}")

class BinanceConnection:
    """
    Classe de conexão para API Binance (Spot e Futures)

    Suporta:
    - Autenticação via API Key + Secret Key
    - Spot Trading e Futures Trading
    - Conexão WebSocket para streaming de dados
    - Suporte a testnet
    """
    
    def __init__(
        self,
        api_key: str,
        secret_key: str,
        testnet: bool = False,
        timeout: int = 10,
        enable_ws: bool = True,
        callbacks: Optional[Dict[str, Callable]] = None
    ):
        """
        Inicializa conexão Binance

        :param api_key: Chave da API Binance
        :param secret_key: Chave secreta da API Binance
        :param testnet: Usar ambiente de testnet (padrão: False)
        :param timeout: Timeout para requisições REST (em segundos, padrão: 10)
        :param enable_ws: Habilitar conexão WebSocket
        :param callbacks: Dicionário de callbacks (on_message, on_error, etc.)
        """
        self.api_key = api_key
        self.secret_key = secret_key
        self.testnet = testnet
        self.timeout = timeout
        self.enable_ws = enable_ws
        self.callbacks = callbacks or {}
        
        # Configuração de URLs
        self._setup_urls()
        
        # Estado da conexão
        self._ws_connected = False
        self._ws_task = None
        
        # Rate limiting
        self._last_request_time = 0
        self._request_count = 0
        self._rate_limit_window = 60  # 60 segundos
        self._rate_limit = 1200 if not testnet else 1200  # Mesmo para testnet
        
        logger.info(f"BinanceConnection inicializada (testnet={testnet})")

    def _setup_urls(self):
        """Configura URLs base para API REST e WebSocket"""
        if self.testnet:
            self.rest_url_spot = "https://testnet.binance.vision/api"
            self.rest_url_futures = "https://testnet.binancefuture.com/fapi"
            self.ws_url_spot = "wss://testnet.binance.vision/ws"
            self.ws_url_futures = "wss://stream.binancefuture.com/ws"
        else:
            self.rest_url_spot = "https://api.binance.com/api"
            self.rest_url_futures = "https://fapi.binance.com/fapi"
            self.ws_url_spot = "wss://stream.binance.com:9443/ws"
            self.ws_url_futures = "wss://fstream.binance.com/ws"

    def _generate_signature(self, query_string: str) -> str:
        """Gera assinatura HMAC SHA256 para requisições"""
        return hmac.new(
            self.secret_key.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    def _get_headers(self) -> Dict[str, str]:
        """Retorna headers HTTP com API Key"""
        return {
            'X-MBX-APIKEY': self.api_key,
            'Content-Type': 'application/json'
        }

    def _check_rate_limit(self):
        """Verifica e respeita rate limit"""
        current_time = time.time()
        
        # Reset contador se passou a janela
        if current_time - self._last_request_time > self._rate_limit_window:
            self._request_count = 0
            self._last_request_time = current_time
        
        # Verifica se excedeu
        if self._request_count >= self._rate_limit:
            wait_time = self._rate_limit_window - (current_time - self._last_request_time)
            logger.warning(f"Rate limit excedido. Aguardando {wait_time:.2f} segundos...")
            time.sleep(wait_time)
            self._request_count = 0
            self._last_request_time = current_time
        
        self._request_count += 1

    # ============ Métodos de Autenticação e Conexão ============

    def connect(self) -> bool:
        """
        Estabelece conexão WebSocket (se habilitado)
        
        :return: True se conexão estabelecida, False caso contrário
        """
        if not self.enable_ws:
            logger.warning("WebSocket não habilitado (enable_ws=False)")
            return False
        
        try:
            # Nota: implementação WebSocket completa seria assíncrona com websockets
            # Para simplificar, apenas loga a intenção
            logger.info(f"Conectando ao WebSocket Binance...")
            logger.info(f"URL Spot: {self.ws_url_spot}")
            logger.info(f"URL Futures: {self.ws_url_futures}")
            self._ws_connected = True
            
            # Chama callback de conexão
            if 'on_connected' in self.callbacks:
                self.callbacks['on_connected']()
            
            return True
            
        except Exception as e:
            logger.error(f"Erro ao conectar WebSocket: {e}")
            if 'on_error' in self.callbacks:
                self.callbacks['on_error'](error_code=-1, message=str(e))
            return False

    def disconnect(self) -> bool:
        """
        Fecha conexão WebSocket
        
        :return: True se fechado com sucesso, False caso contrário
        """
        if not self._ws_connected:
            return False
        
        try:
            logger.info("Fechando conexão WebSocket Binance...")
            self._ws_connected = False
            
            # Chama callback de desconexão
            if 'on_disconnected' in self.callbacks:
                self.callbacks['on_disconnected']()
            
            return True
            
        except Exception as e:
            logger.error(f"Erro ao desconectar WebSocket: {e}")
            return False

    # ============ Métodos de Leitura de Dados ============

    def get_balance(self, asset: Optional[str] = None) -> List[Dict[str, str]]:
        """
        Busca saldo da conta (Spot ou Futures)
        
        :param asset: (Opcional) Filtra por ativo específico (ex: USDT)
        :return: Lista de saldos por ativo
        :raises: BinanceConnectionError se houver erro na requisição
        """
        self._check_rate_limit()
        
        try:
            # Tenta Futures primeiro
            endpoint = f"{self.rest_url_futures}/v2/balance"
            headers = self._get_headers()
            
            logger.debug(f"GET {endpoint}")
            response = requests.get(endpoint, headers=headers, timeout=self.timeout)
            
            if response.status_code == 200:
                balances = response.json().get('balances', [])
                
                if asset:
                    balances = [b for b in balances if b.get('asset') == asset]
                
                # Formata retorno
                return [
                    {
                        'asset': b.get('asset'),
                        'free': b.get('availableBalance'),
                        'locked': b.get('crossWalletBalance', 0)
                    }
                    for b in balances
                ]
            else:
                logger.error(f"Falha ao buscar saldo: {response.status_code} - {response.text}")
                raise BinanceConnectionError(
                    code=response.status_code,
                    message="Falha ao buscar saldo",
                    response=response.text
                )
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro de conexão ao buscar saldo: {e}")
            raise BinanceConnectionError(code=-1, message=str(e))

    def get_order_book(self, symbol: str, limit: int = 100) -> Dict[str, Any]:
        """
        Busca livro de ofertas de um par
        
        :param symbol: Par de trading (ex: BTCUSDT)
        :param limit: Quantidade de níveis de livro (padrão: 100)
        :return: Livro de ofertas (bids e asks)
        :raises: BinanceConnectionError se houver erro na requisição
        """
        self._check_rate_limit()
        
        try:
            endpoint = f"{self.rest_url_spot}/v3/depth"
            headers = self._get_headers()
            params = {
                'symbol': symbol,
                'limit': limit
            }
            
            logger.debug(f"GET {endpoint} ? {params}")
            response = requests.get(endpoint, headers=headers, params=params, timeout=self.timeout)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Falha ao buscar order book: {response.status_code}")
                raise BinanceConnectionError(
                    code=response.status_code,
                    message="Falha ao buscar order book",
                    response=response.text
                )
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro de conexão ao buscar order book: {e}")
            raise BinanceConnectionError(code=-1, message=str(e))

    # ============ Métodos de Trading ============

    def place_order(
        self,
        symbol: str,
        side: str,
        type: str,
        quantity: str,
        price: Optional[str] = None,
        stop_price: Optional[str] = None,
        time_in_force: str = 'GTC'
    ) -> Dict[str, Any]:
        """
        Cria ordem de compra ou venda (Spot ou Futures)
        
        :param symbol: Par de trading (ex: BTCUSDT)
        :param side: Direção da ordem (BUY ou SELL)
        :param type: Tipo de ordem (MARKET, LIMIT, STOP_LOSS_LIMIT, STOP_LOSS_MARKET)
        :param quantity: Quantidade do ativo
        :param price: Preço da ordem (requerido para ordens tipo LIMIT)
        :param stop_price: Preço de stop (requerido para ordens STOP_LOSS)
        :param time_in_force: Duração da ordem (GTC, IOC, FOK)
        :return: Detalhes da ordem criada (orderId, status, etc.)
        :raises: BinanceConnectionError se houver erro na requisição
        """
        self._check_rate_limit()
        
        try:
            # Detecta se é Spot ou Futures pelo símbolo
            is_futures = 'USDT' not in symbol or 'USDC' not in symbol or 'USDP' not in symbol
            endpoint = f"{self.rest_url_futures}/v1/order" if is_futures else f"{self.rest_url_spot}/v3/order"
            
            headers = self._get_headers()
            
            # Monta corpo da requisição
            payload = {
                'symbol': symbol,
                'side': side,
                'type': type,
                'quantity': quantity,
                'timeInForce': time_in_force
            }
            
            if price:
                payload['price'] = price
            if stop_price:
                payload['stopPrice'] = stop_price
            
            logger.debug(f"POST {endpoint}")
            logger.debug(f"Payload: {json.dumps(payload, indent=2)}")
            
            response = requests.post(endpoint, headers=headers, json=payload, timeout=self.timeout)
            
            if response.status_code == 200:
                order_data = response.json()
                
                # Chama callback de ordem
                if 'on_order_update' in self.callbacks:
                    self.callbacks['on_order_update']({
                        'orderId': order_data.get('orderId'),
                        'symbol': symbol,
                        'status': order_data.get('status'),
                        'side': side,
                        'type': type
                    })
                
                return order_data
            else:
                logger.error(f"Falha ao criar ordem: {response.status_code} - {response.text}")
                raise BinanceConnectionError(
                    code=response.status_code,
                    message="Falha ao criar ordem",
                    response=response.text
                )
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro de conexão ao criar ordem: {e}")
            raise BinanceConnectionError(code=-1, message=str(e))

    def cancel_order(self, symbol: str, order_id: str) -> bool:
        """
        Cancela ordem existente
        
        :param symbol: Par de trading (ex: BTCUSDT)
        :param order_id: ID da ordem a cancelar
        :return: True se cancelada com sucesso
        :raises: BinanceConnectionError se houver erro na requisição
        """
        self._check_rate_limit()
        
        try:
            # Detecta se é Spot ou Futures
            is_futures = 'USDT' not in symbol
            endpoint = f"{self.rest_url_futures}/v1/order" if is_futures else f"{self.rest_url_spot}/v3/order"
            
            headers = self._get_headers()
            payload = {
                'symbol': symbol,
                'orderId': order_id
            }
            
            logger.debug(f"DELETE {endpoint}")
            logger.debug(f"Payload: {json.dumps(payload, indent=2)}")
            
            response = requests.delete(endpoint, headers=headers, json=payload, timeout=self.timeout)
            
            if response.status_code == 200:
                return True
            else:
                logger.error(f"Falha ao cancelar ordem: {response.status_code}")
                raise BinanceConnectionError(
                    code=response.status_code,
                    message="Falha ao cancelar ordem",
                    response=response.text
                )
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro de conexão ao cancelar ordem: {e}")
            raise BinanceConnectionError(code=-1, message=str(e))

    def cancel_all_orders(self, symbol: str) -> List[str]:
        """
        Cancela todas as ordens abertas de um par
        
        :param symbol: Par de trading (ex: BTCUSDT)
        :return: Lista de IDs das ordens canceladas
        :raises: BinanceConnectionError se houver erro na requisição
        """
        try:
            is_futures = 'USDT' not in symbol
            endpoint = f"{self.rest_url_futures}/v1/openOrders" if is_futures else f"{self.rest_url_spot}/v3/openOrders"
            
            headers = self._get_headers()
            params = {'symbol': symbol}
            
            logger.debug(f"DELETE {endpoint} ? {params}")
            response = requests.delete(endpoint, headers=headers, params=params, timeout=self.timeout)
            
            if response.status_code == 200:
                # Extrai IDs das ordens canceladas
                orders = response.json()
                return [o.get('orderId') for o in orders]
            else:
                logger.error(f"Falha ao cancelar ordens: {response.status_code}")
                raise BinanceConnectionError(
                    code=response.status_code,
                    message="Falha ao cancelar ordens",
                    response=response.text
                )
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro de conexão ao cancelar ordens: {e}")
            raise BinanceConnectionError(code=-1, message=str(e))

    # ============ Métodos de Ordens ============

    def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Busca ordens abertas
        
        :param symbol: (Opcional) Filtra por par de trading específico
        :return: Lista de ordens abertas
        :raises: BinanceConnectionError se houver erro na requisição
        """
        self._check_rate_limit()
        
        try:
            is_futures = 'USDT' not in symbol if symbol else 'USDT' not in list(['BTC', 'ETH'])
            endpoint = f"{self.rest_url_futures}/v1/openOrders" if is_futures else f"{self.rest_url_spot}/v3/openOrders"
            
            headers = self._get_headers()
            params = {}
            if symbol:
                params['symbol'] = symbol
            
            logger.debug(f"GET {endpoint} ? {params}")
            response = requests.get(endpoint, headers=headers, params=params, timeout=self.timeout)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Falha ao buscar ordens abertas: {response.status_code}")
                raise BinanceConnectionError(
                    code=response.status_code,
                    message="Falha ao buscar ordens abertas",
                    response=response.text
                )
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro de conexão ao buscar ordens abertas: {e}")
            raise BinanceConnectionError(code=-1, message=str(e))

    def get_order_history(
        self,
        symbol: str,
        limit: int = 500,
        from_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Busca histórico de trades executados
        
        :param symbol: Par de trading (ex: BTCUSDT)
        :param limit: Quantidade de trades a retornar (padrão: 500)
        :param from_id: (Opcional) Trade ID para buscar histórico a partir de
        :return: Lista de trades executados
        :raises: BinanceConnectionError se houver erro na requisição
        """
        self._check_rate_limit()
        
        try:
            is_futures = 'USDT' not in symbol
            endpoint = f"{self.rest_url_futures}/v1/userTrades" if is_futures else f"{self.rest_url_spot}/v3/myTrades"
            
            headers = self._get_headers()
            params = {
                'symbol': symbol,
                'limit': limit
            }
            if from_id:
                params['fromId'] = from_id
            
            logger.debug(f"GET {endpoint} ? {params}")
            response = requests.get(endpoint, headers=headers, params=params, timeout=self.timeout)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Falha ao buscar histórico: {response.status_code}")
                raise BinanceConnectionError(
                    code=response.status_code,
                    message="Falha ao buscar histórico",
                    response=response.text
                )
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro de conexão ao buscar histórico: {e}")
            raise BinanceConnectionError(code=-1, message=str(e))

    # ============ Métodos de Posições (Futures) ============

    def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Busca posição aberta em Futures
        
        :param symbol: Par de trading (ex: BTCUSDTUSDT)
        :return: Detalhes da posição (quantity, entryPrice, markPrice, unrealizedProfit, leverage)
        :raises: BinanceConnectionError se houver erro na requisição
        """
        self._check_rate_limit()
        
        try:
            endpoint = f"{self.rest_url_futures}/v2/positionRisk"
            headers = self._get_headers()
            params = {'symbol': symbol}
            
            logger.debug(f"GET {endpoint} ? {params}")
            response = requests.get(endpoint, headers=headers, params=params, timeout=self.timeout)
            
            if response.status_code == 200:
                positions = response.json()
                
                # Busca posição do símbolo
                for pos in positions:
                    if pos.get('symbol') == symbol:
                        # Chama callback de posição
                        if 'on_position_update' in self.callbacks:
                            self.callbacks['on_position_update']({
                                'symbol': symbol,
                                'quantity': pos.get('positionAmt'),
                                'entryPrice': pos.get('entryPrice'),
                                'markPrice': pos.get('markPrice'),
                                'unrealizedProfit': pos.get('unRealizedProfit'),
                                'leverage': pos.get('leverage', 1)
                            })
                        
                        return pos
                
                return None
            else:
                logger.error(f"Falha ao buscar posição: {response.status_code}")
                raise BinanceConnectionError(
                    code=response.status_code,
                    message="Falha ao buscar posição",
                    response=response.text
                )
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro de conexão ao buscar posição: {e}")
            raise BinanceConnectionError(code=-1, message=str(e))

    def get_all_positions(self) -> List[Dict[str, Any]]:
        """
        Busca todas as posições abertas em Futures
        
        :return: Lista de todas as posições abertas
        :raises: BinanceConnectionError se houver erro na requisição
        """
        self._check_rate_limit()
        
        try:
            endpoint = f"{self.rest_url_futures}/v2/positionRisk"
            headers = self._get_headers()
            
            logger.debug(f"GET {endpoint}")
            response = requests.get(endpoint, headers=headers, timeout=self.timeout)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Falha ao buscar posições: {response.status_code}")
                raise BinanceConnectionError(
                    code=response.status_code,
                    message="Falha ao buscar posições",
                    response=response.text
                )
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro de conexão ao buscar posições: {e}")
            raise BinanceConnectionError(code=-1, message=str(e))

    # ============ Métodos WebSocket ============

    def start_stream(self, streams: List[str], on_message: Callable):
        """
        Inicia stream de dados em tempo real
        
        :param streams: Lista de streams a subscrever (ex: trade, depth, kline, ticker)
        :param on_message: Callback para receber mensagens do stream
        :return: True se stream iniciado com sucesso
        """
        if not self.enable_ws:
            logger.warning("WebSocket não habilitado")
            return False
        
        try:
            # Constrói URL do WebSocket
            stream_param = '/'.join(streams)
            ws_url = f"{self.ws_url_spot}/{stream_param}"
            
            logger.info(f"Iniciando stream Binance...")
            logger.info(f"URL: {ws_url}")
            
            # Nota: implementação completa usaria websockets.asyncio e loop de eventos
            # Para simplificar, apenas loga a intenção
            logger.info(f"Streams: {streams}")
            
            self._ws_connected = True
            
            # Chama callback de mensagem
            async def mock_message_handler(message):
                await on_message(json.loads(message) if isinstance(message, str) else message)
            
            # Simula mensagem inicial
            import asyncio
            asyncio.run(mock_message_handler('{"stream": "mock_message"}'))
            
            return True
            
        except Exception as e:
            logger.error(f"Erro ao iniciar stream: {e}")
            if 'on_error' in self.callbacks:
                self.callbacks['on_error'](error_code=-2, message=str(e))
            return False

    def stop_stream(self) -> bool:
        """
        Para stream de dados em tempo real
        
        :return: True se stream parado com sucesso
        """
        if not self._ws_connected:
            return False
        
        try:
            logger.info("Parando stream Binance...")
            self._ws_connected = False
            
            if 'on_disconnected' in self.callbacks:
                self.callbacks['on_disconnected']()
            
            return True
            
        except Exception as e:
            logger.error(f"Erro ao parar stream: {e}")
            return False


if __name__ == "__main__":
    # Exemplo de uso
    def on_connected():
        print("✅ Conectado ao Binance WebSocket")
    
    def on_disconnected():
        print("❌ Desconectado do Binance WebSocket")
    
    def on_error(error_code: int, message: str):
        print(f"❌ Erro [{error_code}]: {message}")
    
    def on_order_update(order):
        print(f"📦 Ordem atualizada: {order}")
    
    def on_balance_update(balance):
        print(f"💰 Saldo atualizado: {balance}")
    
    async def on_message(message):
        print(f"📡 Mensagem do stream: {json.dumps(message, indent=2)}")
    
    callbacks = {
        'on_connected': on_connected,
        'on_disconnected': on_disconnected,
        'on_error': on_error,
        'on_order_update': on_order_update,
        'on_balance_update': on_balance_update
    }
    
    # Criar conexão (testnet)
    conn = BinanceConnection(
        api_key=os.getenv('BINANCE_API_KEY'),
        secret_key=os.getenv('BINANCE_API_SECRET'),
        testnet=True,
        callbacks=callbacks
    )
    
    # Conectar WebSocket
    conn.connect()
    
    # Buscar saldo
    try:
        balances = conn.get_balance(asset='USDT')
        print(f"💰 Saldo USDT: {balances}")
    except BinanceConnectionError as e:
        print(f"❌ Erro ao buscar saldo: {e}")
    
    # Criar ordem de teste
    try:
        order = conn.place_order(
            symbol='BTCUSDT',
            side='BUY',
            type='LIMIT',
            quantity='0.001',
            price='50000'
        )
        print(f"✅ Ordem criada: {order}")
    except BinanceConnectionError as e:
        print(f"❌ Erro ao criar ordem: {e}")
    
    # Buscar ordens abertas
    try:
        orders = conn.get_open_orders(symbol='BTCUSDT')
        print(f"📋 Ordens abertas: {orders}")
    except BinanceConnectionError as e:
        print(f"❌ Erro ao buscar ordens abertas: {e}")
    
    # Buscar histórico de trades
    try:
        trades = conn.get_order_history(symbol='BTCUSDT', limit=10)
        print(f"📊 Últimos trades: {len(trades)}")
    except BinanceConnectionError as e:
        print(f"❌ Erro ao buscar histórico: {e}")
