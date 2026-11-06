import time
from typing import Any

import httpx


class SecEdgarClient:
    """
    Rate-limited SEC EDGAR REST API adapter (`data.sec.gov`).
    Enforces SEC fair-access policy:
    - Descriptive `User-Agent: <AppName> <ContactEmail>` header required.
    - Maximum 8.0 requests/second (safely below SEC's 10 req/sec hard cap).
    """

    def __init__(
        self,
        user_agent: str,
        max_requests_per_second: float = 8.0,
    ) -> None:
        clean_ua = user_agent.strip()
        if not clean_ua or "@" not in clean_ua:
            raise ValueError(
                "SEC_USER_AGENT must be non-empty and include a contact email per SEC policy."
            )
        if max_requests_per_second <= 0.0 or max_requests_per_second > 10.0:
            raise ValueError("SEC EDGAR rate limit cannot exceed 10.0 requests/second.")
        self.user_agent = clean_ua
        self.max_requests_per_second = max_requests_per_second
        self._min_interval = 1.0 / max_requests_per_second
        self._last_request_ts: float = 0.0

    def build_headers(self) -> dict[str, str]:
        return {
            "User-Agent": self.user_agent,
            "Accept-Encoding": "gzip, deflate",
            "Host": "data.sec.gov",
        }

    def _throttle(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_request_ts
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request_ts = time.monotonic()

    def fetch_company_facts(self, cik: str) -> dict[str, Any]:
        padded_cik = cik.strip().zfill(10)
        url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{padded_cik}.json"
        self._throttle()
        with httpx.Client(timeout=20.0, headers=self.build_headers()) as client:
            resp = client.get(url)
            resp.raise_for_status()
            return dict(resp.json())
