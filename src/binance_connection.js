const crypto = require('crypto');

/**
 * BinanceConnection - Classe de conexão para API Binance (Spot e Futures)
 * Baseado na spec: specs/binance-connection.yaml
 */
class BinanceConnection {
    /**
     * Inicializa conexão Binance
     * @param {Object} config - Configurações da conexão
     * @param {string} config.apiKey - Chave da API Binance
     * @param {string} config.secretKey - Chave secreta da API Binance
     * @param {string} config.type - Tipo (spot ou futures)
     * @param {boolean} config.testnet - Usar testnet
     * @param {integer} config.timeout - Timeout (segundos)
     * @param {boolean} config.enableWs - Habilitar WebSocket
     * @param {Object} config.callbacks - Callbacks (on_connected, on_disconnected, etc.)
     */
    constructor(config) {
        this.apiKey = config.apiKey;
        this.secretKey = config.secretKey;
        this.type = config.type || 'spot';
        this.testnet = config.testnet || false;
        this.timeout = config.timeout || 10;
        this.enableWs = config.enableWs !== undefined ? config.enableWs : true;
        this.callbacks = config.callbacks || {};

        // URLs base
        this._setupUrls();

        // Estado da conexão
        this.wsConnected = false;
        this.wsTask = null;

        // Rate limiting
        this.lastRequestTime = 0;
        this.requestCount = 0;
        this.rateLimitWindow = 60; // 60 segundos
        this.rateLimit = 1200; // 1200 requests/min

        console.log(`[BinanceConnection] Inicializada (type=${this.type}, testnet=${this.testnet})`);
    }

    _setupUrls() {
        if (this.testnet) {
            this.restUrlSpot = 'https://testnet.binance.vision/api';
            this.restUrlFutures = 'https://testnet.binancefuture.com/fapi';
            this.wsUrlSpot = 'wss://testnet.binance.vision/ws';
            this.wsUrlFutures = 'wss://stream.binancefuture.com/ws';
        } else {
            this.restUrlSpot = 'https://api.binance.com/api';
            this.restUrlFutures = 'https://fapi.binance.com/fapi';
            this.wsUrlSpot = 'wss://stream.binance.com:9443/ws';
            this.wsUrlFutures = 'wss://fstream.binance.com/ws';
        }
    }

    _getHeaders() {
        return {
            'X-MBX-APIKEY': this.apiKey,
            'Content-Type': 'application/json'
        };
    }

    _checkRateLimit() {
        const currentTime = Date.now() / 1000;

        // Reset contador se passou a janela
        if (currentTime - this.lastRequestTime > this.rateLimitWindow) {
            this.requestCount = 0;
            this.lastRequestTime = currentTime;
        }

        // Verifica se excedeu
        if (this.requestCount >= this.rateLimit) {
            const waitTime = this.rateLimitWindow - (currentTime - this.lastRequestTime);
            console.warn(`[BinanceConnection] Rate limit excedido. Aguardando ${waitTime.toFixed(2)} segundos...`);
            return new Promise(resolve => setTimeout(resolve, waitTime * 1000));
        }

        this.requestCount += 1;
        this.lastRequestTime = currentTime;
    }

    async _request(method, endpoint, params = {}, body = null) {
        await this._checkRateLimit();

        const url = endpoint.startsWith('http') ? endpoint : `${this.type === 'futures' ? this.restUrlFutures : this.restUrlSpot}${endpoint}`;

        const headers = this._getHeaders();

        console.debug(`[${method.toUpperCase()}] ${url}`);
        if (params && Object.keys(params).length > 0) {
            console.debug(`Params: ${JSON.stringify(params)}`);
        }
        if (body) {
            console.debug(`Body: ${JSON.stringify(body)}`);
        }

        const fetch = (await import('node-fetch')).default;
        const response = await fetch(url, {
            method,
            headers,
            params,
            body: body ? JSON.stringify(body) : null,
            timeout: this.timeout * 1000
        });

        const data = await response.json();

        if (response.status !== 200) {
            throw new Error(`[${response.status}] ${JSON.stringify(data)}`);
        }

        return data;
    }

    // ============ Métodos de Autenticação e Conexão ============

    async connect() {
        if (!this.enableWs) {
            console.warn('[BinanceConnection] WebSocket não habilitado');
            return false;
        }

        try {
            console.log(`[BinanceConnection] Conectando ao WebSocket...`);
            const wsUrl = this.type === 'futures' ? this.wsUrlFutures : this.wsUrlSpot;

            // Nota: Implementação WebSocket completa usaria 'ws' ou 'websocket'
            // Para simplificar, apenas simula a conexão
            this.wsConnected = true;

            if (this.callbacks.onConnected) {
                this.callbacks.onConnected();
            }

            return true;
        } catch (error) {
            console.error(`[BinanceConnection] Erro ao conectar: ${error}`);

            if (this.callbacks.onError) {
                this.callbacks.onError({
                    code: -1,
                    message: error.toString()
                });
            }

            return false;
        }
    }

    async disconnect() {
        if (!this.wsConnected) {
            return false;
        }

        try {
            console.log('[BinanceConnection] Fechando conexão WebSocket...');
            this.wsConnected = false;

            if (this.callbacks.onDisconnected) {
                this.callbacks.onDisconnected();
            }

            return true;
        } catch (error) {
            console.error(`[BinanceConnection] Erro ao desconectar: ${error}`);
            return false;
        }
    }

    // ============ Métodos de Leitura de Dados ============

    async getBalance(asset = null) {
        try {
            const endpoint = this.type === 'futures' ? '/v2/balance' : '/v3/account';
            const params = asset ? { asset } : {};

            const data = await this._request('GET', endpoint, params);

            if (this.type === 'futures') {
                return data.map(b => ({
                    asset: b.asset,
                    free: b.availableBalance,
                    locked: b.crossWalletBalance
                }));
            } else {
                return data.balances || data.map(b => ({
                    asset: b.asset,
                    free: b.free,
                    locked: b.locked
                }));
            }
        } catch (error) {
            console.error(`[BinanceConnection] Erro ao buscar saldo: ${error}`);
            throw error;
        }
    }

    async getOrderBook(symbol, limit = 100) {
        try {
            const endpoint = this.type === 'futures' ? '/v1/depth' : '/v3/depth';
            const params = {
                symbol,
                limit
            };

            return await this._request('GET', endpoint, params);
        } catch (error) {
            console.error(`[BinanceConnection] Erro ao buscar order book: ${error}`);
            throw error;
        }
    }

    // ============ Métodos de Trading ============

    async placeOrder(symbol, side, type, quantity, price = null, stopPrice = null, timeInForce = 'GTC') {
        try {
            const endpoint = this.type === 'futures' ? '/v1/order' : '/v3/order';
            const body = {
                symbol,
                side,
                type,
                quantity
            };

            if (price) {
                body.price = price;
            }
            if (stopPrice) {
                body.stopPrice = stopPrice;
            }
            if (timeInForce) {
                body.timeInForce = timeInForce;
            }

            const data = await this._request('POST', endpoint, {}, body);

            if (this.callbacks.onOrderUpdate) {
                this.callbacks.onOrderUpdate({
                    orderId: data.orderId,
                    symbol,
                    status: data.status,
                    side,
                    type
                });
            }

            return data;
        } catch (error) {
            console.error(`[BinanceConnection] Erro ao criar ordem: ${error}`);
            throw error;
        }
    }

    async cancelOrder(symbol, orderId) {
        try {
            const endpoint = this.type === 'futures' ? '/v1/order' : '/v3/order';
            const params = {
                symbol,
                orderId
            };

            return await this._request('DELETE', endpoint, params);
        } catch (error) {
            console.error(`[BinanceConnection] Erro ao cancelar ordem: ${error}`);
            throw error;
        }
    }

    async cancelAllOrders(symbol) {
        try {
            const endpoint = this.type === 'futures' ? '/v1/openOrders' : '/v3/openOrders';
            const params = { symbol };

            return await this._request('DELETE', endpoint, params);
        } catch (error) {
            console.error(`[BinanceConnection] Erro ao cancelar ordens: ${error}`);
            throw error;
        }
    }

    // ============ Métodos de Ordens ============

    async getOpenOrders(symbol = null) {
        try {
            const endpoint = this.type === 'futures' ? '/v1/openOrders' : '/v3/openOrders';
            const params = symbol ? { symbol } : {};

            return await this._request('GET', endpoint, params);
        } catch (error) {
            console.error(`[BinanceConnection] Erro ao buscar ordens abertas: ${error}`);
            throw error;
        }
    }

    async getOrderHistory(symbol, limit = 500, fromId = null) {
        try {
            const endpoint = this.type === 'futures' ? '/v1/userTrades' : '/v3/myTrades';
            const params = {
                symbol,
                limit: limit.toString()
            };

            if (fromId) {
                params.fromId = fromId.toString();
            }

            return await this._request('GET', endpoint, params);
        } catch (error) {
            console.error(`[BinanceConnection] Erro ao buscar histórico: ${error}`);
            throw error;
        }
    }

    // ============ Métodos de Posições (apenas Futures) ============

    async getPosition(symbol) {
        try {
            const endpoint = '/v2/positionRisk';
            const params = { symbol };

            const data = await this._request('GET', endpoint, params);

            if (data && data.length > 0) {
                return data[0];
            }

            return null;
        } catch (error) {
            console.error(`[BinanceConnection] Erro ao buscar posição: ${error}`);
            throw error;
        }
    }

    async getAllPositions() {
        try {
            const endpoint = '/v2/positionRisk';

            return await this._request('GET', endpoint);
        } catch (error) {
            console.error(`[BinanceConnection] Erro ao buscar posições: ${error}`);
            throw error;
        }
    }

    // ============ Métodos WebSocket ============

    async startStream(streams, onMessage) {
        if (!this.enableWs) {
            console.warn('[BinanceConnection] WebSocket não habilitado');
            return false;
        }

        try {
            console.log(`[BinanceConnection] Iniciando stream de dados...`);
            console.log(`Streams: ${streams}`);

            // Nota: Implementação completa usaria 'ws' ou 'websocket'
            // Para simplificar, apenas simula a conexão
            this.wsConnected = true;

            // Simula mensagem inicial
            const mockMessage = {
                stream: 'mock_stream',
                data: 'mock_data'
            };
            await onMessage(mockMessage);

            return true;
        } catch (error) {
            console.error(`[BinanceConnection] Erro ao iniciar stream: ${error}`);

            if (this.callbacks.onError) {
                this.callbacks.onError({
                    code: -2,
                    message: error.toString()
                });
            }

            return false;
        }
    }

    async stopStream() {
        if (!this.wsConnected) {
            return false;
        }

        try {
            console.log('[BinanceConnection] Parando stream de dados...');
            this.wsConnected = false;

            if (this.callbacks.onDisconnected) {
                this.callbacks.onDisconnected();
            }

            return true;
        } catch (error) {
            console.error(`[BinanceConnection] Erro ao parar stream: ${error}`);
            return false;
        }
    }
}

module.exports = BinanceConnection;
