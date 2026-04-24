"""Streamlit entrypoint for SimReady Phase 3 UI."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import streamlit as st

from simready.html_report import render_html_report
from simready.pipeline import analyze_file
from simready.ui.viz import build_face_overlay_payload


st.set_page_config(page_title="SimReady", page_icon="⚙️", layout="wide")

st.markdown(
    """
    <style>
      .severity-critical, .severity-major { color: #ef4444; font-weight: 700; }
      .severity-minor { color: #f59e0b; font-weight: 700; }
      .severity-info { color: #38bdf8; font-weight: 700; }
      .status-green { color: #22c55e; font-weight: 700; }
      .status-yellow { color: #eab308; font-weight: 700; }
      .status-orange { color: #f97316; font-weight: 700; }
      .status-red { color: #ef4444; font-weight: 700; }
      .section-gap { margin-top: 0.75rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

STATUS_CLASS = {
    "SimulationReady": "status-green",
    "ReviewRecommended": "status-yellow",
    "NeedsAttention": "status-orange",
    "NotReady": "status-red",
    "InvalidInput": "status-red",
}
SEVERITY_ORDER = {"Critical": 0, "Major": 1, "Minor": 2, "Info": 3}

st.title("SimReady")
st.caption("AI-assisted geometry readiness analysis for structural FEA")

with st.sidebar:
    st.header("Analysis")
    timeout = st.slider("Analysis timeout (seconds)", 30, 300, 120)
    verbose = st.checkbox("Show raw JSON", value=False)

uploaded = st.file_uploader("Upload a STEP file", type=["step", "stp", "STEP", "STP"])


def _bbox_dims(geometry: dict) -> tuple[float, float, float]:
    bbox = (geometry or {}).get("bounding_box") or {}
    return (
        float(bbox.get("xmax", 0.0) - bbox.get("xmin", 0.0)),
        float(bbox.get("ymax", 0.0) - bbox.get("ymin", 0.0)),
        float(bbox.get("zmax", 0.0) - bbox.get("zmin", 0.0)),
    )


def _severity_class(value: str) -> str:
    return f"severity-{str(value).lower()}"


if uploaded is not None:
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = Path(tmpdir) / uploaded.name
        input_path.write_bytes(uploaded.getvalue())
        healed_path = Path(tmpdir) / f"{input_path.stem}_healed.step"

        with st.spinner("Analyzing geometry..."):
            report = analyze_file(str(input_path), export_healed_path=str(healed_path), timeout=timeout)

        score = report.get("score", {})
        status = report.get("status", "Unknown")
        elapsed = report.get("elapsed_seconds", "n/a")
        complexity = report.get("complexity", {})

        with st.sidebar:
            st.metric("Score", f"{score.get('overall', 'n/a')}", delta=score.get("label", status))
            st.markdown(f"<div class='{STATUS_CLASS.get(status, '')}'>Status: {status}</div>", unsafe_allow_html=True)
            st.caption(f"Elapsed: {elapsed:.2f}s" if isinstance(elapsed, (int, float)) else f"Elapsed: {elapsed}")
            if complexity:
                st.caption(f"{complexity.get('label')} — {complexity.get('confidence')} confidence")

            st.download_button(
                "Download JSON report",
                data=json.dumps(report, indent=2),
                file_name=f"{input_path.stem}_simready_report.json",
                mime="application/json",
            )

            html_path = Path(tmpdir) / f"{input_path.stem}_simready_report.html"
            render_html_report(report, str(html_path))
            st.download_button(
                "Download HTML report",
                data=html_path.read_text(encoding="utf-8"),
                file_name=html_path.name,
                mime="text/html",
            )

            healed_export = report.get("healed_export")
            if healed_export and Path(healed_export).exists():
                st.download_button(
                    "Download healed STEP",
                    data=Path(healed_export).read_bytes(),
                    file_name=Path(healed_export).name,
                    mime="application/step",
                )

        if status == "SimulationReady":
            st.success("Simulation-ready geometry. No blocking issues detected.")
        elif status in {"NeedsAttention", "NotReady", "InvalidInput"}:
            st.warning(f"{status}: review the flagged issues before using this geometry for simulation.")

        geometry = report.get("geometry") or {}
        dims = _bbox_dims(geometry)
        g1, g2, g3, g4 = st.columns(4)
        g1.metric("Faces", geometry.get("face_count", "n/a"))
        g2.metric("Edges", geometry.get("edge_count", "n/a"))
        g3.metric("Solids", geometry.get("solid_count", "n/a"))
        g4.metric("BBox", f"{dims[0]:.2f} × {dims[1]:.2f} × {dims[2]:.2f}")

        st.subheader("Findings")
        findings = sorted(report.get("findings", []), key=lambda item: SEVERITY_ORDER.get(item.get("severity", "Info"), 99))
        if findings:
            findings_rows = []
            for item in findings:
                findings_rows.append(
                    {
                        "Severity": item.get("severity", "Info"),
                        "Check": item.get("check", ""),
                        "Detail": item.get("detail", ""),
                        "Suggestion": item.get("suggestion", ""),
                    }
                )
            st.dataframe(findings_rows, use_container_width=True)
        else:
            st.info("No findings. Clean geometry.")

        st.divider()
        st.subheader("Score Breakdown")
        s1, s2, s3, s4 = st.columns(4)
        s1.metric("Overall", score.get("overall", "n/a"))
        s2.metric("Rule face mean", score.get("rule_face_mean", "n/a"))
        s3.metric("ML penalty", score.get("ml_penalty_points", "n/a"))
        s4.metric("Label", score.get("label", status))

        st.divider()
        st.subheader("Graph Topology")
        graph = report.get("graph") or {}
        t1, t2, t3, t4 = st.columns(4)
        t1.metric("Faces", graph.get("face_count", "n/a"))
        t2.metric("Edges", graph.get("edge_count", "n/a"))
        t3.metric("Coedges", graph.get("coedge_count", "n/a"))
        t4.metric("Adjacency", graph.get("adjacency_count", "n/a"))

        st.divider()
        st.subheader("Per-Face Heatmap Table")
        overlays = build_face_overlay_payload(report)
        if overlays:
            st.dataframe(overlays, use_container_width=True)
        else:
            st.info("No per-face overlay data available.")

        bodies = report.get("bodies") or []
        if bodies:
            st.divider()
            st.subheader("Multi-Body Analysis")
            tabs = st.tabs([f"Body {body.get('body_index', idx + 1)}" for idx, body in enumerate(bodies)])
            for tab, body in zip(tabs, bodies):
                with tab:
                    st.write(f"Status: {body.get('status', 'Unknown')}")
                    st.json(
                        {
                            "geometry": body.get("geometry", {}),
                            "score": body.get("score", {}),
                            "findings": body.get("findings", []),
                        }
                    )

        st.divider()
        st.subheader("ML Details")
        ml = report.get("ml") or {}
        with st.expander("Show ML metadata"):
            st.json(
                {
                    "model_name": ml.get("model_name"),
                    "weights_loaded": ml.get("weights_loaded"),
                    "score_source": ml.get("score_source"),
                    "aggregate_score": ml.get("aggregate_score"),
                    "notes": ml.get("notes", []),
                }
            )

        with st.expander("Raw JSON"):
            st.code(json.dumps(report, indent=2), language="json")
else:
    st.info("Upload a STEP file to begin analysis.")
