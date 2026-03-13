"""Tests for OutputFormatter."""

import json
import pytest
import pandas as pd
from agent.output import OutputFormatter


SAMPLE_DATA = [
    {"date": "2024-01-31", "close": 185.20, "volume": 52_000_000},
    {"date": "2024-02-29", "close": 181.50, "volume": 48_000_000},
    {"date": "2024-03-28", "close": 171.48, "volume": 61_000_000},
]


class TestOutputFormatter:
    def setup_method(self):
        self.fmt = OutputFormatter()

    def test_to_json_returns_valid_json(self):
        result = self.fmt.to_json(SAMPLE_DATA)
        parsed = json.loads(result)
        assert isinstance(parsed, list)
        assert len(parsed) == 3
        assert parsed[0]["date"] == "2024-01-31"

    def test_to_json_dict_input(self):
        result = self.fmt.to_json({"key": "value"})
        parsed = json.loads(result)
        assert parsed["key"] == "value"

    def test_to_csv_returns_string_with_header(self):
        result = self.fmt.to_csv(SAMPLE_DATA)
        lines = [l.strip() for l in result.strip().splitlines()]
        assert lines[0] == "date,close,volume"
        assert len(lines) == 4  # header + 3 rows

    def test_to_csv_correct_values(self):
        result = self.fmt.to_csv(SAMPLE_DATA)
        assert "185.2" in result
        assert "2024-01-31" in result

    def test_to_dataframe_returns_dataframe(self):
        df = self.fmt.to_dataframe(SAMPLE_DATA)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 3
        assert list(df.columns) == ["date", "close", "volume"]

    def test_to_dataframe_numeric_types(self):
        df = self.fmt.to_dataframe(SAMPLE_DATA)
        assert df["close"].dtype == float

    def test_empty_list_produces_empty_outputs(self):
        assert self.fmt.to_json([]) == "[]"
        assert self.fmt.to_csv([]) == ""
        df = self.fmt.to_dataframe([])
        assert len(df) == 0

    def test_to_json_pretty_prints(self):
        result = self.fmt.to_json(SAMPLE_DATA, pretty=True)
        assert "\n" in result  # indented

    def test_to_csv_custom_delimiter(self):
        result = self.fmt.to_csv(SAMPLE_DATA, delimiter=";")
        assert "date;close;volume" in result
