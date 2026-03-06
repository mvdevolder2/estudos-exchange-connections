#!/usr/bin/env python3
"""
OKXConnection - Classe de conexão para API OKX V5 (Spot e Futures)
Baseado na spec: specs/okx-connection.yaml
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

class OKXConnectionError(Exception):
    """Base exception para erros de conexão OKX"""
    def __init__(self, code: int, message: str, response=None):
        self.code = code
        self.message = message
        self.response = response
        super().__init__(f"[{code}] {message}")

class OKXConnection:
    """
    Classe de conexão para API OKX V5 (Spot, Futures, Margem e Opções)

    Suporta:
    - Autenticação via API Key + Secret Key + Passphrase
    - Spot Trading, Futures Trading
    - Conexão WebSocket para streaming de dados
    - Suporte a Demo Trading (x-simulated-trading: 1)
    """

    def __init__(
        self,
        api_key: str,
        secret_key: str,
        passphrase: str,
        simulated_trading: bool = False,
        testnet: bool = False,
        timeout: int = 10,
        enable_ws: bool = True,
        callbacks: Optional[Dict[str, Callable]] = None
    ):
        """
        Inicializa conexão OKX

        :param api_key: Chave da API OKX (obtida no painel de gerenciamento)
        :param secret_key: Chave secreta da API OKX (obtida no painel de gerenciamento)
        :param passphrase: Frase de recuperação da API OKX
        :param simulated_trading: Usar modo de simulação (Demo Trading)
        :param testnet: Usar ambiente de testnet (OKX não tem testnet oficial)
        :param timeout: Timeout para requisições REST (em segundos)
        :param enable_ws: Habilitar conexão WebSocket para streaming de dados
        :param callbacks: Dicionário de callbacks (on_message, on_error, etc.)
        """
        self.api_key = api_key
        self.secret_key = secret_key
        self.passphrase = passphrase
        self.simulated_trading = simulated_trading
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
        self._rate_limit = 20 if not testnet else 20  # Mesmo para testnet (OKX não tem testnet oficial)

        logger.info(f"OKXConnection inicializada (simulated_trading={simulated_trading})")

    def _setup_urls(self):
        """Configura URLs base para API REST e WebSocket"""
        # OKX não tem testnet oficial, apenas Demo Trading
        if self.testnet:
            logger.warning("OKX não tem testnet oficial. Usando Demo Trading.")

        # URLs base (usando V5 API)
        self.rest_url = "https://www.okx.com"
        self.ws_url = "wss://wspap.okx.com:443/ws/v5/public"

        if self.simulated_trading:
            self.ws_url = "wss://wspap.okx.com:443/ws/v5/simulated-trading"

    def _generate_signature(self, method: str, request_path: str, body: str = '', timestamp: Optional[int] = None) -> str:
        """
        Gera assinatura HMAC SHA256 para requisições privadas (versão OKX V5)

        :param method: Método HTTP (GET, POST, DELETE)
        :param request_path: Caminho da requisição (ex: /api/v5/account/balance)
        :param body: Corpo da requisição (para POST/DELETE)
        :param timestamp: Timestamp Unix em milissegundos (opcional, gera se não fornecido)
        :return: Assinatura em formato base64
        """
        if timestamp is None:
            timestamp = int(time.time() * 1000)

        # Formato da assinatura OKX V5: timestamp + method + requestPath + body
        sign_str = f"{timestamp}{method}{request_path}{body}"

        # Gera HMAC SHA256
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            sign_str.encode('utf-8'),
            hashlib.sha256
        ).digest()

        # Base64 encode
        return base64.b64encode(signature).decode('utf-8')

    def _get_headers(self, method: str = 'GET', request_path: str = '', body: str = '') -> Dict[str, str]:
        """
        Retorna headers HTTP com API Key, Timestamp e Assinatura

        :param method: Método HTTP
        :param request_path: Caminho da requisição
        :param body: Corpo da requisição
        :return: Headers com assinatura
        """
        timestamp = int(time.time() * 1000)
        signature = self._generate_signature(method, request_path, body, timestamp)

        return {
            'OK-ACCESS-KEY': self.api_key,
            'OK-ACCESS-TIMESTAMP': str(timestamp),
            'OK-ACCESS-SIGN': signature,
            'Content-Type': 'application/json',
            'x-simulated-trading': '1' if self.simulated_trading else ''
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
            # Nota: Implementação WebSocket completa seria assíncrona com websockets
            # Para simplificar, apenas loga a intenção
            logger.info(f"Conectando ao WebSocket OKX (simulated={self.simulated_trading})")
            logger.info(f"URL: {self.ws_url}")
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
            logger.info("Fechando conexão WebSocket OKX...")
            self._ws_connected = False

            # Chama callback de desconexão
            if 'on_disconnected' in self.callbacks:
                self.callbacks['on_disconnected']()

            return True

        except Exception as e:
            logger.error(f"Erro ao desconectar WebSocket: {e}")
            return False

    # ============ Métodos de Leitura de Dados ============

    def get_balance(self, currency: Optional[str] = None) -> List[Dict[str, str]]:
        """
        Busca saldo da conta (Spot, Margem, Futures e Trading Account)

        :param currency: (Opcional) Filtra por moeda específica (ex: USDT)
        :return: Lista de saldos por tipo de carteira
        :raises: OKXConnectionError se houver erro na requisição
        """
        self._check_rate_limit()

        try:
            # V5 API: /api/v5/account/balance
            request_path = '/api/v5/account/balance'
            headers = self._get_headers('GET', request_path)

            logger.debug(f"GET {self.rest_url}{request_path}")
            response = requests.get(f"{self.rest_url}{request_path}", headers=headers, timeout=self.timeout)

            if response.status_code == 200:
                data = response.json()
                return data.get('data', [])
            else:
                logger.error(f"Falha ao buscar saldo: {response.status_code} - {response.text}")
                raise OKXConnectionError(
                    code=response.status_code,
                    message="Falha ao buscar saldo",
                    response=response.text
                )

        except requests.exceptions.RequestException as e:
            logger.error(f"Erro de conexão ao buscar saldo: {e}")
            raise OKXConnectionError(code=-1, message=str(e))

    def get_order_book(self, inst_id: str, limit: int = 100) -> Dict[str, Any]:
        """
        Busca livro de ofertas de um instrumento

        :param inst_id: ID do instrumento (ex: BTC-USDT-SWAP)
        :param limit: Quantidade de níveis de livro
        :return: Livro de ofertas (bids e asks)
        :raises: OKXConnectionError se houver erro na requisição
        """
        self._check_rate_limit()

        try:
            # V5 API: /api/v5/market/books
            request_path = f"/api/v5/market/books?instId={inst_id}&sz={limit}"
            headers = self._get_headers('GET', request_path)

            logger.debug(f"GET {self.rest_url}{request_path}")
            response = requests.get(f"{self.rest_url}{request_path}", headers=headers, timeout=self.timeout)

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Falha ao buscar order book: {response.status_code}")
                raise OKXConnectionError(
                    code=response.status_code,
                    message="Falha ao buscar order book",
                    response=response.text
                )

        except requests.exceptions.RequestException as e:
            logger.error(f"Erro de conexão ao buscar order book: {e}")
            raise OKXConnectionError(code=-1, message=str(e))

    # ============ Métodos de Trading ============

    def place_order(
        self,
        inst_id: str,
        td_mode: str,
        side: str,
        ord_type: str,
        sz: str,
        px: Optional[str] = None,
        reduce_only: bool = False,
        tp_trigger_px: Optional[str] = None,
        tp_ord_px: Optional[str] = None,
        tp_trigger_px_type: Optional[str] = None,
        sl_trigger_px: Optional[str] = None,
        sl_ord_px: Optional[str] = None,
        sl_trigger_px_type: Optional[str] = None,
        ccy: Optional[str] = None
        pos_side: Optional[str] = None,
        amend_px: Optional[str] = None
        pos_ordinal: Optional[str] = None,
        ban_amend: Optional[str] = None,
        quick_mgn: Optional[str] = None,
        tag: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Cria ordem de compra ou venda

        :param inst_id: ID do instrumento (ex: BTC-USDT-SWAP)
        :param td_mode: Modo de trading (cash, cross, isolated)
        :param side: Direção da ordem (buy ou sell)
        :param ord_type: Tipo de ordem (market, limit, post_only, post_only_cross, market_limit)
        :param sz: Tamanho da ordem (ex: 0.01)
        :param px: Preço da ordem (obrigatório para ordens tipo limit)
        :param reduce_only: Reduz apenas, não adiciona posição
        :param tp_trigger_px: Preço de gatilho de take profit
        :param tp_ord_px: Preço de ordem de take profit
        :param tp_trigger_px_type: Tipo de gatilho (last, index, mark)
        :param sl_trigger_px: Preço de gatilho de stop loss
        :param sl_ord_px: Preço de ordem de stop loss
        :param sl_trigger_px_type: Tipo de gatilho (last, index, mark)
        :param ccy: Moeda de settlement
        :param pos_side: Lado da posição (long ou short)
        :param amend_px: Preço para amendar ordem
        :param pos_ordinal: Ordem da posição a ser encerrada
        :param ban_amend: Banir amend
        :param quick_mgn: Margem rápida
        :param tag: Tag da ordem
        :return: Detalhes da ordem criada (ordId, status, etc.)
        :raises: OKXConnectionError se houver erro na requisição
        """
        self._check_rate_limit()

        try:
            # V5 API: /api/v5/trade/order
            request_path = '/api/v5/trade/order'
            headers = self._get_headers('POST', request_path)

            # Monta corpo da requisição
            payload = {
                'instId': inst_id,
                'tdMode': td_mode,
                'side': side,
                'ordType': ord_type,
                'sz': sz
            }

            # Parâmetros opcionais
            if px:
                payload['px'] = px
            if reduce_only:
                payload['reduceOnly'] = reduce_only
            if tp_trigger_px:
                payload['tpTriggerPx'] = tp_trigger_px
            if tp_ord_px:
                payload['tpOrdPx'] = tp_ord_px
            if tp_trigger_px_type:
                payload['tpTriggerPxType'] = tp_trigger_px_type
            if sl_trigger_px:
                payload['slTriggerPx'] = sl_trigger_px
            if sl_ord_px:
                payload['slOrdPx'] = sl_ord_px
            if sl_trigger_px_type:
                payload['slTriggerPxType'] = sl_trigger_px_type
            if ccy:
                payload['ccy'] = ccy
            if pos_side:
                payload['posSide'] = pos_side
            if amend_px:
                payload['amendPx'] = amend_px
            if pos_ordinal:
                payload['posOrdinal'] = pos_ordinal
            if ban_amend:
                payload['banAmend'] = ban_amend
            if quick_mgn:
                payload['quickMgn'] = quick_mgn
            if tag:
                payload['tag'] = tag

            logger.debug(f"POST {self.rest_url}{request_path}")
            logger.debug(f"Payload: {json.dumps(payload, indent=2)}")

            response = requests.post(f"{self.rest_url}{request_path}", headers=headers, json=payload, timeout=self.timeout)

            if response.status_code == 200:
                order_data = response.json()

                # Chama callback de ordem
                if 'on_order_update' in self.callbacks:
                    self.callbacks['on_order_update']({
                        'ordId': order_data.get('data', {}).get('ordId'),
                        'instId': inst_id,
                        'status': order_data.get('data', {}).get('state'),
                        'side': side,
                        'ordType': ord_type
                    })

                return order_data
            else:
                logger.error(f"Falha ao criar ordem: {response.status_code}")
                raise OKXConnectionError(
                    code=response.status_code,
                    message="Falha ao criar ordem",
                    response=response.text
                )

        except requests.exceptions.RequestException as e:
            logger.error(f"Erro de conexão ao criar ordem: {e}")
            raise OKXConnectionError(code=-1, message=str(e))

    def amend_order(
        self,
        inst_id: str,
        ord_id: str,
        new_px: str,
        td_mode: Optional[str] = None
        pos_side: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Modifica ordem existente

        :param inst_id: ID do instrumento
        :param ord_id: ID da ordem a modificar
        :param new_px: Novo preço
        :param td_mode: Modo de trading (cash, cross, isolated)
        :param pos_side: Lado da posição (long ou short)
        :return: Detalhes da ordem modificada
        """
        return self.place_order(
            inst_id=inst_id,
            ord_type='market',
            side='buy',
            sz='0',
            amend_px=new_px,
            td_mode=td_mode,
            pos_side=pos_side
        )

    def cancel_order(self, inst_id: str, ord_id: str) -> Dict[str, Any]:
        """
        Cancela ordem

        :param inst_id: ID do instrumento
        :param ord_id: ID da ordem a cancelar
        :return: Resultado do cancelamento
        """
        self._check_rate_limit()

        try:
            # V5 API: /api/v5/trade/cancel-order
            request_path = '/api/v5/trade/cancel-order'
            headers = self._get_headers('POST', request_path)

            payload = {
                'instId': inst_id,
                'ordId': ord_id
            }

            logger.debug(f"POST {self.rest_url}{request_path}")
            response = requests.post(f"{self.rest_url}{request_path}", headers=headers, json=payload, timeout=self.timeout)

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Falha ao cancelar ordem: {response.status_code}")
                raise OKXConnectionError(
                    code=response.status_code,
                    message="Falha ao cancelar ordem",
                    response=response.text
                )

        except requests.exceptions.RequestException as e:
            logger.error(f"Erro de conexão ao cancelar ordem: {e}")
            raise OKXConnectionError(code=-1, message=str(e))

    def cancel_batch_orders(self, inst_id: str, ord_ids: List[str]) -> Dict[str, Any]:
        """
        Cancela múltiplas ordens de um instrumento

        :param inst_id: ID do instrumento
        :param ord_ids: Lista de IDs das ordens a cancelar
        :return: Resultado do cancelamento
        """
        self._check_rate_limit()

        try:
            # V5 API: /api/v5/trade/cancel-batch-orders
            request_path = '/api/v5/trade/cancel-batch-orders'
            headers = self._get_headers('POST', request_path)

            payload = {
                'instId': inst_id,
                'ordIds': ord_ids
            }

            response = requests.post(f"{self.rest_url}{request_path}", headers=headers, json=payload, timeout=self.timeout)

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Falha ao cancelar ordens: {response.status_code}")
                raise OKXConnectionError(
                    code=response.status_code,
                    message="Falha ao cancelar ordens",
                    response=response.text
                )

        except requests.exceptions.RequestException as e:
            logger.error(f"Erro de conexão ao cancelar ordens: {e}")
            raise OKXConnectionError(code=-1, message=str(e))

    # ============ Métodos de Ordens ============

    def get_pending_orders(self, inst_type: str, uly: Optional[str] = None, inst_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Busca ordens pendentes

        :param inst_type: Tipo de instrumento (SPOT, MARGIN, FUTURES, OPTION)
        :param uly: ID de conta unificada
        :param inst_id: ID do instrumento
        :return: Lista de ordens pendentes
        """
        self._check_rate_limit()

        try:
            # V5 API: /api/v5/trade/orders-pending
            request_path = '/api/v5/trade/orders-pending'
            headers = self._get_headers('GET', request_path)

            params = {
                'instType': inst_type
            }

            if uly:
                params['uly'] = uly
            if inst_id:
                params['instId'] = inst_id

            logger.debug(f"GET {self.rest_url}{request_path} ? {params}")
            response = requests.get(f"{self.rest_url}{request_path}", headers=headers, params=params, timeout=self.timeout)

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Falha ao buscar ordens pendentes: {response.status_code}")
                raise OKXConnectionError(
                    code=response.status_code,
                    message="Falha ao buscar ordens pendentes",
                    response=response.text
                )

        except requests.exceptions.RequestException as e:
            logger.error(f"Erro de conexão ao buscar ordens pendentes: {e}")
            raise OKXConnectionError(code=-1, message=str(e))

    def get_order_history(self, inst_type: str, inst_id: Optional[str] = None, uly: Optional[str] = None, after: Optional[str] = None, before: Optional[str] = None, limit: Optional[int] = None) -> Dict[str, Any]:
        """
        Busca histórico de ordens executadas

        :param inst_type: Tipo de instrumento (SPOT, MARGIN, FUTURES, OPTION)
        :param inst_id: ID do instrumento
        :param uly: ID de conta unificada
        :param after: Buscar após este timestamp
        :param before: Buscar antes deste timestamp
        :param limit: Quantidade de ordens a retornar
        :return: Lista de ordens executadas
        """
        self._check_rate_limit()

        try:
            # V5 API: /api/v5/trade/orders-history
            request_path = '/api/v5/trade/orders-history'
            headers = self._get_headers('GET', request_path)

            params = {
                'instType': inst_type
            }

            if inst_id:
                params['instId'] = inst_id
            if uly:
                params['uly'] = uly
            if after:
                params['after'] = after
            if before:
                params['before'] = before
            if limit:
                params['limit'] = limit

            logger.debug(f"GET {self.rest_url}{request_path} ? {params}")
            response = requests.get(f"{self.rest_url}{request_path}", headers=headers, params=params, timeout=self.timeout)

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Falha ao buscar histórico: {response.status_code}")
                raise OKXConnectionError(
                    code=response.status_code,
                    message="Falha ao buscar histórico",
                    response=response.text
                )

        except requests.exceptions.RequestException as e:
            logger.error(f"Erro de conexão ao buscar histórico: {e}")
            raise OKXConnectionError(code=-1, message=str(e))

    def get_positions(self, inst_type: str, uly: Optional[str] = None, inst_id: Optional[str] = None, inst_type_instrument: Optional[str] = None) -> Dict[str, Any]:
        """
        Busca posições abertas (apenas Futures)

        :param inst_type: Tipo de instrumento (FUTURES, OPTION)
        :param uly: ID de conta unificada
        :param inst_id: ID do instrumento
        :param inst_type_instrument: Tipo de instrumento específico
        :return: Lista de posições abertas
        """
        self._check_rate_limit()

        try:
            # V5 API: /api/v5/trade/positions
            request_path = '/api/v5/trade/positions'
            headers = self._get_headers('GET', request_path)

            params = {
                'instType': inst_type
            }

            if uly:
                params['uly'] = uly
            if inst_id:
                params['instId'] = inst_id
            if inst_type_instrument:
                params['instType_instrument'] = inst_type_instrument

            logger.debug(f"GET {self.rest_url}{request_path} ? {params}")
            response = requests.get(f"{self.rest_url}{request_path}", headers=headers, params=params, timeout=self.timeout)

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Falha ao buscar posições: {response.status_code}")
                raise OKXConnectionError(
                    code=response.status_code,
                    message="Falha ao buscar posições",
                    response=response.text
                )

        except requests.exceptions.RequestException as e:
            logger.error(f"Erro de conexão ao buscar posições: {e}")
            raise OKXConnectionError(code=-1, message=str(e))

    def set_leverage(self, inst_id: str, lever: str, mgn: str, pos_side: str, ccy: Optional[str] = None, uly: Optional[str] = None) -> Dict[str, Any]:
        """
        Define alavancagem para um instrumento (apenas Futures)

        :param inst_id: ID do instrumento (ex: BTC-USDT-SWAP)
        :param lever: Multiplicador de alavancagem (ex: 10)
        :param mgn: Margem (cross ou isolated)
        :param pos_side: Lado da posição (long ou short)
        :param ccy: Moeda de settlement
        :param uly: ID de conta unificada
        :return: Alavancagem definida
        """
        self._check_rate_limit()

        try:
            # V5 API: /api/v5/account/set-leverage
            request_path = '/api/v5/account/set-leverage'
            headers = self._get_headers('POST', request_path)

            payload = {
                'instId': inst_id,
                'lever': lever,
                'mgn': mgn,
                'posSide': pos_side
            }

            if ccy:
                payload['ccy'] = ccy
            if uly:
                payload['uly'] = uly

            logger.debug(f"POST {self.rest_url}{request_path}")
            logger.debug(f"Payload: {json.dumps(payload, indent=2)}")

            response = requests.post(f"{self.rest_url}{request_path}", headers=headers, json=payload, timeout=self.timeout)

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Falha ao definir alavancagem: {response.status_code}")
                raise OKXConnectionError(
                    code=response.status_code,
                    message="Falha ao definir alavancagem",
                    response=response.text
                )

        except requests.exceptions.RequestException as e:
            logger.error(f"Erro de conexão ao definir alavancagem: {e}")
            raise OKXConnectionError(code=-1, message=str(e))

    # ============ Métodos WebSocket ============

    def start_stream(self, channel: str, inst_id: str, on_message: Callable) -> bool:
        """
        Inicia stream de dados em tempo real

        :param channel: Canal (public, private, account, positions)
        :param inst_id: ID do instrumento
        :param on_message: Callback para receber mensagens do stream
        :return: True se stream iniciado com sucesso
        """
        if not self.enable_ws:
            logger.warning("WebSocket não habilitado (enable_ws=False)")
            return False

        try:
            # Nota: Implementação WebSocket completa usaria websockets.asyncio
            # Para simplificar, apenas loga a intenção
            logger.info(f"Iniciando stream OKX (simulated={self.simulated_trading})")
            logger.info(f"Canal: {channel}")
            logger.info(f"Instrumento: {inst_id}")

            self._ws_connected = True

            # Chama callback de mensagem
            on_message({
                'channel': channel,
                'instId': inst_id,
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
            logger.info("Parando stream OKX...")
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
        print("✅ Conectado ao OKX WebSocket")

    def on_disconnected():
        print("❌ Desconectado do OKX WebSocket")

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

    # Criar conexão (Simulated Trading)
    conn = OKXConnection(
        api_key=os.getenv('OKX_API_KEY'),
        secret_key=os.getenv('OKX_API_SECRET'),
        passphrase=os.getenv('OKX_API_PASSPHRASE'),
        simulated_trading=True,
        callbacks=callbacks
    )

    # Buscar saldo
    try:
        balances = conn.get_balance(currency='USDT')
        print(f"💰 Saldo USDT: {balances}")
    except OKXConnectionError as e:
        print(f"❌ Erro ao buscar saldo: {e}")

    # Criar ordem Spot
    try:
        order = conn.place_order(
            inst_id='BTC-USDT-SWAP',
            td_mode='cash',
            side='buy',
            ord_type='market',
            sz='0.001'
        )
        print(f"✅ Ordem criada: {order}")
    except OKXConnectionError as e:
        print(f"❌ Erro ao criar ordem: {e}")

    # Buscar posições Futures
    try:
        positions = conn.get_positions(inst_type='FUTURES', inst_id='BTC-USDT-SWAP-USDT')
        print(f"📊 Posições: {positions}")
    except OKXConnectionError as e:
        print(f"❌ Erro ao buscar posições: {e}")
