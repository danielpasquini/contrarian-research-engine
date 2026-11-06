"""
Alpaca Market Data Adapter (`src/ingestion/alpaca_data.py`).
Fetches historical daily OHLCV bars from Alpaca (`DataFeed.IEX`) and normalizes
them into Point-in-Time `NormalizedBar` records.
"""

import hashlib
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from alpaca.data.enums import Adjustment, DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.historical.news import NewsClient
from alpaca.data.requests import NewsRequest, StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from src.config import EngineSettings
from src.normalization.pit_models import NormalizedBar

NY_TZ = ZoneInfo("America/New_York")

DEFAULT_LIQUID_UNIVERSE: tuple[str, ...] = (
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "META",
    "GOOGL",
    "TSLA",
    "AVGO",
    "JPM",
    "V",
    "UNH",
    "XOM",
    "MA",
    "COST",
    "HD",
    "PG",
    "WMT",
    "JNJ",
    "NFLX",
    "CRM",
    "BAC",
    "ABBV",
    "CVX",
    "KO",
    "MRK",
    "AMD",
    "PEP",
    "TMO",
    "WFC",
    "ADBE",
    "CSCO",
    "MCD",
    "DIS",
    "ABT",
    "INTU",
    "QCOM",
    "TXN",
    "GE",
    "IBM",
    "CAT",
    "VZ",
    "NOW",
    "AMGN",
    "PFE",
    "ISRG",
    "UBER",
    "GS",
    "SPGI",
    "T",
    "RTX",
    "HON",
    "CMCSA",
    "LOW",
    "UNP",
    "PYPL",
    "BA",
    "INTC",
    "NKE",
    "SBUX",
    "MU",
    "PANW",
    "LRCX",
    "KLAC",
    "ANET",
    "CRWD",
    "SNOW",
    "PLTR",
    "COIN",
    "SOFI",
    "SHOP",
)

COMPANY_NAMES: dict[str, str] = {
    "AAPL": "Apple Inc.",
    "MSFT": "Microsoft Corporation",
    "NVDA": "NVIDIA Corporation",
    "AMZN": "Amazon.com, Inc.",
    "META": "Meta Platforms, Inc.",
    "GOOGL": "Alphabet Inc.",
    "TSLA": "Tesla, Inc.",
    "AVGO": "Broadcom Inc.",
    "JPM": "JPMorgan Chase & Co.",
    "V": "Visa Inc.",
    "UNH": "UnitedHealth Group Inc.",
    "XOM": "Exxon Mobil Corporation",
    "MA": "Mastercard Incorporated",
    "COST": "Costco Wholesale Corp.",
    "HD": "The Home Depot, Inc.",
    "PG": "Procter & Gamble Co.",
    "WMT": "Walmart Inc.",
    "JNJ": "Johnson & Johnson",
    "NFLX": "Netflix, Inc.",
    "CRM": "Salesforce, Inc.",
    "BAC": "Bank of America Corp.",
    "ABBV": "AbbVie Inc.",
    "CVX": "Chevron Corporation",
    "KO": "The Coca-Cola Company",
    "MRK": "Merck & Co., Inc.",
    "AMD": "Advanced Micro Devices, Inc.",
    "PEP": "PepsiCo, Inc.",
    "TMO": "Thermo Fisher Scientific",
    "WFC": "Wells Fargo & Company",
    "ADBE": "Adobe Inc.",
    "CSCO": "Cisco Systems, Inc.",
    "MCD": "McDonald's Corporation",
    "DIS": "The Walt Disney Company",
    "ABT": "Abbott Laboratories",
    "INTU": "Intuit Inc.",
    "QCOM": "QUALCOMM Incorporated",
    "TXN": "Texas Instruments Inc.",
    "GE": "GE Aerospace",
    "IBM": "IBM Corporation",
    "CAT": "Caterpillar Inc.",
    "VZ": "Verizon Communications",
    "NOW": "ServiceNow, Inc.",
    "AMGN": "Amgen Inc.",
    "PFE": "Pfizer Inc.",
    "ISRG": "Intuitive Surgical, Inc.",
    "UBER": "Uber Technologies, Inc.",
    "GS": "The Goldman Sachs Group",
    "SPGI": "S&P Global Inc.",
    "T": "AT&T Inc.",
    "RTX": "RTX Corporation",
    "HON": "Honeywell International",
    "CMCSA": "Comcast Corporation",
    "LOW": "Lowe's Companies, Inc.",
    "UNP": "Union Pacific Corporation",
    "PYPL": "PayPal Holdings, Inc.",
    "BA": "The Boeing Company",
    "INTC": "Intel Corporation",
    "NKE": "NIKE, Inc.",
    "SBUX": "Starbucks Corporation",
    "MU": "Micron Technology, Inc.",
    "PANW": "Palo Alto Networks, Inc.",
    "LRCX": "Lam Research Corporation",
    "KLAC": "KLA Corporation",
    "ANET": "Arista Networks, Inc.",
    "CRWD": "CrowdStrike Holdings, Inc.",
    "SNOW": "Snowflake Inc.",
    "PLTR": "Palantir Technologies Inc.",
    "COIN": "Coinbase Global, Inc.",
    "SOFI": "SoFi Technologies, Inc.",
    "SHOP": "Shopify Inc.",
}


class AlpacaMarketDataAdapter:
    """Fetches daily OHLCV bars from Alpaca IEX/SIP feed and normalizes them into PIT bars."""

    def __init__(self, settings: EngineSettings) -> None:
        self.settings = settings
        self.client = StockHistoricalDataClient(
            api_key=settings.alpaca_api_key,
            secret_key=settings.alpaca_secret_key,
        )
        self.news_client = NewsClient(
            api_key=settings.alpaca_api_key,
            secret_key=settings.alpaca_secret_key,
        )

    def fetch_recent_news_headlines(
        self,
        tickers: list[str],
        limit: int = 25,
    ) -> dict[str, list[str]]:
        """Fetches recent real market news headlines from Alpaca for shortlisted tickers."""
        if not tickers:
            return {}
        result_map: dict[str, list[str]] = {t: [] for t in tickers}
        try:
            req = NewsRequest(symbols=",".join(tickers[:15]), limit=limit)
            resp = self.news_client.get_news(req)
            items = getattr(resp, "news", None)
            if items is None:
                data_dict = getattr(resp, "data", {}) or {}
                items = data_dict.get("news", []) if isinstance(data_dict, dict) else []
            for item in items or []:
                headline = str(getattr(item, "headline", "") or "").strip()
                item_syms = getattr(item, "symbols", []) or []
                if not headline:
                    continue
                for sym in item_syms:
                    if sym in result_map and len(result_map[sym]) < 3:
                        result_map[sym].append(headline)
        except Exception:
            return result_map
        return result_map

    def fetch_universe_daily_bars(
        self,
        as_of_utc: datetime,
        tickers: tuple[str, ...] = DEFAULT_LIQUID_UNIVERSE,
        lookback_calendar_days: int = 365,
    ) -> dict[str, list[NormalizedBar]]:
        feed = (
            DataFeed.SIP
            if self.settings.alpaca_data_feed.strip().lower() == "sip"
            else DataFeed.IEX
        )
        start_dt = as_of_utc - timedelta(days=lookback_calendar_days)
        req = StockBarsRequest(
            symbol_or_symbols=list(tickers),
            timeframe=TimeFrame.Day,
            start=start_dt,
            end=as_of_utc,
            feed=feed,
            adjustment=Adjustment.RAW,
        )
        response = self.client.get_stock_bars(req)
        raw_map = getattr(response, "data", {}) or {}

        normalized_universe: dict[str, list[NormalizedBar]] = {}
        for symbol, bar_list in raw_map.items():
            norm_bars: list[NormalizedBar] = []
            for b in bar_list:
                ts: datetime = getattr(b, "timestamp", as_of_utc)
                s_date = ts.astimezone(NY_TZ).date()
                close_utc = datetime.combine(s_date, time(16, 0), tzinfo=NY_TZ).astimezone(UTC)
                open_p = float(getattr(b, "open", 0.0) or 0.0)
                high_p = float(getattr(b, "high", 0.0) or 0.0)
                low_p = float(getattr(b, "low", 0.0) or 0.0)
                close_p = float(getattr(b, "close", 0.0) or 0.0)
                vol = int(getattr(b, "volume", 0) or 0)
                if open_p <= 0.0 or high_p <= 0.0 or low_p <= 0.0 or close_p <= 0.0:
                    continue
                # Ensure bar bounds consistency on minor IEX odd-lot ticks
                high_p = max(high_p, open_p, close_p, low_p)
                low_p = min(low_p, open_p, close_p, high_p)
                payload_sig = (
                    f"{symbol}:{s_date.isoformat()}:{open_p}:{high_p}:{low_p}:{close_p}:{vol}"
                )
                payload_hash = hashlib.sha256(payload_sig.encode("utf-8")).hexdigest()

                norm_bars.append(
                    NormalizedBar(
                        ticker=symbol,
                        session_date=s_date,
                        open=open_p,
                        high=high_p,
                        low=low_p,
                        close=close_p,
                        raw_open=open_p,
                        raw_high=high_p,
                        raw_low=low_p,
                        raw_close=close_p,
                        volume=vol,
                        dollar_volume=round(close_p * vol, 2),
                        published_at=close_utc,
                        collected_at=max(as_of_utc, close_utc),
                        available_at=close_utc,
                        raw_payload_hash=payload_hash,
                    )
                )
            if norm_bars:
                normalized_universe[symbol] = norm_bars

        return normalized_universe
