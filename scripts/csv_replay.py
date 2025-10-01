#!/usr/bin/env python
"""
CSV to JSONL Replay Converter

Converts CSV tick data to JSONL format for streaming detection.

Usage:
    python scripts/csv_replay.py --csv data/sample.csv --out data/sample.jsonl
    python scripts/csv_replay.py --csv data/sample.csv | python scripts/step03_detect.py --stream
"""

import csv
import json
import sys
import argparse


def csv_to_jsonl(csv_path, out_stream):
    """
    Convert CSV to JSONL format.

    Args:
        csv_path: Path to input CSV file
        out_stream: Output stream (file or stdout)
    """
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Standardize column names: ts, code, price, volume, spread
            event = {
                "ts": int(row.get("ts") or row.get("timestamp") or 0),
                "code": row.get("code") or row.get("stock_code") or "",
                "price": float(row.get("price") or 0),
                "volume": int(row.get("volume") or 0),
                "spread": float(row.get("spread") or 0),
            }
            out_stream.write(json.dumps(event, ensure_ascii=False) + "\n")
            out_stream.flush()


def main():
    """Main entry point for CSV to JSONL converter."""
    parser = argparse.ArgumentParser(
        description="CSV → JSONL 변환기 (Replay converter)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        "--csv",
        required=True,
        help="입력 CSV 파일 경로"
    )

    parser.add_argument(
        "--out",
        required=False,
        help="출력 JSONL 파일 경로 (없으면 stdout)"
    )

    args = parser.parse_args()

    try:
        if args.out:
            with open(args.out, "w", encoding="utf-8") as out_f:
                csv_to_jsonl(args.csv, out_f)
                print(f"Converted {args.csv} → {args.out}", file=sys.stderr)
        else:
            csv_to_jsonl(args.csv, sys.stdout)

        return 0

    except FileNotFoundError as e:
        print(f"Error: File not found - {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
