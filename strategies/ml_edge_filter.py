"""
Machine Learning Edge Filter

Uses XGBoost to predict whether a detected "edge" will actually result in profit.

Problem: LSM might detect false edges due to:
- Model error
- Market microstructure
- Liquidity issues
- Volatility skew

Solution: Train ML model on historical edge outcomes
- Features: IV percentile, stock trend, volume, LSM variance, etc.
- Target: Did this edge result in profit?
- Filter: Only trade edges with >70% ML confidence

Requirements:
    pip install xgboost scikit-learn pandas

"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import pickle
from pathlib import Path

try:
    import xgboost as xgb
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import accuracy_score, precision_score, recall_score, roc_auc_score
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    print("Warning: XGBoost not installed. Install with: pip install xgboost scikit-learn")


@dataclass
class EdgeFeatures:
    """Features for ML edge prediction"""

    # Edge characteristics
    edge_pct: float  # LSM edge percentage
    lsm_price: float  # LSM fair value
    market_price: float  # Market price
    lsm_std: float  # LSM pricing uncertainty

    # Option characteristics
    strike: float
    days_to_expiry: int
    moneyness: float  # strike / spot
    option_type: str  # 'call' or 'put'

    # Market characteristics
    spot_price: float
    iv: float  # Implied volatility
    iv_percentile: Optional[float] = None  # IV rank (0-100)

    # Stock momentum
    stock_momentum_5d: Optional[float] = None  # 5-day return
    stock_momentum_20d: Optional[float] = None  # 20-day return

    # Volume
    volume_ratio: Optional[float] = None  # Today vol / avg vol
    option_volume: Optional[int] = None
    option_open_interest: Optional[int] = None

    # Spread
    bid_ask_spread_pct: Optional[float] = None  # (ask - bid) / mid

    def to_array(self) -> np.ndarray:
        """Convert to numpy array for ML model"""
        return np.array([
            self.edge_pct,
            self.lsm_price,
            self.market_price,
            self.lsm_std,
            self.strike,
            self.days_to_expiry,
            self.moneyness,
            1.0 if self.option_type == 'call' else 0.0,
            self.spot_price,
            self.iv,
            self.iv_percentile or 50.0,
            self.stock_momentum_5d or 0.0,
            self.stock_momentum_20d or 0.0,
            self.volume_ratio or 1.0,
            self.option_volume or 0.0,
            self.option_open_interest or 0.0,
            self.bid_ask_spread_pct or 0.02,
        ])

    @staticmethod
    def feature_names() -> List[str]:
        """Get feature names for model"""
        return [
            'edge_pct', 'lsm_price', 'market_price', 'lsm_std',
            'strike', 'days_to_expiry', 'moneyness', 'is_call',
            'spot_price', 'iv', 'iv_percentile',
            'stock_momentum_5d', 'stock_momentum_20d',
            'volume_ratio', 'option_volume', 'option_open_interest',
            'bid_ask_spread_pct'
        ]


class MLEdgeFilter:
    """ML-based edge filter using XGBoost"""

    def __init__(self, model_path: Optional[str] = None):
        self.model = None
        self.model_path = model_path or 'models/edge_filter.pkl'
        self.is_trained = False

        if not XGBOOST_AVAILABLE:
            raise ImportError("XGBoost not available. Install with: pip install xgboost scikit-learn")

    def train(
        self,
        features: List[EdgeFeatures],
        outcomes: List[bool],  # True if edge resulted in profit
        test_size: float = 0.2,
        random_state: int = 42
    ) -> Dict:
        """
        Train XGBoost model on historical edge outcomes

        Args:
            features: List of EdgeFeatures for historical trades
            outcomes: List of boolean outcomes (True = profitable)
            test_size: Fraction of data for testing
            random_state: Random seed

        Returns:
            dict with training metrics
        """

        # Convert to numpy arrays
        X = np.array([f.to_array() for f in features])
        y = np.array(outcomes).astype(int)

        # Split train/test
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=random_state
        )

        # Train XGBoost
        print(f"Training XGBoost on {len(X_train)} samples...")

        self.model = xgb.XGBClassifier(
            n_estimators=100,
            max_depth=5,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=random_state,
            eval_metric='logloss'
        )

        self.model.fit(
            X_train, y_train,
            eval_set=[(X_test, y_test)],
            verbose=False
        )

        # Evaluate
        y_pred = self.model.predict(X_test)
        y_pred_proba = self.model.predict_proba(X_test)[:, 1]

        metrics = {
            'accuracy': accuracy_score(y_test, y_pred),
            'precision': precision_score(y_test, y_pred),
            'recall': recall_score(y_test, y_pred),
            'auc': roc_auc_score(y_test, y_pred_proba),
            'train_samples': len(X_train),
            'test_samples': len(X_test),
        }

        self.is_trained = True

        print(f"\n✓ Model trained successfully!")
        print(f"  Accuracy:  {metrics['accuracy']:.1%}")
        print(f"  Precision: {metrics['precision']:.1%}")
        print(f"  Recall:    {metrics['recall']:.1%}")
        print(f"  AUC:       {metrics['auc']:.3f}")

        return metrics

    def predict_edge_quality(self, features: EdgeFeatures) -> Tuple[bool, float]:
        """
        Predict if edge is likely to be profitable

        Args:
            features: EdgeFeatures for current opportunity

        Returns:
            (should_trade, confidence)
                should_trade: True if model predicts profit
                confidence: Probability of profit (0-1)
        """

        if not self.is_trained:
            raise ValueError("Model not trained. Call train() first or load().")

        X = features.to_array().reshape(1, -1)

        # Get probability of profit
        prob_profit = self.model.predict_proba(X)[0, 1]

        # Trade if confidence > 70%
        should_trade = prob_profit > 0.70

        return should_trade, prob_profit

    def get_feature_importance(self) -> pd.DataFrame:
        """Get feature importance from trained model"""

        if not self.is_trained:
            raise ValueError("Model not trained")

        importance = self.model.feature_importances_
        feature_names = EdgeFeatures.feature_names()

        df = pd.DataFrame({
            'feature': feature_names,
            'importance': importance
        }).sort_values('importance', ascending=False)

        return df

    def save(self, path: Optional[str] = None):
        """Save trained model to disk"""

        save_path = path or self.model_path
        os.makedirs(os.path.dirname(save_path), exist_ok=True)

        with open(save_path, 'wb') as f:
            pickle.dump(self.model, f)

        print(f"✓ Model saved to {save_path}")

    def load(self, path: Optional[str] = None):
        """Load trained model from disk"""

        load_path = path or self.model_path

        if not os.path.exists(load_path):
            raise FileNotFoundError(f"Model not found at {load_path}")

        with open(load_path, 'rb') as f:
            self.model = pickle.load(f)

        self.is_trained = True
        print(f"✓ Model loaded from {load_path}")


def generate_synthetic_training_data(n_samples: int = 1000) -> Tuple[List[EdgeFeatures], List[bool]]:
    """
    Generate synthetic training data for demonstration

    In production, this would come from actual backtest results
    """

    features = []
    outcomes = []

    np.random.seed(42)

    for _ in range(n_samples):
        # Generate random features
        edge_pct = np.random.uniform(1, 20)  # 1-20% edge
        lsm_price = np.random.uniform(1, 20)
        lsm_std = np.random.uniform(0.1, 2.0)
        market_price = lsm_price * (1 + edge_pct / 100) if np.random.rand() > 0.5 else lsm_price * (1 - edge_pct / 100)

        days_to_expiry = np.random.randint(7, 60)
        moneyness = np.random.uniform(0.85, 1.15)
        iv = np.random.uniform(0.15, 0.60)
        iv_percentile = np.random.uniform(0, 100)

        # Simulate realistic relationships
        # Higher edge + lower IV percentile + trending stock = higher profit probability
        stock_momentum = np.random.uniform(-0.1, 0.1)
        volume_ratio = np.random.uniform(0.5, 3.0)
        bid_ask_spread = np.random.uniform(0.01, 0.10)

        feat = EdgeFeatures(
            edge_pct=edge_pct,
            lsm_price=lsm_price,
            market_price=market_price,
            lsm_std=lsm_std,
            strike=220.0,
            days_to_expiry=days_to_expiry,
            moneyness=moneyness,
            option_type='put' if np.random.rand() > 0.5 else 'call',
            spot_price=220.0,
            iv=iv,
            iv_percentile=iv_percentile,
            stock_momentum_5d=stock_momentum,
            stock_momentum_20d=stock_momentum * 1.5,
            volume_ratio=volume_ratio,
            option_volume=int(np.random.uniform(100, 10000)),
            option_open_interest=int(np.random.uniform(500, 50000)),
            bid_ask_spread_pct=bid_ask_spread,
        )

        # Simulate outcome (profit probability based on features)
        # Good edges: high edge %, low LSM std, low IV percentile, trending
        profit_prob = 0.50  # Base 50%
        profit_prob += (edge_pct / 100) * 0.5  # Higher edge = higher prob
        profit_prob += (0.1 if lsm_std < 0.5 else -0.1)  # Low uncertainty = good
        profit_prob += (0.1 if iv_percentile < 30 else -0.1)  # Low IV = good
        profit_prob += stock_momentum * 2  # Trending = good
        profit_prob -= bid_ask_spread  # Wide spread = bad

        profit_prob = np.clip(profit_prob, 0.1, 0.9)
        outcome = np.random.rand() < profit_prob

        features.append(feat)
        outcomes.append(outcome)

    return features, outcomes


# Example usage
if __name__ == "__main__":
    if not XGBOOST_AVAILABLE:
        print("XGBoost not installed. Install with: pip install xgboost scikit-learn")
        sys.exit(1)

    print("=" * 70)
    print("ML EDGE FILTER - XGBoost Training")
    print("=" * 70)

    # Generate synthetic training data
    print("\nGenerating synthetic training data...")
    features, outcomes = generate_synthetic_training_data(n_samples=1000)

    profit_rate = sum(outcomes) / len(outcomes)
    print(f"Generated {len(features)} samples (base profit rate: {profit_rate:.1%})")

    # Train model
    print("\nTraining ML model...")
    filter_model = MLEdgeFilter()
    metrics = filter_model.train(features, outcomes)

    # Show feature importance
    print("\n" + "=" * 70)
    print("FEATURE IMPORTANCE")
    print("=" * 70)
    importance_df = filter_model.get_feature_importance()
    print(importance_df.head(10).to_string(index=False))

    # Test on new edge
    print("\n" + "=" * 70)
    print("TESTING ON NEW EDGE")
    print("=" * 70)

    test_edge = EdgeFeatures(
        edge_pct=8.5,
        lsm_price=4.50,
        market_price=4.90,
        lsm_std=0.25,
        strike=215.0,
        days_to_expiry=30,
        moneyness=0.98,
        option_type='put',
        spot_price=220.0,
        iv=0.28,
        iv_percentile=25,
        stock_momentum_5d=0.03,
        stock_momentum_20d=0.05,
        volume_ratio=1.5,
        option_volume=5000,
        option_open_interest=25000,
        bid_ask_spread_pct=0.03,
    )

    should_trade, confidence = filter_model.predict_edge_quality(test_edge)

    print(f"\nEdge Opportunity:")
    print(f"  LSM Fair Value: ${test_edge.lsm_price:.2f}")
    print(f"  Market Price: ${test_edge.market_price:.2f}")
    print(f"  Edge: {test_edge.edge_pct:.1f}%")
    print(f"  IV Percentile: {test_edge.iv_percentile:.0f}")
    print(f"  Stock Momentum: {test_edge.stock_momentum_5d*100:+.1f}%")
    print(f"\nML Prediction:")
    print(f"  Profit Confidence: {confidence:.1%}")
    print(f"  Trade Recommendation: {'✓ TRADE' if should_trade else '✗ SKIP'}")

    if should_trade:
        print(f"\n  → Model has {confidence:.1%} confidence this edge will profit")
    else:
        print(f"\n  → Model only has {confidence:.1%} confidence - SKIP this edge")

    # Save model
    print("\n" + "=" * 70)
    os.makedirs('models', exist_ok=True)
    filter_model.save('models/edge_filter.pkl')

    print("\n" + "=" * 70)
    print("USAGE IN LIVE TRADING")
    print("=" * 70)
    print("""
# In your edge scanner:

from strategies.ml_edge_filter import MLEdgeFilter, EdgeFeatures

# Load trained model
ml_filter = MLEdgeFilter()
ml_filter.load('models/edge_filter.pkl')

# For each detected edge:
for edge in detected_edges:
    # Extract features
    features = EdgeFeatures(
        edge_pct=edge.edge,
        lsm_price=edge.lsm_price,
        market_price=edge.market_price,
        # ... other features
    )

    # Check ML filter
    should_trade, confidence = ml_filter.predict_edge_quality(features)

    if should_trade:
        print(f"✓ ML approved ({confidence:.1%} confidence)")
        execute_trade(edge)
    else:
        print(f"✗ ML rejected ({confidence:.1%} confidence) - skipping")

# Result: Only trade high-quality edges!
    """)
