#!/usr/bin/env python
"""
Detection Only Pipeline Script - Step 03

This script runs the onset detection pipeline in Detection Only mode:
1. Load CSV or JSONL data
2. Generate features (if not already present)
3. Run detection pipeline: candidates -> confirm -> refractory
4. Output alerts to JSONL or stdout

Usage:
    python scripts/step03_detect.py --input data/features/sample.csv
    python scripts/step03_detect.py --input data/clean/sample.csv --generate-features
    python scripts/step03_detect.py --config config/onset_default.yaml --input data/features/sample.csv

Environment Variables:
    MVP_CONFIG: Path to config YAML file (default: config/onset_default.yaml)
"""

import argparse
import json
import sys
import os
from pathlib import Path
import logging

# Add project root to path
project_root = Path(__file__).parent.parent
onset_detection_path = project_root / "onset_detection"
sys.path.insert(0, str(onset_detection_path))

from src.detection.onset_pipeline import OnsetPipelineDF
from src.config_loader import load_config
from src.features import calculate_core_indicators


def setup_logging(level: str = "INFO"):
    """Setup logging configuration."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stderr)  # Log to stderr to keep stdout clean for alerts
        ]
    )


def load_data(input_path: str, generate_features: bool = False):
    """
    Load input data from CSV or JSONL.

    Args:
        input_path: Path to input file.
        generate_features: If True, generate features from clean data.

    Returns:
        DataFrame with features ready for detection.
    """
    import pandas as pd

    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    logger = logging.getLogger(__name__)
    logger.info(f"Loading data from: {input_path}")

    # Load data based on extension
    if input_path.suffix == '.csv':
        df = pd.read_csv(input_path)
    elif input_path.suffix == '.jsonl':
        df = pd.read_json(input_path, lines=True)
    else:
        raise ValueError(f"Unsupported file format: {input_path.suffix}")

    logger.info(f"Loaded {len(df)} rows from {input_path}")

    # Generate features if requested
    if generate_features:
        logger.info("Generating features from clean data")
        features_df = calculate_core_indicators(df)
        logger.info(f"Generated {len(features_df)} feature rows")
        return features_df
    else:
        # Assume features are already present
        return df


def output_alerts(alerts, output_path=None):
    """
    Output alerts to file or stdout.

    Args:
        alerts: List of alert events.
        output_path: Optional path to output JSONL file. If None, prints to stdout.
    """
    logger = logging.getLogger(__name__)

    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            for alert in alerts:
                f.write(json.dumps(alert, ensure_ascii=False) + '\n')

        logger.info(f"Saved {len(alerts)} alerts to {output_path}")
    else:
        # Print to stdout
        for alert in alerts:
            print(json.dumps(alert, ensure_ascii=False))
            sys.stdout.flush()


def main():
    """Main entry point for detection pipeline."""
    parser = argparse.ArgumentParser(
        description="Run Detection Only onset pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        '--input',
        type=str,
        required=False,
        help='Input CSV or JSONL file (features or clean data). Not used with --stream.'
    )

    parser.add_argument(
        '--stream',
        action='store_true',
        help='Streaming mode: read JSONL from stdin line-by-line (for csv_replay.py pipe)'
    )

    parser.add_argument(
        '--config',
        type=str,
        default=None,
        help='Path to config YAML file (default: $MVP_CONFIG or config/onset_default.yaml)'
    )

    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='Output JSONL file for alerts (default: stdout)'
    )

    parser.add_argument(
        '--generate-features',
        action='store_true',
        help='Generate features from clean data (use if input is clean CSV, not features)'
    )

    parser.add_argument(
        '--log-level',
        type=str,
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Logging level (default: INFO)'
    )

    parser.add_argument(
        '--stats',
        action='store_true',
        help='Print pipeline statistics to stderr'
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.stream and not args.input:
        parser.error("Either --input or --stream must be specified")

    # Setup logging
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)

    try:
        # Load config
        config_path = args.config or os.environ.get("MVP_CONFIG", "onset_detection/config/onset_default.yaml")
        logger.info(f"Loading config from: {config_path}")
        config = load_config(config_path=config_path, load_env=True)

        # Initialize pipeline
        logger.info("Initializing onset detection pipeline")
        pipeline = OnsetPipelineDF(config=config)

        # Streaming mode
        if args.stream:
            logger.info("Running in streaming mode (stdin)")
            alert_count = 0

            for line in sys.stdin:
                line = line.strip()
                if not line:
                    continue

                try:
                    raw_tick = json.loads(line)
                    alert = pipeline.run_tick(raw_tick)

                    if alert:
                        output_alerts([alert], output_path=args.output)
                        alert_count += 1

                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON: {line[:50]}")
                    continue
                except Exception as e:
                    logger.error(f"Error processing tick: {e}")
                    continue

            logger.info(f"Streaming complete: {alert_count} alerts generated")
            return 0

        # Batch mode
        else:
            # Load data
            features_df = load_data(args.input, generate_features=args.generate_features)

            if features_df.empty:
                logger.warning("No data to process")
                return 0

            # Run detection
            logger.info("Running detection pipeline (batch mode)")
            result = pipeline.run_batch(features_df, return_intermediates=args.stats)

            # Output alerts
            alerts = result['alerts']
            logger.info(f"Pipeline complete: {len(alerts)} alerts generated")

            output_alerts(alerts, output_path=args.output)

            # Print statistics if requested
            if args.stats:
                stats = {
                    "candidates_detected": result['candidates_count'],
                    "rejected_refractory": result['rejected_count'],
                    "onsets_confirmed": result['confirmed_count'],
                    "alerts_output": len(alerts)
                }

                logger.info("=" * 50)
                logger.info("Pipeline Statistics:")
                for key, value in stats.items():
                    logger.info(f"  {key}: {value}")
                logger.info("=" * 50)

            return 0

    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        return 1
    except ValueError as e:
        logger.error(f"Value error: {e}")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
