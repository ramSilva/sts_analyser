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
# .run file loading
# ---------------------------------------------------------------------------

def load_run_files(uploaded_files) -> list[dict]:
    """Parse all uploaded .run files (JSON) and return them as dicts."""
    runs = []
    for f in uploaded_files:
        try:
            data = json.loads(f.read())
            runs.append(data)
        except json.JSONDecodeError as e:
            st.warning(f"⚠️ Skipping **{f.name}**: {e}")
    return runs


def is_win(run: dict) -> bool:
    """A run is a win when the player was not killed by any encounter or event."""
    return (
        run.get("killed_by_encounter", "") == "NONE.NONE"
        and run.get("killed_by_event", "") == "NONE.NONE"
    )


def finished_act1(run: dict) -> bool:
    """A run finished Act 1 if map_point_history contains more than one act."""
    return len(run.get("map_point_history", [])) >= 2


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def show_win_rate(runs: list[dict]) -> None:
    """Calculate the overall win rate across all uploaded runs."""
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
    """Calculate the win rate for runs that completed Act 1."""
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


def show_condition_failure_rate(runs: list[dict]) -> None:
    """Calculate the % of times a specific condition was met but the run was lost."""
    condition = st.text_input("Condition name / key to check")
    if condition:
        # TODO: implement based on your .run schema
        st.info(f"Not yet implemented: Failure rate for condition '{condition}'")


# ---------------------------------------------------------------------------
# Metric registry — add new metrics here, nothing else needs to change
# ---------------------------------------------------------------------------

METRICS: dict[str, callable] = {
    "Win rate":                              show_win_rate,
    "Win rate after finishing Act 1":        show_win_rate_after_act1,
    "% of times a condition was met & lost": show_condition_failure_rate,
}


# ---------------------------------------------------------------------------
# App layout
# ---------------------------------------------------------------------------

def main() -> None:
    st.set_page_config(page_title="STS Run Analyser", page_icon="🗡️", layout="centered")
    st.title("🗡️ STS Run Analyser")

    # ── Sidebar: file upload ─────────────────────────────────────────────
    with st.sidebar:
        st.header("1. Upload your .run files")
        uploaded = st.file_uploader(
            "Select one or more .run files",
            type="run",
            accept_multiple_files=True,
        )

    if not uploaded:
        st.info("👈 Upload your .run files using the sidebar to get started.")
        return

    runs = load_run_files(uploaded)
    if not runs:
        st.error("No valid .run files could be parsed.")
        return

    st.success(f"✅ Loaded **{len(runs)}** run(s) successfully.")

    # ── Main area: metric selection ──────────────────────────────────────
    st.divider()
    st.header("2. Choose a metric")

    metric_label = st.selectbox("What would you like to calculate?", list(METRICS.keys()))

    st.divider()
    st.header("3. Results")

    METRICS[metric_label](runs)


if __name__ == "__main__":
    main()
