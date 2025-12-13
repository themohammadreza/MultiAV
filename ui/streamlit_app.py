import json
import os
from dataclasses import dataclass
from typing import Dict, List, Optional

import streamlit as st

from app.ui.client import APIConfig, MultiAVClient, TERMINAL_STATUSES


@dataclass
class UIConfig:
    api_base_url: str
    poll_interval: float
    request_timeout: float
    max_upload_mb: int
    feature_history: bool = True


TERMINAL_DISPLAY = {
    "done": "✅ Completed",
    "done_with_errors": "⚠️ Completed with errors",
    "error": "❌ Error",
}


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on", "y"}


def load_ui_config() -> UIConfig:
    try:
        secrets = st.secrets  # may raise if no secrets file present
    except FileNotFoundError:
        secrets = {}
    except Exception:
        secrets = {}
    return UIConfig(
        api_base_url=secrets.get("api_base_url") or os.getenv("API_BASE_URL", "http://localhost:8000"),
        poll_interval=float(secrets.get("poll_interval", os.getenv("POLL_INTERVAL", 2))),
        request_timeout=float(secrets.get("REQUEST_TIMEOUT", os.getenv("REQUEST_TIMEOUT", 15))),
        max_upload_mb=int(secrets.get("MAX_UPLOAD_MB", os.getenv("MAX_UPLOAD_MB", 50))),
        feature_history=_as_bool(secrets.get("FEATURE_HISTORY", os.getenv("FEATURE_HISTORY", True))),
    )


def get_client(config: UIConfig) -> MultiAVClient:
    client = st.session_state.get("multiav_client")
    if client:
        return client
    client = MultiAVClient(
        APIConfig(
            base_url=config.api_base_url,
            timeout=config.request_timeout,
            poll_interval=config.poll_interval,
        )
    )
    st.session_state["multiav_client"] = client
    return client


def readable_status(status: Optional[str]) -> str:
    if not status:
        return "pending"
    status_lower = status.lower()
    return TERMINAL_DISPLAY.get(status_lower, status_lower)


def render_engine_table(details: Dict[str, Dict]) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for engine, payload in sorted(details.items()):
        rows.append(
            {
                "engine": engine,
                "status": payload.get("status", "unknown"),
                "verdict": payload.get("verdict") or payload.get("detection_name"),
                "signature": payload.get("signature") or payload.get("rule"),
                "severity": payload.get("severity"),
                "confidence": payload.get("confidence"),
                # Prefer duration_ms, but show any duration we got from the engine.
                "duration_ms": payload.get("duration_ms") or payload.get("duration"),
                "error": payload.get("error") or payload.get("message"),
            }
        )
    return rows


def render_summary(summary: Dict[str, object]) -> None:
    st.subheader("Overall verdict")
    cols = st.columns(3)
    cols[0].metric("Verdict", summary.get("verdict", "pending"))
    cols[1].metric("Severity", summary.get("severity", "informational"))
    cols[2].metric("Confidence", summary.get("confidence", 0))

    st.write(
        "Families:",
        ", ".join(summary.get("families") or []) or "—",
    )
    st.write("Primary family:", summary.get("primary_family") or "—")
    st.write("Categories:", ", ".join(summary.get("categories") or []) or "—")

    # API may send signatures as dicts; flatten to readable strings.
    signatures = summary.get("signatures") or []
    rendered_signatures = []
    for sig in signatures:
        if isinstance(sig, dict):
            rendered_signatures.append(sig.get("signature") or sig.get("rule") or "")
        else:
            rendered_signatures.append(str(sig))
    st.write("Signatures:", ", ".join(filter(None, rendered_signatures)) or "—")

    details = summary.get("details") or {}
    if details:
        st.subheader("Engine details")
        st.table(render_engine_table(details))

    st.download_button(
        "Download raw JSON",
        data=json.dumps(summary, indent=2),
        file_name=f"multiav-summary-{summary.get('job_id', 'job')}.json",
        mime="application/json",
    )


def upload_view(config: UIConfig) -> None:
    st.header("Upload a file for scanning")
    st.caption("Files are scanned server-side; keep size reasonable for quick turnaround.")

    client = get_client(config)
    engines = st.cache_data(ttl=120)(client.get_engines)()
    if engines:
        st.write("Enabled engines")
        st.table(engines)

    uploaded = st.file_uploader("Choose a file", type=None)
    if not uploaded:
        return

    max_bytes = config.max_upload_mb * 1024 * 1024
    if uploaded.size and uploaded.size > max_bytes:
        st.error(f"File exceeds max upload of {config.max_upload_mb} MB")
        return

    if st.button("Submit for scanning"):
        upload_bytes = uploaded.getvalue()
        try:
            response = client.upload_file(upload_bytes, filename=uploaded.name, content_type=uploaded.type)
        except Exception as exc:  # pragma: no cover - Streamlit surfacing
            st.error(f"Upload failed: {exc}")
            return

        st.session_state["job_id"] = response.get("job_id")
        st.session_state["last_file_bytes"] = upload_bytes
        st.session_state["last_file_name"] = uploaded.name
        st.session_state["cached"] = response.get("cached", False)
        st.success(f"Job {response.get('job_id')} submitted. Cached={response.get('cached')}")


def status_view(config: UIConfig) -> None:
    st.header("Live status")
    job_id = st.session_state.get("job_id")
    if not job_id:
        st.info("Upload a file to start tracking a scan job.")
        return

    client = get_client(config)
    try:
        summary = client.get_results(job_id)
    except Exception as exc:  # pragma: no cover - Streamlit surfacing
        st.error(f"Could not fetch status: {exc}")
        return

    status_label = readable_status(summary.get("status"))
    st.subheader(f"Job {job_id}")
    st.write(f"Status: {status_label}")
    st.write("Started:", summary.get("started_at"))
    st.write("Completed:", summary.get("completed_at") or "—")

    if not MultiAVClient.is_terminal(summary.get("status")):
        st.caption("Polling every few seconds…")
        st.autorefresh(interval=int(config.poll_interval * 1000), key="status_poll")
    else:
        st.success("Job reached a terminal state. Navigate to Results to review.")

    details = summary.get("details") or {}
    if details:
        st.table(render_engine_table(details))


def results_view(config: UIConfig) -> None:
    st.header("Results")
    job_id = st.session_state.get("job_id")
    if not job_id:
        st.info("Upload a file to view results.")
        return

    client = get_client(config)
    try:
        summary = client.get_results(job_id)
    except Exception as exc:  # pragma: no cover - Streamlit surfacing
        st.error(f"Could not fetch results: {exc}")
        return

    if not MultiAVClient.is_terminal(summary.get("status")):
        # Keep this tab refreshing so users don't sit on a stale partial summary.
        st.caption("Still processing. Refreshing automatically until the job finishes…")
        st.autorefresh(interval=int(config.poll_interval * 1000), key="results_poll")

    render_summary(summary)


def history_view(config: UIConfig) -> None:
    st.header("Recent scans")
    if not config.feature_history:
        st.info("History view is disabled")
        return

    status_filter = st.selectbox("Status filter", options=["", *sorted(TERMINAL_STATUSES)], index=0)
    hash_filter = st.text_input("SHA256 contains")

    client = get_client(config)
    try:
        jobs = client.list_recent_jobs(status=status_filter or None, sha256=hash_filter or None)
    except Exception as exc:  # pragma: no cover - Streamlit surfacing
        st.error(f"Could not load job history: {exc}")
        return

    if not jobs:
        st.info("No jobs to display yet.")
        return

    st.dataframe(jobs, hide_index=True)

    if st.session_state.get("last_file_bytes") and st.button("Re-run last upload"):
        try:
            response = client.upload_file(
                st.session_state["last_file_bytes"],
                filename=st.session_state.get("last_file_name", "reupload.bin"),
            )
            st.session_state["job_id"] = response.get("job_id")
            st.success(f"Re-run submitted as job {response.get('job_id')}.")
        except Exception as exc:  # pragma: no cover - Streamlit surfacing
            st.error(f"Re-run failed: {exc}")


def main() -> None:
    st.set_page_config(page_title="Multi-AV Dashboard", layout="wide")
    config = load_ui_config()

    st.title("Multi-AV Streamlit Dashboard")
    st.caption("Upload, monitor, and review scan results without touching raw APIs.")

    tabs = st.tabs(["Upload", "Status", "Results", "History"])
    with tabs[0]:
        upload_view(config)
    with tabs[1]:
        status_view(config)
    with tabs[2]:
        results_view(config)
    with tabs[3]:
        history_view(config)


if __name__ == "__main__":
    main()
