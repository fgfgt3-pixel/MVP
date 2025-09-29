"""Report generator for backtest results."""

import pandas as pd
import numpy as np
import json
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ReportGenerator:
    """
    Generate comprehensive backtest reports in multiple formats.
    """

    def __init__(self, report_dir: Optional[str] = None):
        """
        Initialize report generator.

        Args:
            report_dir: Directory to save reports. If None, uses 'reports/'.
        """
        self.report_dir = Path(report_dir or "reports")
        self.report_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Report generator initialized with directory: {self.report_dir}")

    def generate_reports(
        self,
        backtest_results: Dict[str, Any],
        prefix: str = "backtest"
    ) -> Dict[str, str]:
        """
        Generate all report formats from backtest results.

        Args:
            backtest_results: Results dictionary from Backtester.
            prefix: Filename prefix for reports.

        Returns:
            Dict: Mapping of report type to file path.
        """
        generated_files = {}

        # 1. JSON Summary Report
        json_path = self._generate_json_report(backtest_results, prefix)
        generated_files["json"] = json_path

        # 2. CSV Event Summary
        csv_path = self._generate_csv_report(backtest_results, prefix)
        generated_files["csv"] = csv_path

        # 3. PNG Charts
        png_path = self._generate_charts(backtest_results, prefix)
        generated_files["png"] = png_path

        logger.info(f"Generated {len(generated_files)} report files")
        return generated_files

    def _generate_json_report(
        self,
        backtest_results: Dict[str, Any],
        prefix: str
    ) -> str:
        """
        Generate JSON summary report.

        Args:
            backtest_results: Backtest results dictionary.
            prefix: Filename prefix.

        Returns:
            str: Path to generated JSON file.
        """
        json_path = self.report_dir / f"{prefix}_summary.json"

        # Extract metrics and add metadata
        report_data = {
            "generated_at": datetime.now().isoformat(),
            "backtest_config": backtest_results.get("config", {}),
            "metrics": backtest_results.get("metrics", {}),
            "summary": self._create_summary_stats(backtest_results)
        }

        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)

        logger.info(f"JSON report saved: {json_path}")
        return str(json_path)

    def _generate_csv_report(
        self,
        backtest_results: Dict[str, Any],
        prefix: str
    ) -> str:
        """
        Generate CSV event summary report.

        Args:
            backtest_results: Backtest results dictionary.
            prefix: Filename prefix.

        Returns:
            str: Path to generated CSV file.
        """
        csv_path = self.report_dir / f"{prefix}_events.csv"

        # Get event summary DataFrame
        event_summary = backtest_results.get("event_summary", pd.DataFrame())

        if event_summary.empty:
            # Create empty DataFrame with expected columns
            event_summary = pd.DataFrame(columns=[
                "candidate_ts", "stock_code", "candidate_score", "is_confirmed",
                "confirm_ts", "tta_seconds", "onset_strength", "satisfied_axes"
            ])

        # Add human-readable timestamps
        if not event_summary.empty:
            # Convert timestamps to readable format
            if 'candidate_ts' in event_summary.columns:
                event_summary['candidate_datetime'] = pd.to_datetime(
                    event_summary['candidate_ts'], unit='ms', errors='coerce'
                ).dt.strftime('%Y-%m-%d %H:%M:%S')

            if 'confirm_ts' in event_summary.columns:
                event_summary['confirm_datetime'] = pd.to_datetime(
                    event_summary['confirm_ts'], unit='ms', errors='coerce'
                ).dt.strftime('%Y-%m-%d %H:%M:%S')

        event_summary.to_csv(csv_path, index=False, encoding='utf-8')
        logger.info(f"CSV report saved: {csv_path} ({len(event_summary)} events)")
        return str(csv_path)

    def _generate_charts(
        self,
        backtest_results: Dict[str, Any],
        prefix: str
    ) -> str:
        """
        Generate PNG charts from backtest results.

        Args:
            backtest_results: Backtest results dictionary.
            prefix: Filename prefix.

        Returns:
            str: Path to generated PNG file.
        """
        png_path = self.report_dir / f"{prefix}_charts.png"

        # Create figure with subplots
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle('Backtest Results Dashboard', fontsize=16, fontweight='bold')

        try:
            metrics = backtest_results.get("metrics", {})
            event_summary = backtest_results.get("event_summary", pd.DataFrame())

            # Chart 1: Confirmation Rate & Key Metrics
            self._plot_key_metrics(axes[0, 0], metrics)

            # Chart 2: TTA Distribution
            self._plot_tta_distribution(axes[0, 1], event_summary, metrics)

            # Chart 3: Axes Distribution
            self._plot_axes_distribution(axes[1, 0], metrics)

            # Chart 4: Time Series Events
            self._plot_events_timeline(axes[1, 1], event_summary)

            plt.tight_layout()
            plt.savefig(png_path, dpi=300, bbox_inches='tight')
            plt.close()

            logger.info(f"Charts saved: {png_path}")

        except Exception as e:
            logger.error(f"Failed to generate charts: {e}")
            # Create a simple error chart
            fig, ax = plt.subplots(figsize=(8, 6))
            ax.text(0.5, 0.5, f'Chart generation failed:\n{str(e)}',
                   ha='center', va='center', transform=ax.transAxes,
                   fontsize=12, bbox=dict(boxstyle="round,pad=0.3", facecolor="lightcoral"))
            ax.set_title('Backtest Charts - Error')
            ax.axis('off')
            plt.savefig(png_path, dpi=300, bbox_inches='tight')
            plt.close()

        return str(png_path)

    def _plot_key_metrics(self, ax, metrics: Dict[str, Any]):
        """Plot key performance metrics."""
        events = metrics.get("events", {})
        timing = metrics.get("timing", {})

        # Key metrics to display
        key_values = [
            ("Candidates", events.get("candidates", 0)),
            ("Confirmed", events.get("confirmed", 0)),
            ("Confirm Rate %", events.get("confirm_rate", 0) * 100),
            ("FP/Hour", timing.get("fp_per_hour", 0))
        ]

        labels = [kv[0] for kv in key_values]
        values = [kv[1] for kv in key_values]

        bars = ax.bar(labels, values, color=['skyblue', 'lightgreen', 'orange', 'lightcoral'])

        # Add value labels on bars
        for bar, value in zip(bars, values):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{value:.1f}', ha='center', va='bottom')

        ax.set_title('Key Performance Metrics')
        ax.set_ylabel('Count / Rate')
        plt.setp(ax.get_xticklabels(), rotation=45, ha='right')

    def _plot_tta_distribution(self, ax, event_summary: pd.DataFrame, metrics: Dict[str, Any]):
        """Plot Time-to-Alert distribution."""
        if event_summary.empty or 'tta_seconds' not in event_summary.columns:
            ax.text(0.5, 0.5, 'No TTA data available', ha='center', va='center',
                   transform=ax.transAxes, fontsize=12)
            ax.set_title('Time-to-Alert Distribution')
            return

        # Filter confirmed events with valid TTA
        tta_data = event_summary[
            (event_summary['is_confirmed'] == True) &
            (event_summary['tta_seconds'].notna())
        ]['tta_seconds']

        if len(tta_data) == 0:
            ax.text(0.5, 0.5, 'No confirmed events', ha='center', va='center',
                   transform=ax.transAxes, fontsize=12)
            ax.set_title('Time-to-Alert Distribution')
            return

        # Create histogram
        ax.hist(tta_data, bins=min(20, len(tta_data)), alpha=0.7, color='lightblue', edgecolor='black')

        # Add statistics lines
        tta_stats = metrics.get("timing", {}).get("tta_stats", {})
        if tta_stats:
            median_val = tta_stats.get("median", 0)
            p95_val = tta_stats.get("p95", 0)

            ax.axvline(median_val, color='red', linestyle='--', label=f'Median: {median_val:.1f}s')
            ax.axvline(p95_val, color='orange', linestyle='--', label=f'P95: {p95_val:.1f}s')
            ax.legend()

        ax.set_title('Time-to-Alert Distribution')
        ax.set_xlabel('TTA (seconds)')
        ax.set_ylabel('Count')

    def _plot_axes_distribution(self, ax, metrics: Dict[str, Any]):
        """Plot axes satisfaction distribution."""
        axes_data = metrics.get("axes", {}).get("distribution", {})

        if not axes_data:
            ax.text(0.5, 0.5, 'No axes data available', ha='center', va='center',
                   transform=ax.transAxes, fontsize=12)
            ax.set_title('Axes Satisfaction Distribution')
            return

        axes_names = list(axes_data.keys())
        axes_rates = [axes_data[name] * 100 for name in axes_names]

        bars = ax.bar(axes_names, axes_rates, color=['lightblue', 'lightgreen', 'lightcoral'])

        # Add percentage labels
        for bar, rate in zip(bars, axes_rates):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{rate:.1f}%', ha='center', va='bottom')

        ax.set_title('Axes Satisfaction Distribution')
        ax.set_ylabel('Satisfaction Rate (%)')
        ax.set_ylim(0, 100)

    def _plot_events_timeline(self, ax, event_summary: pd.DataFrame):
        """Plot events timeline."""
        if event_summary.empty or 'candidate_ts' not in event_summary.columns:
            ax.text(0.5, 0.5, 'No event data available', ha='center', va='center',
                   transform=ax.transAxes, fontsize=12)
            ax.set_title('Events Timeline')
            return

        # Convert timestamps to datetime
        event_summary_copy = event_summary.copy()
        event_summary_copy['candidate_dt'] = pd.to_datetime(
            event_summary_copy['candidate_ts'], unit='ms', errors='coerce'
        )

        # Separate confirmed and unconfirmed events
        confirmed = event_summary_copy[event_summary_copy['is_confirmed'] == True]
        unconfirmed = event_summary_copy[event_summary_copy['is_confirmed'] == False]

        # Plot events
        if len(unconfirmed) > 0:
            ax.scatter(unconfirmed['candidate_dt'], [0] * len(unconfirmed),
                      c='red', marker='x', s=50, alpha=0.7, label='Unconfirmed')

        if len(confirmed) > 0:
            ax.scatter(confirmed['candidate_dt'], [1] * len(confirmed),
                      c='green', marker='o', s=50, alpha=0.7, label='Confirmed')

        ax.set_title('Events Timeline')
        ax.set_xlabel('Time')
        ax.set_ylabel('Event Type')
        ax.set_yticks([0, 1])
        ax.set_yticklabels(['Unconfirmed', 'Confirmed'])
        ax.grid(True, alpha=0.3)

        if len(event_summary_copy) > 0:
            ax.legend()

        # Format x-axis
        if len(event_summary_copy) > 0:
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            plt.setp(ax.get_xticklabels(), rotation=45)

    def _create_summary_stats(self, backtest_results: Dict[str, Any]) -> Dict[str, Any]:
        """Create high-level summary statistics."""
        metrics = backtest_results.get("metrics", {})
        event_summary = backtest_results.get("event_summary", pd.DataFrame())

        summary = {
            "total_candidates": metrics.get("events", {}).get("candidates", 0),
            "total_confirmed": metrics.get("events", {}).get("confirmed", 0),
            "confirmation_rate": metrics.get("events", {}).get("confirm_rate", 0.0),
            "false_positives_per_hour": metrics.get("timing", {}).get("fp_per_hour", 0.0),
            "backtest_period": {
                "start": metrics.get("period", {}).get("start_date", ""),
                "end": metrics.get("period", {}).get("end_date", ""),
                "duration_hours": metrics.get("period", {}).get("time_span_hours", 0.0)
            }
        }

        # Add TTA statistics if available
        tta_stats = metrics.get("timing", {}).get("tta_stats", {})
        if tta_stats:
            summary["time_to_alert"] = {
                "median_seconds": tta_stats.get("median", 0.0),
                "p95_seconds": tta_stats.get("p95", 0.0),
                "mean_seconds": tta_stats.get("mean", 0.0)
            }

        # Add ML statistics if available
        ml_stats = metrics.get("ml", {})
        if ml_stats:
            summary["ml_integration"] = {
                "hybrid_used": ml_stats.get("hybrid_used", False),
                "onset_strength_available": bool(ml_stats.get("onset_strength_stats"))
            }

        return summary


def generate_backtest_report(
    backtest_results: Dict[str, Any],
    report_dir: Optional[str] = None,
    prefix: str = "backtest"
) -> Dict[str, str]:
    """
    Convenience function to generate backtest reports.

    Args:
        backtest_results: Results dictionary from Backtester.
        report_dir: Directory to save reports.
        prefix: Filename prefix.

    Returns:
        Dict: Mapping of report type to file path.
    """
    generator = ReportGenerator(report_dir)
    return generator.generate_reports(backtest_results, prefix)


if __name__ == "__main__":
    # Demo/test the report generator
    print("Report Generator Demo")
    print("=" * 40)

    # Create sample backtest results
    sample_results = {
        "metrics": {
            "period": {
                "start_date": "2025-09-01",
                "end_date": "2025-09-30",
                "time_span_hours": 240.0
            },
            "events": {
                "candidates": 25,
                "confirmed": 15,
                "confirm_rate": 0.6
            },
            "timing": {
                "tta_stats": {
                    "mean": 3.5,
                    "median": 2.8,
                    "p50": 2.8,
                    "p95": 8.2,
                    "min": 0.5,
                    "max": 15.0
                },
                "fp_per_hour": 0.0625
            },
            "axes": {
                "distribution": {"price": 0.8, "volume": 0.6, "friction": 0.4},
                "counts": {"price": 12, "volume": 9, "friction": 6}
            },
            "ml": {
                "onset_strength_stats": {
                    "mean": 0.72,
                    "median": 0.68,
                    "min": 0.35,
                    "max": 0.95,
                    "count": 15
                },
                "hybrid_used": True
            },
            "data": {
                "features_rows": 8640,
                "features_columns": 23
            }
        },
        "event_summary": pd.DataFrame({
            "candidate_ts": [1725202800000, 1725203400000, 1725204000000],
            "stock_code": ["005930", "005930", "005930"],
            "candidate_score": [2.5, 3.1, 2.8],
            "is_confirmed": [True, False, True],
            "confirm_ts": [1725202803000, None, 1725204005000],
            "tta_seconds": [3.0, None, 5.0],
            "onset_strength": [0.72, None, 0.68],
            "satisfied_axes": ["price,volume", "", "price,friction"]
        }),
        "config": {
            "use_hybrid": True,
            "date_range": "2025-09-01 to 2025-09-30"
        }
    }

    try:
        # Generate reports
        generator = ReportGenerator("reports")
        generated_files = generator.generate_reports(sample_results, "demo")

        print(f"Generated files:")
        for report_type, file_path in generated_files.items():
            print(f"  {report_type.upper()}: {file_path}")

        print(f"\nReport generation completed successfully!")

    except Exception as e:
        print(f"Demo failed: {e}")
        import traceback
        traceback.print_exc()