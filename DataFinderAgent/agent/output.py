"""Output formatting: converts raw extracted data to JSON, CSV, or DataFrame."""

import json
import io
from typing import Any

import pandas as pd


class OutputFormatter:
    """Converts extracted data to the requested output format."""

    def to_json(self, data: Any, pretty: bool = False) -> str:
        """Serialize data to a JSON string.

        Args:
            data: List of dicts, a dict, or any JSON-serializable value.
            pretty: If True, indent with 2 spaces.

        Returns:
            JSON string.
        """
        indent = 2 if pretty else None
        return json.dumps(data, indent=indent, default=str)

    def to_csv(self, data: list[dict], delimiter: str = ",") -> str:
        """Convert a list of dicts to a CSV string.

        Args:
            data: List of dicts (uniform keys assumed).
            delimiter: Column separator character.

        Returns:
            CSV string including header row, or empty string if data is empty.
        """
        if not data:
            return ""
        df = pd.DataFrame(data)
        buf = io.StringIO()
        df.to_csv(buf, index=False, sep=delimiter)
        return buf.getvalue().rstrip("\n")

    def to_dataframe(self, data: list[dict]) -> pd.DataFrame:
        """Convert a list of dicts to a pandas DataFrame.

        Args:
            data: List of dicts (uniform keys assumed).

        Returns:
            pandas DataFrame.
        """
        if not data:
            return pd.DataFrame()
        return pd.DataFrame(data)
