#!/usr/bin/env python3
"""CLI script for testing replay engine functionality."""

import argparse
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.data_loader import DataLoader, load_sample_data
from src.replay_engine import ReplaySource, ReplayEngine, create_simple_replay
from src.config_loader import load_config


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="Test replay engine with CSV data")
    
    # Input options
    parser.add_argument("--csv", type=str, help="Path to CSV file (relative to data/raw or absolute)")
    parser.add_argument("--sample", action="store_true", help="Use built-in sample data")
    
    # Replay options
    parser.add_argument("--head", type=int, default=20, help="Number of rows to replay (default: 20)")
    parser.add_argument("--speed", type=float, default=1.0, help="Playback speed (default: 1.0)")
    parser.add_argument("--sleep", action="store_true", help="Enable real-time delays")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    # Output format
    parser.add_argument("--format", choices=["simple", "detailed", "json"], default="simple",
                       help="Output format (default: simple)")
    
    args = parser.parse_args()
    
    # Validate arguments
    if not args.csv and not args.sample:
        print("Error: Must specify either --csv or --sample")
        return 1
    
    try:
        # Load configuration
        config = load_config()
        loader = DataLoader(config)
        
        # Load data
        if args.sample:
            print("Loading sample data...")
            df = load_sample_data(config)
        else:
            print(f"Loading CSV file: {args.csv}")
            df = loader.load_csv(args.csv)
        
        print(f"Loaded {len(df)} rows of data")
        
        if args.verbose:
            info = loader.get_data_info(df)
            print(f"Date range: {info['date_range']['start']} to {info['date_range']['end']}")
            print(f"Stocks: {info['stocks']}")
            print(f"Price range: {info['price_stats']['min']:.0f} - {info['price_stats']['max']:.0f}")
        
        # Test replay
        print(f"\nReplaying first {args.head} ticks (speed: {args.speed}x, sleep: {args.sleep}):")
        print("-" * 60)
        
        if args.format == "simple":
            run_simple_replay(df, args)
        elif args.format == "detailed":
            run_detailed_replay(df, args)
        elif args.format == "json":
            run_json_replay(df, args)
        
        print("\nReplay completed successfully!")
        return 0
        
    except Exception as e:
        print(f"Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def run_simple_replay(df, args):
    """Run simple replay with basic output."""
    count = 0
    
    for tick in create_simple_replay(df, speed=args.speed, sleep=args.sleep):
        if count >= args.head:
            break
        
        print(f"#{count+1:3d}: {tick['stock_code']} | "
              f"Price: {tick['price']:,} | "
              f"Volume: {tick['volume']:,} | "
              f"Spread: {tick['spread']:.0f} | "
              f"Time: {tick['ts'].strftime('%H:%M:%S')}")
        
        count += 1


def run_detailed_replay(df, args):
    """Run replay with detailed output."""
    engine = ReplayEngine()
    source = engine.add_source("test", df, speed=args.speed, sleep=args.sleep)
    
    def detailed_callback(tick):
        metadata = tick['_metadata']
        print(f"#{metadata['index']+1:3d} [{metadata['progress_pct']:5.1f}%]: "
              f"{tick['stock_code']} @ {tick['price']:,}")
        print(f"     Volume: {tick['volume']:,}, Spread: {tick['spread']:.0f}, "
              f"Imbalance: {tick.get('bid_ask_imbalance', 0):.3f}")
        print(f"     Bid: {tick['bid1']:,} ({tick['bid_qty1']:,}), "
              f"Ask: {tick['ask1']:,} ({tick['ask_qty1']:,})")
        print(f"     Time: {tick['ts']}, Delta: {tick.get('time_delta', 0):.1f}s")
        print()
    
    count = 0
    for tick in engine.replay_source("test", limit=args.head, callback=detailed_callback):
        count += 1
    
    print(f"Total ticks processed: {count}")


def run_json_replay(df, args):
    """Run replay with JSON output."""
    import json
    
    engine = ReplayEngine()
    engine.add_source("test", df, speed=args.speed, sleep=args.sleep)
    
    ticks = []
    for i, tick in enumerate(engine.replay_source("test", limit=args.head)):
        if i >= args.head:
            break
        
        # Convert timestamp to string for JSON serialization
        tick_copy = tick.copy()
        tick_copy['ts'] = tick_copy['ts'].isoformat()
        
        ticks.append(tick_copy)
    
    output = {
        "metadata": {
            "total_ticks": len(ticks),
            "speed": args.speed,
            "sleep_enabled": args.sleep,
            "source_file": args.csv or "sample"
        },
        "ticks": ticks
    }
    
    print(json.dumps(output, indent=2, default=str))


if __name__ == "__main__":
    sys.exit(main())