# MT5 Market Analyzer POC (Clean Architecture + Idempotent Sync)

Prova de Conceito (POC) em Python para coleta automática e análise técnica de dados do **MetaTrader 5 (MT5)**, aplicando **Clean Architecture** e persistência **100% idempotente** em SQLite.

## Estrutura em Clean Architecture

- `src/domain/`: Entidades puras do MT5 (`SymbolInfo`, `Tick`, `Candle`, `Timeframe`, `MarketAnalysis`), portas (`MarketDataProviderPort`, `MarketRepositoryPort`) e serviço de cálculo de indicadores (`MarketAnalyzerService`: SMA 9, EMA 21, RSI 14, ATR 14, volume médio de ticks e sinal de tendência). Zero dependências externas.
- `src/application/`: Caso de uso `SyncAndAnalyzeMarketUseCase` que orquestra a coleta do provedor MT5, o *upsert* idempotente no repositório e a análise de mercado.
- `src/infrastructure/`:
  - `mt5/mt5_provider.py`: `MT5MarketDataProvider` (integração nativa com o pacote `MetaTrader5`) e `MockMT5MarketDataProvider` (fallback determinístico com a estrutura exata do MT5 quando o terminal não está aberto).
  - `persistence/sqlite_repository.py`: `SQLiteMarketRepository` com chaves naturais `UNIQUE` e cláusulas `ON CONFLICT DO UPDATE` para garantir idempotência total.
- `src/presentation/`: CLI (`cli.py`) que executa ciclos de sincronização e exibe os indicadores e a contagem de registros no banco para comprovar que múltiplas execuções nunca duplicam dados.

## Como Executar

```bash
# Executar a CLI (roda 2 ciclos seguidos por padrão para demonstrar a idempotência)
python -m src.presentation.cli --symbols PETR4,VALE3,WIN$N,EURUSD --timeframe M15 --runs 2

# Executar a suíte de testes automatizados
python -m pytest -v
```
