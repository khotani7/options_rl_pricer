"""
Earnings Calendar Filter

Problem: Large losses from earnings surprises
Solution: Skip trades N days before earnings announcements

This filter helps avoid:
- IV crush after earnings
- Large gap moves
- Unpredictable volatility

Usage:
    from strategies.earnings_filter import has_upcoming_earnings

    if has_upcoming_earnings('AAPL', days_ahead=7):
        print("Skipping - earnings in next 7 days")
        continue
"""

import yfinance as yf
from datetime import datetime, timedelta
from typing import Optional
import pandas as pd


def has_upcoming_earnings(ticker: str, days_ahead: int = 7) -> tuple[bool, Optional[datetime]]:
    """
    Check if a ticker has earnings announcement in the next N days

    Args:
        ticker: Stock ticker symbol
        days_ahead: Number of days to look ahead (default: 7)

    Returns:
        (has_earnings, earnings_date)
            has_earnings: True if earnings within days_ahead
            earnings_date: Date of next earnings (None if not found)
    """

    try:
        stock = yf.Ticker(ticker)

        # Get earnings calendar (yfinance returns dict now)
        calendar = stock.calendar

        if calendar is None or (isinstance(calendar, dict) and len(calendar) == 0):
            # No earnings data available - allow trade but warn
            print(f"  ⚠️  No earnings data for {ticker} - proceeding with caution")
            return False, None

        # Handle dict format (new yfinance API)
        if isinstance(calendar, dict):
            if 'Earnings Date' in calendar:
                earnings_dates = calendar['Earnings Date']

                # Handle list of dates
                if isinstance(earnings_dates, list) and len(earnings_dates) > 0:
                    next_earnings = earnings_dates[0]
                else:
                    next_earnings = earnings_dates

            else:
                return False, None
        # Handle DataFrame format (old yfinance API)
        elif hasattr(calendar, 'index') and 'Earnings Date' in calendar.index:
            earnings_dates = calendar.loc['Earnings Date']
            next_earnings = earnings_dates.iloc[0] if isinstance(earnings_dates, pd.Series) else earnings_dates
        else:
            return False, None

        # Convert to datetime if needed
        if isinstance(next_earnings, str):
            next_earnings = pd.to_datetime(next_earnings)
        elif not isinstance(next_earnings, (datetime, pd.Timestamp)):
            return False, None

        # Check if earnings is within the lookahead window
        today = datetime.now()
        days_until = (next_earnings - today).days

        if 0 <= days_until <= days_ahead:
            return True, next_earnings

        return False, next_earnings

    except Exception as e:
        # If we can't get earnings data, err on the side of caution
        print(f"  ⚠️  Error fetching earnings for {ticker}: {e}")
        return False, None


def get_earnings_info(ticker: str) -> dict:
    """
    Get detailed earnings information for a ticker

    Returns:
        dict with:
            - next_earnings_date
            - days_until_earnings
            - previous_earnings_date
            - earnings_history (last 4 quarters)
    """

    try:
        stock = yf.Ticker(ticker)

        info = {
            'next_earnings_date': None,
            'days_until_earnings': None,
            'previous_earnings_date': None,
            'earnings_history': None
        }

        # Get calendar (handle both dict and DataFrame formats)
        calendar = stock.calendar
        if calendar is not None:
            # Handle dict format (new yfinance API)
            if isinstance(calendar, dict) and 'Earnings Date' in calendar:
                earnings_dates = calendar['Earnings Date']

                if isinstance(earnings_dates, list) and len(earnings_dates) > 0:
                    info['next_earnings_date'] = earnings_dates[0]
                else:
                    info['next_earnings_date'] = earnings_dates

                today = pd.Timestamp.now()
                if isinstance(info['next_earnings_date'], str):
                    info['next_earnings_date'] = pd.to_datetime(info['next_earnings_date'])
                elif hasattr(info['next_earnings_date'], 'date'):
                    # Convert date to Timestamp for consistent comparison
                    info['next_earnings_date'] = pd.Timestamp(info['next_earnings_date'])

                if info['next_earnings_date']:
                    info['days_until_earnings'] = (info['next_earnings_date'] - today).days

            # Handle DataFrame format (old yfinance API)
            elif hasattr(calendar, 'index') and 'Earnings Date' in calendar.index:
                earnings_dates = calendar.loc['Earnings Date']

                if isinstance(earnings_dates, pd.Series) and len(earnings_dates) > 0:
                    info['next_earnings_date'] = earnings_dates.iloc[0]

                    today = datetime.now()
                    if isinstance(info['next_earnings_date'], str):
                        info['next_earnings_date'] = pd.to_datetime(info['next_earnings_date'])

                    info['days_until_earnings'] = (info['next_earnings_date'] - today).days

        # Get earnings history
        try:
            earnings_history = stock.earnings_dates
            if earnings_history is not None and not earnings_history.empty:
                info['earnings_history'] = earnings_history.head(4)
        except:
            pass

        return info

    except Exception as e:
        print(f"Error getting earnings info for {ticker}: {e}")
        return {}


def calculate_earnings_risk_score(ticker: str) -> float:
    """
    Calculate a risk score (0-10) based on proximity to earnings

    0 = Safe (no earnings soon)
    10 = Very risky (earnings imminent)

    Args:
        ticker: Stock ticker

    Returns:
        Risk score 0-10
    """

    has_earnings, earnings_date = has_upcoming_earnings(ticker, days_ahead=14)

    if not has_earnings or earnings_date is None:
        return 0.0  # No risk

    today = datetime.now()
    days_until = (earnings_date - today).days

    if days_until < 0:
        return 0.0  # Earnings already passed
    elif days_until <= 1:
        return 10.0  # Earnings tomorrow or today - VERY risky
    elif days_until <= 3:
        return 8.0  # Earnings in 2-3 days - very risky
    elif days_until <= 7:
        return 6.0  # Earnings in a week - risky
    elif days_until <= 14:
        return 3.0  # Earnings in 2 weeks - moderate risk
    else:
        return 0.0  # Safe


# Example usage
if __name__ == "__main__":
    print("=" * 70)
    print("EARNINGS CALENDAR FILTER")
    print("=" * 70)

    test_tickers = ['AAPL', 'NVDA', 'TSLA', 'MSFT', 'META']

    print(f"\n{'Ticker':<10} {'Has Earnings?':<15} {'Days Until':<12} {'Risk Score':<12}")
    print("-" * 70)

    for ticker in test_tickers:
        has_earnings, earnings_date = has_upcoming_earnings(ticker, days_ahead=14)
        risk_score = calculate_earnings_risk_score(ticker)

        if has_earnings and earnings_date:
            days_until = (earnings_date - datetime.now()).days
            print(f"{ticker:<10} {'YES':<15} {days_until:<12} {risk_score:<12.1f}")
        else:
            print(f"{ticker:<10} {'NO':<15} {'N/A':<12} {risk_score:<12.1f}")

    print("\n" + "=" * 70)
    print("DETAILED EARNINGS INFO - AAPL")
    print("=" * 70)

    info = get_earnings_info('AAPL')

    print(f"\nNext Earnings: {info.get('next_earnings_date')}")
    print(f"Days Until: {info.get('days_until_earnings')}")

    if info.get('earnings_history') is not None:
        print("\nRecent Earnings History:")
        print(info['earnings_history'])

    print("\n" + "=" * 70)
    print("USAGE IN EDGE SCANNER")
    print("=" * 70)
    print("""
# In your edge scanner loop:

from strategies.earnings_filter import has_upcoming_earnings, calculate_earnings_risk_score

for ticker in tickers:
    # Check earnings filter
    has_earnings, earnings_date = has_upcoming_earnings(ticker, days_ahead=7)

    if has_earnings:
        print(f"⊗ Skipping {ticker} - earnings on {earnings_date.strftime('%Y-%m-%d')}")
        continue

    # Alternative: Use risk score
    risk_score = calculate_earnings_risk_score(ticker)
    if risk_score >= 6.0:
        print(f"⊗ Skipping {ticker} - earnings risk too high ({risk_score:.1f}/10)")
        continue

    # Safe to scan for edges
    scan_for_edges(ticker)
    """)
