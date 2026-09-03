"""
Vertical Spreads Strategy - Defined Risk Options Trading

A vertical spread consists of buying and selling options of the same type (both calls or both puts)
with different strike prices but the same expiration date.

Types:
1. Bull Put Spread: Sell higher strike put, buy lower strike put (credit spread)
2. Bear Call Spread: Sell lower strike call, buy higher strike call (credit spread)
3. Bull Call Spread: Buy lower strike call, sell higher strike call (debit spread)
4. Bear Put Spread: Buy higher strike put, sell lower strike put (debit spread)

Benefits vs. Naked Options:
- Defined maximum loss (buy option caps risk)
- Lower margin requirements
- Higher win rate (wider profitable range)
- Better risk/reward ratio
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from dataclasses import dataclass
from typing import Tuple, Optional
import numpy as np
from pricing.lsm import lsm_american_option

@dataclass
class VerticalSpread:
    """Vertical spread position"""
    ticker: str
    spread_type: str  # 'bull_put', 'bear_call', 'bull_call', 'bear_put'
    sell_strike: float
    buy_strike: float
    expiry: str  # YYYYMMDD format
    sell_premium: float
    buy_premium: float
    quantity: int = 1

    @property
    def net_credit(self) -> float:
        """Net credit received (for credit spreads)"""
        return (self.sell_premium - self.buy_premium) * 100 * self.quantity

    @property
    def max_profit(self) -> float:
        """Maximum profit possible"""
        if self.spread_type in ['bull_put', 'bear_call']:
            # Credit spreads: max profit = net credit
            return self.net_credit
        else:
            # Debit spreads: max profit = strike difference - net debit
            strike_diff = abs(self.sell_strike - self.buy_strike) * 100 * self.quantity
            return strike_diff - abs(self.net_credit)

    @property
    def max_loss(self) -> float:
        """Maximum loss possible"""
        strike_diff = abs(self.sell_strike - self.buy_strike) * 100 * self.quantity

        if self.spread_type in ['bull_put', 'bear_call']:
            # Credit spreads: max loss = strike difference - net credit
            return strike_diff - self.net_credit
        else:
            # Debit spreads: max loss = net debit
            return abs(self.net_credit)

    @property
    def risk_reward_ratio(self) -> float:
        """Risk/reward ratio"""
        if self.max_profit == 0:
            return float('inf')
        return self.max_loss / self.max_profit

    @property
    def breakeven(self) -> float:
        """Breakeven price at expiration"""
        if self.spread_type == 'bull_put':
            # Breakeven = sell strike - net credit
            return self.sell_strike - (self.net_credit / (100 * self.quantity))
        elif self.spread_type == 'bear_call':
            # Breakeven = sell strike + net credit
            return self.sell_strike + (self.net_credit / (100 * self.quantity))
        elif self.spread_type == 'bull_call':
            # Breakeven = buy strike + net debit
            return self.buy_strike + (abs(self.net_credit) / (100 * self.quantity))
        else:  # bear_put
            # Breakeven = buy strike - net debit
            return self.buy_strike - (abs(self.net_credit) / (100 * self.quantity))


def find_vertical_spread_opportunity(
    ticker: str,
    spot_price: float,
    r: float,
    q: float,
    sigma: float,
    expiry_days: int,
    option_type: str = 'put',
    spread_width: float = 5.0,
    min_credit: float = 0.30
) -> Optional[VerticalSpread]:
    """
    Find vertical spread opportunities using LSM pricing

    Args:
        ticker: Stock ticker
        spot_price: Current stock price
        r: Risk-free rate
        q: Dividend yield
        sigma: Volatility
        expiry_days: Days to expiration
        option_type: 'call' or 'put'
        spread_width: Strike price difference ($5 or $10 typical)
        min_credit: Minimum net credit required (as fraction of spread width)

    Returns:
        VerticalSpread if opportunity found, None otherwise
    """

    T = expiry_days / 365.0

    if option_type == 'put':
        # Bull put spread: Sell ATM put, buy OTM put
        # Bullish strategy - profit if stock stays above sell strike

        sell_strike = spot_price * 0.98  # Slightly OTM (2% below spot)
        buy_strike = sell_strike - spread_width

        # Price both options with LSM
        sell_price, sell_std = lsm_american_option(
            S0=spot_price, K=sell_strike, T=T, r=r, q=q,
            sigma=sigma, option_type='put', n_paths=10000
        )

        buy_price, buy_std = lsm_american_option(
            S0=spot_price, K=buy_strike, T=T, r=r, q=q,
            sigma=sigma, option_type='put', n_paths=10000
        )

        net_credit = sell_price - buy_price
        min_credit_required = spread_width * min_credit

        if net_credit >= min_credit_required:
            spread = VerticalSpread(
                ticker=ticker,
                spread_type='bull_put',
                sell_strike=sell_strike,
                buy_strike=buy_strike,
                expiry=f"exp_{expiry_days}d",
                sell_premium=sell_price,
                buy_premium=buy_price,
                quantity=1
            )
            return spread

    else:  # call
        # Bear call spread: Sell OTM call, buy further OTM call
        # Bearish/neutral strategy - profit if stock stays below sell strike

        sell_strike = spot_price * 1.02  # Slightly OTM (2% above spot)
        buy_strike = sell_strike + spread_width

        sell_price, sell_std = lsm_american_option(
            S0=spot_price, K=sell_strike, T=T, r=r, q=q,
            sigma=sigma, option_type='call', n_paths=10000
        )

        buy_price, buy_std = lsm_american_option(
            S0=spot_price, K=buy_strike, T=T, r=r, q=q,
            sigma=sigma, option_type='call', n_paths=10000
        )

        net_credit = sell_price - buy_price
        min_credit_required = spread_width * min_credit

        if net_credit >= min_credit_required:
            spread = VerticalSpread(
                ticker=ticker,
                spread_type='bear_call',
                sell_strike=sell_strike,
                buy_strike=buy_strike,
                expiry=f"exp_{expiry_days}d",
                sell_premium=sell_price,
                buy_premium=buy_price,
                quantity=1
            )
            return spread

    return None


def calculate_spread_greeks(spread: VerticalSpread, spot_price: float) -> dict:
    """
    Calculate approximate Greeks for vertical spread

    Simplified approach - real implementation would need proper Greek calculation
    """

    # For credit spreads (bull put, bear call):
    # - Max profit at expiry if spot is beyond both strikes
    # - Max loss if spot is between strikes or beyond buy strike

    if spread.spread_type == 'bull_put':
        # Profitable if spot > sell_strike
        if spot_price > spread.sell_strike:
            prob_profit = 0.80  # High probability
        elif spot_price > spread.buy_strike:
            prob_profit = 0.50  # Break even range
        else:
            prob_profit = 0.20  # Low probability

    elif spread.spread_type == 'bear_call':
        # Profitable if spot < sell_strike
        if spot_price < spread.sell_strike:
            prob_profit = 0.80
        elif spot_price < spread.buy_strike:
            prob_profit = 0.50
        else:
            prob_profit = 0.20

    else:
        prob_profit = 0.50  # Debit spreads - simplified

    return {
        'probability_profit': prob_profit,
        'delta': 0.0,  # Simplified - vertical spreads are often delta-neutral
        'theta': spread.net_credit / 30,  # Credit decay per day (simplified)
        'vega': 0.0,  # Simplified - spreads have low vega
    }


def compare_naked_vs_spread(
    ticker: str,
    spot_price: float,
    strike: float,
    premium: float,
    spread: Optional[VerticalSpread]
) -> dict:
    """Compare naked option vs vertical spread"""

    naked_max_profit = premium * 100
    naked_max_loss = (strike - premium) * 100  # For puts

    comparison = {
        'naked': {
            'max_profit': naked_max_profit,
            'max_loss': naked_max_loss,
            'risk_reward': naked_max_loss / naked_max_profit if naked_max_profit > 0 else float('inf'),
            'margin_required': strike * 100 * 0.20,  # ~20% margin requirement
        }
    }

    if spread:
        comparison['spread'] = {
            'max_profit': spread.max_profit,
            'max_loss': spread.max_loss,
            'risk_reward': spread.risk_reward_ratio,
            'margin_required': spread.max_loss,  # Spread margin = max loss
        }

        comparison['improvement'] = {
            'risk_reduction': (1 - spread.max_loss / naked_max_loss) * 100,
            'margin_reduction': (1 - spread.max_loss / comparison['naked']['margin_required']) * 100,
            'profit_reduction': (1 - spread.max_profit / naked_max_profit) * 100,
        }

    return comparison


# Example usage
if __name__ == "__main__":
    # Find a bull put spread opportunity
    spread = find_vertical_spread_opportunity(
        ticker='AAPL',
        spot_price=220.0,
        r=0.04,
        q=0.005,
        sigma=0.25,
        expiry_days=30,
        option_type='put',
        spread_width=5.0,
        min_credit=0.30
    )

    if spread:
        print(f"\n{'=' * 70}")
        print(f"VERTICAL SPREAD OPPORTUNITY: {spread.ticker}")
        print(f"{'=' * 70}\n")
        print(f"Strategy: {spread.spread_type.upper().replace('_', ' ')}")
        print(f"Sell: PUT ${spread.sell_strike:.2f} @ ${spread.sell_premium:.2f}")
        print(f"Buy:  PUT ${spread.buy_strike:.2f} @ ${spread.buy_premium:.2f}")
        print(f"\nNet Credit: ${spread.net_credit:.2f}")
        print(f"Max Profit: ${spread.max_profit:.2f}")
        print(f"Max Loss: ${spread.max_loss:.2f}")
        print(f"Risk/Reward: {spread.risk_reward_ratio:.2f}")
        print(f"Breakeven: ${spread.breakeven:.2f}")
        print(f"\nProbability of Profit: ~70-80% (if stock stays above ${spread.breakeven:.2f})")
        print(f"{'=' * 70}\n")

        # Compare to naked put
        comparison = compare_naked_vs_spread(
            ticker='AAPL',
            spot_price=220.0,
            strike=spread.sell_strike,
            premium=spread.sell_premium,
            spread=spread
        )

        print("NAKED PUT vs VERTICAL SPREAD:")
        print(f"Risk Reduction: {comparison['improvement']['risk_reduction']:.1f}%")
        print(f"Margin Reduction: {comparison['improvement']['margin_reduction']:.1f}%")
        print(f"Profit Reduction: {comparison['improvement']['profit_reduction']:.1f}%")
    else:
        print("No spread opportunity found with current criteria")
