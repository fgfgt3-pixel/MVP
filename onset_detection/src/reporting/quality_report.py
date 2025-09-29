"""Quality reporting for onset detection events."""

import json
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, Any, List, Optional, Union

from ..config_loader import Config, load_config
from ..event_store import EventStore
from ..utils.paths import PathManager


class QualityReporter:
    """
    Generate quality reports for onset detection events.
    
    Analyzes candidate, confirmation, and refractory events to produce
    comprehensive quality metrics and performance statistics.
    """
    
    def __init__(self, config: Optional[Config] = None):
        """
        Initialize quality reporter.
        
        Args:
            config: Configuration object. If None, loads default config.
        """
        self.config = config or load_config()
        self.path_manager = PathManager(self.config)
        self.event_store = EventStore()
    
    def load_events_from_files(self, event_files: List[Union[str, Path]]) -> List[Dict[str, Any]]:
        """
        Load events from multiple JSONL files.
        
        Args:
            event_files: List of paths to JSONL event files.
        
        Returns:
            List[Dict]: Combined list of events from all files.
        """
        all_events = []
        
        for file_path in event_files:
            file_path = Path(file_path)
            if not file_path.exists():
                continue
                
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            event = json.loads(line)
                            all_events.append(event)
                        except json.JSONDecodeError:
                            continue  # Skip malformed lines
        
        return all_events
    
    def analyze_events(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze events to generate quality metrics.
        
        Args:
            events: List of events (candidates, confirmations, rejections).
        
        Returns:
            Dict: Quality metrics and statistics.
        """
        if not events:
            return {
                "n_candidates": 0,
                "n_confirms": 0,
                "n_rejected": 0,
                "confirm_rate": 0.0,
                "rejection_rate": 0.0,
                "tta_avg": 0.0,
                "tta_median": 0.0,
                "tta_p95": 0.0,
                "tta_min": 0.0,
                "tta_max": 0.0,
                "stocks_analyzed": 0,
                "total_events": 0,
                "event_types": {},
                "config_used": {
                    "refractory_duration_s": self.config.refractory.duration_s,
                    "confirm_window_s": self.config.confirm.window_s,
                    "detection_threshold": self.config.detection.score_threshold
                }
            }
        
        # Sort events by timestamp for proper analysis
        sorted_events = sorted(events, key=lambda x: x.get('ts', 0))
        
        # Count events by type
        candidates = [e for e in sorted_events if e.get('event_type') == 'onset_candidate']
        confirmations = [e for e in sorted_events if e.get('event_type') == 'onset_confirmed']
        rejections = [e for e in sorted_events if e.get('event_type') == 'onset_rejected_refractory']
        
        # Event type statistics
        event_types = {}
        for event in sorted_events:
            event_type = event.get('event_type', 'unknown')
            event_types[event_type] = event_types.get(event_type, 0) + 1
        
        # Calculate rates
        n_candidates = len(candidates)
        n_confirms = len(confirmations)
        n_rejected = len(rejections)
        
        confirm_rate = n_confirms / n_candidates if n_candidates > 0 else 0.0
        rejection_rate = n_rejected / n_candidates if n_candidates > 0 else 0.0
        
        # Calculate Time-to-Alert (TTA) statistics
        tta_values = []
        for confirmation in confirmations:
            if 'confirmed_from' in confirmation and 'ts' in confirmation:
                confirmed_from = confirmation['confirmed_from']
                confirmed_at = confirmation['ts']
                tta_seconds = (confirmed_at - confirmed_from) / 1000.0
                if tta_seconds >= 0:  # Valid TTA
                    tta_values.append(tta_seconds)
        
        # TTA statistics
        tta_stats = {}
        if tta_values:
            tta_stats = {
                "tta_avg": float(np.mean(tta_values)),
                "tta_median": float(np.median(tta_values)),
                "tta_p95": float(np.percentile(tta_values, 95)),
                "tta_min": float(np.min(tta_values)),
                "tta_max": float(np.max(tta_values))
            }
        else:
            tta_stats = {
                "tta_avg": 0.0,
                "tta_median": 0.0,
                "tta_p95": 0.0,
                "tta_min": 0.0,
                "tta_max": 0.0
            }
        
        # Count unique stocks
        stock_codes = set()
        for event in sorted_events:
            if 'stock_code' in event:
                stock_codes.add(str(event['stock_code']))
        
        # Compile final report
        report = {
            "n_candidates": n_candidates,
            "n_confirms": n_confirms,
            "n_rejected": n_rejected,
            "confirm_rate": confirm_rate,
            "rejection_rate": rejection_rate,
            "stocks_analyzed": len(stock_codes),
            "total_events": len(sorted_events),
            "event_types": event_types,
            "config_used": {
                "refractory_duration_s": self.config.refractory.duration_s,
                "confirm_window_s": self.config.confirm.window_s,
                "detection_threshold": self.config.detection.score_threshold
            }
        }
        
        # Add TTA statistics
        report.update(tta_stats)
        
        return report
    
    def generate_report(
        self, 
        event_files: Optional[List[Union[str, Path]]] = None,
        events: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Generate quality report from events.
        
        Args:
            event_files: List of paths to JSONL event files. If None, uses events parameter.
            events: List of events. Used if event_files is None.
        
        Returns:
            Dict: Complete quality report.
        """
        if events is None:
            if event_files is None:
                # Use default event files from EventStore
                events_dir = self.event_store.events_dir
                default_files = [
                    events_dir / "events.jsonl",
                    events_dir / "sample.jsonl",
                    events_dir / "sample_candidates.jsonl",
                    events_dir / "sample_confirms.jsonl",
                    events_dir / "sample_refractory.jsonl"
                ]
                event_files = [f for f in default_files if f.exists()]
            
            events = self.load_events_from_files(event_files)
        
        return self.analyze_events(events)
    
    def save_report(self, report: Dict[str, Any], output_path: Union[str, Path]) -> bool:
        """
        Save quality report to JSON file.
        
        Args:
            report: Quality report dictionary.
            output_path: Path to save JSON file.
        
        Returns:
            bool: True if saved successfully.
        """
        output_path = Path(output_path)
        
        # Ensure parent directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error saving report: {e}")
            return False
    
    def generate_and_save_report(
        self,
        output_path: Union[str, Path],
        event_files: Optional[List[Union[str, Path]]] = None,
        events: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Generate and save quality report in one operation.
        
        Args:
            output_path: Path to save JSON report.
            event_files: List of paths to JSONL event files.
            events: List of events (alternative to event_files).
        
        Returns:
            Dict: Generated report with save status.
        """
        report = self.generate_report(event_files=event_files, events=events)
        save_success = self.save_report(report, output_path)
        
        # Add metadata about the operation
        report["_metadata"] = {
            "generated_at": pd.Timestamp.now().isoformat(),
            "output_path": str(Path(output_path).absolute()),
            "save_success": save_success
        }
        
        return report
    
    def print_summary(self, report: Dict[str, Any]) -> None:
        """
        Print a human-readable summary of the quality report.
        
        Args:
            report: Quality report dictionary.
        """
        print("\n" + "="*50)
        print("ONSET DETECTION QUALITY REPORT")
        print("="*50)
        
        print(f"Total Events Analyzed: {report['total_events']}")
        print(f"Stocks Analyzed: {report['stocks_analyzed']}")
        
        print(f"\nEvent Breakdown:")
        print(f"  Candidates: {report['n_candidates']}")
        print(f"  Confirmations: {report['n_confirms']}")
        print(f"  Rejections (Refractory): {report['n_rejected']}")
        
        print(f"\nPerformance Metrics:")
        print(f"  Confirmation Rate: {report['confirm_rate']:.2%}")
        print(f"  Rejection Rate: {report['rejection_rate']:.2%}")
        
        if report['n_confirms'] > 0:
            print(f"\nTime-to-Alert (TTA) Statistics:")
            print(f"  Average TTA: {report['tta_avg']:.2f}s")
            print(f"  Median TTA: {report['tta_median']:.2f}s")
            print(f"  95th Percentile TTA: {report['tta_p95']:.2f}s")
            print(f"  TTA Range: {report['tta_min']:.2f}s - {report['tta_max']:.2f}s")
        else:
            print(f"\nNo confirmations found - TTA statistics not available")
        
        print(f"\nConfiguration Used:")
        config = report['config_used']
        print(f"  Refractory Duration: {config['refractory_duration_s']}s")
        print(f"  Confirmation Window: {config['confirm_window_s']}s")
        print(f"  Detection Threshold: {config['detection_threshold']}")
        
        if '_metadata' in report:
            metadata = report['_metadata']
            if 'generated_at' in metadata:
                print(f"\nReport Generated: {metadata['generated_at']}")
            if 'output_path' in metadata and metadata.get('save_success'):
                print(f"Report Saved: {metadata['output_path']}")


def generate_quality_report(
    event_files: Optional[List[Union[str, Path]]] = None,
    events: Optional[List[Dict[str, Any]]] = None,
    output_path: Optional[Union[str, Path]] = None,
    config: Optional[Config] = None
) -> Dict[str, Any]:
    """
    Convenience function to generate quality report.
    
    Args:
        event_files: List of paths to JSONL event files.
        events: List of events (alternative to event_files).
        output_path: Path to save JSON report. If None, doesn't save.
        config: Configuration object.
    
    Returns:
        Dict: Generated quality report.
    """
    reporter = QualityReporter(config)
    
    if output_path is not None:
        return reporter.generate_and_save_report(output_path, event_files, events)
    else:
        return reporter.generate_report(event_files, events)


if __name__ == "__main__":
    # Demo/test the quality reporter
    import pandas as pd
    from pathlib import Path
    
    print("Quality Reporter Demo")
    print("=" * 40)
    
    # Create sample events for demonstration
    base_ts = 1704067200000
    sample_events = [
        # Candidates
        {
            'ts': base_ts,
            'event_type': 'onset_candidate',
            'stock_code': '005930',
            'score': 2.5
        },
        {
            'ts': base_ts + 10000,
            'event_type': 'onset_candidate',
            'stock_code': '005930',
            'score': 2.8
        },
        {
            'ts': base_ts + 60000,
            'event_type': 'onset_candidate',
            'stock_code': '000660',
            'score': 3.0
        },
        # Confirmations
        {
            'ts': base_ts + 5000,
            'event_type': 'onset_confirmed',
            'stock_code': '005930',
            'confirmed_from': base_ts
        },
        {
            'ts': base_ts + 65000,
            'event_type': 'onset_confirmed',
            'stock_code': '000660',
            'confirmed_from': base_ts + 60000
        },
        # Rejections
        {
            'ts': base_ts + 15000,
            'event_type': 'onset_rejected_refractory',
            'stock_code': '005930',
            'rejected_at': base_ts + 15000,
            'original_score': 2.8
        }
    ]
    
    print(f"Sample events created: {len(sample_events)}")
    
    # Generate report
    reporter = QualityReporter()
    report = reporter.generate_report(events=sample_events)
    
    # Print summary
    reporter.print_summary(report)
    
    # Save to demo file
    demo_output = Path("demo_quality_report.json")
    save_success = reporter.save_report(report, demo_output)
    
    if save_success and demo_output.exists():
        print(f"\n[SUCCESS] Demo report saved to: {demo_output.absolute()}")
        print(f"File size: {demo_output.stat().st_size} bytes")
    else:
        print(f"\n[WARNING] Could not save demo report")