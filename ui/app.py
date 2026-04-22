"""Streamlit entrypoint for SimReady Phase 2 UI."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import streamlit as st

from simready.pipeline import analyze_file
from simready.ui.viz import build_face_overlay_payload


st.set_page_config(page_title="SimReady", layout="wide")
st.title("SimReady")
st.caption("AI-assisted geometry readiness analysis for structural FEA")

uploaded = st.file_uploader("Upload a STEP file", type=["step", "stp", "STEP", "STP"])
verbose = st.checkbox("Show per-face detail", value=False)

if uploaded is not None:
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = Path(tmpdir) / uploaded.name
        input_path.write_bytes(uploaded.getvalue())
        report = analyze_file(str(input_path))

        score = report.get("score", {})
        st.metric("Readiness score", f"{score.get('overall', 'n/a')}")
        st.write(report.get("status", "Unknown"))

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Findings")
            st.json(report.get("findings", []))
        with col2:
            st.subheader("Geometry")
            st.json(report.get("geometry", {}))

        st.subheader("Face overlays")
        overlays = build_face_overlay_payload(report)
        st.dataframe(overlays, use_container_width=True)

        if verbose:
            st.subheader("Raw report")
            st.code(json.dumps(report, indent=2), language="json")
else:
    st.info("Upload a STEP file to begin analysis.")
