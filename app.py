#!/usr/bin/env python3
"""
app.py
Streamlit web app — analyses STS .run files and calculates various metrics.

Run locally:
    streamlit run app.py

Deploy free:
    https://streamlit.io/cloud  (point it at this file in your GitHub repo)
"""

import json

import streamlit as st


# ---------------------------------------------------------------------------
# Persistent file store — keyed by username
# ---------------------------------------------------------------------------

@st.cache_resource
def get_all_stores() -> dict[str, dict[str, bytes]]:
    """Global store: { username -> { filename -> raw bytes } }. Persists across refreshes."""
    return {}


def get_user_store(username: str) -> dict[str, bytes]:
    all_stores = get_all_stores()
    if username not in all_stores:
        all_stores[username] = {}
    return all_stores[username]


# ---------------------------------------------------------------------------
# .run file loading
# ---------------------------------------------------------------------------

def parse_run(name: str, raw: bytes) -> dict | None:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        st.warning(f"⚠️ Skipping **{name}**: {e}")
        return None


def sync_uploads(uploaded_files, username: str) -> None:
    store = get_user_store(username)
    for f in uploaded_files:
        if f.name not in store:
            store[f.name] = f.read()


def load_runs(username: str) -> list[dict]:
    runs = []
    for name, raw in get_user_store(username).items():
        data = parse_run(name, raw)
        if data is not None:
            runs.append(data)
    return runs


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def is_win(run: dict) -> bool:
    return run.get("win", False)


def finished_act1(run: dict) -> bool:
    return len(run.get("map_point_history", [])) >= 2


def format_duration(seconds: float) -> str:
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h > 0:
        return f"{h}h {m:02d}m {s:02d}s"
    return f"{m}m {s:02d}s"


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def show_win_rate(runs: list[dict]) -> None:
    total = len(runs)
    wins = sum(1 for r in runs if is_win(r))
    losses = total - wins
    rate = (wins / total * 100) if total > 0 else 0.0

    col1, col2, col3 = st.columns(3)
    col1.metric("Total runs", total)
    col2.metric("Wins", wins)
    col3.metric("Losses", losses)
    st.progress(rate / 100)
    st.markdown(f"### Win rate: **{rate:.1f}%**")


def show_win_rate_after_act1(runs: list[dict]) -> None:
    qualifying = [r for r in runs if finished_act1(r)]
    skipped = len(runs) - len(qualifying)
    total = len(qualifying)

    if total == 0:
        st.warning("None of the uploaded runs made it past Act 1.")
        return

    wins = sum(1 for r in qualifying if is_win(r))
    losses = total - wins
    rate = (wins / total * 100) if total > 0 else 0.0

    if skipped > 0:
        st.caption(f"ℹ️ {skipped} run(s) excluded — did not finish Act 1.")

    col1, col2, col3 = st.columns(3)
    col1.metric("Runs past Act 1", total)
    col2.metric("Wins", wins)
    col3.metric("Losses", losses)
    st.progress(rate / 100)
    st.markdown(f"### Win rate after Act 1: **{rate:.1f}%**")


def show_average_time(runs: list[dict]) -> None:
    times = [r["run_time"] for r in runs if "run_time" in r]
    if not times:
        st.warning("No run_time data found in the uploaded files.")
        return

    avg = sum(times) / len(times)
    col1, col2, col3 = st.columns(3)
    col1.metric("Runs with time data", len(times))
    col2.metric("Shortest", format_duration(min(times)))
    col3.metric("Longest", format_duration(max(times)))
    st.markdown(f"### Average time per run: **{format_duration(avg)}**")


def show_total_time(runs: list[dict]) -> None:
    times = [r["run_time"] for r in runs if "run_time" in r]
    if not times:
        st.warning("No run_time data found in the uploaded files.")
        return

    col1, col2 = st.columns(2)
    col1.metric("Runs with time data", len(times))
    col2.metric("Total time", format_duration(sum(times)))
    st.markdown(f"### Total time spent: **{format_duration(sum(times))}**")


def show_total_time_truncated(runs: list[dict]) -> None:
    st.markdown("**Truncation thresholds**")
    col1, col2 = st.columns(2)
    win_cap_mins = col1.number_input("Max time for wins (minutes)", min_value=1, value=60)
    loss_cap_mins = col2.number_input("Max time for losses (minutes)", min_value=1, value=15)

    win_cap = win_cap_mins * 60
    loss_cap = loss_cap_mins * 60

    times = []
    for r in runs:
        if "run_time" not in r:
            continue
        cap = win_cap if is_win(r) else loss_cap
        times.append(min(r["run_time"], cap))

    if not times:
        st.warning("No run_time data found in the uploaded files.")
        return

    col1, col2 = st.columns(2)
    col1.metric("Runs with time data", len(times))
    col2.metric("Total time (truncated)", format_duration(sum(times)))
    st.markdown(f"### Total time (truncated): **{format_duration(sum(times))}**")


# ---------------------------------------------------------------------------
# Metric registry
# ---------------------------------------------------------------------------

METRICS: dict[str, callable] = {
    "Win rate":                              show_win_rate,
    "Win rate after finishing Act 1":        show_win_rate_after_act1,
    "Average time per run":                  show_average_time,
    "Total time spent on runs":              show_total_time,
    "Total time (truncated per outcome)":    show_total_time_truncated,
    "% of times a condition was met & lost": lambda runs: st.info("Not yet implemented"),
}


# ---------------------------------------------------------------------------
# App layout
# ---------------------------------------------------------------------------

def main() -> None:
    st.set_page_config(page_title="STS Run Analyser", page_icon="🗡️", layout="centered")
    st.title("🗡️ STS Run Analyser")

    # ── Sidebar ──────────────────────────────────────────────────────────
    with st.sidebar:
        st.header("Who are you?")
        username = st.text_input("Enter your name", placeholder="e.g. Ricardo").strip()

        if not username:
            st.info("Enter your name to get started.")
            st.stop()

        st.divider()
        st.header("Upload your .run files")
        uploaded = st.file_uploader(
            "Select one or more .run files",
            type="run",
            accept_multiple_files=True,
        )

        if uploaded:
            sync_uploads(uploaded, username)

        store = get_user_store(username)
        if store:
            st.success(f"{len(store)} file(s) loaded")
            with st.expander("Loaded files"):
                for name in store:
                    st.text(f"• {name}")
            if st.button("🗑️ Clear my files", use_container_width=True):
                store.clear()
                st.rerun()

    runs = load_runs(username)

    if not runs:
        st.info("👈 Upload your .run files using the sidebar to get started.")
        return

    st.divider()
    st.header("2. Choose a metric")
    metric_label = st.selectbox("What would you like to calculate?", list(METRICS.keys()))

    st.divider()
    st.header("3. Results")
    METRICS[metric_label](runs)


if __name__ == "__main__":
    main()
