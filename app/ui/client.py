from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional
import time

import httpx

TERMINAL_STATUSES = {"done", "done_with_errors", "error"}


@dataclass
class APIConfig:
    base_url: str = "http://localhost:8000"
    timeout: float = 10.0
    poll_interval: float = 2.0
    api_key: Optional[str] = None
    api_key_header: str = "X-API-Key"


class MultiAVClient:
    def __init__(self, config: APIConfig):
        self.config = config
        headers: Dict[str, str] = {}
        if self.config.api_key:
            headers[self.config.api_key_header] = self.config.api_key
        self._client = httpx.Client(
            base_url=self.config.base_url,
            timeout=self.config.timeout,
            headers=headers,
        )

    def close(self) -> None:
        self._client.close()

    @staticmethod
    def is_terminal(status: Optional[str]) -> bool:
        if not status:
            return False
        return status.lower() in TERMINAL_STATUSES

    def upload_file(
        self,
        file_bytes: bytes,
        filename: str = "upload.bin",
        content_type: str = "application/octet-stream",
    ) -> Dict[str, Any]:
        response = self._client.post(
            "/api/v1/scan/",
            files={"file": (filename, file_bytes, content_type)},
        )
        response.raise_for_status()
        payload = response.json()
        expected_keys = {"job_id", "status", "cached"}
        missing = expected_keys.difference(payload)
        if missing:
            raise ValueError(f"Upload response missing expected keys: {missing}")
        return payload

    def get_results(self, job_id: str) -> Dict[str, Any]:
        response = self._client.get(f"/api/v1/results/{job_id}/")
        response.raise_for_status()
        return response.json()

    def poll_results(self, job_id: str, *, timeout: Optional[float] = None) -> Dict[str, Any]:
        start = time.time()
        while True:
            result = self.get_results(job_id)
            if self.is_terminal(result.get("status")):
                return result

            if timeout is not None and (time.time() - start) >= timeout:
                return result

            time.sleep(self.config.poll_interval)

    def list_recent_jobs(
        self,
        *,
        limit: int = 50,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        sha256: Optional[str] = None,
        job_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        params = {"limit": min(max(limit, 1), 200)}
        if status:
            params["status"] = status
        if sha256:
            params["sha256"] = sha256
        if severity:
            params["severity"] = severity
        if job_id:
            params["job_id"] = job_id
        response = self._client.get("/api/v1/ui/jobs/recent/", params=params)
        response.raise_for_status()
        payload = response.json()
        return payload.get("items", [])

    def get_engines(self) -> List[Dict[str, Any]]:
        response = self._client.get("/api/v1/ui/engines/active/")
        response.raise_for_status()
        payload = response.json()
        engines = payload.get("engines")
        if isinstance(engines, Iterable):
            return list(engines)
        return []
