from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


OUTPUT_PATH = Path(__file__).resolve().parents[1] / "data" / "sample_etf_daily.csv"


def make_one_etf(symbol: str, name: str, start_price: float, drift: float, vol: float, seed: int) -> pd.DataFrame:
    """Generate synthetic OHLCV daily ETF data for pandas practice.

    This is fake data, not investment data. It is designed to be stable and
    reproducible so learning examples always produce the same result.
    """
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2023-01-02", "2024-12-31")
    n = len(dates)

    # Daily log returns with light regime/noise effects.
    log_ret = rng.normal(loc=drift, scale=vol, size=n)
    close = start_price * np.exp(np.cumsum(log_ret))

    # Open is near previous close; high/low wrap around open and close.
    overnight = rng.normal(loc=0.0, scale=vol * 0.25, size=n)
    open_ = np.empty(n)
    open_[0] = start_price * (1 + overnight[0])
    open_[1:] = close[:-1] * (1 + overnight[1:])

    intraday_spread = np.abs(rng.normal(loc=vol * 0.9, scale=vol * 0.35, size=n))
    high = np.maximum(open_, close) * (1 + intraday_spread)
    low = np.minimum(open_, close) * (1 - intraday_spread)

    volume_base = rng.integers(800_000, 2_500_000, size=n)
    volume_noise = rng.lognormal(mean=0.0, sigma=0.35, size=n)
    volume = (volume_base * volume_noise).astype(int)
    amount = volume * close

    df = pd.DataFrame(
        {
            "date": dates,
            "symbol": symbol,
            "name": name,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "amount": amount,
        }
    )

    price_cols = ["open", "high", "low", "close"]
    df[price_cols] = df[price_cols].round(3)
    df["amount"] = df["amount"].round(2)
    return df


def main() -> None:
    etfs = [
        # symbol, name, start_price, daily_drift, daily_vol, seed
        ("510300", "沪深300ETF", 3.90, 0.00018, 0.011, 101),
        ("159915", "创业板ETF", 2.15, 0.00010, 0.018, 202),
        ("511010", "国债ETF", 110.00, 0.00004, 0.002, 303),
    ]

    df = pd.concat(
        [make_one_etf(*args) for args in etfs],
        ignore_index=True,
    )

    # Sort like a normal long-format market data file.
    df = df.sort_values(["date", "symbol"]).reset_index(drop=True)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")

    print(f"written: {OUTPUT_PATH}")
    print(f"rows: {len(df)}")
    print(f"columns: {list(df.columns)}")
    print(df.head(9).to_string(index=False))


if __name__ == "__main__":
    main()
