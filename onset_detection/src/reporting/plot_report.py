"""Plot reporting for onset detection events visualization."""

import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Tuple

from ..config_loader import Config, load_config
from ..event_store import EventStore
from ..utils.paths import PathManager


class PlotReporter:
    """
    Generate visual reports for onset detection events.
    
    Creates charts showing price data with overlaid candidate, confirmation,
    and refractory events, plus optional label spans.
    """
    
    def __init__(self, config: Optional[Config] = None):
        """
        Initialize plot reporter.
        
        Args:
            config: Configuration object. If None, loads default config.
        """
        self.config = config or load_config()
        self.path_manager = PathManager(self.config)
        self.event_store = EventStore()
        
        # Set up matplotlib style
        plt.style.use('default')
        self.setup_plot_style()
    
    def setup_plot_style(self):
        """Set up consistent plot styling."""
        plt.rcParams.update({
            'figure.figsize': (14, 8),
            'font.size': 10,
            'axes.labelsize': 11,
            'axes.titlesize': 14,
            'legend.fontsize': 10,
            'xtick.labelsize': 9,
            'ytick.labelsize': 9,
            'lines.linewidth': 1.0,
            'grid.alpha': 0.3
        })
    
    def load_price_data(self, csv_path: Union[str, Path]) -> pd.DataFrame:
        """
        Load price data from CSV file.
        
        Args:
            csv_path: Path to CSV file with price data.
        
        Returns:
            pd.DataFrame: Price data with timestamp index.
        """
        csv_path = Path(csv_path)
        if not csv_path.exists():
            raise FileNotFoundError(f"Price data file not found: {csv_path}")
        
        df = pd.read_csv(csv_path)
        
        # Convert timestamp to datetime for plotting
        if 'ts' in df.columns:
            df['datetime'] = pd.to_datetime(df['ts'], unit='ms')
        else:
            raise ValueError("Price data must contain 'ts' column")
        
        # Ensure required columns exist
        required_cols = ['ts', 'stock_code', 'price']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}")
        
        return df
    
    def load_events_from_files(self, event_files: List[Union[str, Path]]) -> List[Dict[str, Any]]:
        """
        Load events from JSONL files.
        
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
                            # Add datetime for plotting
                            if 'ts' in event:
                                event['datetime'] = pd.to_datetime(event['ts'], unit='ms')
                            all_events.append(event)
                        except json.JSONDecodeError:
                            continue  # Skip malformed lines
        
        return all_events
    
    def load_labels_data(self, labels_path: Union[str, Path]) -> Optional[pd.DataFrame]:
        """
        Load labels data from CSV file.
        
        Args:
            labels_path: Path to CSV file with label data.
        
        Returns:
            pd.DataFrame: Labels data, or None if file doesn't exist.
        """
        labels_path = Path(labels_path)
        if not labels_path.exists():
            return None
        
        try:
            df = pd.read_csv(labels_path)
            
            # Convert timestamps to datetime
            if 'timestamp_start' in df.columns and 'timestamp_end' in df.columns:
                df['datetime_start'] = pd.to_datetime(df['timestamp_start'], unit='ms')
                df['datetime_end'] = pd.to_datetime(df['timestamp_end'], unit='ms')
            
            return df
        except Exception:
            return None
    
    def filter_events_by_stock_and_timerange(
        self,
        events: List[Dict[str, Any]],
        stock_code: str,
        start_time: pd.Timestamp,
        end_time: pd.Timestamp
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Filter events by stock code and time range, categorized by type.
        
        Args:
            events: List of all events.
            stock_code: Stock code to filter by.
            start_time: Start of time range.
            end_time: End of time range.
        
        Returns:
            Dict: Events categorized by type (candidates, confirmations, rejections).
        """
        filtered_events = {
            'candidates': [],
            'confirmations': [],
            'rejections': []
        }
        
        for event in events:
            # Filter by stock code
            event_stock = str(event.get('stock_code', ''))
            if event_stock != str(stock_code):
                continue
            
            # Filter by time range
            if 'datetime' not in event:
                continue
            
            event_time = event['datetime']
            if not (start_time <= event_time <= end_time):
                continue
            
            # Categorize by event type
            event_type = event.get('event_type', '')
            if event_type == 'onset_candidate':
                filtered_events['candidates'].append(event)
            elif event_type == 'onset_confirmed':
                filtered_events['confirmations'].append(event)
            elif event_type == 'onset_rejected_refractory':
                filtered_events['rejections'].append(event)
        
        return filtered_events
    
    def create_plot(
        self,
        price_data: pd.DataFrame,
        events: Dict[str, List[Dict[str, Any]]],
        labels_data: Optional[pd.DataFrame] = None,
        stock_code: Optional[str] = None,
        title_suffix: str = ""
    ) -> Tuple[plt.Figure, plt.Axes]:
        """
        Create the main plot with price data and events.
        
        Args:
            price_data: DataFrame with price data.
            events: Categorized events dict.
            labels_data: Optional labels DataFrame.
            stock_code: Stock code for filtering.
            title_suffix: Additional title text.
        
        Returns:
            Tuple of (figure, axes) objects.
        """
        # Create figure and axis
        fig, ax = plt.subplots(figsize=(14, 8))
        
        # Filter price data by stock if specified
        if stock_code:
            price_data = price_data[price_data['stock_code'].astype(str) == str(stock_code)]
        
        if price_data.empty:
            ax.text(0.5, 0.5, f'No price data found for stock {stock_code}', 
                   transform=ax.transAxes, ha='center', va='center', fontsize=14)
            return fig, ax
        
        # Plot price line
        ax.plot(price_data['datetime'], price_data['price'], 
               color='black', linewidth=1.5, label='Price', alpha=0.8)
        
        # Add label spans (background)
        if labels_data is not None and not labels_data.empty:
            # Filter labels by stock code if specified
            if stock_code:
                labels_data = labels_data[labels_data['stock_code'].astype(str) == str(stock_code)]
            
            for _, label in labels_data.iterrows():
                ax.axvspan(label['datetime_start'], label['datetime_end'], 
                          alpha=0.2, color='blue', label='Label Span' if _ == 0 else "")
        
        # Plot events
        self.plot_events(ax, events, price_data)
        
        # Formatting
        self.format_plot(ax, price_data, stock_code, title_suffix)
        
        return fig, ax
    
    def plot_events(self, ax: plt.Axes, events: Dict[str, List[Dict[str, Any]]], price_data: pd.DataFrame):
        """
        Plot event markers on the chart.
        
        Args:
            ax: Matplotlib axes object.
            events: Categorized events dict.
            price_data: Price data for getting price levels at event times.
        """
        # Get price interpolation function for event positioning
        def get_price_at_time(timestamp):
            """Get price at specific timestamp by interpolation."""
            if price_data.empty:
                return 0
            
            # Find closest price point
            time_diffs = np.abs(price_data['ts'] - timestamp)
            closest_idx = time_diffs.idxmin()
            return price_data.loc[closest_idx, 'price']
        
        # Plot candidates (orange triangles)
        if events['candidates']:
            times = [event['datetime'] for event in events['candidates']]
            prices = [get_price_at_time(event['ts']) for event in events['candidates']]
            ax.scatter(times, prices, marker='^', color='orange', s=80, 
                      label=f'Candidates ({len(events["candidates"])})', 
                      alpha=0.8, edgecolors='black', linewidth=0.5, zorder=5)
        
        # Plot confirmations (red circles)
        if events['confirmations']:
            times = [event['datetime'] for event in events['confirmations']]
            prices = [get_price_at_time(event['ts']) for event in events['confirmations']]
            ax.scatter(times, prices, marker='o', color='red', s=100, 
                      label=f'Confirmations ({len(events["confirmations"])})', 
                      alpha=0.9, edgecolors='darkred', linewidth=1, zorder=6)
        
        # Plot rejections (gray X marks)
        if events['rejections']:
            times = [event['datetime'] for event in events['rejections']]
            prices = [get_price_at_time(event['ts']) for event in events['rejections']]
            ax.scatter(times, prices, marker='x', color='gray', s=60, 
                      label=f'Rejections ({len(events["rejections"])})', 
                      alpha=0.7, linewidth=2, zorder=4)
    
    def format_plot(self, ax: plt.Axes, price_data: pd.DataFrame, stock_code: Optional[str], title_suffix: str):
        """
        Format the plot with labels, title, and styling.
        
        Args:
            ax: Matplotlib axes object.
            price_data: Price data for determining time range.
            stock_code: Stock code for title.
            title_suffix: Additional title text.
        """
        # Set title
        title = f"Onset Detection Report"
        if stock_code:
            title += f" - {stock_code}"
        if title_suffix:
            title += f" - {title_suffix}"
        
        ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
        
        # Set labels
        ax.set_xlabel('Time', fontsize=12)
        ax.set_ylabel('Price', fontsize=12)
        
        # Format time axis
        if not price_data.empty:
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
            ax.xaxis.set_major_locator(mdates.MinuteLocator(interval=1))
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
        
        # Grid and legend
        ax.grid(True, alpha=0.3)
        ax.legend(loc='upper left', framealpha=0.9)
        
        # Tight layout
        plt.tight_layout()
    
    def save_plot(self, fig: plt.Figure, output_path: Union[str, Path], dpi: int = 300) -> bool:
        """
        Save plot to file.
        
        Args:
            fig: Matplotlib figure object.
            output_path: Path to save the plot.
            dpi: Resolution for PNG output.
        
        Returns:
            bool: True if saved successfully.
        """
        output_path = Path(output_path)
        
        # Ensure parent directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            fig.savefig(output_path, dpi=dpi, bbox_inches='tight', 
                       facecolor='white', edgecolor='none')
            return True
        except Exception as e:
            print(f"Error saving plot: {e}")
            return False
        finally:
            plt.close(fig)
    
    def generate_report(
        self,
        csv_path: Union[str, Path],
        event_files: List[Union[str, Path]],
        output_path: Union[str, Path],
        labels_path: Optional[Union[str, Path]] = None,
        stock_code: Optional[str] = None,
        title_suffix: str = ""
    ) -> Dict[str, Any]:
        """
        Generate complete visual report.
        
        Args:
            csv_path: Path to price data CSV.
            event_files: List of paths to event JSONL files.
            output_path: Path to save plot.
            labels_path: Optional path to labels CSV.
            stock_code: Optional stock code filter.
            title_suffix: Additional title text.
        
        Returns:
            Dict: Report generation summary.
        """
        try:
            # Load data
            price_data = self.load_price_data(csv_path)
            events_list = self.load_events_from_files(event_files)
            labels_data = self.load_labels_data(labels_path) if labels_path else None
            
            # Determine stock code and time range
            if not stock_code:
                if not price_data.empty:
                    stock_code = str(price_data['stock_code'].iloc[0])
                else:
                    stock_code = "unknown"
            
            # Filter data by time range
            if not price_data.empty:
                start_time = price_data['datetime'].min()
                end_time = price_data['datetime'].max()
            else:
                # Use event time range as fallback
                event_times = [pd.to_datetime(e['ts'], unit='ms') for e in events_list if 'ts' in e]
                if event_times:
                    start_time = min(event_times)
                    end_time = max(event_times)
                else:
                    start_time = pd.Timestamp.now()
                    end_time = pd.Timestamp.now()
            
            # Filter events
            filtered_events = self.filter_events_by_stock_and_timerange(
                events_list, stock_code, start_time, end_time
            )
            
            # Create plot
            fig, ax = self.create_plot(price_data, filtered_events, labels_data, stock_code, title_suffix)
            
            # Save plot
            save_success = self.save_plot(fig, output_path)
            
            # Generate summary
            summary = {
                "stock_code": stock_code,
                "time_range": {
                    "start": start_time.isoformat(),
                    "end": end_time.isoformat()
                },
                "price_data_points": len(price_data),
                "events": {
                    "candidates": len(filtered_events['candidates']),
                    "confirmations": len(filtered_events['confirmations']),
                    "rejections": len(filtered_events['rejections'])
                },
                "labels_count": len(labels_data) if labels_data is not None else 0,
                "output_path": str(Path(output_path).absolute()),
                "save_success": save_success
            }
            
            return summary
            
        except Exception as e:
            return {
                "error": str(e),
                "save_success": False
            }


def generate_plot_report(
    csv_path: Union[str, Path],
    event_files: List[Union[str, Path]],
    output_path: Union[str, Path],
    labels_path: Optional[Union[str, Path]] = None,
    stock_code: Optional[str] = None,
    title_suffix: str = "",
    config: Optional[Config] = None
) -> Dict[str, Any]:
    """
    Convenience function to generate plot report.
    
    Args:
        csv_path: Path to price data CSV.
        event_files: List of paths to event JSONL files.
        output_path: Path to save plot.
        labels_path: Optional path to labels CSV.
        stock_code: Optional stock code filter.
        title_suffix: Additional title text.
        config: Configuration object.
    
    Returns:
        Dict: Report generation summary.
    """
    reporter = PlotReporter(config)
    return reporter.generate_report(
        csv_path, event_files, output_path, labels_path, stock_code, title_suffix
    )


if __name__ == "__main__":
    # Demo/test the plot reporter
    from pathlib import Path
    
    print("Plot Reporter Demo")
    print("=" * 40)
    
    # Use sample data
    project_root = Path(__file__).parent.parent.parent
    csv_path = project_root / "data" / "clean" / "sample.csv"
    event_files = [
        project_root / "data" / "events" / "sample_candidates.jsonl",
        project_root / "data" / "events" / "sample_confirms.jsonl",
        project_root / "data" / "events" / "sample_refractory.jsonl"
    ]
    labels_path = project_root / "data" / "labels" / "sample.csv"
    output_path = project_root / "reports" / "plots" / "demo_report.png"
    
    print(f"CSV path: {csv_path}")
    print(f"Event files: {len([f for f in event_files if f.exists()])} files found")
    print(f"Labels path: {labels_path} ({'exists' if labels_path.exists() else 'missing'})")
    
    # Generate report
    reporter = PlotReporter()
    summary = reporter.generate_report(
        csv_path=csv_path,
        event_files=event_files,
        output_path=output_path,
        labels_path=labels_path,
        title_suffix="Demo"
    )
    
    # Print results
    print(f"\nReport Generation Summary:")
    if "error" in summary:
        print(f"  Error: {summary['error']}")
    else:
        print(f"  Stock: {summary['stock_code']}")
        print(f"  Time range: {summary['time_range']['start']} to {summary['time_range']['end']}")
        print(f"  Price data points: {summary['price_data_points']}")
        print(f"  Events: {summary['events']}")
        print(f"  Labels: {summary['labels_count']}")
        print(f"  Save successful: {summary['save_success']}")
        print(f"  Output: {summary['output_path']}")
        
        if summary['save_success'] and Path(summary['output_path']).exists():
            print(f"\n[SUCCESS] Demo plot saved!")
        else:
            print(f"\n[WARNING] Plot was not saved successfully")