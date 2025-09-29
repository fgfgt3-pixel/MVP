"""Metrics computation for onset detection evaluation."""

import json
import pandas as pd
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Union, Optional

from .config_loader import Config, load_config
from .utils.paths import PathManager


class MetricsCalculator:
    """
    Calculate performance metrics for onset detection system.
    
    Computes standard metrics like recall, false positive rate, and time-to-alert
    by matching detection events against ground truth labels.
    """
    
    def __init__(self, config: Optional[Config] = None):
        """
        Initialize metrics calculator.
        
        Args:
            config: Configuration object. If None, loads default config.
        """
        self.config = config or load_config()
        self.path_manager = PathManager(self.config)
    
    def load_labels(self, labels_path: Union[str, Path]) -> pd.DataFrame:
        """
        Load label data from CSV file.
        
        Args:
            labels_path: Path to labels CSV file.
            
        Returns:
            pd.DataFrame: Labels with columns [timestamp_start, timestamp_end, stock_code, label_type].
            
        Raises:
            FileNotFoundError: If labels file doesn't exist.
            ValueError: If required columns are missing.
        """
        # Convert to absolute path if relative
        if not Path(labels_path).is_absolute():
            # If path contains directory separators, it's already a relative path from project root
            if '/' in str(labels_path) or '\\' in str(labels_path):
                labels_path = self.path_manager.project_root / labels_path
            else:
                # Just a filename, use the labels directory
                labels_path = self.path_manager.get_file_path('labels', labels_path)
        else:
            labels_path = Path(labels_path)
        
        if not labels_path.exists():
            raise FileNotFoundError(f"Labels file not found: {labels_path}")
        
        # Load labels
        labels_df = pd.read_csv(labels_path)
        
        # Validate required columns
        required_columns = ['timestamp_start', 'timestamp_end', 'stock_code', 'label_type']
        missing_columns = set(required_columns) - set(labels_df.columns)
        if missing_columns:
            raise ValueError(f"Missing required columns in labels: {missing_columns}")
        
        # Convert timestamps to numeric if they're strings
        labels_df['timestamp_start'] = pd.to_numeric(labels_df['timestamp_start'])
        labels_df['timestamp_end'] = pd.to_numeric(labels_df['timestamp_end'])
        
        return labels_df
    
    def compute_in_window_detection(self, events: List[Dict[str, Any]], labels_df: pd.DataFrame) -> Dict[str, float]:
        """
        Compute in-window detection rate (recall).
        
        For each labeled interval, check if there's at least one confirmed detection.
        
        Args:
            events: List of event dictionaries from EventStore.
            labels_df: DataFrame with ground truth labels.
            
        Returns:
            Dict with recall metrics.
        """
        if labels_df.empty:
            return {"recall": 0.0, "n_labels": 0, "n_detected": 0}
        
        # Filter confirmed detections only
        confirmed_events = [
            e for e in events 
            if e.get('event_type') in ['onset_confirmed']
        ]
        
        n_labels = len(labels_df)
        n_detected = 0
        detected_labels = []
        
        for idx, label in labels_df.iterrows():
            stock_code = label['stock_code']
            start_time = label['timestamp_start']
            end_time = label['timestamp_end']
            
            # Check if any confirmed event falls within this label window
            detected = False
            for event in confirmed_events:
                event_time = event.get('ts', 0)
                event_stock = event.get('stock_code', '')
                
                # Match stock code and time window
                if (event_stock == stock_code and 
                    start_time <= event_time <= end_time):
                    detected = True
                    break
            
            if detected:
                n_detected += 1
                detected_labels.append(idx)
        
        recall = n_detected / n_labels if n_labels > 0 else 0.0
        
        return {
            "recall": recall,
            "n_labels": n_labels,
            "n_detected": n_detected,
            "detected_label_indices": detected_labels
        }
    
    def compute_false_positive_rate(
        self, 
        events: List[Dict[str, Any]], 
        labels_df: pd.DataFrame, 
        trading_hours: float = 6.5
    ) -> Dict[str, float]:
        """
        Compute false positive rate (FP per hour).
        
        Count confirmed detections that don't fall within any labeled interval.
        
        Args:
            events: List of event dictionaries.
            labels_df: DataFrame with ground truth labels.
            trading_hours: Total trading hours for rate calculation.
            
        Returns:
            Dict with FP rate metrics.
        """
        # Filter confirmed detections only
        confirmed_events = [
            e for e in events 
            if e.get('event_type') in ['onset_confirmed']
        ]
        
        if not confirmed_events:
            return {"fp_per_hour": 0.0, "n_fp": 0, "n_confirmed": 0}
        
        n_confirmed = len(confirmed_events)
        n_fp = 0
        fp_events = []
        
        for event in confirmed_events:
            event_time = event.get('ts', 0)
            event_stock = event.get('stock_code', '')
            
            # Check if this event falls within any labeled window
            is_true_positive = False
            
            for idx, label in labels_df.iterrows():
                if (label['stock_code'] == event_stock and 
                    label['timestamp_start'] <= event_time <= label['timestamp_end']):
                    is_true_positive = True
                    break
            
            if not is_true_positive:
                n_fp += 1
                fp_events.append(event)
        
        fp_per_hour = n_fp / trading_hours if trading_hours > 0 else 0.0
        
        return {
            "fp_per_hour": fp_per_hour,
            "n_fp": n_fp,
            "n_confirmed": n_confirmed,
            "fp_events": fp_events
        }
    
    def compute_time_to_alert(self, events: List[Dict[str, Any]], labels_df: pd.DataFrame) -> Dict[str, float]:
        """
        Compute time-to-alert (TTA) statistics.
        
        Measure delay from label start time to first confirmed detection.
        
        Args:
            events: List of event dictionaries.
            labels_df: DataFrame with ground truth labels.
            
        Returns:
            Dict with TTA statistics.
        """
        if labels_df.empty:
            return {"tta_p50": 0.0, "tta_p95": 0.0, "n_tta_samples": 0}
        
        # Filter confirmed detections only
        confirmed_events = [
            e for e in events 
            if e.get('event_type') in ['onset_confirmed']
        ]
        
        tta_values = []
        
        for idx, label in labels_df.iterrows():
            stock_code = label['stock_code']
            start_time = label['timestamp_start']
            end_time = label['timestamp_end']
            
            # Find first detection within window
            first_detection_time = None
            
            for event in confirmed_events:
                event_time = event.get('ts', 0)
                event_stock = event.get('stock_code', '')
                
                if (event_stock == stock_code and 
                    start_time <= event_time <= end_time):
                    if first_detection_time is None or event_time < first_detection_time:
                        first_detection_time = event_time
            
            # Calculate TTA if detection found
            if first_detection_time is not None:
                tta = first_detection_time - start_time
                # Convert from ms to seconds if needed
                if tta > 1000:  # Assume milliseconds if > 1000
                    tta = tta / 1000.0
                tta_values.append(tta)
        
        if not tta_values:
            return {"tta_p50": 0.0, "tta_p95": 0.0, "n_tta_samples": 0}
        
        tta_array = np.array(tta_values)
        
        return {
            "tta_p50": float(np.percentile(tta_array, 50)),
            "tta_p95": float(np.percentile(tta_array, 95)),
            "tta_mean": float(np.mean(tta_array)),
            "tta_std": float(np.std(tta_array)),
            "n_tta_samples": len(tta_values),
            "tta_values": tta_values
        }
    
    def compute_all_metrics(
        self, 
        events: List[Dict[str, Any]], 
        labels_df: pd.DataFrame,
        trading_hours: float = 6.5
    ) -> Dict[str, Any]:
        """
        Compute all metrics at once.
        
        Args:
            events: List of event dictionaries.
            labels_df: DataFrame with ground truth labels.
            trading_hours: Total trading hours for FP rate calculation.
            
        Returns:
            Dict with all computed metrics.
        """
        # Compute individual metrics
        recall_metrics = self.compute_in_window_detection(events, labels_df)
        fp_metrics = self.compute_false_positive_rate(events, labels_df, trading_hours)
        tta_metrics = self.compute_time_to_alert(events, labels_df)
        
        # Event counts by type
        event_counts = {}
        for event in events:
            event_type = event.get('event_type', 'unknown')
            event_counts[event_type] = event_counts.get(event_type, 0) + 1
        
        # Combine all metrics
        all_metrics = {
            # Core metrics
            "recall": recall_metrics["recall"],
            "fp_per_hour": fp_metrics["fp_per_hour"],
            "tta_p95": tta_metrics["tta_p95"],
            
            # Detailed metrics
            "tta_p50": tta_metrics["tta_p50"],
            "tta_mean": tta_metrics.get("tta_mean", 0.0),
            
            # Counts
            "n_events": len(events),
            "n_labels": recall_metrics["n_labels"],
            "n_detected": recall_metrics["n_detected"],
            "n_confirmed": fp_metrics["n_confirmed"],
            "n_fp": fp_metrics["n_fp"],
            "n_tta_samples": tta_metrics["n_tta_samples"],
            
            # Event breakdown
            "event_counts": event_counts,
            
            # Parameters
            "trading_hours": trading_hours
        }
        
        return all_metrics
    
    def save_metrics_report(self, metrics: Dict[str, Any], output_path: Optional[Union[str, Path]] = None) -> Path:
        """
        Save metrics to JSON report file.
        
        Args:
            metrics: Computed metrics dictionary.
            output_path: Output file path. If None, uses default reports path.
            
        Returns:
            Path: Path to saved report file.
        """
        if output_path is None:
            reports_dir = self.path_manager.get_reports_path()
            output_path = reports_dir / "eval_summary.json"
        else:
            output_path = Path(output_path)
        
        # Ensure directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save metrics as JSON
        with open(output_path, 'w') as f:
            json.dump(metrics, f, indent=2, default=str)
        
        return output_path


# Convenience functions
def compute_in_window(events: List[Dict[str, Any]], labels: pd.DataFrame) -> float:
    """
    Compute in-window detection rate (recall).
    
    Args:
        events: List of event dictionaries.
        labels: DataFrame with ground truth labels.
        
    Returns:
        float: Recall value (0.0 to 1.0).
    """
    calculator = MetricsCalculator()
    result = calculator.compute_in_window_detection(events, labels)
    return result["recall"]


def compute_fp_rate(events: List[Dict[str, Any]], labels: pd.DataFrame, trading_hours: float = 6.5) -> float:
    """
    Compute false positive rate per hour.
    
    Args:
        events: List of event dictionaries.
        labels: DataFrame with ground truth labels.
        trading_hours: Total trading hours.
        
    Returns:
        float: FP per hour.
    """
    calculator = MetricsCalculator()
    result = calculator.compute_false_positive_rate(events, labels, trading_hours)
    return result["fp_per_hour"]


def compute_tta(events: List[Dict[str, Any]], labels: pd.DataFrame) -> float:
    """
    Compute time-to-alert 95th percentile.
    
    Args:
        events: List of event dictionaries.
        labels: DataFrame with ground truth labels.
        
    Returns:
        float: TTA p95 in seconds.
    """
    calculator = MetricsCalculator()
    result = calculator.compute_time_to_alert(events, labels)
    return result["tta_p95"]


if __name__ == "__main__":
    # Demo/test the metrics calculator
    from .event_store import EventStore, create_event
    import time
    
    print("Metrics Calculator Demo")
    print("=" * 40)
    
    # Create sample events
    base_time = time.time()
    sample_events = [
        create_event(base_time + 5, "onset_candidate", stock_code="005930"),
        create_event(base_time + 10, "onset_confirmed", stock_code="005930", score=2.5),
        create_event(base_time + 50, "onset_confirmed", stock_code="005930", score=1.8),  # FP
        create_event(base_time + 100, "onset_confirmed", stock_code="000660", score=3.2),
    ]
    
    # Create sample labels
    labels_data = {
        'timestamp_start': [base_time, base_time + 90],
        'timestamp_end': [base_time + 30, base_time + 120],
        'stock_code': ['005930', '000660'],
        'label_type': ['onset', 'onset']
    }
    labels_df = pd.DataFrame(labels_data)
    
    print(f"Sample events: {len(sample_events)}")
    print(f"Sample labels: {len(labels_df)}")
    
    # Compute metrics
    calculator = MetricsCalculator()
    metrics = calculator.compute_all_metrics(sample_events, labels_df, trading_hours=1.0)
    
    print(f"\nMetrics Results:")
    print(f"  Recall: {metrics['recall']:.3f}")
    print(f"  FP/hour: {metrics['fp_per_hour']:.3f}")
    print(f"  TTA p95: {metrics['tta_p95']:.3f}s")
    print(f"  Confirmed events: {metrics['n_confirmed']}")
    print(f"  Detected labels: {metrics['n_detected']}/{metrics['n_labels']}")
    
    # Save report
    report_path = calculator.save_metrics_report(metrics)
    print(f"\nReport saved to: {report_path}")