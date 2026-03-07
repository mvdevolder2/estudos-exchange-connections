# estudos-exchange-connections

## 📖 Objetivo

Estudo e documentação de conexões com exchanges de cripto para o Squad Crypto.

## 🎯 Escopo

**Suporte Multi-Tenant:**
- Binance (Spot e Futuros)
- Bybit (Spot e Futuros)
- OKX (Spot e Futuros)

**Funcionalidades:**
- Conexão com contas API
- Operações em Spot (cruzado/derivativos)
- Operações em Futuros (perpétuo/termo)
- Gerenciamento multi-tenant (múltiplos usuários/contas)

## 📚 Testnet vs Mainnet

### Binance ✅

| Tipo | Testnet Spot | Testnet Futures | Status | Como Obter |
|------|--------------|-----------------|--------|--------------|
| **Spot** | ✅ Sim | - | Ativo | 1. Acessar: https://testnet.binance.vision/<br>2. Registrar/Login<br>3. Gerar API Keys no painel |
| **Futures** | - | ✅ Sim | Ativo | 1. Acessar: https://testnet.binancefuture.com/<br>2. Registrar/Login<br>3. Gerar API Keys no painel |

**Detalhes:**
- **URLs:**
  - REST Spot: `https://testnet.binance.vision/api`
  - REST Futures: `https://testnet.binancefuture.com/fapi`
  - WS Spot: `wss://testnet.binance.vision/ws`
  - WS Futures: `wss://stream.binancefuture.com/ws`
- **Ambiente:** Isolado (não conectado com mainnet)
- **Saldos:** Podem ser resetados periodicamente
- **Limitações:** Restrições geográficas (ex: EUA)
- **Rate Limits:** Mesmos da mainnet

### Bybit ✅

| Tipo | Testnet Spot | Testnet Futures | Status | Como Obter |
|------|--------------|-----------------|--------|--------------|
| **Spot** | ✅ Sim | - | Ativo | 1. Acessar: https://testnet.bybit.com/<br>2. Criar conta<br>3. Chaves API geradas no painel API da conta testnet |
| **Futures** | - | ✅ Sim | Ativo | Mesmo processo acima |

**Detalhes:**
- **URLs:**
  - REST Spot: `https://api-testnet.bybit.com`
  - REST Futures: `https://api-testnet.bybit.com` (unificado)
  - WS Spot: `wss://stream-testnet.bybit.com/v5/public/spot`
  - WS Futures: `wss://stream-testnet.bybit.com/v5/public/linear`
- **Ambiente:** Robusto, simula liquidez de mercado
- **Limitações:**
  - Motor de execução pode ser mais lento
  - Bloqueio de IPs (China, Singapura)

### OKX ⚠️

| Tipo | Testnet Spot | Testnet Futures | Status | Como Obter |
|------|--------------|-----------------|--------|--------------|
| **Spot** | ❌ Não | - | - | Usa ambiente de produção |
| **Futures** | ❌ Não | - | - | Usa ambiente de produção |

**Alternativa - Demo Trading:**
- **Modo:** Não há site separado
- **Como usar:** 
  1. No site principal, mude para "Demo Trading"
  2. Gere chaves API na aba Demo Trading
- **Obrigatório:** Enviar header `x-simulated-trading: 1` em todas as requisições

**Detalhes:**
- **URLs:**
  - REST: `https://www.okx.com` (produção)
  - WS: `wss://wspap.okx.com:443/ws/v5/public?brokerId=9999`
- **Limitações:**
  - Chaves expiram após 14 dias (se não vinculadas a IP)
  - Usa ambiente de produção (não isolado)
  - Sem garantia de isolamento

## 📊 Comparativo de Testnet

| Exchange | Testnet Spot | Testnet Futures | Teste Alternativo | Recomendação |
|----------|--------------|-----------------|------------------|--------------|
| Binance | ✅ Oficial | ✅ Oficial | Portal isolado | **Melhor opção** (completo e isolado) |
| Bybit | ✅ Oficial | ✅ Oficial | Portal robusto | **Segunda opção** (robusto) |
| OKX | ❌ Não | ❌ Não | Demo Trading | **Use apenas para testes rápidos** (não isolado) |

## 🔑 Autenticação e Permissões

### Chaves API Necessárias

| Exchange | Spot | Futures | Notas |
|----------|------|---------|--------|
| Binance | API Key + Secret | API Key + Secret | Passphrase opcional para alguns endpoints |
| Bybit | API Key + Secret | API Key + Secret | Diferentes para Spot e Derivatives |
| OKX | API Key + Secret | API Key + Secret + Passphrase | Passphrase OBRIGATÓRIA |

### Permissões por Tipo de Operação

| Operação | Permissões Necessárias | Binance | Bybit | OKX |
|-----------|-------------------------|---------|--------|-----|
| Leitura de Saldo | `Read` | ✅ | ✅ | ✅ |
| Trading Spot | `Read` + `Trade` | ✅ | ✅ | ✅ |
| Trading Futures | `Futures` + `Futures Trading` | ✅ | ✅ | ✅ |
| Streaming de Dados | `Read` + `Trading Stream` | ✅ | ✅ | ✅ |

## 📖 Documentação por Exchange

### Binance

**API REST Oficial:**
- Spot: https://binance-docs.github.io/apidocs/
- Futures: https://binance-docs.github.io/apidocs/futures/
- Testnet Spot: https://testnet.binance.vision/en/
- Testnet Futures: https://testnet.binancefuture.com/en/

**WebSocket:**
- Spot: https://binance-docs.github.io/apidocs/websocket_api/
- Futures: https://binance-docs.github.io/apidocs/fapi/websocket/

**SDK Python Oficial:**
- Mainnet: https://github.com/binance/binance-connector-python
- Testnet: Mesmo SDK (apenas altera URL base)

**Rate Limits:**
- Mainnet: 1200 requests/min
- Testnet: Mesmos da mainnet

### Bybit

**API REST Oficial (V5):**
- Mainnet: https://bybit-exchange.github.io/docs/
- Testnet: https://bybit-exchange.github.io/docs/en/testnet/

**WebSocket:**
- Mainnet: https://bybit-exchange.github.io/docs/websocket/
- Testnet: https://bybit-exchange.github.io/docs/websocket_testnet/

**SDK Python Oficial:**
- Mainnet: https://github.com/bybit-exchange/bybit-official-api-python
- Testnet: Mesmo SDK (apenas altera URL base)

**Rate Limits:**
- Mainnet: 100 requests/min
- Testnet: Mesmos da mainnet

### OKX

**API REST Oficial (V5):**
- Mainnet: https://www.okx.com/docs-v5/
- Demo Trading: https://www.okx.com/docs-v5/#trading-account-balance-demo-trading

**WebSocket:**
- Mainnet: https://www.okx.com/docs-v5/#websocket-api
- Simulado: Header `x-simulated-trading: 1`

**SDK Python Oficial:**
- Mainnet: https://github.com/okex/V5-Python-official-api
- Demo: Mesmo SDK (apenas com header de simulação)

**Rate Limits:**
- Mainnet: 20 requests/min
- Demo: Mesmos da mainnet

## 📚 Guias de Conexão

### Binance

**Para Testnet:**
```bash
# 1. Acesse https://testnet.binance.vision/
# 2. Faça login com e-mail ou conta Google
# 3. Vá em "API Management"
# 4. Crie API Keys (API Key + Secret Key)
# 5. Defina permissões: "Reading" + "Spot & Margin Trading" + "Futures Trading"
```

**Para Mainnet:**
```bash
# 1. Acesse https://www.binance.com/en/my/settings/api-management
# 2. Crie API Keys
# 3. Defina permissões conforme necessidade
```

### Bybit

**Para Testnet:**
```bash
# 1. Acesse https://testnet.bybit.com/
# 2. Faça login (e-mail ou Google)
# 3. Crie conta
# 4. Vá em "API Keys"
# 5. Crie API Key (API Key + Secret Key)
```

**Para Mainnet:**
```bash
# 1. Acesse https://www.bybit.com/user/api-management
# 2. Crie API Key (API Key + Secret Key)
```

### OKX

**Para Demo Trading:**
```bash
# 1. Acesse https://www.okx.com/account/my-api
# 2. Clique em "Demo Trading"
# 3. Mude para "Demo Trading"
# 4. Gere API Key (API Key + Secret Key + Passphrase)
# 5. IMPORTANTE: Enviar header `x-simulated-trading: 1` em todas as requisições
```

**Para Mainnet:**
```bash
# 1. Acesse https://www.okx.com/account/my-api
# 2. Gere API Key (API Key + Secret Key + Passphrase)
```

## 📚 Guias Especialistas

### 1. Binance Connection Guide
- **Arquivo:** `docs/binance_guide.md`
- **Cobertura:**
  - API REST (Spot e Futures)
  - WebSocket
  - SDK Python oficial
  - Autenticação
  - Rate limits
  - Permissões
  - Endpoints principais
  - Testnet vs Mainnet

### 2. Bybit Connection Guide
- **Arquivo:** `docs/bybit_guide.md`
- **Cobertura:**
  - API REST V5 (Spot e Futures)
  - WebSocket
  - SDK Python oficial
  - Autenticação
  - Rate limits
  - Permissões
  - Endpoints principais
  - Testnet vs Mainnet
  - Spot vs Futures

### 3. OKX Connection Guide
- **Arquivo:** `docs/okx_guide.md`
- **Cobertura:**
  - API REST V5 (Spot e Futures)
  - WebSocket
  - SDK Python oficial
  - Autenticação (com Passphrase)
  - Rate limits
  - Permissões
  - Endpoints principais
  - Demo Trading (alternativa ao Testnet)
  - Header `x-simulated-trading: 1`

## 📦 Instalação de SDKs Python

```bash
# Binance
pip install python-binance

# Bybit
pip install pybit

# OKX
pip install okx
```

## 📦 Bibliotecas de Suporte

```bash
# WebSockets
pip install websockets

# Requisições assíncronas
pip install aiohttp

# Gerenciamento de variáveis de ambiente
pip install python-dotenv

# Criptografia (assinatura)
pip install cryptography
```

## 🔗 Estrutura Multi-Tenant

```python
# Multi-tenant: múltiplos usuários com múltiplas contas
exchange_connections = {
    'binance': {
        'user1': {
            'spot_testnet': Connection(api_key_spot_test, secret_key_spot_test),
            'futures_testnet': Connection(api_key_futures_test, secret_key_futures_test),
            'spot_mainnet': Connection(api_key_spot_main, secret_key_spot_main),
            'futures_mainnet': Connection(api_key_futures_main, secret_key_futures_main)
        },
        'user2': {
            'spot_testnet': Connection(api_key_spot_2, secret_key_spot_2)
        }
    },
    'bybit': {
        'user1': {
            'spot_testnet': Connection(api_key_bybit_spot, secret_key_bybit_spot),
            'futures_testnet': Connection(api_key_bybit_futures, secret_key_bybit_futures),
            'spot_mainnet': Connection(api_key_bybit_main, secret_key_bybit_main),
            'futures_mainnet': Connection(api_key_bybit_futures_main, secret_key_bybit_futures_main)
        }
    },
    'okx': {
        'user1': {
            'demo': Connection(api_key_okx_demo, secret_key_okx_demo, passphrase_okx_demo),
            'mainnet': Connection(api_key_okx_main, secret_key_okx_main, passphrase_okx_main)
        }
    }
}
```

## ⚠️ Limitações e Riscos

### Rate Limits

| Exchange | Rate Limit | Como Respeitar |
|----------|------------|----------------|
| Binance | 1200 req/min | Implementar backoff exponencial |
| Bybit | 100 req/min | Implementar backoff exponencial |
| OKX | 20 req/min | Implementar backoff exponencial |

### Riscos Comuns

- **Perda de chaves API** - Armazene de forma segura
- **Execução não intencional** - Nunca execute ordens em mainnet sem verificação
- **Latência em conexões WebSocket** - Monitore e implemente reconexão
- **Dados desincronizados** - Use ordens ID para rastreamento
- **Testnet não isolado (OKX)** - Use apenas para testes rápidos

## 📊 Estrutura do Projeto

```
estudos-exchange-connections/
├── docs/
│   ├── binance_guide.md      ✅
│   ├── bybit_guide.md        ✅
│   └── okx_guide.md           ✅
├── src/
│   ├── binance_connection.py
│   ├── bybit_connection.py
│   └── okx_connection.py
├── examples/
│   ├── binance_spot.py
│   ├── binance_futures.py
│   ├── bybit_spot.py
│   ├── bybit_futures.py
│   ├── okx_spot.py
│   └── okx_futures.py
├── .env.example
├── README.md                 ✅
└── requirements.txt
```

## 📝 Próximos Passos

1. ✅ Criar repositório GitHub
2. ✅ Inicializar com README
3. ✅ Criar planilha de estudos
4. ✅ Subagentes especialistas (Binance, Bybit, OKX)
5. ✅ Documentação de Testnet vs Mainnet
6. ⏳ Implementar classes de conexão
7. ⏳ Implementar exemplos de Spot e Futures
8. ⏳ Implementar estrutura multi-tenant
9. ⏳ Criar testes de conexão
10. ⏳ Commitar e push para GitHub

## 🚀 Início Rápido

### 1. Clone e Instale
```bash
git clone https://github.com/mvdevolder2/estudos-exchange-connections.git
cd estudos-exchange-connections

# Python
pip install -r requirements.txt

# Node.js (opcional)
npm install
```

### 2. Configure Suas Chaves
```bash
# Copie o arquivo de exemplo
cp .env.example .env

# Abra e preencha APENAS as chaves que você vai usar
nano .env
```

### 3. Teste Primeiro em Testnet
```bash
# Teste Binance Spot (sem risco)
python -c "from src.binance_connection import BinanceConnection; conn = BinanceConnection(api_key='$BINANCE_SPOT_TEST_API_KEY', secret_key='$BINANCE_SPOT_TEST_API_SECRET', testnet=True); print(conn.get_balance(asset='USDT'))"
```

### 4. Leia a Documentação
- **README.md** - Visão geral do projeto
- **.env.example** - Todas as chaves que você precisa
- **specs/** - Especificações técnicas de cada exchange
- **examples/** - Exemplos de código funcionais

### 5. Use as Classes de Conexão
```python
# Binance
from src.binance_connection import BinanceConnection

conn_binance = BinanceConnection(
    api_key=os.getenv('BINANCE_SPOT_TEST_API_KEY'),
    secret_key=os.getenv('BINANCE_SPOT_TEST_API_SECRET'),
    testnet=True
)

# Bybit
from src.bybit_connection import BybitConnection

conn_bybit = BybitConnection(
    api_key=os.getenv('BYBIT_SPOT_TEST_API_KEY'),
    secret_key=os.getenv('BYBIT_SPOT_TEST_API_SECRET'),
    category='spot',
    testnet=True
)

# OKX
from src.okx_connection import OKXConnection

conn_okx = OKXConnection(
    api_key=os.getenv('OKX_DEMO_API_KEY'),
    secret_key=os.getenv('OKX_DEMO_API_SECRET'),
    passphrase=os.getenv('OKX_DEMO_API_PASSPHRASE'),
    simulated_trading=True
)
```

### 6. Comece a Construir
- Teste cada método das classes de conexão
- Crie seu próprio wrapper para multi-tenancy
- Implemente sua lógica de trading
- Documente seu código

---

## 🆘 Suporte

- **Documentação Oficial:**
  - Binance: https://binance-docs.github.io/apidocs/
  - Bybit: https://bybit-exchange.github.io/docs/
  - OKX: https://www.okx.com/docs-v5/

- **Comunidade:**
  - Telegram do Squad: @CryptoSquad
  - Issues no GitHub: https://github.com/mvdevolder2/estudos-exchange-connections/issues

---

## 📝 Notas Importantes

- **Testnet ≠ Mainnet** - Ambientes completamente isolados
- **OKX Demo** - Usa ambiente de produção, apenas simulação
- **Rate Limits** - Respeite os limites de cada exchange
- **Permissões** - Use sempre as mínimas necessárias (Read + Trade)
- **Chaves Teste** - Revoque-as periodicamente se suspeitar de vazamento
- **Mainnet** - Use apenas quando seu código foi testado completamente

---

## ✅ Pronto para Operar?

Antes de operar em Mainnet com dinheiro real:

- [ ] Código testado em Testnet
- [ ] Lógica de trading validada
- [ ] Stop-loss implementado
- [ ] Gerenciamento de risco configurado
- [ ] Chaves de mainnet com permissões mínimas
- [ ] Estratégias paper-trading validadas
- [ ] Testes de estresse realizados

---

**Criado em:** 2026-03-07
**Squad:** Crypto
**Lead:** Data (crypto-lead)
**Licença:** MIT

- **Planilha:** https://docs.google.com/spreadsheets/d/1XuH2kmObJ1a7AXO2L_4Yk80rG42wBVlbBWrcSvc7cIk/edit
- **Repositório:** https://github.com/mvdevolder2/estudos-exchange-connections
- **README:** https://github.com/mvdevolder2/estudos-exchange-connections#readme

## 🚀 Recursos

### Documentação Oficial
- Binance: https://binance-docs.github.io/apidocs/
- Bybit: https://bybit-exchange.github.io/docs/
- OKX: https://www.okx.com/docs-v5/

### Testnets
- Binance Testnet Spot: https://testnet.binance.vision/
- Binance Testnet Futures: https://testnet.binancefuture.com/
- Bybit Testnet: https://testnet.bybit.com/
- OKX Demo Trading: https://www.okx.com (mudar para "Demo Trading")

### SDKs Python
- Binance: https://github.com/binance/binance-connector-python
- Bybit: https://github.com/bybit-exchange/bybit-official-api-python
- OKX: https://github.com/okex/V5-Python-official-api

---

**Criado em:** 2026-03-06
**Squad:** Crypto
**Lead:** Data (crypto-lead)
