"""Trading simulator for onset detection strategy evaluation."""

import pandas as pd
import numpy as np
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Tuple
from datetime import datetime
import logging

from ..config_loader import Config, load_config
from ..ml.labeler import load_events_from_jsonl

logger = logging.getLogger(__name__)


class TradingSimulator:
    """
    Trading simulator for evaluating onset detection strategy.
    """

    def __init__(self, config: Optional[Config] = None):
        """
        Initialize trading simulator.

        Args:
            config: Configuration object. If None, loads default config.
        """
        self.config = config or load_config()

        # Get trading configuration
        trading_config = getattr(self.config, 'trading', None)
        if trading_config is None:
            logger.warning("No trading configuration found. Using defaults.")
            self.capital = 10000000  # 10M KRW
            self.fee_rate = 0.0005
            self.slippage = 0.0002
            self.hold_time_s = 60
            self.stop_loss_pct = 0.01
            self.take_profit_pct = 0.02
        else:
            simulator_config = getattr(trading_config, 'simulator', None)
            if simulator_config is None:
                logger.warning("No simulator configuration found. Using defaults.")
                self.capital = 10000000
                self.fee_rate = 0.0005
                self.slippage = 0.0002
                self.hold_time_s = 60
                self.stop_loss_pct = 0.01
                self.take_profit_pct = 0.02
            else:
                self.capital = getattr(simulator_config, 'capital', 10000000)
                self.fee_rate = getattr(simulator_config, 'fee_rate', 0.0005)
                self.slippage = getattr(simulator_config, 'slippage', 0.0002)
                self.hold_time_s = getattr(simulator_config, 'hold_time_s', 60)
                self.stop_loss_pct = getattr(simulator_config, 'stop_loss_pct', 0.01)
                self.take_profit_pct = getattr(simulator_config, 'take_profit_pct', 0.02)

        logger.info(f"Trading simulator initialized")
        logger.info(f"Capital: {self.capital:,} KRW")
        logger.info(f"Fee rate: {self.fee_rate:.4f}, Slippage: {self.slippage:.4f}")
        logger.info(f"Hold time: {self.hold_time_s}s, Stop loss: {self.stop_loss_pct:.2%}, Take profit: {self.take_profit_pct:.2%}")

    def simulate_trades(
        self,
        features_df: pd.DataFrame,
        confirmed_events: List[Dict[str, Any]]
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Simulate trades based on confirmed onset events.

        Args:
            features_df: Features DataFrame with price data.
            confirmed_events: List of confirmed onset events.

        Returns:
            Tuple: (trades_df, summary_dict).
        """
        if features_df.empty or not confirmed_events:
            logger.warning("No data for simulation")
            return pd.DataFrame(), self._create_empty_summary()

        # Required columns check
        required_cols = ['ts', 'stock_code', 'price']
        missing_cols = set(required_cols) - set(features_df.columns)
        if missing_cols:
            raise ValueError(f"Missing required columns for simulation: {missing_cols}")

        # Sort features by timestamp
        features_df = features_df.sort_values('ts')

        trades = []
        current_capital = self.capital

        for event_idx, event in enumerate(confirmed_events):
            # Get entry signal
            entry_ts = event['ts']
            stock_code = event['stock_code']

            # Convert timestamp if needed
            if isinstance(entry_ts, (int, float)):
                if entry_ts < 1e10:  # Likely seconds
                    entry_dt = pd.to_datetime(entry_ts, unit='s')
                else:  # Likely milliseconds
                    entry_dt = pd.to_datetime(entry_ts, unit='ms')
            else:
                entry_dt = pd.to_datetime(entry_ts)

            # Find entry price
            entry_idx = self._find_nearest_index(features_df, entry_dt)
            if entry_idx is None:
                continue

            entry_price = features_df.iloc[entry_idx]['price']

            # Apply slippage for entry
            entry_price_actual = entry_price * (1 + self.slippage)

            # Calculate position size
            position_size = int(current_capital * 0.95 / entry_price_actual)  # Use 95% of capital
            if position_size == 0:
                logger.warning(f"Insufficient capital for trade at {entry_dt}")
                continue

            # Find exit conditions
            exit_dt = entry_dt + pd.Timedelta(seconds=self.hold_time_s)
            exit_idx, exit_price, exit_reason = self._find_exit(
                features_df,
                entry_idx,
                entry_price_actual,
                exit_dt,
                stock_code
            )

            if exit_idx is None:
                continue

            # Apply slippage for exit
            exit_price_actual = exit_price * (1 - self.slippage)

            # Calculate PnL
            gross_pnl = position_size * (exit_price_actual - entry_price_actual)
            fees = position_size * (entry_price_actual + exit_price_actual) * self.fee_rate
            net_pnl = gross_pnl - fees
            pnl_pct = net_pnl / (position_size * entry_price_actual)

            # Update capital
            current_capital += net_pnl

            # Record trade
            trade = {
                "trade_id": f"T{event_idx+1:04d}",
                "stock_code": stock_code,
                "entry_ts": entry_ts,
                "entry_dt": entry_dt,
                "entry_price": entry_price,
                "entry_price_actual": entry_price_actual,
                "exit_ts": features_df.iloc[exit_idx]['ts'],
                "exit_dt": pd.to_datetime(features_df.iloc[exit_idx]['ts']),
                "exit_price": exit_price,
                "exit_price_actual": exit_price_actual,
                "position_size": position_size,
                "gross_pnl": gross_pnl,
                "fees": fees,
                "net_pnl": net_pnl,
                "pnl_pct": pnl_pct,
                "exit_reason": exit_reason,
                "capital_after": current_capital,
                "onset_strength": event.get('evidence', {}).get('onset_strength', None)
            }
            trades.append(trade)

        # Create trades DataFrame
        trades_df = pd.DataFrame(trades)

        # Calculate summary statistics
        summary = self._calculate_summary(trades_df, self.capital)

        return trades_df, summary

    def _find_nearest_index(
        self,
        features_df: pd.DataFrame,
        target_dt: pd.Timestamp
    ) -> Optional[int]:
        """Find the nearest index in features DataFrame."""
        # Convert features timestamps to datetime for comparison
        features_ts = pd.to_datetime(features_df['ts'])

        # Find the nearest timestamp
        time_diff = (features_ts - target_dt).abs()
        if time_diff.min() > pd.Timedelta(seconds=5):
            return None

        return time_diff.idxmin()

    def _find_exit(
        self,
        features_df: pd.DataFrame,
        entry_idx: int,
        entry_price: float,
        exit_dt: pd.Timestamp,
        stock_code: str
    ) -> Tuple[Optional[int], Optional[float], str]:
        """
        Find exit conditions (stop loss, take profit, or time-based).

        Returns:
            Tuple: (exit_idx, exit_price, exit_reason).
        """
        # Look for exit conditions in subsequent rows
        for i in range(entry_idx + 1, len(features_df)):
            row = features_df.iloc[i]

            # Check if same stock
            if str(row['stock_code']) != str(stock_code):
                continue

            current_price = row['price']
            current_dt = pd.to_datetime(row['ts'])

            # Calculate return
            price_return = (current_price - entry_price) / entry_price

            # Check stop loss
            if price_return <= -self.stop_loss_pct:
                return i, current_price, "stop_loss"

            # Check take profit
            if price_return >= self.take_profit_pct:
                return i, current_price, "take_profit"

            # Check time-based exit
            if current_dt >= exit_dt:
                return i, current_price, "time_exit"

        # If no exit found within data, use last available price
        last_idx = len(features_df) - 1
        return last_idx, features_df.iloc[last_idx]['price'], "data_end"

    def _calculate_summary(
        self,
        trades_df: pd.DataFrame,
        initial_capital: float
    ) -> Dict[str, Any]:
        """Calculate trading summary statistics."""
        if trades_df.empty:
            return self._create_empty_summary()

        # Basic metrics
        n_trades = len(trades_df)
        n_wins = len(trades_df[trades_df['net_pnl'] > 0])
        n_losses = len(trades_df[trades_df['net_pnl'] < 0])
        win_rate = n_wins / n_trades if n_trades > 0 else 0

        # PnL metrics
        total_pnl = trades_df['net_pnl'].sum()
        total_return = total_pnl / initial_capital
        avg_pnl = trades_df['net_pnl'].mean()
        avg_pnl_pct = trades_df['pnl_pct'].mean()

        # Risk metrics
        if n_trades > 1:
            returns = trades_df['pnl_pct'].values
            sharpe = np.sqrt(252) * returns.mean() / returns.std() if returns.std() > 0 else 0

            # Calculate MDD
            cumulative_capital = [initial_capital]
            for pnl in trades_df['net_pnl'].values:
                cumulative_capital.append(cumulative_capital[-1] + pnl)
            cumulative_capital = np.array(cumulative_capital)
            running_max = np.maximum.accumulate(cumulative_capital)
            drawdown = (cumulative_capital - running_max) / running_max
            mdd = drawdown.min()
        else:
            sharpe = 0
            mdd = 0

        # Exit reason distribution
        exit_reasons = trades_df['exit_reason'].value_counts().to_dict()

        # Average hold time
        if not trades_df.empty:
            hold_times = (pd.to_datetime(trades_df['exit_dt']) - pd.to_datetime(trades_df['entry_dt'])).dt.total_seconds()
            avg_hold_time = hold_times.mean()
        else:
            avg_hold_time = 0

        summary = {
            "performance": {
                "initial_capital": initial_capital,
                "final_capital": initial_capital + total_pnl,
                "total_pnl": total_pnl,
                "total_return": total_return,
                "n_trades": n_trades,
                "n_wins": n_wins,
                "n_losses": n_losses,
                "win_rate": win_rate
            },
            "per_trade": {
                "avg_pnl": avg_pnl,
                "avg_pnl_pct": avg_pnl_pct,
                "max_pnl": trades_df['net_pnl'].max() if not trades_df.empty else 0,
                "min_pnl": trades_df['net_pnl'].min() if not trades_df.empty else 0,
                "avg_hold_time_s": avg_hold_time
            },
            "risk": {
                "sharpe_ratio": sharpe,
                "max_drawdown": mdd,
                "total_fees": trades_df['fees'].sum() if not trades_df.empty else 0
            },
            "exits": exit_reasons,
            "config": {
                "fee_rate": self.fee_rate,
                "slippage": self.slippage,
                "hold_time_s": self.hold_time_s,
                "stop_loss_pct": self.stop_loss_pct,
                "take_profit_pct": self.take_profit_pct
            }
        }

        return summary

    def _create_empty_summary(self) -> Dict[str, Any]:
        """Create empty summary structure."""
        return {
            "performance": {
                "initial_capital": self.capital,
                "final_capital": self.capital,
                "total_pnl": 0,
                "total_return": 0,
                "n_trades": 0,
                "n_wins": 0,
                "n_losses": 0,
                "win_rate": 0
            },
            "per_trade": {
                "avg_pnl": 0,
                "avg_pnl_pct": 0,
                "max_pnl": 0,
                "min_pnl": 0,
                "avg_hold_time_s": 0
            },
            "risk": {
                "sharpe_ratio": 0,
                "max_drawdown": 0,
                "total_fees": 0
            },
            "exits": {},
            "config": {
                "fee_rate": self.fee_rate,
                "slippage": self.slippage,
                "hold_time_s": self.hold_time_s,
                "stop_loss_pct": self.stop_loss_pct,
                "take_profit_pct": self.take_profit_pct
            }
        }


def run_simulation(
    features_file: Union[str, Path],
    events_file: Union[str, Path],
    config: Optional[Config] = None
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Convenience function to run trading simulation.

    Args:
        features_file: Path to features CSV file.
        events_file: Path to confirmed events JSONL file.
        config: Optional configuration object.

    Returns:
        Tuple: (trades_df, summary_dict).
    """
    simulator = TradingSimulator(config)

    # Load data
    features_df = pd.read_csv(features_file)
    events = load_events_from_jsonl(events_file)

    # Filter for confirmed events only
    confirmed_events = [e for e in events if e.get('event_type') == 'onset_confirmed']
    logger.info(f"Found {len(confirmed_events)} confirmed events for simulation")

    return simulator.simulate_trades(features_df, confirmed_events)


if __name__ == "__main__":
    # Demo/test the trading simulator
    import sys
    from pathlib import Path

    # Add project root to Python path
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))

    print("Trading Simulator Demo")
    print("=" * 40)

    # Initialize simulator
    try:
        simulator = TradingSimulator()
        print(f"Simulator initialized")
        print(f"Capital: {simulator.capital:,} KRW")

        # Create dummy data for testing
        sample_features = pd.DataFrame({
            'ts': pd.date_range('2025-09-02 09:00:00', periods=200, freq='1s'),
            'stock_code': ['005930'] * 200,
            'price': 70000 + np.cumsum(np.random.randn(200) * 50)  # Random walk
        })

        # Add some upward trend
        sample_features['price'] = sample_features['price'] + np.arange(200) * 5

        sample_events = [
            {
                'ts': sample_features['ts'].iloc[10].timestamp() * 1000,
                'event_type': 'onset_confirmed',
                'stock_code': '005930',
                'evidence': {'onset_strength': 0.75}
            },
            {
                'ts': sample_features['ts'].iloc[100].timestamp() * 1000,
                'event_type': 'onset_confirmed',
                'stock_code': '005930',
                'evidence': {'onset_strength': 0.82}
            }
        ]

        print(f"Sample features shape: {sample_features.shape}")
        print(f"Sample events: {len(sample_events)}")

        # Run simulation
        trades_df, summary = simulator.simulate_trades(sample_features, sample_events)

        print(f"\nSimulation Results:")
        print(f"Total trades: {summary['performance']['n_trades']}")
        print(f"Win rate: {summary['performance']['win_rate']:.1%}")
        print(f"Total return: {summary['performance']['total_return']:.2%}")
        print(f"Sharpe ratio: {summary['risk']['sharpe_ratio']:.2f}")

        if not trades_df.empty:
            print(f"\nSample trades:")
            print(trades_df[['trade_id', 'entry_price', 'exit_price', 'net_pnl', 'exit_reason']].head())

    except Exception as e:
        print(f"Demo failed: {e}")
        import traceback
        traceback.print_exc()