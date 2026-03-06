const crypto = require('crypto');

/**
 * BybitConnection - Classe de conexão para API Bybit V5 (Spot e Derivatives/Futures)
 * Baseado na spec: specs/bybit-connection.yaml
 */
class BybitConnection {
    /**
     * Inicializa conexão Bybit V5
     * @param {Object} config - Configurações da conexão
     * @param {string} config.apiKey - Chave da API Bybit (obtida no painel de gerenciamento)
     * @param {string} config.secretKey - Chave secreta da API Bybit (obtida no painel de gerenciamento)
     * @param {string} config.category - Categoria (spot, linear, inverse, option)
     * @param {boolean} config.testnet - Usar ambiente de testnet
     * @param {integer} config.timeout - Timeout para requisições REST (em segundos)
     * @param {boolean} config.enableWs - Habilitar conexão WebSocket
     * @param {Object} config.callbacks - Callbacks (on_connected, on_message, etc.)
     */
    constructor(config) {
        this.apiKey = config.apiKey;
        this.secretKey = config.secretKey;
        this.category = config.category || 'spot';
        this.testnet = config.testnet || false;
        this.timeout = config.timeout || 10;
        this.enableWs = config.enableWs !== undefined ? config.enableWs : true;
        this.callbacks = config.callbacks || {};

        // URLs base
        this._setupUrls();

        // Estado da conexão
        this._wsConnected = false;
        this._wsTask = null;

        // Rate limiting
        this._lastRequestTime = 0;
        this._requestCount = 0;
        this._rateLimitWindow = 60; // 60 segundos
        this._rateLimit = 100; // 100 req/min

        console.log(`[BybitConnection] Inicializada (category=${this.category}, testnet=${this.testnet})`);
    }

    _setupUrls() {
        if (this.testnet) {
            this.restUrl = 'https://api-testnet.bybit.com';
            this.wsUrl = 'wss://stream-testnet.bybit.com/v5/public';
        } else {
            if (this.category === 'spot') {
                this.restUrl = 'https://api.bybit.com';
                this.wsUrl = 'wss://stream.bybit.com/v5/public';
            } else {
                this.restUrl = 'https://api.bybit.com';
                this.wsUrl = 'wss://stream.bybit.com/v5/public';
            }
        }
    }

    _generateSignature(queryString, timestamp, recvWindow = 5000) {
        // Gera assinatura HMAC SHA256 para requisições privadas (versão Bybit V5)
        const signatureString = `${timestamp}${this.apiKey}${recvWindow}${queryString}`;

        // Gera HMAC SHA256
        const signature = crypto.createHmac('sha256', this.secretKey);
        return signature.update(signatureString).digest('hex');
    }

    _getHeaders(timestamp, recvWindow = 5000) {
        // Retorna headers HTTP com API Key, Timestamp e Assinatura
        const signature = this._generateSignature('', timestamp, recvWindow);

        return {
            'X-BAPI-API-KEY': this.apiKey,
            'X-BAPI-TIMESTAMP': timestamp,
            'X-BAPI-SIGN': signature,
            'X-BAPI-RECV-WINDOW': recvWindow.toString(),
            'Content-Type': 'application/json'
        };
    }

    async _checkRateLimit() {
        // Verifica e respeita rate limit
        const currentTime = Date.now();

        // Reset contador se passou a janela
        if (currentTime - this._lastRequestTime > this._rateLimitWindow) {
            this._requestCount = 0;
            this._lastRequestTime = currentTime;
        }

        // Verifica se excedeu
        if (this._requestCount >= this._rateLimit) {
            const waitTime = this._rateLimitWindow - (currentTime - this._lastRequestTime);
            console.warn(`[BybitConnection] Rate limit excedido. Aguardando ${waitTime/1000.toFixed(2)} segundos...`);
            await new Promise(resolve => setTimeout(resolve, waitTime));
            this._requestCount = 0;
            this._lastRequestTime = currentTime;
        }

        this._requestCount++;
        this._lastRequestTime = currentTime;
    }

    // ============ Métodos de Autenticação e Conexão ============

    async connect() {
        /**
         * Estabelece conexão WebSocket (se habilitado)
         * @return {Promise<boolean>} true se conexão estabelecida, false caso contrário
         */
        if (!this.enableWs) {
            console.warn('[BybitConnection] WebSocket não habilitado (enableWs=false)');
            return false;
        }

        try {
            console.log('[BybitConnection] Conectando ao WebSocket Bybit...');
            console.log(`[BybitConnection] URL: ${this.wsUrl}`);

            // Nota: Implementação completa de WebSocket usaria 'ws' ou 'websocket'
            // Para simplificar, apenas loga a intenção
            this._wsConnected = true;

            // Chama callback de conexão
            if (this.callbacks.onConnected) {
                this.callbacks.onConnected();
            }

            return true;
        } catch (error) {
            console.error(`[BybitConnection] Erro ao conectar: ${error}`);
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
        /**
         * Fecha conexão WebSocket
         * @return {Promise<boolean>} true se fechado com sucesso
         */
        if (!this._wsConnected) {
            return false;
        }

        try {
            console.log('[BybitConnection] Fechando conexão WebSocket Bybit...');
            this._wsConnected = false;

            // Chama callback de desconexão
            if (this.callbacks.onDisconnected) {
                this.callbacks.onDisconnected();
            }

            return true;
        } catch (error) {
            console.error(`[BybitConnection] Erro ao desconectar: ${error}`);
            return false;
        }
    }

    // ============ Métodos de Leitura de Dados ============

    async getBalance(coin = null) {
        /**
         * Busca saldo da conta (Wallet Balance)
         * @param {string} coin - (Opcional) Filtra por moeda específica (ex: USDT)
         * @return {Promise<Array>} Lista de saldos por moeda
         */
        await this._checkRateLimit();

        try {
            const endpoint = `${this.restUrl}/v5/account/wallet-balance`;
            const params = {};
            if (coin) {
                params.coin = coin;
            }

            console.debug(`GET ${endpoint} ? ${JSON.stringify(params)}`);
            const fetch = (await import('node-fetch')).default;
            const response = await fetch(`${endpoint}?${new URLSearchParams(params)}`, {
                method: 'GET',
                headers: this._getHeaders(Date.now().toString()),
                timeout: this.timeout * 1000
            });

            const data = await response.json();

            if (data.retCode === 0) {
                if (coin) {
                    return data.result.filter(b => b.coin === coin);
                }
                return data.result;
            } else {
                console.error(`[BybitConnection] Falha ao buscar saldo: ${data.retCode} - ${data.retMsg}`);
                throw new Error(`[${data.retCode}] ${data.retMsg}`);
            }
        } catch (error) {
            console.error(`[BybitConnection] Erro ao buscar saldo: ${error}`);
            throw error;
        }
    }

    async getWalletBalance(coin) {
        /**
         * Busca saldo de uma moeda específica
         * @param {string} coin - Código da moeda (ex: USDT)
         * @return {Promise<Object>} Dados do saldo
         */
        const balances = await this.getBalance(coin);

        if (balances && balances.length > 0) {
            return balances[0];
        } else {
            return {};
        }
    }

    // ============ Métodos de Trading ============

    async placeOrder(category, symbol, side, orderType, qty, price = null, timeInForce = 'GTC', reduceOnly = false, takeProfit = null, stopLoss = null, tpSlippage = null, slSlippage = null, closeOnTrigger = false, options = {}) {
        /**
         * Cria ordem (Spot, Derivatives ou Futures)
         * @param {string} category - Categoria (spot, linear, inverse, option)
         * @param {string} symbol - Par de trading (ex: BTCUSDT)
         * @param {string} side - Direção da ordem (Buy, Sell)
         * @param {string} orderType - Tipo de ordem (Market, Limit, LimitMaker)
         * @param {string} qty - Quantidade (ex: 0.01)
         * @param {string} price - Preço (obrigatório para ordens tipo Limit)
         * @param {string} timeInForce - Tipo de validação (GTC, IOC, FOK, PostOnly)
         * @param {boolean} reduceOnly - Reduz apenas, não adiciona posição
         * @param {string} takeProfit - Preço de take profit
         * @param {string} stopLoss - Preço de stop loss
         * @param {string} tpSlippage - Slippage de take profit
         * @param {string} slSlippage - Slippage de stop loss
         * @param {boolean} closeOnTrigger - Fecha posição ao ser atingido
         * @param {Object} options - Opções adicionais (client_order_id, etc.)
         * @return {Promise<Object>} Detalhes da ordem criada
         */
        await this._checkRateLimit();

        try {
            const endpoint = `${this.restUrl}/v5/order/create`;
            const timestamp = Date.now().toString();

            const payload = {
                category,
                symbol,
                side,
                orderType,
                qty,
                timeInForce,
                reduceOnly,
                closeOnTrigger,
                ...options
            };

            if (price) {
                payload.price = price;
            }
            if (takeProfit) {
                payload.takeProfit = takeProfit;
            }
            if (stopLoss) {
                payload.stopLoss = stopLoss;
            }
            if (tpSlippage) {
                payload.tpSlippage = tpSlippage;
            }
            if (slSlippage) {
                payload.slSlippage = slSlippage;
            }

            console.debug(`POST ${endpoint}`);
            console.debug(`Payload: ${JSON.stringify(payload, null, 2)}`);

            const fetch = (await import('node-fetch')).default;
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: this._getHeaders(timestamp),
                body: JSON.stringify(payload),
                timeout: this.timeout * 1000
            });

            const data = await response.json();

            if (data.retCode === 0) {
                // Chama callback de ordem
                if (this.callbacks.onOrderUpdate) {
                    this.callbacks.onOrderUpdate({
                        orderId: data.result.orderId,
                        symbol,
                        status: data.result.orderStatus,
                        side,
                        orderType,
                        category
                    });
                }

                return data;
            } else {
                console.error(`[BybitConnection] Falha ao criar ordem: ${data.retCode} - ${data.retMsg}`);
                throw new Error(`[${data.retCode}] ${data.retMsg}`);
            }
        } catch (error) {
            console.error(`[BybitConnection] Erro ao criar ordem: ${error}`);
            throw error;
        }
    }

    async amendOrder(category, symbol, orderId, orderType = null, qty = null, price = null, takeProfit = null, stopLoss = null, tpSlippage = null, slSlippage = null, trailingStop = null, options = {}) {
        /**
         * Modifica ordem existente
         * @param {string} category - Categoria (spot, linear, inverse, option)
         * @param {string} symbol - Par de trading
         * @param {string} orderId - ID da ordem a modificar
         * @param {string} orderType - Tipo de ordem (Limit, LimitMaker)
         * @param {string} qty - Nova quantidade
         * @param {string} price - Novo preço
         * @param {string} takeProfit - Novo take profit
         * @param {string} stopLoss - Novo stop loss
         * @param {string} tpSlippage - Slippage de take profit
         * @param {string} slSlippage - Slippage de stop loss
         * @param {string} trailingStop - Trailing stop
         * @param {Object} options - Opções adicionais
         * @return {Promise<Object>} Resultado da modificação
         */
        await this._checkRateLimit();

        try {
            const endpoint = `${this.restUrl}/v5/order/amend`;
            const timestamp = Date.now().toString();

            const payload = {
                category,
                symbol,
                orderId,
                ...options
            };

            if (orderType) {
                payload.orderType = orderType;
            }
            if (qty) {
                payload.qty = qty;
            }
            if (price) {
                payload.price = price;
            }
            if (takeProfit) {
                payload.takeProfit = takeProfit;
            }
            if (stopLoss) {
                payload.stopLoss = stopLoss;
            }
            if (tpSlippage) {
                payload.tpSlippage = tpSlippage;
            }
            if (slSlippage) {
                payload.slSlippage = slSlippage;
            }
            if (trailingStop) {
                payload.trailingStop = trailingStop;
            }

            console.debug(`POST ${endpoint}`);
            console.debug(`Payload: ${JSON.stringify(payload, null, 2)}`);

            const fetch = (await import('node-fetch')).default;
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: this._getHeaders(timestamp),
                body: JSON.stringify(payload),
                timeout: this.timeout * 1000
            });

            const data = await response.json();

            if (data.retCode === 0) {
                return data;
            } else {
                console.error(`[BybitConnection] Falha ao modificar ordem: ${data.retCode} - ${data.retMsg}`);
                throw new Error(`[${data.retCode}] ${data.retMsg}`);
            }
        } catch (error) {
            console.error(`[BybitConnection] Erro ao modificar ordem: ${error}`);
            throw error;
        }
    }

    async cancelOrder(category, symbol, orderId) {
        /**
         * Cancela ordem
         * @param {string} category - Categoria (spot, linear, inverse, option)
         * @param {string} symbol - Par de trading (ex: BTCUSDT)
         * @param {string} orderId - ID da ordem a cancelar
         * @return {Promise<Object>} Resultado do cancelamento
         */
        await this._checkRateLimit();

        try {
            const endpoint = `${this.restUrl}/v5/order/cancel`;
            const timestamp = Date.now().toString();

            const payload = {
                category,
                symbol,
                orderId
            };

            console.debug(`POST ${endpoint}`);
            console.debug(`Payload: ${JSON.stringify(payload, null, 2)}`);

            const fetch = (await import('node-fetch')).default;
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: this._getHeaders(timestamp),
                body: JSON.stringify(payload),
                timeout: this.timeout * 1000
            });

            const data = await response.json();

            if (data.retCode === 0) {
                return data;
            } else {
                console.error(`[BybitConnection] Falha ao cancelar ordem: ${data.retCode} - ${data.retMsg}`);
                throw new Error(`[${data.retCode}] ${data.retMsg}`);
            }
        } catch (error) {
            console.error(`[BybitConnection] Erro ao cancelar ordem: ${error}`);
            throw error;
        }
    }

    async cancelAllOrders(category, symbol, settleCoin = null, options = {}) {
        /**
         * Cancela todas as ordens de um símbolo
         * @param {string} category - Categoria (spot, linear, inverse, option)
         * @param {string} symbol - Par de trading
         * @param {string} settleCoin - Moeda de settlement (apenas Futures)
         * @param {Object} options - Opções adicionais (client_order_id, stop_order_type, etc.)
         * @return {Promise<Array>} Lista de ordens canceladas
         */
        await this._checkRateLimit();

        try {
            const endpoint = `${this.restUrl}/v5/order/cancel-all`;
            const timestamp = Date.now().toString();

            const payload = {
                category,
                symbol,
                settleCoin,
                ...options
            };

            console.debug(`POST ${endpoint}`);
            console.debug(`Payload: ${JSON.stringify(payload, null, 2)}`);

            const fetch = (await import('node-fetch')).default;
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: this._getHeaders(timestamp),
                body: JSON.stringify(payload),
                timeout: this.timeout * 1000
            });

            const data = await response.json();

            if (data.retCode === 0) {
                return data;
            } else {
                console.error(`[BybitConnection] Falha ao cancelar ordens: ${data.retCode} - ${data.retMsg}`);
                throw new Error(`[${data.retCode}] ${data.retMsg}`);
            }
        } catch (error) {
            console.error(`[BybitConnection] Erro ao cancelar ordens: ${error}`);
            throw error;
        }
    }

    // ============ Métodos de Ordens ============

    async getOpenOrders(category, symbol = null, settleCoin = null, orderId = null, orderFilter = {}, limit = null, cursor = null) {
        /**
         * Busca ordens abertas
         * @param {string} category - Categoria (spot, linear, inverse, option)
         * @param {string} symbol - (Opcional) Filtra por símbolo específico
         * @param {string} settleCoin - (Opcional) Moeda de settlement
         * @param {string} orderId - (Opcional) Filtra por ID de ordem
         * @param {Object} orderFilter - Filtro de ordem (order_status, stop_order_type, etc.)
         * @param {integer} limit - Quantidade de ordens a retornar
         * @param {string} cursor - Cursor para paginação
         * @return {Promise<Object>} Lista de ordens abertas
         */
        await this._checkRateLimit();

        try {
            const endpoint = `${this.restUrl}/v5/order/realtime`;
            const params = {
                category
            };

            if (symbol) {
                params.symbol = symbol;
            }
            if (settleCoin) {
                params.settleCoin = settleCoin;
            }
            if (orderId) {
                params.orderId = orderId;
            }
            if (orderFilter && Object.keys(orderFilter).length > 0) {
                params.filter = JSON.stringify(orderFilter);
            }
            if (limit) {
                params.limit = limit;
            }
            if (cursor) {
                params.cursor = cursor;
            }

            console.debug(`GET ${endpoint} ? ${JSON.stringify(params)}`);
            const fetch = (await import('node-fetch')).default;
            const response = await fetch(`${endpoint}?${new URLSearchParams(params)}`, {
                method: 'GET',
                headers: this._getHeaders(Date.now().toString()),
                timeout: this.timeout * 1000
            });

            const data = await response.json();

            if (data.retCode === 0) {
                return data;
            } else {
                console.error(`[BybitConnection] Falha ao buscar ordens abertas: ${data.retCode} - ${data.retMsg}`);
                throw new Error(`[${data.retCode}] ${data.retMsg}`);
            }
        } catch (error) {
            console.error(`[BybitConnection] Erro ao buscar ordens abertas: ${error}`);
            throw error;
        }
    }

    async getOrderHistory(category, symbol, options = {}) {
        /**
         * Busca histórico de trades executados
         * @param {string} category - Categoria (spot, linear, inverse, option)
         * @param {string} symbol - Par de trading
         * @param {Object} options - Opções adicionais (orderId, orderCategory, orderType, etc.)
         * @return {Promise<Object>} Lista de trades executados
         */
        await this._checkRateLimit();

        try {
            const endpoint = `${this.restUrl}/v5/execution/list`;
            const params = {
                category,
                symbol
            };

            if (options) {
                params.orderId = options.orderId;
                params.orderCategory = options.orderCategory;
                params.orderType = options.orderType;
                options.createTime && (params.createTime = options.createTime);
                options.startTime && (params.startTime = options.startTime);
                options.endTime && (params.endTime = options.endTime);
                options.limit && (params.limit = options.limit);
                options.cursor && (params.cursor = options.cursor);
            }

            console.debug(`GET ${endpoint} ? ${JSON.stringify(params)}`);
            const fetch = (await import('node-fetch')).default;
            const response = await fetch(`${endpoint}?${new URLSearchParams(params)}`, {
                method: 'GET',
                headers: this._getHeaders(Date.now().toString()),
                timeout: this.timeout * 1000
            });

            const data = await response.json();

            if (data.retCode === 0) {
                return data;
            } else {
                console.error(`[BybitConnection] Falha ao buscar histórico: ${data.retCode} - ${data.retMsg}`);
                throw new Error(`[${data.retCode}] ${data.retMsg}`);
            }
        } catch (error) {
            console.error(`[BybitConnection] Erro ao buscar histórico: ${error}`);
            throw error;
        }
    }

    // ============ Métodos de Posições (Futures/Derivatives) ============

    async getPosition(category, symbol) {
        /**
         * Busca posição aberta em Futures/Derivatives
         * @param {string} category - Categoria (linear, inverse, option)
         * @param {string} symbol - Par de trading
         * @return {Promise<Object>} Detalhes da posição
         */
        await this._checkRateLimit();

        try {
            const endpoint = `${this.restUrl}/v5/position/list`;
            const params = {
                category,
                symbol
            };

            console.debug(`GET ${endpoint} ? ${JSON.stringify(params)}`);
            const fetch = (await import('node-fetch')).default;
            const response = await fetch(`${endpoint}?${new URLSearchParams(params)}`, {
                method: 'GET',
                headers: this._getHeaders(Date.now().toString()),
                timeout: this.timeout * 1000
            });

            const data = await response.json();

            if (data.retCode === 0) {
                if (data.result && data.result.length > 0) {
                    const position = data.result.find(p => p.symbol === symbol);

                    if (position) {
                        // Chama callback de posição
                        if (this.callbacks.onPositionUpdate) {
                            this.callbacks.onPositionUpdate({
                                symbol,
                                side: position.side,
                                size: position.size,
                                unrealizedPnl: position.unrealizedPnl,
                                avgPrice: position.avgPrice,
                                markPrice: position.markPrice,
                                leverage: position.leverage
                            });
                        }

                        return position;
                    }

                    return null;
                } else {
                    return null;
                }
            } else {
                console.error(`[BybitConnection] Falha ao buscar posição: ${data.retCode} - ${data.retMsg}`);
                throw new Error(`[${data.retCode}] ${data.retMsg}`);
            }
        } catch (error) {
            console.error(`[BybitConnection] Erro ao buscar posição: ${error}`);
            throw error;
        }
    }

    async getAllPositions(category) {
        /**
         * Busca todas as posições abertas em Futures/Derivatives
         * @param {string} category - Categoria (linear, inverse, option)
         * @return {Promise<Array>} Lista de todas as posições abertas
         */
        await this._checkRateLimit();

        try {
            const endpoint = `${this.restUrl}/v5/position/list`;
            const params = {
                category
            };

            console.debug(`GET ${endpoint} ? ${JSON.stringify(params)}`);
            const fetch = (await import('node-fetch')).default;
            const response = await fetch(`${endpoint}?${new URLSearchParams(params)}`, {
                method: 'GET',
                headers: this._getHeaders(Date.now().toString()),
                timeout: this.timeout * 1000
            });

            const data = await response.json();

            if (data.retCode === 0) {
                return data.result || [];
            } else {
                console.error(`[BybitConnection] Falha ao buscar posições: ${data.retCode} - ${data.retMsg}`);
                throw new Error(`[${data.retCode}] ${data.retMsg}`);
            }
        } catch (error) {
            console.error(`[BybitConnection] Erro ao buscar posições: ${error}`);
            throw error;
        }
    }

    async closePosition(category, symbol, side, qty, price = null) {
        /**
         * Fecha posição aberta
         * @param {string} category - Categoria (linear, inverse, option)
         * @param {string} symbol - Par de trading
         * @param {string} side - Direção (Buy ou Sell)
         * @param {string} qty - Quantidade
         * @return {Promise<Object>} Resultado do fechamento
         */
        return await this.placeOrder(category, symbol, side, 'Market', qty, price);
    }

    // ============ Métodos de Leverage (Futures) ============

    async setLeverage(category, symbol, buyLeverage, sellLeverage) {
        /**
         * Define alavancagem para um símbolo
         * @param {string} category - Categoria (linear, inverse, option)
         * @param {string} symbol - Par de trading (ex: BTCUSDTUSDT)
         * @param {string} buyLeverage - Alavancagem para posições longas
         * @param {string} sellLeverage - Alavancagem para posições curtas
         * @return {Promise<Object>} Alavancagem definida
         */
        await this._checkRateLimit();

        try {
            const endpoint = `${this.restUrl}/v5/position/set-leverage`;
            const timestamp = Date.now().toString();

            const payload = {
                category,
                symbol,
                buyLeverage,
                sellLeverage
            };

            console.debug(`POST ${endpoint}`);
            console.debug(`Payload: ${JSON.stringify(payload, null, 2)}`);

            const fetch = (await import('node-fetch')).default;
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: this._getHeaders(timestamp),
                body: JSON.stringify(payload),
                timeout: this.timeout * 1000
            });

            const data = await response.json();

            if (data.retCode === 0) {
                return data;
            } else {
                console.error(`[BybitConnection] Falha ao definir alavancagem: ${data.retCode} - ${data.retMsg}`);
                throw new Error(`[${data.retCode}] ${data.retMsg}`);
            }
        } catch (error) {
            console.error(`[BybitConnection] Erro ao definir alavancagem: ${error}`);
            throw error;
        }
    }

    // ============ Métodos WebSocket ============

    async startStream(category, streams, onMessage) {
        /**
         * Inicia stream de dados em tempo real
         * @param {string} category - Categoria (spot, linear, inverse, option)
         * @param {Array<string>} streams - Lista de streams (trade, depth, kline, ticker)
         * @param {Function} onMessage - Callback para receber mensagens
         * @return {Promise<boolean>} true se iniciado com sucesso
         */
        if (!this.enableWs) {
            console.warn('[BybitConnection] WebSocket não habilitado (enableWs=false)');
            return false;
        }

        try {
            console.log(`[BybitConnection] Iniciando stream de dados (${category})...`);
            console.log(`[BybitConnection] Streams: ${streams}`);

            // Nota: Implementação completa de WebSocket usaria 'ws' ou 'websocket'
            // Para simplificar, apenas loga a intenção
            this._wsConnected = true;

            // Simula mensagem inicial
            await onMessage({
                stream: streams.join('/'),
                category,
                data: 'mock_message'
            });

            return true;
        } catch (error) {
            console.error(`[BybitConnection] Erro ao iniciar stream: ${error}`);
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
        /**
         * Para stream de dados
         * @return {Promise<boolean>} true se parado com sucesso
         */
        if (!this._wsConnected) {
            return false;
        }

        try {
            console.log('[BybitConnection] Parando stream de dados...');
            this._wsConnected = false;

            if (this.callbacks.onDisconnected) {
                this.callbacks.onDisconnected();
            }

            return true;
        } catch (error) {
            console.error(`[BybitConnection] Erro ao parar stream: ${error}`);
            return false;
        }
    }
}

module.exports = BybitConnection;
