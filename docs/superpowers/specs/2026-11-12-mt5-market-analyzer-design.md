# Design Doc: POC de Sistema de Análise de Mercado Financeiro (MT5 + Clean Architecture)

## 1. Intenção e Objetivo (Why)
Construir uma Prova de Conceito (POC) simples em Python para coletar dados de mercado fornecidos pelo MetaTrader 5 (MT5), persistir esses dados automaticamente de forma idempotente em banco local e realizar análises técnicas básicas sobre os ativos, estruturando todo o código em **Clean Architecture** (separação estrita entre regras de negócio, casos de uso e detalhes de infraestrutura).

## 2. Escopo (Goals, Non-Goals, Anti-Goals)
- **Goals:**
  - Extrair apenas informações disponíveis nativamente via MetaTrader 5: especificações do ativo (`SymbolInfo`: dígitos, spread, tick size, lote mínimo/máximo, moeda), cotação atual (`Tick`: bid, ask, last, volume, time) e histórico de barras/candles (`Candle`: time, open, high, low, close, tick_volume, real_volume, spread).
  - Persistir os dados automaticamente de maneira **100% idempotente** (executar a sincronização $N$ vezes para a mesma janela de tempo atualiza/mantém os mesmos registros sem jamais duplicar dados).
  - Calcular indicadores e sinais de análise no domínio puro (SMA, EMA, RSI, ATR/Volatilidade, tendência e resumo de spread/liquidez).
  - Fornecer um adaptador MT5 real (`MetaTrader5` package) e um adaptador Mock/Fallback com a mesma estrutura exata do MT5 para permitir validação e testes automatizados mesmo quando o terminal MT5 não estiver aberto ou conectado.
- **Non-Goals:**
  - Envio de ordens de compra/venda (execução de trades).
  - Dados fundamentalistas externos (balanços, notícias) que não existem na API de mercado do MT5.
- **Anti-Goals:**
  - Acoplar entidades de domínio ou casos de uso diretamente ao pacote `MetaTrader5` ou ao `sqlite3`.

## 3. Abordagens Consideradas
1. **Abordagem 1 (Escolhida): Coletor + Analisador em SQLite nativo com CLI / Loop de Sincronização (`sqlite3` + `MetaTrader5`)**
   - *Trade-off:* Zero servidores externos, usa `sqlite3` nativo com `ON CONFLICT DO UPDATE` (Upsert) para idempotência garantida no banco, foco total na clareza da Clean Architecture e facilidade de execução via CLI (execução única ou contínua).
2. **Abordagem 2: API REST com FastAPI + Background Worker**
   - *Trade-off:* Boa para integração web, mas adiciona complexidade de servidor HTTP desnecessária para validar a POC inicialmente.
3. **Abordagem 3: Pipeline com PostgreSQL / DuckDB**
   - *Trade-off:* Melhor para milhões de registros, mas exige dependências extras ou infraestrutura externa.

## 4. Arquitetura e Camadas (Clean Architecture)

```
src/
├── domain/                  # Camada 1: Enterprise Business Rules (Zero dependências externas)
│   ├── entities/            # SymbolInfo, Tick, Candle, MarketAnalysis, Timeframe
│   ├── services/            # MarketAnalyzerService (cálculo puro de SMA, EMA, RSI, ATR, Tendência)
│   └── repositories/        # Interfaces (Ports): MarketDataProviderPort, MarketRepositoryPort
├── application/             # Camada 2: Application Business Rules (Orquestração)
│   ├── dtos/                # SyncResultDTO, AnalysisReportDTO
│   └── use_cases/           # SyncMarketDataUseCase (coleta + upsert idempotente), AnalyzeMarketUseCase
├── infrastructure/          # Camada 3: Frameworks & Drivers (Implementações concretas)
│   ├── mt5/                 # MT5MarketDataProvider (oficial) e MockMT5MarketDataProvider (fallback)
│   └── persistence/         # SQLiteMarketRepository (DDL + Upsert idempotente com UNIQUE constraints)
└── presentation/            # Camada 4: Interface Adapters / Entrypoint
    └── cli.py               # CLI para sincronizar, analisar e demonstrar idempotência (--loop, --symbols)
tests/                       # Testes automatizados (unitários de domínio e integração de idempotência)
```

## 5. Estratégia de Idempotência
A idempotência é garantida em dois níveis:
1. **Chaves Naturais de Domínio:**
   - `symbols`: chave única por `name` (ex: `PETR4`, `EURUSD`).
   - `candles`: chave única composta por `(symbol, timeframe, time)` onde `time` é o timestamp Unix (abertura do candle no MT5).
   - `ticks`: chave única composta por `(symbol, time_msc, bid, ask, last, flags)`.
   - `analyses`: chave única composta por `(symbol, timeframe, reference_time)`.
2. **Upsert Atômico no Repositório (`ON CONFLICT DO UPDATE`):**
   - Candles já fechados mantêm seus valores; o candle em aberto (barra atual do MT5) é atualizado in-place com os novos `high`, `low`, `close` e `tick_volume` sem gerar linhas duplicadas.
   - O caso de uso `SyncMarketDataUseCase` retorna métricas explícitas da operação, permitindo verificar que re-execuções mantêm a contagem de registros estável.
