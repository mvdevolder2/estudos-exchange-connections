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

## 📚 Documentação por Exchange

### Binance
- API REST: https://binance-docs.github.io/apidocs/
- Websocket: https://binance-docs.github.io/apidocs/websocket_api/
- SDK Python: https://github.com/binance/binance-connector-python
- Rate Limits: https://binance-docs.github.io/apidocs/limits/

### Bybit
- API REST: https://bybit-exchange.github.io/docs/
- Websocket: https://bybit-exchange.github.io/docs/websocket/
- SDK Python: https://github.com/bybit-exchange/bybit-official-api-python
- Rate Limits: https://bybit-exchange.github.io/docs/rate_limit/

### OKX
- API REST: https://www.okx.com/docs-v5/
- Websocket: https://www.okx.com/docs-v5/#websocket-api
- SDK Python: https://github.com/okex/V5-Python-official-api
- Rate Limits: https://www.okx.com/docs-v5/#system-rate-limit

## 🔑 Autenticação

### Chaves API Necessárias
- **API Key**: Identificador da aplicação
- **Secret Key**: Chave secreta para assinar requisições
- **Passphrase**: (Opcional para algumas exchanges) Frase de recuperação

### Permissões por Tipo de Operação
| Operação | Permissões Necessárias |
|-----------|-------------------------|
| Spot Trading | `Read` + `Trade` |
| Futures Trading | `Futures` + `Futures Trading` |
| Leitura de Saldo | `Read` |
| Streaming | `Read` + `Trading Stream` |

## 📊 Endpoints Principais

### Spot Trading
- `/api/v3/account` - Saldo da conta
- `/api/v3/order` - Criar ordem
- `/api/v3/openOrders` - Ordens abertas
- `/api/v3/myTrades` - Histórico de trades

### Futures Trading
- `/fapi/v2/balance` - Saldo futures
- `/fapi/v1/order` - Criar ordem futures
- `/fapi/v1/openOrders` - Ordens abertas futures
- `/fapi/v1/userTrades` - Histórico de trades futures

## 🔗 Estrutura de Conexão

```python
class ExchangeConnection:
    def __init__(self, api_key, secret_key, passphrase=None):
        self.api_key = api_key
        self.secret_key = secret_key
        self.passphrase = passphrase

    def connect(self):
        # Estabelece conexão WebSocket
        pass

    def get_balance(self):
        # Busca saldo da conta
        pass

    def place_order(self, symbol, side, type, amount, price=None):
        # Cria ordem
        pass

    def get_open_orders(self, symbol=None):
        # Busca ordens abertas
        pass

    def cancel_order(self, symbol, order_id):
        # Cancela ordem
        pass
```

## 🔄 Multi-Tenancy

### Estrutura de Usuários/Contas
```python
# Multi-tenant: múltiplos usuários com múltiplas contas
exchange_connections = {
    'binance': {
        'user1': {
            'spot': Connection(api_key1, secret_key1),
            'futures': Connection(api_key2, secret_key2)
        },
        'user2': {
            'spot': Connection(api_key3, secret_key3)
        }
    },
    'bybit': {
        'user1': {
            'spot': Connection(api_key4, secret_key4),
            'futures': Connection(api_key5, secret_key5)
        }
    }
}
```

## ⚠️ Limitações e Riscos

### Rate Limits
- Binance: 1200 requests/min
- Bybit: 100 requests/min
- OKX: 20 requests/min

### Riscos
- Perda de chaves API
- Execução não intencional de ordens
- Latência em conexões WebSocket
- Dados desincronizados

## 📝 Próximos Passos

1. ✅ Criar repositório GitHub
2. ⏳ Subagentes especialistas:
   - Binance Exchange Specialist
   - Bybit Exchange Specialist
   - OKX Exchange Specialist
3. ⏳ Implementar classes de conexão
4. ⏳ Desenvolver exemplos de Spot e Futures
5. ⏳ Implementar estrutura multi-tenant
6. ⏳ Criar testes de conexão

## 🔗 Links

- Planilha de Estudos: https://docs.google.com/spreadsheets/d/1XuH2kmObJ1a7AXO2L_4Yk80rG42wBVlbBWrcSvc7cIk/edit
- Repositório GitHub: https://github.com/mvdevolder2/estudos-exchange-connections

## 📚 Recursos

### SDKs Python Oficiais
- Binance: `pip install python-binance`
- Bybit: `pip install pybit`
- OKX: `pip install okx`

### Bibliotecas de Suporte
- `websockets` - Conexões WebSocket
- `aiohttp` - Requisições assíncronas
- `python-dotenv` - Gerenciamento de variáveis de ambiente

## 🏷️ Status

- 🟢 Binance: Aguardando especialista
- 🟢 Bybit: Aguardando especialista
- 🟢 OKX: Aguardando especialista
- 🟡 Multi-tenancy: Arquitetura definida
- 🟡 Spot/Futures: Escopo definido

---

**Criado em:** 2026-03-06
**Squad:** Crypto
**Lead:** Data (crypto-lead)
