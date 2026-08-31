"""
Analyze stress test results and generate insights

Usage:
    python analyze_stress_test.py
"""

import pandas as pd
import numpy as np
import json
from datetime import datetime


def load_results():
    """Load stress test results"""
    try:
        df = pd.read_csv('outputs/stress_test/all_scenarios.csv')
        return df
    except FileNotFoundError:
        print("No stress test results found. Run stress_test.py first.")
        return None


def analyze_by_market_condition(df):
    """Analyze performance by market regime"""
    print("\n" + "="*70)
    print("ANALYSIS: Performance by Market Condition")
    print("="*70)

    # Identify market condition scenarios
    market_scenarios = df[df['scenario'].str.contains('Market|COVID|Recent|Sideways', case=False, na=False)]

    if len(market_scenarios) > 0:
        print(f"\n{'Scenario':<30} {'Return':<12} {'Trades':<8} {'Win Rate':<10} {'Sharpe':<8}")
        print("-" * 70)

        for _, row in market_scenarios.iterrows():
            scenario = row['scenario'][:28]
            ret = f"{row.get('total_return_pct', 0):.2f}%"
            trades = int(row.get('total_trades', 0))
            win_rate = f"{row.get('win_rate_pct', 0):.1f}%" if 'win_rate_pct' in row else 'N/A'
            sharpe = f"{row.get('sharpe_ratio', 0):.2f}" if 'sharpe_ratio' in row else 'N/A'

            print(f"{scenario:<30} {ret:<12} {trades:<8} {win_rate:<10} {sharpe:<8}")

        print("\n--- Key Insights ---")
        bull = market_scenarios[market_scenarios['scenario'].str.contains('Bull', case=False, na=False)]
        bear = market_scenarios[market_scenarios['scenario'].str.contains('Bear', case=False, na=False)]
        crash = market_scenarios[market_scenarios['scenario'].str.contains('Crash', case=False, na=False)]

        if len(bull) > 0:
            print(f"Bull Market Avg Return: {bull['total_return_pct'].mean():.2f}%")
        if len(bear) > 0:
            print(f"Bear Market Avg Return: {bear['total_return_pct'].mean():.2f}%")
        if len(crash) > 0:
            print(f"Crash Scenario Avg Return: {crash['total_return_pct'].mean():.2f}%")


def analyze_parameter_sensitivity(df):
    """Analyze parameter sensitivity"""
    print("\n" + "="*70)
    print("ANALYSIS: Parameter Sensitivity")
    print("="*70)

    # Edge threshold sensitivity
    edge_scenarios = df[df['scenario'].str.contains('Edge Threshold', case=False, na=False)]
    if len(edge_scenarios) > 0:
        print("\n--- Edge Threshold Impact ---")
        print(f"{'Threshold':<15} {'Return':<12} {'Trades':<10} {'Sharpe':<10}")
        print("-" * 50)
        for _, row in edge_scenarios.sort_values('edge_threshold').iterrows():
            threshold = f"{row['edge_threshold']:.1f}%"
            ret = f"{row.get('total_return_pct', 0):.2f}%"
            trades = int(row.get('total_trades', 0))
            sharpe = f"{row.get('sharpe_ratio', 0):.2f}" if 'sharpe_ratio' in row else 'N/A'
            print(f"{threshold:<15} {ret:<12} {trades:<10} {sharpe:<10}")

    # Position sizing sensitivity
    pos_scenarios = df[df['scenario'].str.contains('Max Positions', case=False, na=False)]
    if len(pos_scenarios) > 0:
        print("\n--- Position Sizing Impact ---")
        print(f"{'Max Positions':<15} {'Return':<12} {'Trades':<10} {'Sharpe':<10}")
        print("-" * 50)
        for _, row in pos_scenarios.sort_values('max_positions').iterrows():
            positions = int(row['max_positions'])
            ret = f"{row.get('total_return_pct', 0):.2f}%"
            trades = int(row.get('total_trades', 0))
            sharpe = f"{row.get('sharpe_ratio', 0):.2f}" if 'sharpe_ratio' in row else 'N/A'
            print(f"{positions:<15} {ret:<12} {trades:<10} {sharpe:<10}")

    # Maturity sensitivity
    mat_scenarios = df[df['scenario'].str.contains('Maturity', case=False, na=False)]
    if len(mat_scenarios) > 0:
        print("\n--- Maturity Impact ---")
        print(f"{'Maturity (days)':<15} {'Return':<12} {'Trades':<10} {'Sharpe':<10}")
        print("-" * 50)
        for _, row in mat_scenarios.sort_values('maturity_days').iterrows():
            maturity = int(row['maturity_days'])
            ret = f"{row.get('total_return_pct', 0):.2f}%"
            trades = int(row.get('total_trades', 0))
            sharpe = f"{row.get('sharpe_ratio', 0):.2f}" if 'sharpe_ratio' in row else 'N/A'
            print(f"{maturity:<15} {ret:<12} {trades:<10} {sharpe:<10}")


def analyze_diversification(df):
    """Analyze diversification impact"""
    print("\n" + "="*70)
    print("ANALYSIS: Diversification Impact")
    print("="*70)

    ticker_scenarios = df[df['scenario'].str.contains('Ticker|Tech|Diversified', case=False, na=False)]

    if len(ticker_scenarios) > 0:
        print(f"\n{'Strategy':<30} {'Return':<12} {'Trades':<10} {'Sharpe':<10}")
        print("-" * 65)

        for _, row in ticker_scenarios.iterrows():
            strategy = row['scenario'][:28]
            ret = f"{row.get('total_return_pct', 0):.2f}%"
            trades = int(row.get('total_trades', 0))
            sharpe = f"{row.get('sharpe_ratio', 0):.2f}" if 'sharpe_ratio' in row else 'N/A'

            print(f"{strategy:<30} {ret:<12} {trades:<10} {sharpe:<10}")


def identify_risk_factors(df):
    """Identify key risk factors"""
    print("\n" + "="*70)
    print("RISK ANALYSIS")
    print("="*70)

    successful = df[df['total_trades'] > 0].copy()

    if len(successful) == 0:
        print("No successful backtests to analyze")
        return

    print("\n--- Scenarios with Losses ---")
    losses = successful[successful['total_return_pct'] < 0]
    if len(losses) > 0:
        print(f"Number of losing scenarios: {len(losses)}/{len(successful)} ({len(losses)/len(successful)*100:.1f}%)")
        print(f"\nWorst losses:")
        worst = losses.nsmallest(5, 'total_return_pct')[['scenario', 'total_return_pct', 'max_drawdown_pct', 'win_rate_pct']]
        print(worst.to_string(index=False))
    else:
        print("✓ No losing scenarios detected")

    print("\n--- High Drawdown Scenarios ---")
    if 'max_drawdown_pct' in successful.columns:
        high_dd = successful[successful['max_drawdown_pct'] > 10]
        if len(high_dd) > 0:
            print(f"Scenarios with >10% drawdown: {len(high_dd)}/{len(successful)}")
            print(f"\nHighest drawdowns:")
            worst_dd = high_dd.nlargest(5, 'max_drawdown_pct')[['scenario', 'total_return_pct', 'max_drawdown_pct']]
            print(worst_dd.to_string(index=False))
        else:
            print("✓ No scenarios with >10% drawdown")

    print("\n--- Low Win Rate Scenarios ---")
    if 'win_rate_pct' in successful.columns:
        low_wr = successful[successful['win_rate_pct'] < 60]
        if len(low_wr) > 0:
            print(f"Scenarios with <60% win rate: {len(low_wr)}/{len(successful)}")
            print(f"\nLowest win rates:")
            worst_wr = low_wr.nsmallest(5, 'win_rate_pct')[['scenario', 'win_rate_pct', 'total_return_pct']]
            print(worst_wr.to_string(index=False))
        else:
            print("✓ All scenarios have ≥60% win rate")


def generate_recommendations(df):
    """Generate recommendations based on stress test results"""
    print("\n" + "="*70)
    print("RECOMMENDATIONS")
    print("="*70)

    successful = df[df['total_trades'] > 0].copy()

    if len(successful) == 0:
        print("Insufficient data for recommendations")
        return

    print("\n--- Optimal Parameters ---")

    # Find best edge threshold
    edge_scenarios = successful[successful['scenario'].str.contains('Edge Threshold', na=False)]
    if len(edge_scenarios) > 0:
        best_edge = edge_scenarios.loc[edge_scenarios['total_return_pct'].idxmax()]
        print(f"Best Edge Threshold: {best_edge['edge_threshold']:.1f}% (Return: {best_edge['total_return_pct']:.2f}%)")

    # Find best position size
    pos_scenarios = successful[successful['scenario'].str.contains('Max Positions', na=False)]
    if len(pos_scenarios) > 0:
        best_pos = pos_scenarios.loc[pos_scenarios['total_return_pct'].idxmax()]
        print(f"Best Max Positions: {int(best_pos['max_positions'])} (Return: {best_pos['total_return_pct']:.2f}%)")

    # Find best maturity
    mat_scenarios = successful[successful['scenario'].str.contains('Maturity', na=False)]
    if len(mat_scenarios) > 0:
        best_mat = mat_scenarios.loc[mat_scenarios['total_return_pct'].idxmax()]
        print(f"Best Maturity: {int(best_mat['maturity_days'])} days (Return: {best_mat['total_return_pct']:.2f}%)")

    print("\n--- Risk-Adjusted Best Practices ---")
    if 'sharpe_ratio' in successful.columns:
        high_sharpe = successful[successful['sharpe_ratio'] > 1.5]
        if len(high_sharpe) > 0:
            print(f"Scenarios with Sharpe >1.5: {len(high_sharpe)}")
            print(f"Average return: {high_sharpe['total_return_pct'].mean():.2f}%")

            # Common characteristics
            if 'edge_threshold' in high_sharpe.columns:
                print(f"Average edge threshold: {high_sharpe['edge_threshold'].mean():.1f}%")
            if 'max_positions' in high_sharpe.columns:
                print(f"Average max positions: {high_sharpe['max_positions'].mean():.0f}")

    print("\n--- Market Condition Recommendations ---")
    # Check bull vs bear performance
    bull = successful[successful['scenario'].str.contains('Bull', na=False)]
    bear = successful[successful['scenario'].str.contains('Bear', na=False)]

    if len(bull) > 0 and len(bear) > 0:
        bull_avg = bull['total_return_pct'].mean()
        bear_avg = bear['total_return_pct'].mean()

        if bull_avg > bear_avg * 2:
            print("⚠️  Strategy performs much better in bull markets")
            print("   Recommendation: Reduce position size or edge threshold in bear markets")
        elif bear_avg < 0:
            print("⚠️  Strategy loses money in bear markets")
            print("   Recommendation: Consider market regime filter or hedging")
        else:
            print("✓ Strategy works in both bull and bear markets")


def main():
    df = load_results()
    if df is None:
        return

    print("\n" + "="*70)
    print("STRESS TEST ANALYSIS")
    print("="*70)
    print(f"Loaded {len(df)} scenarios")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Run all analyses
    analyze_by_market_condition(df)
    analyze_parameter_sensitivity(df)
    analyze_diversification(df)
    identify_risk_factors(df)
    generate_recommendations(df)

    print("\n" + "="*70)
    print("Analysis complete!")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
