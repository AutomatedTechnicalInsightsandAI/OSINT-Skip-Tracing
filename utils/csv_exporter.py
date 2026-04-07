"""
CSV exporter utility.
"""

from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Optional, Union

import pandas as pd

logger = logging.getLogger(__name__)


class CSVExporter:
    """Export a DataFrame to a CSV file or in-memory bytes buffer."""

    @staticmethod
    def to_bytes(df: pd.DataFrame) -> bytes:
        """
        Serialize *df* to UTF-8 CSV bytes (suitable for Streamlit download).
        """
        buffer = io.StringIO()
        df.to_csv(buffer, index=False, encoding="utf-8")
        return buffer.getvalue().encode("utf-8")

    @staticmethod
    def to_file(df: pd.DataFrame, path: Union[str, Path]) -> Path:
        """
        Write *df* to a CSV file at *path*.

        Returns the resolved Path of the written file.
        """
        resolved = Path(path).resolve()
        resolved.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(resolved, index=False, encoding="utf-8")
        logger.info("CSV written to %s (%d rows)", resolved, len(df))
        return resolved
