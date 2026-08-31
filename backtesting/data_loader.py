"""
Historical options data loader for backtesting

Since real historical options data is expensive, this module:
1. Uses yfinance for recent live data (free)
2. Simulates historical options using Black-Scholes + realized vol
3. Can integrate with paid data sources (CBOE, OptionMetrics) later
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from scipy.stats import norm


class HistoricalOptionsData:
    """Load and manage historical options data"""

    def __init__(self, ticker: str):
        self.ticker = ticker
        self.stock_data = None
        self.options_data = {}

    def load_stock_history(self, start_date: str, end_date: str) -> pd.DataFrame:
        """Load historical stock prices"""
        t = yf.Ticker(self.ticker)
        hist = t.history(start=start_date, end=end_date)

        if hist.empty:
            raise ValueError(f"No stock data for {self.ticker} from {start_date} to {end_date}")

        self.stock_data = hist
        return hist

    def calculate_realized_vol(self, window: int = 30) -> pd.Series:
        """Calculate rolling realized volatility"""
        if self.stock_data is None:
            raise ValueError("Load stock history first")

        log_returns = np.log(self.stock_data['Close'] / self.stock_data['Close'].shift(1))
        realized_vol = log_returns.rolling(window).std() * np.sqrt(252)
        return realized_vol

    def estimate_dividend_yield(self) -> float:
        """Estimate dividend yield from stock data"""
        try:
            t = yf.Ticker(self.ticker)
            info = t.info
            div_yield = info.get('trailingAnnualDividendYield', 0.0)
            return div_yield if div_yield else 0.0
        except:
            return 0.0

    def bs_option_price(self, S: float, K: float, T: float, r: float, q: float,
                        sigma: float, option_type: str = 'put') -> Dict[str, float]:
        """
        Calculate Black-Scholes option price and Greeks

        Returns dict with: price, delta, gamma, theta, vega
        """
        if T <= 0:
            intrinsic = max(K - S, 0) if option_type == 'put' else max(S - K, 0)
            return {
                'price': intrinsic,
                'delta': -1.0 if (option_type == 'put' and S < K) else (1.0 if (option_type == 'call' and S > K) else 0.0),
                'gamma': 0.0,
                'theta': 0.0,
                'vega': 0.0,
                'bid': intrinsic * 0.98,
                'ask': intrinsic * 1.02,
                'mid': intrinsic
            }

        if sigma <= 0:
            sigma = 0.01  # Prevent division by zero

        d1 = (np.log(S/K) + (r - q + 0.5*sigma**2)*T) / (sigma*np.sqrt(T))
        d2 = d1 - sigma*np.sqrt(T)

        if option_type == 'put':
            price = K*np.exp(-r*T)*norm.cdf(-d2) - S*np.exp(-q*T)*norm.cdf(-d1)
            delta = -np.exp(-q*T)*norm.cdf(-d1)
        else:  # call
            price = S*np.exp(-q*T)*norm.cdf(d1) - K*np.exp(-r*T)*norm.cdf(d2)
            delta = np.exp(-q*T)*norm.cdf(d1)

        gamma = np.exp(-q*T)*norm.pdf(d1) / (S*sigma*np.sqrt(T))
        theta = (-S*norm.pdf(d1)*sigma*np.exp(-q*T)/(2*np.sqrt(T))
                 - r*K*np.exp(-r*T)*norm.cdf(d2 if option_type == 'call' else -d2)
                 + q*S*np.exp(-q*T)*norm.cdf(d1 if option_type == 'call' else -d1))
        vega = S*np.exp(-q*T)*norm.pdf(d1)*np.sqrt(T)

        # Simulate bid-ask spread (1-3% of mid for liquid options)
        spread_pct = 0.02  # 2% spread
        bid = price * (1 - spread_pct)
        ask = price * (1 + spread_pct)

        return {
            'price': price,
            'delta': delta,
            'gamma': gamma,
            'theta': theta,
            'vega': vega,
            'bid': bid,
            'ask': ask,
            'mid': price
        }

    def simulate_option_chain(self, date: datetime, strikes: List[float],
                             maturity_days: int = 30, risk_free_rate: float = 0.04,
                             option_type: str = 'put') -> pd.DataFrame:
        """
        Simulate option chain for a given date using Black-Scholes

        In production, replace this with real historical options data
        """
        if self.stock_data is None:
            raise ValueError("Load stock history first")

        # Get stock price on that date
        date_str = date.strftime('%Y-%m-%d')
        if date_str not in self.stock_data.index:
            # Find nearest date
            nearest_idx = self.stock_data.index.get_indexer([date], method='nearest')[0]
            spot = self.stock_data['Close'].iloc[nearest_idx]
            actual_date = self.stock_data.index[nearest_idx]
        else:
            spot = self.stock_data.loc[date_str, 'Close']
            actual_date = date

        # Calculate realized vol
        vol_series = self.calculate_realized_vol(window=30)
        vol = vol_series.loc[actual_date] if actual_date in vol_series.index else 0.30

        # Get dividend yield
        div_yield = self.estimate_dividend_yield()

        # Time to maturity
        T = maturity_days / 365.0

        # Simulate options for each strike
        chain_data = []
        for K in strikes:
            option = self.bs_option_price(spot, K, T, risk_free_rate, div_yield, vol, option_type)

            chain_data.append({
                'date': actual_date,
                'strike': K,
                'maturity_days': maturity_days,
                'spot': spot,
                'option_type': option_type,
                'bid': option['bid'],
                'ask': option['ask'],
                'mid': option['mid'],
                'delta': option['delta'],
                'gamma': option['gamma'],
                'theta': option['theta'],
                'vega': option['vega'],
                'iv': vol,
                'volume': 100,  # Simulated
                'open_interest': 1000  # Simulated
            })

        return pd.DataFrame(chain_data)

    def load_current_options(self) -> Dict[str, pd.DataFrame]:
        """Load current live options data from yfinance"""
        t = yf.Ticker(self.ticker)
        expiries = t.options

        chains = {}
        for expiry in expiries[:5]:  # First 5 expiries
            try:
                chain = t.option_chain(expiry)
                chains[expiry] = {
                    'puts': chain.puts,
                    'calls': chain.calls
                }
            except:
                continue

        return chains

    def get_option_quote(self, date: datetime, strike: float, maturity_days: int,
                        option_type: str = 'put') -> Optional[Dict]:
        """
        Get option quote for specific parameters

        Returns None if data not available
        """
        # For now, simulate using BS
        # In production, look up in historical database
        chain = self.simulate_option_chain(date, [strike], maturity_days, option_type=option_type)

        if chain.empty:
            return None

        return chain.iloc[0].to_dict()


class BacktestDataProvider:
    """
    Provides historical market data for backtesting

    In production, integrate with:
    - OptionMetrics (academic/institutional)
    - CBOE DataShop (exchange data)
    - Polygon.io (retail API)
    """

    def __init__(self, tickers: List[str], start_date: str, end_date: str):
        self.tickers = tickers
        self.start_date = start_date
        self.end_date = end_date
        self.data = {}

        for ticker in tickers:
            self.data[ticker] = HistoricalOptionsData(ticker)

    def load_all_data(self):
        """Load historical data for all tickers"""
        for ticker, loader in self.data.items():
            print(f"Loading data for {ticker}...")
            loader.load_stock_history(self.start_date, self.end_date)

    def get_trading_dates(self) -> pd.DatetimeIndex:
        """Get all trading dates in the backtest period"""
        # Use first ticker's data
        first_ticker = list(self.data.keys())[0]
        return self.data[first_ticker].stock_data.index

    def get_stock_price(self, ticker: str, date: datetime) -> float:
        """Get stock price on a specific date"""
        data = self.data[ticker].stock_data
        date_str = date.strftime('%Y-%m-%d')

        if date_str in data.index:
            return data.loc[date_str, 'Close']
        else:
            # Find nearest date
            nearest_idx = data.index.get_indexer([date], method='nearest')[0]
            return data['Close'].iloc[nearest_idx]

    def get_option_quote(self, ticker: str, date: datetime, strike: float,
                        maturity_days: int, option_type: str = 'put') -> Optional[Dict]:
        """Get option quote for backtesting"""
        return self.data[ticker].get_option_quote(date, strike, maturity_days, option_type)
