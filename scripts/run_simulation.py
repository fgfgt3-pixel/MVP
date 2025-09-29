#!/usr/bin/env python3
"""
Trading simulation script for onset detection strategy evaluation.

Example usage:
    python scripts/run_simulation.py \
      --features data/features/023790_44indicators_realtime_20250902_withwin.csv \
      --events data/events/023790_confirmed.jsonl \
      --config config/onset_default.yaml
"""

import argparse
import sys
import json
import logging
from pathlib import Path
from datetime import datetime

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from onset_detection.src.trading import TradingSimulator
from onset_detection.src.config_loader import load_config


def setup_logging(level: str = "INFO"):
    """Setup logging configuration."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("logs/simulation.log", encoding='utf-8')
        ]
    )


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description="Run trading simulation for onset detection strategy",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic simulation
  python scripts/run_simulation.py --features data/features/sample.csv --events data/events/confirmed.jsonl

  # With custom config and output directory
  python scripts/run_simulation.py \
    --features data/features/023790_features.csv \
    --events data/events/023790_confirmed.jsonl \
    --config config/onset_default.yaml \
    --output reports/023790_simulation
        """
    )

    parser.add_argument(
        "--features",
        required=True,
        type=str,
        help="Path to features CSV file"
    )

    parser.add_argument(
        "--events",
        required=True,
        type=str,
        help="Path to events JSONL file containing confirmed events"
    )

    parser.add_argument(
        "--config",
        type=str,
        default="config/onset_default.yaml",
        help="Path to configuration YAML file (default: config/onset_default.yaml)"
    )

    parser.add_argument(
        "--output",
        type=str,
        default="reports",
        help="Output directory for simulation results (default: reports)"
    )

    parser.add_argument(
        "--prefix",
        type=str,
        default="simulation",
        help="Filename prefix for generated reports (default: simulation)"
    )

    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)"
    )

    parser.add_argument(
        "--capital",
        type=float,
        help="Override initial capital (KRW)"
    )

    parser.add_argument(
        "--hold-time",
        type=int,
        help="Override hold time in seconds"
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)

    try:
        # Validate input files
        features_path = Path(args.features)
        events_path = Path(args.events)

        if not features_path.exists():
            logger.error(f"Features file not found: {features_path}")
            return 1

        if not events_path.exists():
            logger.error(f"Events file not found: {events_path}")
            return 1

        logger.info("Starting trading simulation")
        logger.info(f"Features: {features_path}")
        logger.info(f"Events: {events_path}")
        logger.info(f"Config: {args.config}")

        # Load configuration
        config = load_config(args.config)
        logger.info(f"Configuration loaded from: {args.config}")

        # Override parameters if specified
        if args.capital is not None:
            if hasattr(config.trading, 'simulator'):
                config.trading.simulator.capital = args.capital
            logger.info(f"Capital override: {args.capital:,} KRW")

        if args.hold_time is not None:
            if hasattr(config.trading, 'simulator'):
                config.trading.simulator.hold_time_s = args.hold_time
            logger.info(f"Hold time override: {args.hold_time}s")

        # Initialize simulator
        simulator = TradingSimulator(config)
        logger.info(f"Simulator initialized")
        logger.info(f"Capital: {simulator.capital:,} KRW")
        logger.info(f"Fee rate: {simulator.fee_rate:.4f}, Slippage: {simulator.slippage:.4f}")
        logger.info(f"Hold time: {simulator.hold_time_s}s")

        # Run simulation
        logger.info("Running simulation...")
        start_time = datetime.now()

        from onset_detection.src.trading.simulator import run_simulation
        trades_df, summary = run_simulation(features_path, events_path, config)

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info(f"Simulation completed in {duration:.2f} seconds")

        # Print results
        print("\n" + "="*60)
        print("TRADING SIMULATION RESULTS")
        print("="*60)

        # Performance metrics
        perf = summary["performance"]
        print(f"Initial Capital: {perf['initial_capital']:,} KRW")
        print(f"Final Capital: {perf['final_capital']:,} KRW")
        print(f"Total PnL: {perf['total_pnl']:,} KRW")
        print(f"Total Return: {perf['total_return']:.2%}")
        print()

        # Trading metrics
        print("Trading Metrics:")
        print(f"  Total trades: {perf['n_trades']}")
        print(f"  Wins: {perf['n_wins']}, Losses: {perf['n_losses']}")
        print(f"  Win rate: {perf['win_rate']:.1%}")

        # Per-trade metrics
        per_trade = summary["per_trade"]
        print(f"  Average PnL: {per_trade['avg_pnl']:,.0f} KRW ({per_trade['avg_pnl_pct']:.2%})")
        print(f"  Best trade: {per_trade['max_pnl']:,.0f} KRW")
        print(f"  Worst trade: {per_trade['min_pnl']:,.0f} KRW")
        print(f"  Average hold time: {per_trade['avg_hold_time_s']:.1f}s")

        # Risk metrics
        risk = summary["risk"]
        print()
        print("Risk Metrics:")
        print(f"  Sharpe ratio: {risk['sharpe_ratio']:.2f}")
        print(f"  Max drawdown: {risk['max_drawdown']:.2%}")
        print(f"  Total fees: {risk['total_fees']:,.0f} KRW")

        # Exit reasons
        exits = summary["exits"]
        if exits:
            print()
            print("Exit Reasons:")
            for reason, count in exits.items():
                print(f"  {reason}: {count} trades")

        # Create output directory
        output_dir = Path(args.output)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save detailed trades
        if not trades_df.empty:
            trades_file = output_dir / f"{args.prefix}_trades.csv"
            trades_df.to_csv(trades_file, index=False)
            print(f"\nDetailed trades saved: {trades_file}")

        # Save summary
        summary_file = output_dir / f"{args.prefix}_summary.json"
        summary_data = {
            "generated_at": datetime.now().isoformat(),
            "simulation_config": {
                "features_file": str(features_path),
                "events_file": str(events_path),
                "config_file": args.config
            },
            "results": summary
        }

        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary_data, f, indent=2, ensure_ascii=False)
        print(f"Summary saved: {summary_file}")

        print("\n" + "="*60)
        logger.info("Trading simulation completed successfully")

        # Return success or failure based on results
        if perf['n_trades'] > 0:
            return 0
        else:
            logger.warning("No trades executed in simulation")
            return 1

    except KeyboardInterrupt:
        logger.info("Simulation interrupted by user")
        return 1

    except Exception as e:
        logger.error(f"Simulation execution failed: {e}")
        logger.debug("", exc_info=True)
        return 1


if __name__ == "__main__":
    # Create logs directory if it doesn't exist
    Path("logs").mkdir(exist_ok=True)

    exit_code = main()
    sys.exit(exit_code)