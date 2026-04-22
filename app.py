#!/usr/bin/env python3
"""
test_run_analyzer.py
Streamlit web app — analyzes XML test run files and calculates various metrics.

Run locally:
    streamlit run test_run_analyzer.py

Deploy free:
    https://streamlit.io/cloud  (point it at this file in your GitHub repo)
"""

import xml.etree.ElementTree as ET

import streamlit as st


# ---------------------------------------------------------------------------
# XML loading
# ---------------------------------------------------------------------------

def load_xml_files(uploaded_files) -> list[ET.Element]:
    """Parse all uploaded XML files and return their root elements."""
    roots = []
    for f in uploaded_files:
        try:
            root = ET.fromstring(f.read())
            roots.append(root)
        except ET.ParseError as e:
            st.warning(f"⚠️ Skipping **{f.name}**: {e}")
    return roots


# ---------------------------------------------------------------------------
# Metrics — add your implementations here
# ---------------------------------------------------------------------------

def show_success_rate(roots: list[ET.Element]) -> None:
    """Calculate the overall success rate across all test runs."""
    # TODO: implement based on your XML schema
    st.info("Not yet implemented: Overall success rate")


def show_success_rate_after_phase1(roots: list[ET.Element]) -> None:
    """Calculate the success rate for runs that completed Phase 1."""
    # TODO: implement based on your XML schema
    st.info("Not yet implemented: Success rate after Phase 1")


def show_condition_failure_rate(roots: list[ET.Element]) -> None:
    """Calculate the % of times a specific condition was met but failed."""
    condition = st.text_input("Condition name / key to check")
    if condition:
        # TODO: implement based on your XML schema
        st.info(f"Not yet implemented: Failure rate for condition '{condition}'")


# ---------------------------------------------------------------------------
# Metric registry — add new metrics here, nothing else needs to change
# ---------------------------------------------------------------------------

METRICS: dict[str, callable] = {
    "Overall success rate":                    show_success_rate,
    "Success rate after finishing Phase 1":    show_success_rate_after_phase1,
    "% of times a condition was met & failed": show_condition_failure_rate,
}


# ---------------------------------------------------------------------------
# App layout
# ---------------------------------------------------------------------------

def main() -> None:
    st.set_page_config(page_title="Test Run Analyzer", page_icon="🧪", layout="centered")
    st.title("🧪 Test Run Analyzer")

    # ── Sidebar: file upload ─────────────────────────────────────────────
    with st.sidebar:
        st.header("1. Upload your XML files")
        uploaded = st.file_uploader(
            "Select one or more XML test run files",
            type="xml",
            accept_multiple_files=True,
        )

    if not uploaded:
        st.info("👈 Upload your XML test run files using the sidebar to get started.")
        return

    roots = load_xml_files(uploaded)
    if not roots:
        st.error("No valid XML files could be parsed.")
        return

    st.success(f"✅ Loaded **{len(roots)}** file(s) successfully.")

    # ── Main area: metric selection ──────────────────────────────────────
    st.divider()
    st.header("2. Choose a metric")

    metric_label = st.selectbox("What would you like to calculate?", list(METRICS.keys()))

    st.divider()
    st.header("3. Results")

    METRICS[metric_label](roots)


if __name__ == "__main__":
    main()

