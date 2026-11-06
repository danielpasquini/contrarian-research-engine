---
trigger: always_on
description: Regras permanentes de arquitetura modular e separação entre IA e cálculo determinístico.
---
# Architecture Rules
- Maintain a modular monolith in Python 3.12+.
- Keep domain logic independent of external providers.
- Use provider adapters for Alpaca, SEC EDGAR, and future data sources.
- Execute deterministic Python price/volume scanners BEFORE calling LLM APIs to preserve quotas.
- Use Pydantic v2 schemas at all system and LLM boundaries.
- Use SQLAlchemy 2.0 for persistence with PostgreSQL as the primary database.
- Store large historical time-series datasets in Parquet when appropriate.
- Never put financial calculations, ATR math, or position sizing inside LLM prompts.
- Avoid unnecessary abstractions and microservices.