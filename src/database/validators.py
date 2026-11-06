from datetime import datetime


def validate_pit_timestamps(
    published_at: datetime,
    collected_at: datetime,
    available_at: datetime,
) -> None:
    """
    Validate that all three Point-in-Time timestamps are timezone-aware
    and satisfy available_at >= published_at (`C-PIT-01`, `C-DB-05`).
    """
    for label, ts in (
        ("published_at", published_at),
        ("collected_at", collected_at),
        ("available_at", available_at),
    ):
        if ts.tzinfo is None or ts.tzinfo.utcoffset(ts) is None:
            raise ValueError(f"{label} must be a timezone-aware UTC datetime.")

    if available_at < published_at:
        raise ValueError(
            f"PIT violation: available_at ({available_at.isoformat()}) "
            f"cannot precede published_at ({published_at.isoformat()})."
        )
