import pytest

pytest.importorskip("httpx")

import httpx
from typing import Any, Dict

from app.ui.client import APIConfig, MultiAVClient


def build_client(responder: httpx.MockTransport, api_key: str | None = "test-key") -> MultiAVClient:
    client = MultiAVClient(
        APIConfig(base_url="http://testserver", timeout=1.0, poll_interval=0.01, api_key=api_key)
    )
    client._client = httpx.Client(
        base_url="http://testserver",
        transport=responder,
        headers=client._client.headers,
    )
    return client


def test_upload_and_poll_flow():
    calls: Dict[str, int] = {"results": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/scan/":
            assert request.headers.get("X-API-Key") == "test-key"
            return httpx.Response(200, json={"job_id": "abc", "status": "queued", "cached": False})

        if request.url.path == "/api/v1/results/abc":
            assert request.headers.get("X-API-Key") == "test-key"
            calls["results"] += 1
            if calls["results"] < 2:
                return httpx.Response(200, json={"job_id": "abc", "status": "queued"})
            return httpx.Response(200, json={"job_id": "abc", "status": "done", "details": {}})

        return httpx.Response(404)

    client = build_client(httpx.MockTransport(handler))

    upload = client.upload_file(b"hello", filename="hello.txt", content_type="text/plain")
    assert upload["job_id"] == "abc"
    assert upload["cached"] is False

    summary = client.poll_results("abc", timeout=1.0)
    assert summary["status"] == "done"
    assert calls["results"] >= 2


def test_list_recent_jobs_and_engines():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/ui/jobs/recent":
            assert request.headers.get("X-API-Key") == "test-key"
            assert request.url.params.get("severity") == "high"
            assert request.url.params.get("job_id") == "abc"
            return httpx.Response(200, json={"items": [{"job_id": "1", "filename": "foo.bin"}]})
        if request.url.path == "/api/v1/ui/engines/active":
            assert request.headers.get("X-API-Key") == "test-key"
            return httpx.Response(200, json={"engines": [{"engine": "stub", "timeout": 10, "weight": 1.0}]})
        return httpx.Response(404)

    client = build_client(httpx.MockTransport(handler))

    jobs = client.list_recent_jobs(limit=5, severity="high", job_id="abc")
    assert jobs == [{"job_id": "1", "filename": "foo.bin"}]

    engines = client.get_engines()
    assert engines == [{"engine": "stub", "timeout": 10, "weight": 1.0}]


def test_list_recent_jobs_scoped_per_api_key():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/ui/jobs/recent":
            api_key = request.headers.get("X-API-Key")
            if api_key == "key-a":
                return httpx.Response(200, json={"items": [{"job_id": "a1", "filename": "alpha.bin"}]})
            if api_key == "key-b":
                return httpx.Response(200, json={"items": [{"job_id": "b1", "filename": "bravo.bin"}]})
            return httpx.Response(401, json={"detail": "Invalid api_key"})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    client_a = build_client(transport, api_key="key-a")
    client_b = build_client(transport, api_key="key-b")

    jobs_a = client_a.list_recent_jobs(limit=5)
    jobs_b = client_b.list_recent_jobs(limit=5)

    assert jobs_a == [{"job_id": "a1", "filename": "alpha.bin"}]
    assert jobs_b == [{"job_id": "b1", "filename": "bravo.bin"}]


def test_upload_response_missing_keys_raises():
    client = build_client(httpx.MockTransport(lambda request: httpx.Response(200, json={})))
    with pytest.raises(ValueError):
        client.upload_file(b"oops")
