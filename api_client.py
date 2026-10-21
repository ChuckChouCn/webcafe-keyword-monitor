import time
import requests
from typing import Dict, Any, Optional
from config import WEBCAFE_API_BASE, WEBCAFE_TOKEN, DEFAULT_USER_AGENT

class WebCafeAPIClient:
    def __init__(self, token: Optional[str] = None, base_url: Optional[str] = None):
        self.base_url = (base_url or WEBCAFE_API_BASE).rstrip("/")
        self.token = token or WEBCAFE_TOKEN
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.token}",
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "application/json"
        })

    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        url = f"{self.base_url}{endpoint}"
        max_retries = 3
        backoff = 2

        for attempt in range(max_retries):
            try:
                resp = self.session.request(method, url, timeout=30, **kwargs)
                if resp.status_code == 429:
                    # Rate limit
                    wait_time = backoff * (2 ** attempt)
                    time.sleep(wait_time)
                    continue
                elif resp.status_code in (502, 503):
                    wait_time = backoff * (2 ** attempt)
                    time.sleep(wait_time)
                    continue

                resp.raise_for_status()
                data = resp.json()
                if not data.get("ok", False):
                    raise RuntimeError(f"API Error: {data.get('error') or data.get('code') or 'Unknown error'}")
                return data

            except requests.RequestException as e:
                if attempt == max_retries - 1:
                    raise RuntimeError(f"Failed to call {url} after {max_retries} attempts: {e}")
                time.sleep(backoff * (2 ** attempt))

        raise RuntimeError(f"Failed to call {url}: exceeded max retries")

    def get_me(self) -> Dict[str, Any]:
        """Check current user profile and credit balances."""
        return self._request("GET", "/me")

    def get_keyword_batches(self, page: int = 1) -> Dict[str, Any]:
        """
        Fetch keyword batches list.
        Cost: 0 credits.
        """
        return self._request("GET", f"/keywords/batches?page={page}")

    def get_batch_details(self, batch_id: str) -> Dict[str, Any]:
        """
        Fetch all keywords and analysis data for a batch.
        Cost: 0 credits.
        """
        return self._request("GET", f"/keywords/batches/{batch_id}")
