import json
import os
import time
from dataclasses import dataclass
from typing import Dict, List, Optional
from pathlib import Path
from uuid import UUID
from collections import deque

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


def _poll_if_needed(config: UIConfig, job_id: str) -> None:
    """Background polling for non-terminal jobs across all tabs."""
    if not job_id:
        return
    
    client = get_client(config)
    try:
        summary = client.get_results(job_id)
        if not MultiAVClient.is_terminal(summary.get("status")):
            time.sleep(config.poll_interval)
            st.rerun()
    except Exception:
        pass


def _save_job_id(job_id: str) -> None:
    """Persist the latest job_id in session (and URL) so refreshes can restore it."""
    if not job_id:
        return
    try:
        # Enforce valid UUID to avoid hammering the API with bad IDs.
        job_id = str(UUID(str(job_id)))
    except Exception:
        st.session_state.pop("job_id", None)
        return

    st.session_state["job_id"] = job_id
    
    # Maintain recent job list
    if "recent_job_ids" not in st.session_state:
        st.session_state["recent_job_ids"] = []
    
    recent = st.session_state["recent_job_ids"]
    if job_id not in recent:
        recent.insert(0, job_id)
        st.session_state["recent_job_ids"] = recent[:20]
    
    try:
        if hasattr(st, "query_params"):
            st.query_params["job_id"] = job_id
        else:
            st.experimental_set_query_params(job_id=job_id)
    except Exception:
        # Older Streamlit versions may not support query params; ignore quietly.
        pass


def render_status_or_results(config: UIConfig, job_id: str, auto_refresh: bool = True) -> None:
    """Shared renderer to show current status/results for a job id."""
    try:
        job_id = str(UUID(str(job_id)))
    except Exception:
        st.warning("Invalid job ID format")
        return  # Exit before making API call

    client = get_client(config)
    try:
        summary = client.get_results(job_id)
    except Exception as exc:
        st.error(f"Could not fetch status for {job_id}: {exc}")
        return

    status = summary.get("status")
    is_terminal = MultiAVClient.is_terminal(status)
    
    st.write(f"Job: {job_id}")
    st.write(f"Status: {readable_status(status)}")
    
    if not is_terminal:
        st.caption("Polling…")
        details = summary.get("details") or {}
        if details:
            st.table(render_engine_table(details))
        if auto_refresh:
            _poll_if_needed(config, job_id)
    else:
        render_summary(summary)


def load_ui_config() -> UIConfig:
    # Prefer environment variables first, then secrets as fallback
    api_base_url = os.getenv("API_BASE_URL")
    poll_interval = os.getenv("POLL_INTERVAL")
    request_timeout = os.getenv("REQUEST_TIMEOUT")
    max_upload_mb = os.getenv("MAX_UPLOAD_MB")
    feature_history = os.getenv("FEATURE_HISTORY")
    
    # Only try secrets if env vars are missing
    if not api_base_url:
        try:
            api_base_url = st.secrets.get("api_base_url", "http://localhost:8000")
        except Exception:
            api_base_url = "http://localhost:8000"
    
    if not poll_interval:
        try:
            poll_interval = st.secrets.get("poll_interval", 2)
        except Exception:
            poll_interval = 2
    
    if not request_timeout:
        try:
            request_timeout = st.secrets.get("REQUEST_TIMEOUT", 15)
        except Exception:
            request_timeout = 15
    
    if not max_upload_mb:
        try:
            max_upload_mb = st.secrets.get("MAX_UPLOAD_MB", 50)
        except Exception:
            max_upload_mb = 50
    
    if feature_history is None:
        try:
            feature_history = st.secrets.get("FEATURE_HISTORY", True)
        except Exception:
            feature_history = True
    
    return UIConfig(
        api_base_url=str(api_base_url),
        poll_interval=float(poll_interval),
        request_timeout=float(request_timeout),
        max_upload_mb=int(max_upload_mb),
        feature_history=_as_bool(feature_history),
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
    
    # Register cleanup on session end (best effort with atexit)
    if "client_cleanup_registered" not in st.session_state:
        import atexit
        atexit.register(lambda: client.close() if client else None)
        st.session_state["client_cleanup_registered"] = True
    
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
    st.header("Results")
    st.subheader("Overall verdict")

    verdict = summary.get("verdict", "pending")
    severity = summary.get("severity", "informational")
    confidence = summary.get("confidence", 0)

    cols = st.columns(3)
    cols[0].markdown("**Verdict**")
    cols[0].markdown(f"### {verdict}")
    cols[1].markdown("**Severity**")
    cols[1].markdown(f"### {severity}")
    cols[2].markdown("**Confidence**")
    cols[2].markdown(f"### {confidence}")

    st.write("Families:", ", ".join(summary.get("families") or []) or "—")
    st.write("Primary family:", summary.get("primary_family") or "—")
    st.write("Categories:", ", ".join(summary.get("categories") or []) or "—")

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

    # Use stable key to prevent uploader reset
    upload_key = f"uploader_{st.session_state.get('job_id', 'default')}"
    uploaded = st.file_uploader("Choose a file", type=None, key=upload_key)
    if not uploaded:
        if st.session_state.get("job_id"):
            st.divider()
            st.subheader("Latest job status")
            render_status_or_results(config, st.session_state["job_id"])
        return

    max_bytes = config.max_upload_mb * 1024 * 1024
    if uploaded.size and uploaded.size > max_bytes:
        st.error(f"File exceeds max upload of {config.max_upload_mb} MB")
        return

    # optional for re-upload:
    store_for_reupload = st.checkbox("Enable re-upload feature", value=False, 
                                  help="Keep file in memory for quick re-scan")
    if st.button("Submit for scanning"):
        upload_bytes = uploaded.getvalue()
        try:
            response = client.upload_file(upload_bytes, filename=uploaded.name, content_type=uploaded.type)
        except Exception as exc:
            st.error(f"Upload failed: {exc}")
            return

        _save_job_id(response.get("job_id"))
        # Only store bytes if user opted in
        if store_for_reupload:
            st.session_state["last_file_bytes"] = upload_bytes
            
        # Only store if re-upload feature enabled (moved to before upload button)
        st.session_state["last_file_name"] = uploaded.name
        st.session_state["cached"] = response.get("cached", False)
        # fix unexpexted re-run:
        
        # Store upload in history queue (max 5 recent uploads)
        if "upload_history" not in st.session_state:
            st.session_state["upload_history"] = deque(maxlen=5)
        
        st.session_state["upload_history"].appendleft({
            "bytes": upload_bytes,
            "name": uploaded.name,
            "job_id": response.get("job_id"),
            "cached": response.get("cached", False),
        })
        
        # Different messages for cached vs new
        cached_flag = response.get("cached")
        message = (
            f"✅ Job `{response.get('job_id')}` submitted. Cached: True 📋 This file was scanned before."
            if cached_flag
            else f"✅ Job `{response.get('job_id')}` submitted. Cached: False"
        )
        st.session_state["upload_message"] = message
        st.success(message)

    # Show live preview after upload
    job_id = st.session_state.get("job_id")
    if job_id:
        if st.session_state.get("upload_message"):
            st.success(st.session_state["upload_message"])
        st.divider()
        st.subheader("Latest job status")
        render_status_or_results(config, job_id)


def status_view(config: UIConfig) -> None:
    st.header("Live status")
    job_id = st.session_state.get("job_id")
    if not job_id:
        st.info("Upload a file to start tracking a scan job.")
        return

    try:
        job_id = str(UUID(str(job_id)))
    except Exception:
        st.session_state.pop("job_id", None)
        st.warning("Invalid job ID cleared. Please upload a new file.")
        return

    client = get_client(config)
    try:
        summary = client.get_results(job_id)
    except Exception as exc:
        st.error(f"Could not fetch status: {exc}")
        return

    status = summary.get("status")
    is_terminal = MultiAVClient.is_terminal(status)
    
    status_label = readable_status(status)
    st.subheader(f"Job {job_id}")
    st.write(f"Status: {status_label}")
    st.write("Started:", summary.get("started_at"))
    st.write("Completed:", summary.get("completed_at") or "—")

    if not is_terminal:
        st.caption("Polling every few seconds…")
        details = summary.get("details") or {}
        if details:
            st.table(render_engine_table(details))
        _poll_if_needed(config, job_id)
    else:
        st.success("Job reached a terminal state. Navigate to Results to review.")
        details = summary.get("details") or {}
        if details:
            st.table(render_engine_table(details))


def results_view(config: UIConfig) -> None:
    st.header("Results")
    client = get_client(config)

    # Load job_id from URL if present
    if "job_id" not in st.session_state:
        try:
            params = st.query_params if hasattr(st, "query_params") else st.experimental_get_query_params()
            if params.get("job_id"):
                _save_job_id(params.get("job_id")[0])
        except Exception:
            pass

    job_id = st.session_state.get("job_id", "")
    
    # Show results immediately if job_id exists
    if job_id:
        try:
            UUID(str(job_id))  # Validate
            try:
                summary = client.get_results(job_id)
                if not MultiAVClient.is_terminal(summary.get("status")):
                    st.caption("Still processing. Refreshing automatically until the job finishes…")
                    _poll_if_needed(config, job_id)
                render_summary(summary)
            except Exception as exc:
                st.error(f"Could not fetch results for {job_id}: {exc}")
        except ValueError:
            pass  # Invalid UUID, show input form below
    
    # Input form for manual lookup
    st.divider()
    st.subheader("Load different job")
    default_job = st.session_state.get("job_id", "")
    job_input = st.text_input("Job ID", value=default_job, key="job_input_manual")
    sha_lookup = st.text_input("Lookup by SHA256 (uses most recent match)", value="")
    
    if st.button("Load job"):
        if job_input:
            try:
                _save_job_id(job_input.strip())
                st.rerun()
            except Exception:
                st.warning("Invalid job ID format. Please paste a full UUID.")
                return
        elif sha_lookup:
            try:
                matches = client.list_recent_jobs(sha256=sha_lookup.strip(), limit=1)
                if matches:
                    _save_job_id(matches[0]["job_id"])
                    st.success(f"Loaded job {matches[0]['job_id']} from SHA256 search.")
                    st.rerun()
                else:
                    st.warning("No jobs found for that SHA256.")
            except Exception as exc:
                st.error(f"Lookup failed: {exc}")
    

def history_view(config: UIConfig) -> None:
    st.header("Recent scans")
    if not config.feature_history:
        st.info("History view is disabled")
        return

    # Persist filter state across tab switches
    status_filter = st.selectbox(
        "Status filter",
        options=["", *sorted(TERMINAL_STATUSES)],
        index=0,
        key="history_status_filter"
    )
    severity_filter = st.selectbox(
        "Severity filter",
        options=["", "informational", "low", "medium", "high", "critical"],
        index=0,
        key="history_severity_filter"
    )
    hash_filter = st.text_input("SHA256 contains", key="history_hash_filter")
    job_id_filter = st.text_input("Job ID contains", key="history_job_id_filter")

    client = get_client(config)
    try:
        jobs = client.list_recent_jobs(
            status=status_filter or None,
            severity=severity_filter or None,
            sha256=hash_filter or None,
            job_id=job_id_filter or None,
        )
    except Exception as exc:
        st.error(f"Could not load job history: {exc}")
        return

    if not jobs:
        st.info("No jobs to display yet.")
        return

    feed_job_ids = [item["job_id"] for item in jobs if item.get("job_id")]
    recent_job_ids = st.session_state.get("recent_job_ids") or []
    merged_job_ids = list(dict.fromkeys(feed_job_ids + recent_job_ids))

    selected_job = st.selectbox("Jump to job_id", options=[""] + merged_job_ids, index=0)
    if selected_job:
        _save_job_id(selected_job)
        st.success(f"Loaded job {selected_job} for viewing. Check the Results tab.")

    st.dataframe(jobs, hide_index=True)

    # Re-run last upload with better UX
    if "upload_history" in st.session_state and st.session_state["upload_history"]:
        st.divider()
        st.subheader("Recent uploads")
        
        for idx, upload_record in enumerate(st.session_state["upload_history"]):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.text(f"{upload_record['name']} (Job: {upload_record['job_id'][:8]}...)")
            with col2:
                if st.button(f"Re-scan", key=f"rescan_{idx}"):
                    try:
                        response = client.upload_file(
                            upload_record["bytes"],
                            filename=upload_record["name"],
                        )
                        new_job_id = response.get("job_id")
                        _save_job_id(new_job_id)
                        st.success(f"Re-scan submitted as job {new_job_id}.")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Re-scan failed: {exc}")


def main() -> None:
    st.set_page_config(page_title="Multi-AV Dashboard", layout="wide")
    config = load_ui_config()

    st.title("Multi-AV Streamlit Dashboard")
    st.caption("Upload, monitor, and review scan results without touching raw APIs.")

    tabs = st.tabs(["Upload", "Results", "Status", "History"])
    with tabs[0]:
        upload_view(config)
    with tabs[1]:
        results_view(config)
    with tabs[2]:
        status_view(config)
    with tabs[3]:
        history_view(config)


if __name__ == "__main__":
    main()
