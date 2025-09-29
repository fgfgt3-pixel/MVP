#!/usr/bin/env python3
"""
Backtest execution script for onset detection evaluation.

Example usage:
    python scripts/backtest_run.py \
      --features data/features/023790_44indicators_realtime_20250902_withwin.csv \
      --events data/events/023790_candidates.jsonl \
      --config config/onset_default.yaml
"""

import argparse
import sys
import logging
from pathlib import Path
from datetime import datetime

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from onset_detection.src.backtest import Backtester, ReportGenerator
from onset_detection.src.config_loader import load_config


def setup_logging(level: str = "INFO"):
    """Setup logging configuration."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("logs/backtest.log", encoding='utf-8')
        ]
    )


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description="Run backtest for onset detection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic backtest
  python scripts/backtest_run.py --features data/features/sample.csv --events data/events/sample.jsonl

  # With custom config and output directory
  python scripts/backtest_run.py \
    --features data/features/023790_features.csv \
    --events data/events/023790_candidates.jsonl \
    --config config/onset_default.yaml \
    --output reports/023790_backtest
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
        help="Path to events JSONL file containing candidates"
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
        help="Output directory for reports (default: from config.backtest.report_dir)"
    )

    parser.add_argument(
        "--prefix",
        type=str,
        default="backtest",
        help="Filename prefix for generated reports (default: backtest)"
    )

    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)"
    )

    parser.add_argument(
        "--no-reports",
        action="store_true",
        help="Skip report generation, only run backtest"
    )

    parser.add_argument(
        "--hybrid",
        type=bool,
        help="Override hybrid confirmation setting (true/false)"
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

        logger.info("Starting backtest execution")
        logger.info(f"Features: {features_path}")
        logger.info(f"Events: {events_path}")
        logger.info(f"Config: {args.config}")

        # Load configuration
        config = load_config(args.config)
        logger.info(f"Configuration loaded from: {args.config}")

        # Override hybrid setting if specified
        if args.hybrid is not None:
            if hasattr(config, 'backtest'):
                config.backtest.use_hybrid_confirm = args.hybrid
            else:
                logger.warning("No backtest configuration found, cannot override hybrid setting")
            logger.info(f"Hybrid confirmation override: {args.hybrid}")

        # Initialize backtester
        backtester = Backtester(config)
        logger.info(f"Backtester initialized for period: {backtester.start_date} to {backtester.end_date}")
        logger.info(f"Hybrid mode: {backtester.use_hybrid_confirm}")

        # Run backtest
        logger.info("Running backtest...")
        start_time = datetime.now()

        results = backtester.run_backtest(features_path, events_path)

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info(f"Backtest completed in {duration:.2f} seconds")

        # Print key metrics
        metrics = results.get("metrics", {})
        events = metrics.get("events", {})
        timing = metrics.get("timing", {})

        print("\n" + "="*60)
        print("BACKTEST RESULTS SUMMARY")
        print("="*60)
        print(f"Period: {metrics.get('period', {}).get('start_date')} to {metrics.get('period', {}).get('end_date')}")
        print(f"Time span: {metrics.get('period', {}).get('time_span_hours', 0):.1f} hours")
        print(f"Hybrid mode: {results.get('config', {}).get('use_hybrid', False)}")
        print()
        print("Event Metrics:")
        print(f"  Candidates: {events.get('candidates', 0)}")
        print(f"  Confirmed: {events.get('confirmed', 0)}")
        print(f"  Confirmation rate: {events.get('confirm_rate', 0) * 100:.1f}%")
        print()
        print("Performance Metrics:")
        tta_stats = timing.get("tta_stats", {})
        if tta_stats:
            print(f"  TTA Median: {tta_stats.get('median', 0):.1f}s")
            print(f"  TTA P95: {tta_stats.get('p95', 0):.1f}s")
        print(f"  False positives/hour: {timing.get('fp_per_hour', 0):.3f}")

        axes_dist = metrics.get("axes", {}).get("distribution", {})
        if axes_dist:
            print()
            print("Axes Distribution:")
            for axis, rate in axes_dist.items():
                print(f"  {axis.capitalize()}: {rate * 100:.1f}%")

        # Generate reports if requested
        if not args.no_reports:
            logger.info("Generating reports...")

            # Determine output directory
            if args.output:
                report_dir = args.output
            else:
                report_dir = getattr(config.backtest, 'report_dir', 'reports')

            # Generate reports
            generator = ReportGenerator(report_dir)
            generated_files = generator.generate_reports(results, args.prefix)

            print()
            print("Generated Reports:")
            for report_type, file_path in generated_files.items():
                print(f"  {report_type.upper()}: {file_path}")
                logger.info(f"Generated {report_type} report: {file_path}")

        print("\n" + "="*60)
        logger.info("Backtest execution completed successfully")
        return 0

    except KeyboardInterrupt:
        logger.info("Backtest interrupted by user")
        return 1

    except Exception as e:
        logger.error(f"Backtest execution failed: {e}")
        logger.debug("", exc_info=True)
        return 1


if __name__ == "__main__":
    # Create logs directory if it doesn't exist
    Path("logs").mkdir(exist_ok=True)

    exit_code = main()
    sys.exit(exit_code)