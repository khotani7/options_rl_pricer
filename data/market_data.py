"""
Market data layer: calibrates simulator parameters (spot, volatility,
risk-free rate, dividend yield) to real mid/high-cap equities.

Tries a live pull via yfinance first. If the network is unreachable
(e.g. this code is running inside a sandboxed environment with no
outbound internet access) it transparently falls back to a small,
dated calibration cache built from a manual data pull -- so the
pipeline stays runnable end to end, and on a machine with normal
internet access the live path is what actually gets used.
"""

from __future__ import annotations

import json
import os
import warnings
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import numpy as np

from config import classify_cap

_CACHE_PATH = os.path.join(os.path.dirname(__file__), "calibration_cache.json")


@dataclass
class MarketParams:
    ticker: str
    spot: float
    vol: float                # annualized volatility used for simulation
    risk_free_rate: float
    dividend_yield: float
    market_cap: Optional[float]
    cap_bucket: str
    source: str                # "live" or "cache"
    as_of: str


def _load_cache() -> dict:
    with open(_CACHE_PATH, "r") as f:
        return json.load(f)


def _params_from_cache(ticker: str) -> MarketParams:
    cache = _load_cache()
    ticker = ticker.upper()
    if ticker not in cache["tickers"]:
        available = ", ".join(cache["tickers"].keys())
        raise KeyError(
            f"'{ticker}' has no live data and is not in the offline calibration "
            f"cache. Cached tickers: {available}. Add it to "
            f"data/calibration_cache.json or run with internet access."
        )
    row = cache["tickers"][ticker]
    vol = row.get("implied_vol") or row.get("hist_vol")
    return MarketParams(
        ticker=ticker,
        spot=row["spot"],
        vol=vol,
        risk_free_rate=cache["risk_free_rate_3m"],
        dividend_yield=row.get("dividend_yield", 0.0),
        market_cap=row.get("market_cap"),
        cap_bucket=classify_cap(row.get("market_cap")),
        source="cache",
        as_of=cache["_meta"]["as_of"],
    )


def _realized_vol_from_history(hist, window_days: int = 90) -> float:
    closes = hist["Close"].dropna()
    if len(closes) < 10:
        raise ValueError("not enough price history to estimate volatility")
    closes = closes.tail(window_days)
    log_ret = np.log(closes / closes.shift(1)).dropna()
    return float(log_ret.std() * np.sqrt(252))


def _implied_vol_from_options(ticker_obj, spot: float) -> Optional[float]:
    """
    Extract ATM implied volatility from option chain.
    Returns None if unable to fetch or calculate.
    """
    try:
        expiries = ticker_obj.options
        if not expiries or len(expiries) == 0:
            return None

        # Use first expiry (nearest term)
        chain = ticker_obj.option_chain(expiries[0])

        # Get ATM options (within 5% of spot)
        atm_puts = chain.puts[abs(chain.puts['strike'] - spot) < spot * 0.05]
        atm_calls = chain.calls[abs(chain.calls['strike'] - spot) < spot * 0.05]

        # Average implied vols from both puts and calls
        ivs = []
        if not atm_puts.empty:
            put_iv = atm_puts['impliedVolatility'].dropna()
            ivs.extend(put_iv.tolist())
        if not atm_calls.empty:
            call_iv = atm_calls['impliedVolatility'].dropna()
            ivs.extend(call_iv.tolist())

        if len(ivs) == 0:
            return None

        # Return median to avoid outlier influence
        return float(np.median(ivs))
    except Exception:
        return None


def _params_from_yfinance(ticker: str, risk_free_rate: Optional[float]) -> MarketParams:
    import yfinance as yf

    t = yf.Ticker(ticker)
    hist = t.history(period="6mo")
    if hist is None or hist.empty:
        raise ConnectionError(f"empty price history for {ticker}")

    spot = float(hist["Close"].dropna().iloc[-1])

    # Try to get implied volatility from option chain first (more accurate for pricing)
    # Fall back to historical volatility if options data unavailable
    implied_vol = _implied_vol_from_options(t, spot)
    hist_vol = _realized_vol_from_history(hist)

    # Prefer implied vol, but use historical if implied is unavailable or unreasonable
    if implied_vol is not None and 0.05 < implied_vol < 2.0:
        vol = implied_vol
    else:
        vol = hist_vol

    info = {}
    try:
        info = t.info or {}
    except Exception:
        pass

    # yfinance has two dividend yield fields:
    # - "dividendYield": reported as percentage (e.g. 0.34 = 0.34%, not 34%)
    # - "trailingAnnualDividendYield": reported as decimal fraction (e.g. 0.0034 = 0.34%)
    # We use trailingAnnualDividendYield as it's already in the correct format,
    # and fall back to dividendYield/100 if needed.
    dividend_yield = float(info.get("trailingAnnualDividendYield") or 0.0)
    if dividend_yield == 0.0:
        # Fallback: dividendYield is reported as a percentage, so divide by 100
        dividend_yield = float(info.get("dividendYield") or 0.0)
        if dividend_yield > 0.0:
            dividend_yield /= 100.0

    market_cap = info.get("marketCap")

    if risk_free_rate is None:
        try:
            irx = yf.Ticker("^IRX").history(period="5d")
            risk_free_rate = float(irx["Close"].dropna().iloc[-1]) / 100.0
        except Exception:
            risk_free_rate = 0.04  # conservative fallback

    return MarketParams(
        ticker=ticker.upper(),
        spot=spot,
        vol=vol,
        risk_free_rate=risk_free_rate,
        dividend_yield=dividend_yield,
        market_cap=market_cap,
        cap_bucket=classify_cap(market_cap),
        source="live",
        as_of=datetime.utcnow().strftime("%Y-%m-%d"),
    )


def fetch_market_params(ticker: str, risk_free_rate: Optional[float] = None) -> MarketParams:
    """
    Returns calibrated MarketParams for `ticker`. Tries a live yfinance
    pull; falls back to the bundled offline cache on any network/data
    failure so the rest of the pipeline is never blocked.
    """
    try:
        return _params_from_yfinance(ticker, risk_free_rate)
    except Exception as exc:
        warnings.warn(
            f"Live market data pull for '{ticker}' failed ({exc!r}); "
            f"falling back to offline calibration cache "
            f"({_load_cache()['_meta']['as_of']})."
        )
        return _params_from_cache(ticker)


def get_real_option_quote(
    ticker: str, option_type: str = "put", moneyness: float = 1.0, min_days_out: int = 30
) -> Optional[dict]:
    """
    Best-effort pull of a real near-the-money American option quote for
    validation. Returns None (with a warning) if option chain data is
    unavailable -- this is expected in network-restricted environments.
    """
    try:
        import yfinance as yf

        t = yf.Ticker(ticker)
        spot = float(t.history(period="5d")["Close"].dropna().iloc[-1])
        target_strike = spot * moneyness

        expiries = t.options
        if not expiries:
            raise ValueError("no listed expiries")
        today = datetime.utcnow().date()
        chosen_expiry = None
        for exp in expiries:
            exp_date = datetime.strptime(exp, "%Y-%m-%d").date()
            if (exp_date - today).days >= min_days_out:
                chosen_expiry = exp
                break
        chosen_expiry = chosen_expiry or expiries[-1]

        chain = t.option_chain(chosen_expiry)
        table = chain.puts if option_type == "put" else chain.calls
        idx = (table["strike"] - target_strike).abs().idxmin()
        row = table.loc[idx]
        mid = (
            float(row["bid"]) + float(row["ask"])
        ) / 2.0 if row["bid"] and row["ask"] else float(row["lastPrice"])

        return {
            "ticker": ticker.upper(),
            "expiry": chosen_expiry,
            "strike": float(row["strike"]),
            "market_price": mid,
            "bid": float(row["bid"]),
            "ask": float(row["ask"]),
            "last_price": float(row["lastPrice"]),
            "implied_vol": float(row.get("impliedVolatility", np.nan)),
        }
    except Exception as exc:
        warnings.warn(
            f"Could not pull a live option chain quote for '{ticker}' ({exc!r}). "
            f"Skipping market-quote validation for this run."
        )
        return None
