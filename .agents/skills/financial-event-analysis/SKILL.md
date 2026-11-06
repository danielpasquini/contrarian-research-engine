---
name: financial-event-analysis
description: Analyzes financial news, SEC filings, earnings events, company fundamentals, and market narratives for contrarian research. Use when investigating a company event, building LLM extraction pipelines, or evaluating a potential contrarian opportunity.
---

# Financial Event Analysis

## Objective
Produce evidence-based financial event analysis and risk-veto classifications without confusing temporary negative sentiment with structural fundamental deterioration.

## Workflow
1. Identify the company, ticker, event type, `published_at`, and `available_at` timestamps.
2. Retrieve original sources and primary documents (prioritizing SEC 8-K, 10-Q, 10-K over secondary news).
3. Deduplicate syndicated news articles to avoid inflating evidence weight.
4. Identify what information was genuinely new at the event time versus already public.
5. Separate verified facts from journalist or analyst interpretations.
6. Check for structural red flags (accounting fraud, SEC investigation, distressed debt/bankruptcy risk, abrupt C-suite resignation, or upcoming earnings within 3 days).
7. Compare the magnitude of the price drop with the actual multi-quarter fundamental impact.
8. Identify positive evidence, negative counter-evidence, and thesis invalidation conditions.

## Required Output (Pydantic Schema)
- Company and ticker.
- Event classification and material red flags.
- Event timestamps (`published_at`, `available_at`).
- Original source references.
- Verified facts vs. market narrative.
- Fundamental impact assessment (temporary vs. structural).
- Contradicting evidence (why the price drop might be rational).
- Veto decision (`APPROVE` or `VETO` for trading).
- Confidence score and missing information list.

## Rules
- Never invent financial facts or extrapolate numbers not in the text.
- Never assume a sharp price decline automatically represents an overreaction ("falling knife" trap).
- Never interpret a single positive headline as a sentiment reversal without price stabilization.
- Always flag structural red flags or imminent earnings releases as a mandatory `VETO`.
- Explicitly document evidence that contradicts the contrarian buy thesis.

## Completion Criteria
Every material conclusion is traceable to a source ID, schema validation passes with `temperature=0.0`, and uncertainty or missing data is explicitly quantified.