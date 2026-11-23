"""StormForce (Salesforce) REST API client with OAuth 2.0 and retry logic."""

import time
from typing import Any

import requests


class StormForceClient:
    """REST client for StormForce (Salesforce) with managed OAuth.

    Production: OAuth tokens from Secrets Manager with 90-day rotation.
    Development: USE_MOCKS=true bypasses this entirely.
    """

    API_VERSION = "v58.0"
    MAX_RETRIES = 3
    BACKOFF_BASE = 1  # seconds

    def __init__(self, instance_url: str, access_token: str):
        self._base = f"{instance_url}/services/data/{self.API_VERSION}"
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        })

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        """Execute HTTP request with exponential backoff retry on 429/5xx."""
        url = f"{self._base}{path}"
        for attempt in range(self.MAX_RETRIES):
            response = self._session.request(method, url, **kwargs)
            if response.status_code < 400:
                return response.json() if response.content else {"success": True}
            if response.status_code in (429, 500, 502, 503, 504) and attempt < self.MAX_RETRIES - 1:
                time.sleep(self.BACKOFF_BASE * (2 ** attempt))
                continue
            response.raise_for_status()
        return {"success": False, "error": "Max retries exceeded"}

    def query(self, soql: str) -> dict[str, Any]:
        """Execute a SOQL query against StormForce."""
        return self._request("GET", "/query", params={"q": soql})

    def create_record(self, object_type: str, data: dict[str, Any]) -> dict[str, Any]:
        """Create a new record in StormForce."""
        return self._request("POST", f"/sobjects/{object_type}/", json=data)

    def update_record(self, object_type: str, record_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """Update an existing record in StormForce."""
        return self._request("PATCH", f"/sobjects/{object_type}/{record_id}", json=data)

    def get_record(self, object_type: str, record_id: str) -> dict[str, Any]:
        """Get a single record by ID."""
        return self._request("GET", f"/sobjects/{object_type}/{record_id}")
