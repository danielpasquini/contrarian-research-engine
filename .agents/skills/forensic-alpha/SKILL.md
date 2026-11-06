---
name: forensic-alpha
description: Performs cross-entity contagion analysis, SEC filing text-diff forensics, Form 4 discretionary insider filtering, and intraday institutional absorption detection. Use when building the differentiated alpha engines.
---

# Forensic & Structural Contagion Alpha

## Objective
Differentiate genuine contrarian institutional accumulation from retail "falling knife" traps using four structural edges that standard sentiment bots ignore.

## 1. Cross-Entity Sympathy & Contagion Analysis
When a target stock drops >= 3% without a primary company-specific negative catalyst:
1. Identify which sector peer or ETF constituent experienced an earnings miss or shock on the same day.
2. Analyze the peer's event via Gemini Flash to classify the root cause:
   - `SECTOR_HEADWIND`: Macro/industry-wide demand collapse (Dangerous -> VETO target).
   - `IDIOSYNCRATIC_COMPETITOR_FAILURE`: Execution failure, product recall, or market share loss by the rival (Bullish contrarian signal for our target stock).

## 2. SEC EDGAR Redline Diff Forensics
Never send full unparsed 10-Q/10-K boilerplate to the LLM:
1. In Python (`difflib`), compute the exact sentence-level additions and deletions between the current filing and the previous filing's Item 1A (Risk Factors) and Item 7/2 (MD&A).
2. Send ONLY the delta (added/removed sentences) to Gemini Flash to score subtle legal warnings, liquidity phrasing shifts, or accounting policy changes.

## 3. SEC Form 4 Discretionary Cluster Filter
Parse SEC Form 4 XML filings in Python and reject noise:
- Keep ONLY transactions where `transactionCoding.transactionCode == 'P'` (Open Market Purchase).
- Exclude automatic `10b5-1` pre-scheduled plans (check footnotes/checkboxes).
- Weight purchases by CEO, CFO, or 10%+ owners occurring within 10 trading days after a price drop.

## 4. Intraday Institutional Absorption (AM vs. PM Regime)
Using Alpaca 15-minute bars for shortlisted candidates:
- Measure **AM Panic Window (09:30–10:30 ET)** vs. **PM Institutional Window (15:00–16:00 ET)**.
- Confirm absorption when: the majority of the price drop occurred in the AM window, price stabilizes above the post-11:00 ET VWAP, and the PM window shows positive price-volume divergence (closing in the top 35% of the afternoon range on above-average closing volume).