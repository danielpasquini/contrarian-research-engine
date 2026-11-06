# Contrarian Research Engine

Projeto pessoal de pesquisa quantitativa voltado para identificação de oportunidades contrárias e pullbacks em ações líquidas do mercado norte-americano (horizonte de 3 a 20 pregões).

## Visão Geral

O sistema combina uma abordagem em duas etapas:
1. **Filtro Técnico Determinístico:** Varredura quantitativa em Python sobre o universo de ações para detectar quedas anormais aliadas a sinais de exaustão técnica (ex: sobrevenda extrema, suporte estrutural ou estabilização de volume), filtrando o universo para uma lista diária restrita.
2. **Análise de Contexto e Narrativa:** Extração de fatos e análise de divergência de sentimento a partir de fatos relevantes (SEC filings 8-K/10-Q) e notícias, com regras estritas de veto a bandeiras vermelhas e validação de risco determinística.

## Pilares do Projeto

- **Filter First, LLM Second:** Processamento quantitativo primeiro para preservar cota e reduzir ruído antes de qualquer análise contextual.
- **Integridade Point-in-Time:** Rastreabilidade temporal rigorosa com carimbos UTC (`published_at`, `collected_at`, `available_at`) para mitigar viés de antecipação (look-ahead bias).
- **Gestão de Risco Estrita:** Cálculo de risco 100% determinístico em Python, ordens com stop/alvo obrigatórios (bracket) e bloqueio automático de preço médio em posições desfavoráveis.

## Configuração

1. Clone o repositório.
2. Crie seu ambiente virtual Python (`3.12+`) e instale as dependências.
3. Configure suas variáveis de ambiente com base no arquivo `.env.example`.

---
*Aviso: Este é um projeto estritamente pessoal para pesquisa quantitativa e simulação em paper-trading. Não constitui recomendação de investimento ou aconselhamento financeiro.*
