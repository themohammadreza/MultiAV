import pytest

pytest.importorskip("httpx")

import httpx
from typing import Any, Dict

from app.ui.client import APIConfig, MultiAVClient


def build_client(responder: httpx.MockTransport) -> MultiAVClient:
    client = MultiAVClient(APIConfig(base_url="http://testserver", timeout=1.0, poll_interval=0.01))
    client._client = httpx.Client(base_url="http://testserver", transport=responder)
    return client


def test_upload_and_poll_flow():
    calls: Dict[str, int] = {"results": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/scan/":
            return httpx.Response(200, json={"job_id": "abc", "status": "queued", "cached": False})

        if request.url.path == "/api/v1/results/abc":
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
            assert request.url.params.get("severity") == "high"
            assert request.url.params.get("job_id") == "abc"
            return httpx.Response(200, json={"items": [{"job_id": "1"}]})
        if request.url.path == "/api/v1/ui/engines/active":
            return httpx.Response(200, json={"engines": [{"engine": "stub", "timeout": 10, "weight": 1.0}]})
        return httpx.Response(404)

    client = build_client(httpx.MockTransport(handler))

    jobs = client.list_recent_jobs(limit=5, severity="high", job_id="abc")
    assert jobs == [{"job_id": "1"}]

    engines = client.get_engines()
    assert engines == [{"engine": "stub", "timeout": 10, "weight": 1.0}]


def test_upload_response_missing_keys_raises():
    client = build_client(httpx.MockTransport(lambda request: httpx.Response(200, json={})))
    with pytest.raises(ValueError):
        client.upload_file(b"oops")
