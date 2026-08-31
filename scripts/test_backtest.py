"""
Quick test of the backtesting system

Run this to verify everything works before full backtesting
"""

from backtesting.data_loader import BacktestDataProvider
from backtesting.engine import BacktestEngine, BacktestConfig
from backtesting.strategies import simple_buy_and_hold

print("\n" + "="*70)
print("Backtesting System Test")
print("="*70 + "\n")

# Small backtest period for quick testing
start_date = '2024-06-01'
end_date = '2024-08-31'

print("Loading data...")
data_provider = BacktestDataProvider(['AAPL'], start_date, end_date)
data_provider.load_all_data()

print("Creating backtest engine...")
config = BacktestConfig(
    initial_capital=100000,
    max_positions=5,
    commission_per_contract=0.65
)

engine = BacktestEngine(config, data_provider)

print("Running simple buy and hold strategy...\n")
engine.run_backtest(simple_buy_and_hold, start_date, end_date)

print("\n" + "="*70)
print("Test Complete!")
print("="*70)

metrics = engine.get_performance_metrics()
print(f"\nTotal trades: {metrics.get('total_trades', 0)}")
print(f"Final value: ${metrics.get('final_value', 0):,.2f}")

engine.export_results()
