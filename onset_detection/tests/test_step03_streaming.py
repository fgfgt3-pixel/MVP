"""Tests for step03_detect.py streaming mode."""

import io
import json
import pytest
import pandas as pd

from src.detection.onset_pipeline import OnsetPipelineDF
from src.config_loader import load_config


class TestStreamingMode:
    """Test suite for streaming detection mode."""

    @pytest.fixture
    def config(self):
        """Load test configuration."""
        return load_config()

    @pytest.fixture
    def pipeline(self, config):
        """Create pipeline instance."""
        return OnsetPipelineDF(config=config)

    def test_run_tick_basic(self, pipeline):
        """Test basic run_tick functionality."""
        # Create sample tick
        tick = {
            "ts": 1704067200000,  # 2024-01-01 09:00:00 in ms
            "code": "005930",
            "price": 74000,
            "volume": 1000,
            "spread": 50
        }

        # First few ticks should return None (buffering)
        for i in range(10):
            result = pipeline.run_tick({
                **tick,
                "ts": tick["ts"] + i * 1000,
                "price": tick["price"] + i * 10
            })
            # Buffer not full yet
            if i < 30:
                assert result is None or isinstance(result, dict)

    def test_run_tick_with_onset_pattern(self, pipeline):
        """Test run_tick with onset-like pattern."""
        base_ts = 1704067200000
        base_price = 74000

        # Feed ticks with surge pattern
        for i in range(100):
            if i < 50:
                # Normal period
                price = base_price + i
                volume = 1000
            else:
                # Surge period
                price = base_price + 50 + (i - 50) * 100  # Sharp increase
                volume = 5000 + (i - 50) * 100  # Volume surge

            tick = {
                "ts": base_ts + i * 1000,
                "code": "005930",
                "price": price,
                "volume": volume,
                "spread": 50
            }

            result = pipeline.run_tick(tick)

            # Should not raise exceptions
            if result:
                assert isinstance(result, dict)
                assert "event_type" in result
                assert result["event_type"] == "onset_confirmed"

    def test_run_tick_buffer_management(self, pipeline):
        """Test that buffer is properly managed."""
        base_ts = 1704067200000

        # Feed many ticks
        for i in range(1100):  # More than buffer size
            tick = {
                "ts": base_ts + i * 1000,
                "code": "005930",
                "price": 74000 + i,
                "volume": 1000,
                "spread": 50
            }

            pipeline.run_tick(tick)

        # Buffer should be limited to maxlen
        assert len(pipeline.tick_buffer) <= 1000

    def test_run_tick_invalid_data(self, pipeline):
        """Test run_tick with invalid data."""
        # Missing required fields
        tick = {
            "ts": 1704067200000,
            # Missing code, price, volume
        }

        # Should handle gracefully
        try:
            result = pipeline.run_tick(tick)
            # Should not crash
            assert result is None or isinstance(result, dict)
        except Exception as e:
            # If it raises, it should be caught in the pipeline
            pytest.fail(f"run_tick should handle invalid data gracefully: {e}")


def test_csv_replay_integration(tmp_path):
    """Test integration with csv_replay.py (mock)."""
    from scripts.csv_replay import csv_to_jsonl

    # Create sample CSV
    csv_path = tmp_path / "sample.csv"
    csv_path.write_text(
        "ts,code,price,volume,spread\n"
        "1704067200000,005930,74000,1000,50\n"
        "1704067201000,005930,74100,1200,50\n"
        "1704067202000,005930,74200,1500,50\n"
    )

    # Convert to JSONL
    buf = io.StringIO()
    csv_to_jsonl(str(csv_path), buf)
    buf.seek(0)

    # Parse JSONL
    ticks = []
    for line in buf:
        ticks.append(json.loads(line))

    assert len(ticks) == 3
    assert ticks[0]["code"] == "005930"
    assert ticks[0]["price"] == 74000
    assert ticks[1]["price"] == 74100


def test_streaming_mode_smoke():
    """Smoke test for streaming mode."""
    config = load_config()
    pipeline = OnsetPipelineDF(config=config)

    # Feed minimal ticks
    for i in range(50):
        tick = {
            "ts": 1704067200000 + i * 1000,
            "code": "TEST",
            "price": 100 + i,
            "volume": 1000,
            "spread": 1
        }

        result = pipeline.run_tick(tick)
        # Should not raise exceptions
        assert result is None or isinstance(result, dict)


if __name__ == "__main__":
    # Run smoke test
    print("Running streaming mode smoke test...")
    test_streaming_mode_smoke()
    print("Smoke test passed!")
