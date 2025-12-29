# nemo_client.py

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


@dataclass
class NeMoClientConfig:
    """
    Configuration for NeMo Data Designer client.
    Adjust base_url and endpoints based on your actual deployment.
    """
    base_url: str
    api_key: str
    timeout_seconds: int = 300


class NeMoClient:
    """
    Minimal client for NVIDIA NeMo Data Designer microservice.

    This is intentionally simple and opinionated:
    - JSON over HTTP
    - API key in Authorization header
    - One endpoint: generate a synthetic dataset for a table.
    """

    def __init__(self, config: Optional[NeMoClientConfig] = None) -> None:
        if config is None:
            config = self._from_env()
        self.config = config

        logger.debug("Initialized NeMoClient with base_url=%s", self.config.base_url)

    @staticmethod
    def _from_env() -> NeMoClientConfig:
        """
        Convenience factory that reads config from environment variables:
        - NEMO_BASE_URL
        - NEMO_API_KEY
        """
        base_url = os.getenv("NEMO_BASE_URL")
        api_key = os.getenv("NEMO_API_KEY")

        if not base_url:
            raise ValueError("NEMO_BASE_URL environment variable is not set")
        if not api_key:
            raise ValueError("NEMO_API_KEY environment variable is not set")

        return NeMoClientConfig(
            base_url=base_url.rstrip("/"),
            api_key=api_key,
        )

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def generate_table(
        self,
        table_name: str,
        nemo_config: Dict[str, Any],
        num_rows: int,
    ) -> List[Dict[str, Any]]:
        """
        Call NeMo Data Designer to generate synthetic rows for a single table.

        Parameters
        ----------
        table_name:
            Logical name of the table/entity.
        nemo_config:
            Model/config definition for this table (columns, types, constraints, etc.).
        num_rows:
            How many rows to generate.

        Returns
        -------
        List[Dict[str, Any]]:
            List of synthetic rows (JSON-serializable).
        """
        payload = {
            "table_name": table_name,
            "num_rows": num_rows,
            "config": nemo_config,
        }

        url = f"{self.config.base_url}/data-designer/v1/generate"
        logger.info("Calling NeMo for table=%s, rows=%s", table_name, num_rows)
        logger.debug("NeMo payload for %s: %s", table_name, payload)

        resp = requests.post(
            url,
            headers=self._headers(),
            json=payload,
            timeout=self.config.timeout_seconds,
        )

        try:
            resp.raise_for_status()
        except requests.HTTPError as exc:
            logger.error(
                "NeMo generation failed for table=%s: %s", table_name, resp.text
            )
            raise RuntimeError(
                f"NeMo generation failed for table={table_name}: {exc}"
            ) from exc

        data = resp.json()
        # Expecting {"rows": [...]} but you can adapt to the actual schema
        rows = data.get("rows")
        if rows is None:
            logger.error("NeMo response missing 'rows' field for table=%s: %s", table_name, data)
            raise ValueError(f"NeMo response missing 'rows' for table={table_name}")

        logger.info("NeMo returned %s rows for table=%s", len(rows), table_name)
        return rows