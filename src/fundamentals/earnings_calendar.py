from datetime import date

from pydantic import BaseModel, ConfigDict

from src.normalization.calendar import count_trading_days_between


class EarningsBlackoutStatus(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    ticker: str
    as_of_date: date
    next_earnings_date: date | None
    trading_days_to_earnings: int | None
    earnings_blackout: bool


def evaluate_earnings_blackout(
    ticker: str,
    as_of_date: date,
    next_earnings_date: date | None,
    blackout_trading_days: int = 3,
) -> EarningsBlackoutStatus:
    """
    Automatically flag a ticker for earnings blackout if:
    - `next_earnings_date` is None or `< as_of_date` -> fail-closed (`earnings_blackout=True`).
    - An earnings announcement is scheduled within `[0, blackout_trading_days]` trading sessions.
    """
    if next_earnings_date is None or next_earnings_date < as_of_date:
        return EarningsBlackoutStatus(
            ticker=ticker,
            as_of_date=as_of_date,
            next_earnings_date=next_earnings_date,
            trading_days_to_earnings=None,
            earnings_blackout=True,
        )

    sessions = count_trading_days_between(as_of_date, next_earnings_date)
    is_blackout = 0 <= sessions <= blackout_trading_days

    return EarningsBlackoutStatus(
        ticker=ticker,
        as_of_date=as_of_date,
        next_earnings_date=next_earnings_date,
        trading_days_to_earnings=sessions,
        earnings_blackout=is_blackout,
    )
