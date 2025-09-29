"""Live trading runner for real-time onset detection execution."""

import pandas as pd
import numpy as np
import json
import time
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
import logging

from ..config_loader import Config, load_config
from ..features.core_indicators import calculate_core_indicators
from ..ml.window_features import generate_window_features
from ..detection.candidate_detector import CandidateDetector
from ..detection.confirm_hybrid import HybridConfirmDetector
from ..event_store import EventStore, create_event

logger = logging.getLogger(__name__)


class DummyAPI:
    """Dummy trading API for testing and simulation."""

    def __init__(self, account_no: str):
        self.account_no = account_no
        self.balance = 10000000  # 10M KRW
        self.positions = {}

    def get_balance(self) -> float:
        """Get current account balance."""
        return self.balance

    def buy_order(self, stock_code: str, quantity: int, price: float) -> Dict[str, Any]:
        """Execute buy order."""
        total_cost = quantity * price
        if total_cost > self.balance:
            return {"status": "rejected", "reason": "insufficient_balance"}

        self.balance -= total_cost
        if stock_code not in self.positions:
            self.positions[stock_code] = {"quantity": 0, "avg_price": 0}

        old_qty = self.positions[stock_code]["quantity"]
        old_avg = self.positions[stock_code]["avg_price"]

        new_qty = old_qty + quantity
        new_avg = ((old_qty * old_avg) + (quantity * price)) / new_qty

        self.positions[stock_code] = {"quantity": new_qty, "avg_price": new_avg}

        return {
            "status": "filled",
            "stock_code": stock_code,
            "quantity": quantity,
            "price": price,
            "order_id": f"BUY_{int(time.time() * 1000)}"
        }

    def sell_order(self, stock_code: str, quantity: int, price: float) -> Dict[str, Any]:
        """Execute sell order."""
        if stock_code not in self.positions or self.positions[stock_code]["quantity"] < quantity:
            return {"status": "rejected", "reason": "insufficient_position"}

        total_value = quantity * price
        self.balance += total_value
        self.positions[stock_code]["quantity"] -= quantity

        if self.positions[stock_code]["quantity"] == 0:
            del self.positions[stock_code]

        return {
            "status": "filled",
            "stock_code": stock_code,
            "quantity": quantity,
            "price": price,
            "order_id": f"SELL_{int(time.time() * 1000)}"
        }

    def get_positions(self) -> Dict[str, Dict[str, float]]:
        """Get current positions."""
        return self.positions.copy()


class LiveRunner:
    """
    Live trading runner for real-time onset detection and execution.
    """

    def __init__(self, config: Optional[Config] = None):
        """
        Initialize live runner.

        Args:
            config: Configuration object. If None, loads default config.
        """
        self.config = config or load_config()
        self.is_running = False
        self.trades_file = "reports/live_trades.jsonl"

        # Get trading configuration
        trading_config = getattr(self.config, 'trading', None)
        if trading_config is None:
            logger.warning("No trading configuration found. Using defaults.")
            self.api_type = "dummy"
            self.account_no = "1234567890"
            self.risk_limit_pct = 0.05
        else:
            live_config = getattr(trading_config, 'live', None)
            if live_config is None:
                logger.warning("No live trading configuration found. Using defaults.")
                self.api_type = "dummy"
                self.account_no = "1234567890"
                self.risk_limit_pct = 0.05
            else:
                self.api_type = getattr(live_config, 'api', 'dummy')
                self.account_no = getattr(live_config, 'account_no', '1234567890')
                self.risk_limit_pct = getattr(live_config, 'risk_limit_pct', 0.05)

        # Initialize trading API
        self.api = self._initialize_api()

        # Initialize detection components
        self.candidate_detector = CandidateDetector(self.config)
        self.confirm_detector = HybridConfirmDetector(self.config)

        # Data buffer for features
        self.data_buffer = pd.DataFrame()
        self.buffer_size = 300  # Keep last 5 minutes of data (1s intervals)

        # Position tracking
        self.active_positions = {}

        # Event store for trades
        self.event_store = EventStore(self.trades_file)

        logger.info(f"Live runner initialized")
        logger.info(f"API: {self.api_type}, Account: {self.account_no}")
        logger.info(f"Risk limit: {self.risk_limit_pct:.1%}")

    def _initialize_api(self) -> Any:
        """Initialize trading API based on configuration."""
        if self.api_type == "dummy":
            return DummyAPI(self.account_no)
        elif self.api_type == "kiwoom":
            # TODO: Implement Kiwoom API integration
            logger.warning("Kiwoom API not implemented. Using dummy API.")
            return DummyAPI(self.account_no)
        else:
            logger.warning(f"Unknown API type: {self.api_type}. Using dummy API.")
            return DummyAPI(self.account_no)

    def start(self, data_callback: Optional[Callable] = None):
        """
        Start live trading runner.

        Args:
            data_callback: Optional callback function to provide real-time data.
                         If None, uses simulated data.
        """
        if self.is_running:
            logger.warning("Live runner is already running")
            return

        self.is_running = True
        logger.info("Starting live trading runner...")

        # Create reports directory
        Path("reports").mkdir(exist_ok=True)

        # Start data processing loop
        if data_callback:
            self._run_with_callback(data_callback)
        else:
            self._run_with_simulated_data()

    def stop(self):
        """Stop live trading runner."""
        self.is_running = False
        logger.info("Stopping live trading runner...")

    def _run_with_simulated_data(self):
        """Run with simulated market data for testing."""
        logger.info("Running with simulated data")

        # Generate simulated market data
        start_time = datetime.now()
        price = 70000

        try:
            while self.is_running:
                # Generate next tick
                current_time = datetime.now()

                # Random price movement
                price += np.random.randn() * 50
                volume = np.random.randint(100, 1000)

                # Create tick data
                tick_data = {
                    'ts': current_time,
                    'stock_code': '005930',
                    'price': price,
                    'volume': volume,
                    'bid1': price - 50,
                    'ask1': price + 50,
                    'bid_qty1': 500,
                    'ask_qty1': 300
                }

                # Process tick
                self._process_tick(tick_data)

                # Sleep for 1 second (1s interval simulation)
                time.sleep(1)

        except KeyboardInterrupt:
            logger.info("Live runner interrupted by user")
        except Exception as e:
            logger.error(f"Error in live runner: {e}")
        finally:
            self.stop()

    def _run_with_callback(self, data_callback: Callable):
        """Run with external data callback."""
        logger.info("Running with external data callback")

        try:
            while self.is_running:
                # Get data from callback
                tick_data = data_callback()
                if tick_data:
                    self._process_tick(tick_data)

                time.sleep(0.1)  # Small delay to prevent excessive CPU usage

        except Exception as e:
            logger.error(f"Error in live runner with callback: {e}")
        finally:
            self.stop()

    def _process_tick(self, tick_data: Dict[str, Any]):
        """
        Process incoming tick data.

        Args:
            tick_data: Dictionary containing tick data.
        """
        # Add to buffer
        new_row = pd.DataFrame([tick_data])
        self.data_buffer = pd.concat([self.data_buffer, new_row], ignore_index=True)

        # Maintain buffer size
        if len(self.data_buffer) > self.buffer_size:
            self.data_buffer = self.data_buffer.tail(self.buffer_size).reset_index(drop=True)

        # Need sufficient data for features
        if len(self.data_buffer) < 60:  # Need at least 1 minute of data
            return

        try:
            # Calculate features
            features_df = calculate_core_indicators(self.data_buffer.copy())

            # Generate window features if ML is enabled
            ml_config = getattr(self.config, 'ml', None)
            if ml_config and getattr(ml_config, 'enabled', True):
                features_df = generate_window_features(features_df, self.config)

            # Check for onset candidates
            latest_features = features_df.tail(1)
            candidates = self.candidate_detector.detect_candidates(latest_features)

            if candidates:
                logger.info(f"Found {len(candidates)} candidates at {tick_data['ts']}")

                # Check confirmation
                confirmed_events = self.confirm_detector.confirm_candidates(features_df, candidates)

                if confirmed_events:
                    logger.info(f"Confirmed {len(confirmed_events)} events")

                    for event in confirmed_events:
                        self._execute_trade(event, tick_data)

            # Check existing positions for exit conditions
            self._check_position_exits(tick_data)

        except Exception as e:
            logger.error(f"Error processing tick: {e}")

    def _execute_trade(self, confirmed_event: Dict[str, Any], current_tick: Dict[str, Any]):
        """
        Execute trade based on confirmed onset event.

        Args:
            confirmed_event: Confirmed onset event.
            current_tick: Current market tick data.
        """
        stock_code = confirmed_event['stock_code']
        current_price = current_tick['price']

        # Risk management - calculate position size
        account_balance = self.api.get_balance()
        max_position_value = account_balance * self.risk_limit_pct
        position_size = int(max_position_value / current_price)

        if position_size <= 0:
            logger.warning(f"Position size too small for {stock_code}")
            return

        # Execute buy order
        order_result = self.api.buy_order(stock_code, position_size, current_price)

        if order_result["status"] == "filled":
            # Record entry
            entry_event = create_event(
                timestamp=time.time() * 1000,
                event_type="trade_entry",
                stock_code=stock_code,
                entry_price=current_price,
                quantity=position_size,
                onset_strength=confirmed_event.get('evidence', {}).get('onset_strength', 0.5),
                order_id=order_result["order_id"],
                confirmed_from=confirmed_event['confirmed_from']
            )

            self.event_store.add_event(entry_event)

            # Track position
            self.active_positions[stock_code] = {
                "quantity": position_size,
                "entry_price": current_price,
                "entry_time": datetime.now(),
                "order_id": order_result["order_id"],
                "onset_strength": confirmed_event.get('evidence', {}).get('onset_strength', 0.5)
            }

            logger.info(f"TRADE ENTRY: {stock_code} x{position_size} @ {current_price}")
        else:
            logger.warning(f"Trade execution failed: {order_result}")

    def _check_position_exits(self, current_tick: Dict[str, Any]):
        """
        Check existing positions for exit conditions.

        Args:
            current_tick: Current market tick data.
        """
        stock_code = current_tick['stock_code']
        current_price = current_tick['price']
        current_time = datetime.now()

        if stock_code not in self.active_positions:
            return

        position = self.active_positions[stock_code]
        entry_price = position['entry_price']
        entry_time = position['entry_time']
        quantity = position['quantity']

        # Calculate return
        price_return = (current_price - entry_price) / entry_price

        # Get trading config for exit rules
        trading_config = getattr(self.config, 'trading', None)
        if trading_config and hasattr(trading_config, 'simulator'):
            simulator_config = trading_config.simulator
            hold_time_s = getattr(simulator_config, 'hold_time_s', 60)
            stop_loss_pct = getattr(simulator_config, 'stop_loss_pct', 0.01)
            take_profit_pct = getattr(simulator_config, 'take_profit_pct', 0.02)
        else:
            hold_time_s = 60
            stop_loss_pct = 0.01
            take_profit_pct = 0.02

        exit_reason = None

        # Check time-based exit
        if (current_time - entry_time).total_seconds() >= hold_time_s:
            exit_reason = "time_exit"

        # Check stop loss
        elif price_return <= -stop_loss_pct:
            exit_reason = "stop_loss"

        # Check take profit
        elif price_return >= take_profit_pct:
            exit_reason = "take_profit"

        if exit_reason:
            # Execute sell order
            order_result = self.api.sell_order(stock_code, quantity, current_price)

            if order_result["status"] == "filled":
                # Calculate PnL
                gross_pnl = quantity * (current_price - entry_price)
                fees = quantity * (entry_price + current_price) * 0.0005  # Assumed fee rate
                net_pnl = gross_pnl - fees

                # Record exit
                exit_event = create_event(
                    timestamp=time.time() * 1000,
                    event_type="trade_exit",
                    stock_code=stock_code,
                    exit_price=current_price,
                    quantity=quantity,
                    gross_pnl=gross_pnl,
                    net_pnl=net_pnl,
                    exit_reason=exit_reason,
                    order_id=order_result["order_id"],
                    entry_order_id=position["order_id"],
                    onset_strength=position["onset_strength"]
                )

                self.event_store.add_event(exit_event)

                # Remove from active positions
                del self.active_positions[stock_code]

                logger.info(f"TRADE EXIT: {stock_code} x{quantity} @ {current_price}, PnL: {net_pnl:,.0f} KRW ({exit_reason})")

    def get_status(self) -> Dict[str, Any]:
        """Get current runner status."""
        balance = self.api.get_balance()
        positions = self.api.get_positions()

        return {
            "is_running": self.is_running,
            "balance": balance,
            "positions": positions,
            "active_positions": len(self.active_positions),
            "buffer_size": len(self.data_buffer),
            "api_type": self.api_type
        }


def run_live(config: Optional[Config] = None, data_callback: Optional[Callable] = None):
    """
    Convenience function to run live trading.

    Args:
        config: Optional configuration object.
        data_callback: Optional callback function for real-time data.
    """
    runner = LiveRunner(config)
    runner.start(data_callback)


if __name__ == "__main__":
    # Demo/test the live runner
    print("Live Runner Demo")
    print("=" * 40)

    try:
        # Initialize runner
        runner = LiveRunner()
        print(f"Live runner initialized")
        print(f"API: {runner.api_type}")
        print(f"Risk limit: {runner.risk_limit_pct:.1%}")

        # Check initial status
        status = runner.get_status()
        print(f"Initial balance: {status['balance']:,} KRW")

        # Run for a short demo (10 seconds)
        print("\nStarting demo run for 10 seconds...")

        def demo_run():
            time.sleep(10)
            runner.stop()

        # Start timer to stop demo
        timer = threading.Thread(target=demo_run)
        timer.start()

        # Start runner
        runner.start()

        # Wait for demo to complete
        timer.join()

        # Final status
        final_status = runner.get_status()
        print(f"\nDemo completed")
        print(f"Final balance: {final_status['balance']:,} KRW")
        print(f"Positions: {final_status['positions']}")

    except Exception as e:
        print(f"Demo failed: {e}")
        import traceback
        traceback.print_exc()