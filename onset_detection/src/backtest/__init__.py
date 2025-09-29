"""Backtest module for onset detection evaluation."""

from .backtester import Backtester, run_backtest
from .report import ReportGenerator, generate_backtest_report

__all__ = ['Backtester', 'run_backtest', 'ReportGenerator', 'generate_backtest_report']