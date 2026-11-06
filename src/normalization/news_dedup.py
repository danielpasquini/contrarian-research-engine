import hashlib
import re
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.normalization.calendar import compute_available_at, ensure_utc

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _normalize_text(text: str) -> str:
    return " ".join(_TOKEN_RE.findall(text.lower()))


def _token_set(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text.lower()))


def _jaccard_similarity(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


class RawNewsArticle(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source_id: str = Field(min_length=1)
    publisher: str = Field(min_length=1)
    ticker: str = Field(min_length=1)
    headline: str = Field(min_length=1)
    summary: str = Field(default="")
    published_at: datetime
    collected_at: datetime

    @field_validator("published_at", "collected_at", mode="before")
    @classmethod
    def ensure_utc_ts(cls, v: datetime) -> datetime:
        return ensure_utc(v)


class NewsCluster(BaseModel):
    """Deduplicated news story preventing syndicated wire inflation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cluster_id: UUID = Field(default_factory=uuid4)
    ticker: str
    primary_source_id: str
    duplicate_source_ids: list[str] = Field(default_factory=list)
    independent_source_count: int = Field(default=1, ge=1)
    total_raw_articles: int = Field(default=1, ge=1)
    headline: str
    summary_text: str
    published_at: datetime
    collected_at: datetime
    available_at: datetime
    raw_payload_hash: str


def deduplicate_news_articles(
    articles: list[RawNewsArticle],
    similarity_threshold: float = 0.85,
    window_hours: int = 24,
) -> list[NewsCluster]:
    """
    Collapse syndicated news copies for the same ticker within `window_hours`
    when normalized headlines match or token Jaccard similarity >= `similarity_threshold`.
    """
    if not articles:
        return []

    sorted_articles = sorted(articles, key=lambda a: (a.published_at, a.source_id))
    clusters: list[NewsCluster] = []
    cluster_tokens: list[set[str]] = []
    cluster_norm_headlines: list[str] = []

    max_delta = timedelta(hours=window_hours)

    for article in sorted_articles:
        norm_h = _normalize_text(article.headline)
        tokens_h = _token_set(article.headline)
        matched_idx: int | None = None

        for idx, existing in enumerate(clusters):
            if existing.ticker != article.ticker:
                continue
            if abs(article.published_at - existing.published_at) > max_delta:
                continue
            if norm_h == cluster_norm_headlines[idx] or (
                _jaccard_similarity(tokens_h, cluster_tokens[idx]) >= similarity_threshold
            ):
                matched_idx = idx
                break

        if matched_idx is None:
            digest = hashlib.sha256(
                f"{article.source_id}:{article.headline}:{article.published_at.isoformat()}".encode()
            ).hexdigest()
            clusters.append(
                NewsCluster(
                    ticker=article.ticker,
                    primary_source_id=article.source_id,
                    duplicate_source_ids=[],
                    independent_source_count=1,
                    total_raw_articles=1,
                    headline=article.headline.strip(),
                    summary_text=article.summary.strip(),
                    published_at=article.published_at,
                    collected_at=article.collected_at,
                    available_at=compute_available_at(article.published_at),
                    raw_payload_hash=digest,
                )
            )
            cluster_tokens.append(tokens_h)
            cluster_norm_headlines.append(norm_h)
        else:
            prev = clusters[matched_idx]
            new_dups = [*prev.duplicate_source_ids, article.source_id]
            clusters[matched_idx] = NewsCluster(
                cluster_id=prev.cluster_id,
                ticker=prev.ticker,
                primary_source_id=prev.primary_source_id,
                duplicate_source_ids=new_dups,
                independent_source_count=1,
                total_raw_articles=prev.total_raw_articles + 1,
                headline=prev.headline,
                summary_text=prev.summary_text,
                published_at=prev.published_at,
                collected_at=prev.collected_at,
                available_at=prev.available_at,
                raw_payload_hash=prev.raw_payload_hash,
            )

    return clusters
