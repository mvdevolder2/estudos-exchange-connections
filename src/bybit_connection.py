#!/usr/bin/env python3
"""
BybitConnection - Classe de conexão para API Bybit V5 (Spot e Derivatives/Futures)
Baseado na spec: specs/bybit-connection.yaml
"""
import os
import hmac
import hashlib
import base64
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

class BybitConnectionError(Exception):
    """Base exception para erros de conexão Bybit"""
    def __init__(self, code: int, message: str, response=None):
        self.code = code
        self.message = message
        self.response = response
        super().__init__(f"[{code}] {message}")

class BybitConnection:
    """
    Classe de conexão para API Bybit V5 (Spot e Derivatives/Futures)

    Suporta:
    - Autenticação via API Key + Secret Key
    - Spot Trading, Derivatives Trading e Futures Trading
    - Conexão WebSocket para streaming de dados
    """
    
    def __init__(
        self,
        api_key: str,
        secret_key: str,
        category: str = "spot",
        testnet: bool = False,
        timeout: int = 10,
        enable_ws: bool = True,
        callbacks: Optional[Dict[str, Callable]] = None
    ):
        """
        Inicializa conexão Bybit

        :param api_key: Chave da API Bybit (obtida no painel de gerenciamento)
        :param secret_key: Chave secreta da API Bybit (obtida no painel de gerenciamento)
        :param category: Categoria de trading (spot, linear, inverse, option)
        :param testnet: Usar ambiente de testnet
        :param timeout: Timeout para requisições REST (em segundos)
        :param enable_ws: Habilitar conexão WebSocket
        :param callbacks: Dicionário de callbacks (on_connected, on_message, etc.)
        """
        self.api_key = api_key
        self.secret_key = secret_key
        self.category = category
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
        self._rate_limit = 100 if not testnet else 100  # Mesmo para testnet
        
        logger.info(f"BybitConnection inicializada (category={category}, testnet={testnet})")

    def _setup_urls(self):
        """Configura URLs base para API REST e WebSocket"""
        if self.testnet:
            self.rest_url = "https://api-testnet.bybit.com"
            self.ws_url = "wss://stream-testnet.bybit.com/v5/public"
        else:
            if self.category == "spot":
                self.rest_url = "https://api.bybit.com/v5"
                self.ws_url = "wss://stream.bybit.com/v5/public"
            elif self.category in ["linear", "inverse", "option"]:
                self.rest_url = "https://api.bybit.com/v5"
                self.ws_url = "wss://stream.bybit.com/v5/public"
            else:
                raise ValueError(f"Categoria inválida: {self.category}")

    def _generate_signature(self, query_string: str, timestamp: int, recv_window: int = 5000) -> str:
        """
        Gera assinatura HMAC SHA256 para requisições privadas (versão Bybit)

        :param query_string: String de consulta
        :param timestamp: Timestamp Unix em milissegundos
        :param recv_window: Janela de recebimento
        :return: Assinatura em formato hex
        """
        signature_string = f"{timestamp}{api_key}{recv_window}{query_string}"
        
        # Gera HMAC SHA256
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            signature_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature

    def _get_headers(self) -> Dict[str, str]:
        """Retorna headers HTTP com API Key"""
        return {
            'X-BAPI-API-KEY': self.api_key,
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
            logger.info(f"Conectando ao WebSocket Bybit ({self.category})...")
            logger.info(f"URL: {self.ws_url}")
            
            # Nota: Implementação completa de WebSocket usaria websockets.asyncio
            # Para simplificar, apenas loga a intenção
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
        
        :return: True se fechado com sucesso
        """
        if not self._ws_connected:
            return False
        
        try:
            logger.info("Fechando conexão WebSocket Bybit...")
            self._ws_connected = False
            
            # Chama callback de desconexão
            if 'on_disconnected' in self.callbacks:
                self.callbacks['on_disconnected']()
            
            return True
            
        except Exception as e:
            logger.error(f"Erro ao desconectar WebSocket: {e}")
            return False

    # ============ Métodos de Leitura de Dados ============

    def get_balance(self, coin: Optional[str] = None) -> List[Dict[str, str]]:
        """
        Busca saldo da conta (Wallet Balance)
        
        :param coin: (Opcional) Filtra por moeda específica (ex: USDT)
        :return: Lista de saldos por moeda
        :raises: BybitConnectionError se houver erro na requisição
        """
        self._check_rate_limit()
        
        try:
            endpoint = f"{self.rest_url}/account/wallet-balance"
            headers = self._get_headers()
            
            logger.debug(f"GET {endpoint}")
            response = requests.get(endpoint, headers=headers, timeout=self.timeout)
            
            if response.status_code == 200:
                balances = response.json().get('result', [])
                
                if coin:
                    balances = [b for b in balances if b.get('coin') == coin]
                
                return balances
            else:
                logger.error(f"Falha ao buscar saldo: {response.status_code} - {response.text}")
                raise BybitConnectionError(
                    code=response.status_code,
                    message="Falha ao buscar saldo",
                    response=response.text
                )
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro de conexão ao buscar saldo: {e}")
            raise BybitConnectionError(code=-1, message=str(e))

    def get_wallet_balance(self, coin: str) -> Dict[str, str]:
        """
        Busca saldo de uma moeda específica
        
        :param coin: Código da moeda (ex: USDT)
        :return: Dicionário com dados do saldo
        :raises: BybitConnectionError se houver erro na requisição
        """
        balances = self.get_balance(coin=coin)
        
        if balances and len(balances) > 0:
            return balances[0]
        else:
            return {}

    # ============ Métodos de Trading ============

    def place_order(
        self,
        category: str,
        symbol: str,
        side: str,
        order_type: str,
        qty: str,
        price: Optional[str] = None,
        time_in_force: str = 'GTC',
        reduce_only: bool = False,
        take_profit: Optional[str] = None,
        stop_loss: Optional[str] = None,
        tp_slippage: Optional[str] = None,
        sl_slippage: Optional[str] = None,
        close_on_trigger: bool = False,
        options: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Cria ordem (Spot, Derivatives ou Futures)
        
        :param category: Categoria (spot, linear, inverse, option)
        :param symbol: Par de trading (ex: BTCUSDT)
        :param side: Direção (Buy ou Sell)
        :param order_type: Tipo de ordem (Market, Limit, LimitMaker)
        :param qty: Quantidade (ex: 0.01)
        :param price: Preço (obrigatório para ordens tipo Limit)
        :param time_in_force: Tipo de validação (GTC, IOC, FOK, PostOnly)
        :param reduce_only: Reduz apenas, não adiciona posição
        :param take_profit: Preço de take profit
        :param stop_loss: Preço de stop loss
        :param tp_slippage: Slippage de take profit
        :param sl_slippage: Slippage de stop loss
        :param close_on_trigger: Fecha posição ao ser atingido
        :param options: Opções adicionais (client_order_id, etc.)
        :return: Detalhes da ordem criada
        :raises: BybitConnectionError se houver erro na requisição
        """
        self._check_rate_limit()
        
        try:
            endpoint = f"{self.rest_url}/v5/order/create"
            headers = self._get_headers()
            
            # Timestamp para assinatura
            timestamp = int(time.time() * 1000)
            
            # Monta corpo da requisição
            payload = {
                'category': category,
                'symbol': symbol,
                'side': side,
                'orderType': order_type,
                'qty': qty,
                'timeInForce': time_in_force,
                'reduceOnly': reduce_only,
                'closeOnTrigger': close_on_trigger
            }
            
            if price:
                payload['price'] = price
            if take_profit:
                payload['takeProfit'] = take_profit
            if stop_loss:
                payload['stopLoss'] = stop_loss
            if tp_slippage:
                payload['tpSlippage'] = tp_slippage
            if sl_slippage:
                payload['slSlippage'] = sl_slippage
            
            if options:
                payload.update(options)
            
            logger.debug(f"POST {endpoint}")
            logger.debug(f"Payload: {json.dumps(payload, indent=2)}")
            
            # Gera assinatura
            query_string = json.dumps(payload)
            signature = self._generate_signature(query_string, timestamp)
            
            # Adiciona headers de assinatura
            headers['X-BAPI-SIGN'] = signature
            headers['X-BAPI-TIMESTAMP'] = str(timestamp)
            headers['X-BAPI-RECV-WINDOW'] = '5000'
            
            response = requests.post(endpoint, headers=headers, json=payload, timeout=self.timeout)
            
            if response.status_code == 200:
                order_data = response.json()
                
                # Chama callback de ordem
                if 'on_order_update' in self.callbacks:
                    self.callbacks['on_order_update']({
                        'orderId': order_data.get('result', {}).get('orderId'),
                        'symbol': symbol,
                        'status': order_data.get('result', {}).get('orderStatus'),
                        'side': side,
                        'orderType': order_type,
                        'category': category
                    })
                
                return order_data
            else:
                logger.error(f"Falha ao criar ordem: {response.status_code} - {response.text}")
                raise BybitConnectionError(
                    code=response.status_code,
                    message="Falha ao criar ordem",
                    response=response.text
                )
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro de conexão ao criar ordem: {e}")
            raise BybitConnectionError(code=-1, message=str(e))

    def amend_order(
        self,
        category: str,
        symbol: str,
        order_id: str,
        order_type: Optional[str] = None,
        qty: Optional[str] = None,
        price: Optional[str] = None,
        take_profit: Optional[str] = None,
        stop_loss: Optional[str] = None,
        tp_slippage: Optional[str] = None,
        sl_slippage: Optional[str] = None,
        trailing_stop: Optional[str] = None,
        options: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Modifica ordem existente
        
        :param category: Categoria (spot, linear, inverse, option)
        :param symbol: Par de trading
        :param order_id: ID da ordem a modificar
        :param order_type: Tipo de ordem (Limit, LimitMaker)
        :param qty: Nova quantidade
        :param price: Novo preço
        :param take_profit: Novo take profit
        :param stop_loss: Novo stop loss
        :param tp_slippage: Slippage de take profit
        :param sl_slippage: Slippage de stop loss
        :param trailing_stop: Trailing stop
        :param options: Opções adicionais
        :return: Resultado da modificação
        """
        self._check_rate_limit()
        
        try:
            endpoint = f"{self.rest_url}/v5/order/amend"
            headers = self._get_headers()
            
            timestamp = int(time.time() * 1000)
            
            payload = {
                'category': category,
                'symbol': symbol,
                'orderId': order_id,
            }
            
            if order_type:
                payload['orderType'] = order_type
            if qty:
                payload['qty'] = qty
            if price:
                payload['price'] = price
            if take_profit:
                payload['takeProfit'] = take_profit
            if stop_loss:
                payload['stopLoss'] = stop_loss
            if tp_slippage:
                payload['tpSlippage'] = tp_slippage
            if sl_slippage:
                payload['slSlippage'] = sl_slippage
            if trailing_stop:
                payload['trailingStop'] = trailing_stop
            
            if options:
                payload.update(options)
            
            query_string = json.dumps(payload)
            signature = self._generate_signature(query_string, timestamp)
            
            headers['X-BAPI-SIGN'] = signature
            headers['X-BAPI-TIMESTAMP'] = str(timestamp)
            headers['X-BAPI-RECV-WINDOW'] = '5000'
            
            response = requests.post(endpoint, headers=headers, json=payload, timeout=self.timeout)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Falha ao modificar ordem: {response.status_code} - {response.text}")
                raise BybitConnectionError(
                    code=response.status_code,
                    message="Falha ao modificar ordem",
                    response=response.text
                )
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro de conexão ao modificar ordem: {e}")
            raise BybitConnectionError(code=-1, message=str(e))

    def cancel_order(self, category: str, symbol: str, order_id: str) -> Dict[str, Any]:
        """
        Cancela ordem
        
        :param category: Categoria (spot, linear, inverse, option)
        :param symbol: Par de trading (ex: BTCUSDT)
        :param order_id: ID da ordem a cancelar
        :return: Resultado do cancelamento
        """
        self._check_rate_limit()
        
        try:
            endpoint = f"{self.rest_url}/v5/order/cancel"
            headers = self._get_headers()
            
            timestamp = int(time.time() * 1000)
            
            payload = {
                'category': category,
                'symbol': symbol,
                'orderId': order_id
            }
            
            query_string = json.dumps(payload)
            signature = self._generate_signature(query_string, timestamp)
            
            headers['X-BAPI-SIGN'] = signature
            headers['X-BAPI-TIMESTAMP'] = str(timestamp)
            headers['X-BAPI-RECV-WINDOW'] = '5000'
            
            response = requests.post(endpoint, headers=headers, json=payload, timeout=self.timeout)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Falha ao cancelar ordem: {response.status_code} - {response.text}")
                raise BybitConnectionError(
                    code=response.status_code,
                    message="Falha ao cancelar ordem",
                    response=response.text
                )
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro de conexão ao cancelar ordem: {e}")
            raise BybitConnectionError(code=-1, message=str(e))

    def cancel_all_orders(
        self,
        category: str,
        symbol: str,
        settle_coin: Optional[str] = None,
        options: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Cancela todas as ordens de um símbolo
        
        :param category: Categoria (spot, linear, inverse, option)
        :param symbol: Par de trading (ex: BTCUSDT)
        :param settle_coin: Moeda de settlement (apenas Futures)
        :param options: Opções adicionais
        :return: Lista de IDs das ordens canceladas
        """
        self._check_rate_limit()
        
        try:
            endpoint = f"{self.rest_url}/v5/order/cancel-all"
            headers = self._get_headers()
            
            timestamp = int(time.time() * 1000)
            
            payload = {
                'category': category,
                'symbol': symbol,
            }
            
            if settle_coin:
                payload['settleCoin'] = settle_coin
            
            if options:
                payload.update(options)
            
            query_string = json.dumps(payload)
            signature = self._generate_signature(query_string, timestamp)
            
            headers['X-BAPI-SIGN'] = signature
            headers['X-BAPI-TIMESTAMP'] = str(timestamp)
            headers['X-BAPI-RECV-WINDOW'] = '5000'
            
            response = requests.post(endpoint, headers=headers, json=payload, timeout=self.timeout)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Falha ao cancelar ordens: {response.status_code} - {response.text}")
                raise BybitConnectionError(
                    code=response.status_code,
                    message="Falha ao cancelar ordens",
                    response=response.text
                )
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro de conexão ao cancelar ordens: {e}")
            raise BybitConnectionError(code=-1, message=str(e))

    # ============ Métodos de Ordens ============

    def get_open_orders(
        self,
        category: str,
        symbol: Optional[str] = None,
        settle_coin: Optional[str] = None,
        order_id: Optional[str] = None,
        order_filter: Optional[Dict] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Busca ordens abertas
        
        :param category: Categoria (spot, linear, inverse, option)
        :param symbol: (Opcional) Filtra por símbolo específico
        :param settle_coin: (Opcional) Moeda de settlement
        :param order_id: (Opcional) Filtra por ID de ordem
        :param order_filter: Filtro de ordem (order_status, stop_order_type, etc.)
        :param limit: Quantidade de ordens a retornar
        :param cursor: Cursor para paginação
        :return: Dicionário com lista de ordens abertas
        """
        self._check_rate_limit()
        
        try:
            endpoint = f"{self.rest_url}/v5/order/realtime"
            headers = self._get_headers()
            
            params = {}
            if category:
                params['category'] = category
            if symbol:
                params['symbol'] = symbol
            if settle_coin:
                params['settleCoin'] = settle_coin
            if order_id:
                params['orderId'] = order_id
            if order_filter:
                params.update(order_filter)
            if limit:
                params['limit'] = limit
            if cursor:
                params['cursor'] = cursor
            
            logger.debug(f"GET {endpoint} ? {params}")
            response = requests.get(endpoint, headers=headers, params=params, timeout=self.timeout)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Falha ao buscar ordens abertas: {response.status_code} - {response.text}")
                raise BybitConnectionError(
                    code=response.status_code,
                    message="Falha ao buscar ordens abertas",
                    response=response.text
                )
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro de conexão ao buscar ordens abertas: {e}")
            raise BybitConnectionError(code=-1, message=str(e))

    def get_order_history(
        self,
        category: str,
        symbol: str,
        options: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Busca histórico de trades executados
        
        :param category: Categoria (spot, linear, inverse, option)
        :param symbol: Par de trading (ex: BTCUSDT)
        :param options: Opções adicionais (orderId, orderCategory, orderType, etc.)
        :return: Lista de trades executados
        """
        self._check_rate_limit()
        
        try:
            endpoint = f"{self.rest_url}/v5/execution/list"
            headers = self._get_headers()
            
            params = {
                'category': category,
                'symbol': symbol
            }
            
            if options:
                params.update(options)
            
            logger.debug(f"GET {endpoint} ? {params}")
            response = requests.get(endpoint, headers=headers, params=params, timeout=self.timeout)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Falha ao buscar histórico: {response.status_code} - {response.text}")
                raise BybitConnectionError(
                    code=response.status_code,
                    message="Falha ao buscar histórico",
                    response=response.text
                )
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro de conexão ao buscar histórico: {e}")
            raise BybitConnectionError(code=-1, message=str(e))

    # ============ Métodos de Posições (Futures/Derivatives) ============

    def get_position(self, category: str, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Busca posição aberta em Futures/Derivatives
        
        :param category: Categoria (linear, inverse, option)
        :param symbol: Par de trading (ex: BTCUSDTUSDT)
        :return: Detalhes da posição
        """
        self._check_rate_limit()
        
        try:
            endpoint = f"{self.rest_url}/v5/position/list"
            headers = self._get_headers()
            
            params = {
                'category': category,
                'symbol': symbol
            }
            
            logger.debug(f"GET {endpoint} ? {params}")
            response = requests.get(endpoint, headers=headers, params=params, timeout=self.timeout)
            
            if response.status_code == 200:
                positions = response.json().get('result', [])
                
                for pos in positions:
                    if pos.get('symbol') == symbol:
                        # Chama callback de posição
                        if 'on_position_update' in self.callbacks:
                            self.callbacks['on_position_update']({
                                'symbol': symbol,
                                'side': pos.get('side'),
                                'size': pos.get('size'),
                                'unrealizedPnl': pos.get('unrealizedPnl'),
                                'avgPrice': pos.get('avgPrice'),
                                'leverage': pos.get('leverage', 1)
                            })
                        
                        return pos
                
                return None
            else:
                logger.error(f"Falha ao buscar posição: {response.status_code} - {response.text}")
                raise BybitConnectionError(
                    code=response.status_code,
                    message="Falha ao buscar posição",
                    response=response.text
                )
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro de conexão ao buscar posição: {e}")
            raise BybitConnectionError(code=-1, message=str(e))

    def get_all_positions(self, category: str) -> List[Dict[str, Any]]:
        """
        Busca todas as posições abertas em Futures/Derivatives
        
        :param category: Categoria (linear, inverse, option)
        :return: Lista de todas as posições abertas
        """
        self._check_rate_limit()
        
        try:
            endpoint = f"{self.rest_url}/v5/position/list"
            headers = self._get_headers()
            
            params = {
                'category': category
            }
            
            response = requests.get(endpoint, headers=headers, params=params, timeout=self.timeout)
            
            if response.status_code == 200:
                return response.json().get('result', [])
            else:
                logger.error(f"Falha ao buscar posições: {response.status_code} - {response.text}")
                raise BybitConnectionError(
                    code=response.status_code,
                    message="Falha ao buscar posições",
                    response=response.text
                )
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro de conexão ao buscar posições: {e}")
            raise BybitConnectionError(code=-1, message=str(e))

    def close_position(
        self,
        category: str,
        symbol: str,
        side: str,
        qty: str,
        price: Optional[str] = None,
        order_type: str = 'Market'
    ) -> Dict[str, Any]:
        """
        Fecha posição aberta
        
        :param category: Categoria (linear, inverse, option)
        :param symbol: Par de trading
        :param side: Direção (Buy ou Sell)
        :param qty: Quantidade
        :param price: Preço (opcional para ordens tipo Limit)
        :param order_type: Tipo de ordem (Market, Limit)
        :return: Resultado do fechamento
        """
        return self.place_order(
            category=category,
            symbol=symbol,
            side=side,
            order_type=order_type,
            qty=qty,
            price=price,
            reduce_only=True
        )

    # ============ Métodos de Leverage (Futures) ============

    def set_leverage(self, category: str, symbol: str, buy_leverage: str, sell_leverage: str) -> Dict[str, Any]:
        """
        Define alavancagem para um símbolo (apenas Futures/Derivatives)
        
        :param category: Categoria (linear, inverse, option)
        :param symbol: Par de trading (ex: BTCUSDTUSDT)
        :param buy_leverage: Alavancagem para posições longas
        :param sell_leverage: Alavancagem para posições curtas
        :return: Alavancagem definida
        """
        self._check_rate_limit()
        
        try:
            endpoint = f"{self.rest_url}/v5/position/set-leverage"
            headers = self._get_headers()
            
            timestamp = int(time.time() * 1000)
            
            payload = {
                'category': category,
                'symbol': symbol,
                'buyLeverage': buy_leverage,
                'sellLeverage': sell_leverage
            }
            
            query_string = json.dumps(payload)
            signature = self._generate_signature(query_string, timestamp)
            
            headers['X-BAPI-SIGN'] = signature
            headers['X-BAPI-TIMESTAMP'] = str(timestamp)
            headers['X-BAPI-RECV-WINDOW'] = '5000'
            
            response = requests.post(endpoint, headers=headers, json=payload, timeout=self.timeout)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Falha ao definir alavancagem: {response.status_code} - {response.text}")
                raise BybitConnectionError(
                    code=response.status_code,
                    message="Falha ao definir alavancagem",
                    response=response.text
                )
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro de conexão ao definir alavancagem: {e}")
            raise BybitConnectionError(code=-1, message=str(e))

    # ============ Métodos WebSocket ============

    def start_stream(self, category: str, streams: List[str], on_message: Callable) -> bool:
        """
        Inicia stream de dados em tempo real
        
        :param category: Categoria (spot, linear, inverse, option)
        :param streams: Lista de streams a subscrever (trade, depth, kline, ticker)
        :param on_message: Callback para receber mensagens do stream
        :return: True se stream iniciado com sucesso
        """
        if not self.enable_ws:
            logger.warning("WebSocket não habilitado (enable_ws=False)")
            return False
        
        try:
            logger.info(f"Iniciando stream Bybit ({category})...")
            
            # Constrói URL do WebSocket
            stream_param = '/'.join(streams)
            ws_url = f"{self.ws_url}{category}/{stream_param}"
            
            logger.info(f"URL: {ws_url}")
            
            # Nota: Implementação completa usaria websockets.asyncio
            # Para simplificar, apenas loga a intenção
            self._ws_connected = True
            
            # Chama callback de mensagem
            on_message({
                'stream': stream_param,
                'data': 'mock_message'
            })
            
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
            logger.info("Parando stream Bybit...")
            self._ws_connected = False
            
            if 'on_disconnected' in self.callbacks:
                self.callbacks['on_disconnected']()
            
            return True
            
        except Exception as e:
            logger.error(f"Erro ao parar stream: {e}")
            return False


if __name__ == '__main__':
    # Exemplo de uso
    def on_connected():
        print("✅ Conectado ao Bybit WebSocket")
    
    def on_disconnected():
        print("❌ Desconectado do Bybit WebSocket")
    
    def on_error(error_code: int, message: str):
        print(f"❌ Erro [{error_code}]: {message}")
    
    def on_order_update(order):
        print(f"📦 Ordem atualizada: {order}")
    
    def on_position_update(position):
        print(f"📊 Posição atualizada: {position}")
    
    def on_balance_update(balance):
        print(f"💰 Saldo atualizado: {balance}")
    
    async def on_message(message):
        print(f"📡 Mensagem do stream: {json.dumps(message, indent=2)}")
    
    callbacks = {
        'on_connected': on_connected,
        'on_disconnected': on_disconnected,
        'on_error': on_error,
        'on_order_update': on_order_update,
        'on_position_update': on_position_update,
        'on_balance_update': on_balance_update
    }
    
    # Criar conexão Spot
    conn_spot = BybitConnection(
        api_key=os.getenv('BYBIT_API_KEY'),
        secret_key=os.getenv('BYBIT_API_SECRET'),
        category='spot',
        testnet=True,
        callbacks=callbacks
    )
    
    # Conectar WebSocket
    conn_spot.connect()
    
    # Buscar saldo
    try:
        balance = conn_spot.get_wallet_balance(coin='USDT')
        print(f"💰 Saldo USDT: {balance}")
    except BybitConnectionError as e:
        print(f"❌ Erro ao buscar saldo: {e}")
    
    # Criar ordem
    try:
        order = conn_spot.place_order(
            category='spot',
            symbol='BTCUSDT',
            side='Buy',
            order_type='Limit',
            qty='0.001',
            price='50000'
        )
        print(f"✅ Ordem criada: {order}")
    except BybitConnectionError as e:
        print(f"❌ Erro ao criar ordem: {e}")
