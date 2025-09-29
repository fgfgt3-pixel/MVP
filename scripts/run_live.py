#!/usr/bin/env python3
"""
Live trading execution script for onset detection strategy.

Example usage:
    python scripts/run_live.py --config config/onset_default.yaml
"""

import argparse
import sys
import time
import signal
import logging
from pathlib import Path
from datetime import datetime

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from onset_detection.src.trading import LiveRunner
from onset_detection.src.config_loader import load_config


def setup_logging(level: str = "INFO"):
    """Setup logging configuration."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("logs/live.log", encoding='utf-8')
        ]
    )


def signal_handler(signum, frame):
    """Handle interrupt signals gracefully."""
    print("\nReceived interrupt signal. Shutting down...")
    global runner
    if runner:
        runner.stop()
    sys.exit(0)


runner = None  # Global variable for signal handler


def main():
    """Main execution function."""
    global runner

    parser = argparse.ArgumentParser(
        description="Run live trading execution for onset detection strategy",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic live trading
  python scripts/run_live.py --config config/onset_default.yaml

  # With custom API and risk settings
  python scripts/run_live.py \
    --config config/onset_default.yaml \
    --api dummy \
    --risk-limit 0.03

  # Demo mode (shorter run for testing)
  python scripts/run_live.py --config config/onset_default.yaml --demo
        """
    )

    parser.add_argument(
        "--config",
        type=str,
        default="config/onset_default.yaml",
        help="Path to configuration YAML file (default: config/onset_default.yaml)"
    )

    parser.add_argument(
        "--api",
        type=str,
        choices=["dummy", "kiwoom"],
        help="Override API type (dummy or kiwoom)"
    )

    parser.add_argument(
        "--account",
        type=str,
        help="Override trading account number"
    )

    parser.add_argument(
        "--risk-limit",
        type=float,
        help="Override risk limit percentage (0.01 = 1%%)"
    )

    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)"
    )

    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run in demo mode (30 seconds) for testing"
    )

    parser.add_argument(
        "--status-interval",
        type=int,
        default=30,
        help="Status update interval in seconds (default: 30)"
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)

    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        logger.info("Starting live trading runner")
        logger.info(f"Config: {args.config}")

        # Load configuration
        config = load_config(args.config)
        logger.info(f"Configuration loaded from: {args.config}")

        # Override parameters if specified
        if args.api is not None:
            if hasattr(config.trading, 'live'):
                config.trading.live.api = args.api
            logger.info(f"API override: {args.api}")

        if args.account is not None:
            if hasattr(config.trading, 'live'):
                config.trading.live.account_no = args.account
            logger.info(f"Account override: {args.account}")

        if args.risk_limit is not None:
            if hasattr(config.trading, 'live'):
                config.trading.live.risk_limit_pct = args.risk_limit
            logger.info(f"Risk limit override: {args.risk_limit:.1%}")

        # Initialize live runner
        runner = LiveRunner(config)
        logger.info(f"Live runner initialized")
        logger.info(f"API: {runner.api_type}, Account: {runner.account_no}")
        logger.info(f"Risk limit: {runner.risk_limit_pct:.1%}")

        # Create reports directory
        Path("reports").mkdir(exist_ok=True)

        # Print initial status
        initial_status = runner.get_status()
        print("\n" + "="*60)
        print("LIVE TRADING RUNNER STARTED")
        print("="*60)
        print(f"API Type: {initial_status['api_type']}")
        print(f"Initial Balance: {initial_status['balance']:,} KRW")
        print(f"Active Positions: {initial_status['active_positions']}")
        print(f"Risk Limit: {runner.risk_limit_pct:.1%}")
        print()

        if args.demo:
            print("DEMO MODE - Running for 30 seconds...")
        else:
            print("LIVE MODE - Press Ctrl+C to stop")

        print()
        logger.info("Live runner starting...")

        # Start live runner in separate thread for status monitoring
        import threading

        def run_live():
            try:
                runner.start()
            except Exception as e:
                logger.error(f"Live runner error: {e}")

        live_thread = threading.Thread(target=run_live, daemon=True)
        live_thread.start()

        # Status monitoring loop
        start_time = datetime.now()
        last_status_time = start_time

        while runner.is_running:
            try:
                current_time = datetime.now()

                # Demo mode timeout
                if args.demo and (current_time - start_time).total_seconds() >= 30:
                    logger.info("Demo mode timeout reached")
                    break

                # Status update
                if (current_time - last_status_time).total_seconds() >= args.status_interval:
                    status = runner.get_status()
                    runtime = (current_time - start_time).total_seconds()

                    print(f"[{current_time.strftime('%H:%M:%S')}] "
                          f"Runtime: {runtime:.0f}s, "
                          f"Balance: {status['balance']:,} KRW, "
                          f"Positions: {status['active_positions']}, "
                          f"Buffer: {status['buffer_size']}")

                    last_status_time = current_time

                time.sleep(1)

            except KeyboardInterrupt:
                break

        # Stop runner
        if runner.is_running:
            runner.stop()

        # Wait for live thread to finish
        if live_thread.is_alive():
            live_thread.join(timeout=5)

        # Final status
        final_status = runner.get_status()
        end_time = datetime.now()
        total_runtime = (end_time - start_time).total_seconds()

        print("\n" + "="*60)
        print("LIVE TRADING RUNNER STOPPED")
        print("="*60)
        print(f"Total Runtime: {total_runtime:.0f} seconds")
        print(f"Final Balance: {final_status['balance']:,} KRW")
        print(f"Final Positions: {final_status['positions']}")

        # Calculate PnL
        pnl = final_status['balance'] - initial_status['balance']
        pnl_pct = pnl / initial_status['balance'] if initial_status['balance'] > 0 else 0

        print(f"Session PnL: {pnl:,} KRW ({pnl_pct:.2%})")
        print(f"Trade log: reports/live_trades.jsonl")

        # Check if trade log exists and show summary
        trades_file = Path("reports/live_trades.jsonl")
        if trades_file.exists():
            try:
                import json
                trades = []
                with open(trades_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        trades.append(json.loads(line))

                entries = [t for t in trades if t.get('event_type') == 'trade_entry']
                exits = [t for t in trades if t.get('event_type') == 'trade_exit']

                print(f"Trade entries: {len(entries)}")
                print(f"Trade exits: {len(exits)}")

                if exits:
                    total_pnl = sum(t.get('net_pnl', 0) for t in exits)
                    print(f"Total trade PnL: {total_pnl:,} KRW")

            except Exception as e:
                logger.warning(f"Failed to read trade log: {e}")

        print("\n" + "="*60)
        logger.info("Live trading runner completed successfully")

        return 0

    except KeyboardInterrupt:
        logger.info("Live runner interrupted by user")
        return 1

    except Exception as e:
        logger.error(f"Live runner execution failed: {e}")
        logger.debug("", exc_info=True)
        return 1

    finally:
        if runner and runner.is_running:
            runner.stop()


if __name__ == "__main__":
    # Create logs directory if it doesn't exist
    Path("logs").mkdir(exist_ok=True)

    exit_code = main()
    sys.exit(exit_code)