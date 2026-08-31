"""
Comprehensive Stress Testing for Options Trading Strategy

Tests the LSM arbitrage strategy across:
- Different time periods (bull, bear, sideways, volatile markets)
- Multiple tickers (tech, energy, finance, different sectors)
- Various parameter settings (edge thresholds, position sizes, maturities)
- Extreme market conditions (crashes, rallies, high volatility)

Usage:
    python stress_test.py --mode all
    python stress_test.py --mode market_conditions
    python stress_test.py --mode parameter_sweep
    python stress_test.py --mode multi_ticker
"""

import argparse
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import os
from typing import List, Dict, Tuple

from backtesting.data_loader import BacktestDataProvider
from backtesting.engine import BacktestEngine, BacktestConfig
from backtesting.strategies import LSMArbitrageStrategy


class StressTester:
    """Comprehensive stress testing framework"""

    def __init__(self, output_dir: str = "outputs/stress_test"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self.results = []

    def run_single_backtest(self,
                          tickers: List[str],
                          start_date: str,
                          end_date: str,
                          capital: float,
                          edge_threshold: float,
                          max_positions: int,
                          maturity_days: int,
                          scenario_name: str) -> Dict:
        """Run a single backtest and return results"""

        print(f"\n{'='*70}")
        print(f"Scenario: {scenario_name}")
        print(f"Tickers: {tickers}")
        print(f"Period: {start_date} to {end_date}")
        print(f"Edge threshold: {edge_threshold}% | Max positions: {max_positions}")
        print(f"{'='*70}")

        try:
            # Load data
            data_provider = BacktestDataProvider(tickers, start_date, end_date)
            data_provider.load_all_data()

            # Configure backtest
            config = BacktestConfig(
                initial_capital=capital,
                commission_per_contract=0.65,
                slippage_bps=10  # 10 basis points = 0.1%
            )

            # Run backtest
            engine = BacktestEngine(config, data_provider)
            strategy = LSMArbitrageStrategy(
                edge_threshold_pct=edge_threshold,
                max_positions=max_positions,
                maturity_days=maturity_days,
                min_days_to_expiry=5  # Use fixed edge scanner logic
            )

            engine.run_backtest(strategy, start_date, end_date)
            metrics = engine.get_performance_metrics()

            # Add scenario metadata
            result = {
                'scenario': scenario_name,
                'tickers': ','.join(tickers),
                'start_date': start_date,
                'end_date': end_date,
                'capital': capital,
                'edge_threshold': edge_threshold,
                'max_positions': max_positions,
                'maturity_days': maturity_days,
                **metrics
            }

            self.results.append(result)
            print(f"\n✓ Completed: Return={metrics.get('total_return_pct', 0):.2f}% | Trades={metrics.get('total_trades', 0)}")

            return result

        except Exception as e:
            print(f"\n✗ Failed: {e}")
            result = {
                'scenario': scenario_name,
                'tickers': ','.join(tickers),
                'start_date': start_date,
                'end_date': end_date,
                'error': str(e),
                'total_return_pct': 0,
                'total_trades': 0
            }
            self.results.append(result)
            return result

    def test_market_conditions(self):
        """Test across different market conditions"""
        print("\n" + "="*70)
        print("STRESS TEST 1: Different Market Conditions")
        print("="*70)

        scenarios = [
            # Bull market (2023)
            {
                'name': 'Bull Market 2023',
                'tickers': ['AAPL'],
                'start': '2023-01-01',
                'end': '2023-12-31',
                'description': 'Strong uptrend year'
            },
            # Bear market (2022)
            {
                'name': 'Bear Market 2022',
                'tickers': ['AAPL'],
                'start': '2022-01-01',
                'end': '2022-12-31',
                'description': 'Down market year'
            },
            # COVID crash (2020 Q1)
            {
                'name': 'COVID Crash 2020',
                'tickers': ['AAPL'],
                'start': '2020-02-01',
                'end': '2020-05-31',
                'description': 'Extreme volatility and crash'
            },
            # COVID recovery (2020 Q2-Q4)
            {
                'name': 'COVID Recovery 2020',
                'tickers': ['AAPL'],
                'start': '2020-06-01',
                'end': '2020-12-31',
                'description': 'Strong V-shaped recovery'
            },
            # Recent period (2024)
            {
                'name': 'Recent 2024',
                'tickers': ['AAPL'],
                'start': '2024-01-01',
                'end': '2024-08-31',
                'description': 'Most recent market conditions'
            },
            # Sideways market (2015)
            {
                'name': 'Sideways 2015',
                'tickers': ['AAPL'],
                'start': '2015-01-01',
                'end': '2015-12-31',
                'description': 'Range-bound market'
            }
        ]

        for scenario in scenarios:
            self.run_single_backtest(
                tickers=scenario['tickers'],
                start_date=scenario['start'],
                end_date=scenario['end'],
                capital=100000,
                edge_threshold=5.0,
                max_positions=5,
                maturity_days=30,
                scenario_name=scenario['name']
            )

    def test_multi_ticker(self):
        """Test with multiple tickers across sectors"""
        print("\n" + "="*70)
        print("STRESS TEST 2: Multiple Tickers (Diversification)")
        print("="*70)

        scenarios = [
            {
                'name': 'Single Ticker - AAPL',
                'tickers': ['AAPL'],
            },
            {
                'name': 'Tech Heavy (3 stocks)',
                'tickers': ['AAPL', 'MSFT', 'GOOGL'],
            },
            {
                'name': 'Diversified (5 stocks)',
                'tickers': ['AAPL', 'XOM', 'JPM', 'JNJ', 'WMT'],
            },
            {
                'name': 'Mega Diversified (10 stocks)',
                'tickers': ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA',
                           'XOM', 'JPM', 'JNJ', 'WMT', 'PG'],
            }
        ]

        for scenario in scenarios:
            self.run_single_backtest(
                tickers=scenario['tickers'],
                start_date='2023-01-01',
                end_date='2024-08-31',
                capital=100000,
                edge_threshold=5.0,
                max_positions=10,
                maturity_days=30,
                scenario_name=scenario['name']
            )

    def test_parameter_sweep(self):
        """Test different parameter combinations"""
        print("\n" + "="*70)
        print("STRESS TEST 3: Parameter Sensitivity")
        print("="*70)

        # Edge threshold sensitivity
        print("\n--- Edge Threshold Sweep ---")
        for edge in [3.0, 5.0, 7.0, 10.0, 15.0]:
            self.run_single_backtest(
                tickers=['AAPL'],
                start_date='2023-01-01',
                end_date='2024-08-31',
                capital=100000,
                edge_threshold=edge,
                max_positions=5,
                maturity_days=30,
                scenario_name=f'Edge Threshold {edge}%'
            )

        # Position sizing sensitivity
        print("\n--- Position Sizing Sweep ---")
        for max_pos in [1, 3, 5, 10, 20]:
            self.run_single_backtest(
                tickers=['AAPL'],
                start_date='2023-01-01',
                end_date='2024-08-31',
                capital=100000,
                edge_threshold=5.0,
                max_positions=max_pos,
                maturity_days=30,
                scenario_name=f'Max Positions {max_pos}'
            )

        # Maturity sensitivity
        print("\n--- Maturity Sweep ---")
        for days in [7, 14, 30, 45, 60]:
            self.run_single_backtest(
                tickers=['AAPL'],
                start_date='2023-01-01',
                end_date='2024-08-31',
                capital=100000,
                edge_threshold=5.0,
                max_positions=5,
                maturity_days=days,
                scenario_name=f'Maturity {days} days'
            )

    def test_capital_scaling(self):
        """Test with different capital amounts"""
        print("\n" + "="*70)
        print("STRESS TEST 4: Capital Scaling")
        print("="*70)

        for capital in [10000, 50000, 100000, 500000, 1000000]:
            self.run_single_backtest(
                tickers=['AAPL'],
                start_date='2023-01-01',
                end_date='2024-08-31',
                capital=capital,
                edge_threshold=5.0,
                max_positions=5,
                maturity_days=30,
                scenario_name=f'Capital ${capital:,}'
            )

    def test_extended_periods(self):
        """Test longer time periods"""
        print("\n" + "="*70)
        print("STRESS TEST 5: Extended Time Periods")
        print("="*70)

        scenarios = [
            {
                'name': '3 Months (Q2 2024)',
                'start': '2024-04-01',
                'end': '2024-06-30'
            },
            {
                'name': '6 Months (H1 2024)',
                'start': '2024-01-01',
                'end': '2024-06-30'
            },
            {
                'name': '1 Year (2023)',
                'start': '2023-01-01',
                'end': '2023-12-31'
            },
            {
                'name': '2 Years (2022-2023)',
                'start': '2022-01-01',
                'end': '2023-12-31'
            },
            {
                'name': '5 Years (2019-2023)',
                'start': '2019-01-01',
                'end': '2023-12-31'
            }
        ]

        for scenario in scenarios:
            self.run_single_backtest(
                tickers=['AAPL'],
                start_date=scenario['start'],
                end_date=scenario['end'],
                capital=100000,
                edge_threshold=5.0,
                max_positions=5,
                maturity_days=30,
                scenario_name=scenario['name']
            )

    def generate_summary_report(self):
        """Generate comprehensive summary report"""
        if not self.results:
            print("No results to summarize")
            return

        df = pd.DataFrame(self.results)

        # Save full results
        df.to_csv(f"{self.output_dir}/all_scenarios.csv", index=False)
        print(f"\n✓ Saved all results to {self.output_dir}/all_scenarios.csv")

        # Generate summary statistics
        print("\n" + "="*70)
        print("STRESS TEST SUMMARY")
        print("="*70)

        print(f"\nTotal Scenarios Tested: {len(df)}")
        print(f"Successful Backtests: {len(df[df['total_trades'] > 0])}")
        print(f"Failed Backtests: {len(df[df['total_trades'] == 0])}")

        # Filter to successful backtests
        successful = df[df['total_trades'] > 0]

        if len(successful) > 0:
            print(f"\n--- Performance Statistics (Successful Backtests Only) ---")
            print(f"Average Return: {successful['total_return_pct'].mean():.2f}%")
            print(f"Median Return: {successful['total_return_pct'].median():.2f}%")
            print(f"Best Return: {successful['total_return_pct'].max():.2f}%")
            print(f"Worst Return: {successful['total_return_pct'].min():.2f}%")
            print(f"Std Dev Returns: {successful['total_return_pct'].std():.2f}%")

            print(f"\n--- Win Rate Statistics ---")
            if 'win_rate_pct' in successful.columns:
                print(f"Average Win Rate: {successful['win_rate_pct'].mean():.1f}%")
                print(f"Scenarios with 100% Win Rate: {len(successful[successful['win_rate_pct'] == 100])}")

            print(f"\n--- Risk Metrics ---")
            if 'sharpe_ratio' in successful.columns:
                print(f"Average Sharpe Ratio: {successful['sharpe_ratio'].mean():.2f}")
            if 'max_drawdown_pct' in successful.columns:
                print(f"Average Max Drawdown: {successful['max_drawdown_pct'].mean():.2f}%")
                print(f"Worst Max Drawdown: {successful['max_drawdown_pct'].max():.2f}%")

            # Best and worst scenarios
            print(f"\n--- Top 5 Scenarios by Return ---")
            top5 = successful.nlargest(5, 'total_return_pct')[['scenario', 'total_return_pct', 'total_trades', 'win_rate_pct']]
            print(top5.to_string(index=False))

            print(f"\n--- Bottom 5 Scenarios by Return ---")
            bottom5 = successful.nsmallest(5, 'total_return_pct')[['scenario', 'total_return_pct', 'total_trades', 'win_rate_pct']]
            print(bottom5.to_string(index=False))

        # Scenarios with no trades
        no_trades = df[df['total_trades'] == 0]
        if len(no_trades) > 0:
            print(f"\n--- Scenarios with No Trades ({len(no_trades)}) ---")
            print(no_trades[['scenario', 'tickers', 'start_date', 'end_date']].to_string(index=False))

        print(f"\n{'='*70}")
        print(f"Full results saved to: {self.output_dir}/all_scenarios.csv")
        print(f"{'='*70}\n")

        # Create summary JSON
        summary = {
            'total_scenarios': len(df),
            'successful': len(successful),
            'failed': len(df) - len(successful),
            'avg_return_pct': float(successful['total_return_pct'].mean()) if len(successful) > 0 else 0,
            'median_return_pct': float(successful['total_return_pct'].median()) if len(successful) > 0 else 0,
            'best_return_pct': float(successful['total_return_pct'].max()) if len(successful) > 0 else 0,
            'worst_return_pct': float(successful['total_return_pct'].min()) if len(successful) > 0 else 0,
            'timestamp': datetime.now().isoformat()
        }

        with open(f"{self.output_dir}/summary.json", 'w') as f:
            json.dump(summary, f, indent=2)

        return df


def main():
    parser = argparse.ArgumentParser(description="Comprehensive stress testing for options strategy")
    parser.add_argument('--mode', type=str, default='all',
                       choices=['all', 'market_conditions', 'multi_ticker', 'parameter_sweep',
                               'capital_scaling', 'extended_periods'],
                       help='Which stress tests to run')
    args = parser.parse_args()

    tester = StressTester()

    print("\n" + "="*70)
    print("OPTIONS STRATEGY STRESS TESTING")
    print("="*70)
    print(f"Mode: {args.mode}")
    print(f"Output: outputs/stress_test/")
    print("="*70)

    if args.mode == 'all':
        tester.test_market_conditions()
        tester.test_multi_ticker()
        tester.test_parameter_sweep()
        tester.test_capital_scaling()
        tester.test_extended_periods()
    elif args.mode == 'market_conditions':
        tester.test_market_conditions()
    elif args.mode == 'multi_ticker':
        tester.test_multi_ticker()
    elif args.mode == 'parameter_sweep':
        tester.test_parameter_sweep()
    elif args.mode == 'capital_scaling':
        tester.test_capital_scaling()
    elif args.mode == 'extended_periods':
        tester.test_extended_periods()

    # Generate summary report
    tester.generate_summary_report()


if __name__ == "__main__":
    main()
