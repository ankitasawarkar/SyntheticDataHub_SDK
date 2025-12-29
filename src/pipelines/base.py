from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict

import pandas as pd


class Pipeline(ABC):
    """Abstract base class for all schema-specific pipelines.

    The high-level contract is:
    1. prepare_schema: Ensure the DB schema exists / is refreshed
    2. generate_data: Build in-memory DataFrames of synthetic data
    3. load_data: Persist the generated data into the target DB
    4. validate: Run integrity / business validations
    """

    # Unique name used for registration and CLI selection, e.g. "edl_pipeline" or "rds_pipeline".
    name: str

    def run(self, **kwargs: Any) -> None:
        """Run the full pipeline with the standard steps."""
        self.prepare_schema(**kwargs)
        data = self.generate_data(**kwargs)
        self.load_data(data, **kwargs)
        self.validate(**kwargs)

    @abstractmethod
    def prepare_schema(self, **kwargs: Any) -> None:
        """Create or refresh DB schema/objects as needed."""

    @abstractmethod
    def generate_data(self, **kwargs: Any) -> Dict[str, pd.DataFrame]:
        """Generate synthetic data as table_name -> DataFrame."""

    @abstractmethod
    def load_data(self, data: Dict[str, pd.DataFrame], **kwargs: Any) -> None:
        """Persist generated data into the target database."""

    @abstractmethod
    def validate(self, **kwargs: Any) -> None:
        """Run validation queries/checks to ensure integrity."""
