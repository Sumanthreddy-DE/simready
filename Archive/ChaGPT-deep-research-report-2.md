# Executive Summary  
We surveyed relevant open-source CAD/B‑Rep projects on GitHub to guide an MVP (minimum viable product) vs production-ready SimReady tool for geometry-to-FEA readiness.  The core geometry libraries are **pythonocc-core** (Python bindings to OpenCASCADE【10†L318-L324】) or its lightweight wrapper **occwl**【12†L275-L282】, both of which support importing STEP/IGES models.  These can parse and visualize CAD parts.  For optional ML-driven analysis, Autodesk’s **BRepNet** (and related UV-Net) provide graph-based networks on B‑Rep data【7†L305-L313】.  For visualization/UX, established tools like **PyVista** (VTK-based 3D plotting)【29†L379-L388】 and **Streamlit** (easy Python dashboards)【31†L341-L347】 are recommended.  No single repo was found dedicated to automatic “CAD cleaning” checks; these must be implemented via OpenCascade queries.  

Below we compare key projects, outline rule-based checks (gaps, non-manifold edges, thin features, fillets, etc.), sketch a pipeline (with a Mermaid diagram), and list an implementation checklist.  We also contrast an MVP prototype (quick demo, minimal UI/tests) vs a polished product (robust UX, CI, documentation, packaging/licensing).  We propose validation methods (use sample CAD models, e.g. from GrabCAD, compute precision/recall of detected issues) and an example severity‑to‑action table.  

## Core Libraries & Tools  
| **Repository (GitHub)** | **Role/Features** | **Notes** |  
|-------------------------|-------------------|-----------|  
| [tpaviot/pythonocc-core](https://github.com/tpaviot/pythonocc-core) | Python bindings for OpenCASCADE (OCC) kernel.  Full CAD modeling API, including STEP/IGES import and topology operations【10†L318-L324】. | 1.9k★, actively maintained (latest release Feb 2026). Supports headless geometry checks and visualization. |  
| [AutodeskAILab/occwl](https://github.com/AutodeskAILab/occwl) | Lightweight Pythonic wrapper over pythonocc.  Simplifies OCC usage (e.g. `Solid.make_box()`)【12†L275-L282】. Good for quick prototyping. | 83★. Provides example viewer integration. |  
| [AutodeskAILab/BRepNet](https://github.com/AutodeskAILab/BRepNet) | Neural network on boundary representations. Uses topological message passing on faces/edges【7†L305-L313】. For ML tasks (segmentation, complexity hints). | 222★. Research code, requires dataset generation (see below). |  
| [pyvista/pyvista](https://github.com/pyvista/pyvista) | VTK-based 3D plotting and mesh analysis【29†L379-L388】. High-level Python API for visualization. | 8.6k★. Good for showing results (meshes, highlighted defects) in browser/Jupyter. |  
| [streamlit/streamlit](https://github.com/streamlit/streamlit) | Rapid data-app UI framework【31†L341-L347】. Build web apps from Python scripts. | 44k★. Easy interactivity (sliders, displays) for a demo/prototype. |  

*Table: Selected GitHub libraries for parsing (STEP/B‑Rep), rule-checks, ML, and visualization.  Stars (★) noted as of 2026. Official repos are linked.*  

## Parser and Geometry-Check Examples  
Using pythonocc (or occwl), one loads a STEP/BREP and queries its topology.  For example, PythonOCC’s `STEPControl_Reader` can import a STEP file into a `TopoDS_Shape` (a solid or compound).  A simple pattern is: 

```python
from OCC.Core.STEPControl import STEPControl_Reader
from OCC.Core.IFSelect import IFSelect_RetDone

step_reader = STEPControl_Reader()
status = step_reader.ReadFile("model.step")
if status == IFSelect_RetDone:
    step_reader.TransferRoot(1)
    shape = step_reader.Shape(1)    # TopoDS_Shape for the whole model
else:
    print("STEP import failed")
```

This approach comes from the official PythonOCC examples【60†L622-L630】.  Similarly, one can read a native OCC brep with `breptools_Read`【45†L352-L359】. Once loaded, the shape’s topology (faces, edges) can be navigated via OCC’s `TopExp_Explorer` or `TopologyExplorer` utilities.  

With the geometry loaded, rule-based checks must be implemented. For instance:  
- **Gaps/Holes:** Detect if the model has open wires or missing faces. One can traverse edges that bound no face or look for “open shell” boundaries.  
- **Non-manifold edges:** Identify edges belonging to >2 faces or zero faces; these violate a solid’s manifoldness. (The FreeCAD FEM guide notes that “non-manifold geometries… have to be fixed before meshing”【20†L366-L373】.) OCC can find edges and count adjacent faces to flag anomalies.  
- **Thin walls/features:** For each face or shell, compute wall thickness. (Thin features can be inferred by small face areas or small edge lengths relative to body size.) Alternatively, approximate by offsetting surfaces.  
- **Tiny details:** Small fillets/chamfers or holes: detect features whose dimensions fall below a threshold. For example, measure each fillet radius or hole diameter; if under a set tolerance, mark it for removal/simplification. The FreeCAD guide suggests omitting “small fillets, small holes, other small details” for FEM simplification【20†L387-L394】.  

No single open-source repo was found that automates all these checks, so they must be coded, often using OCC calls. However, scripts in the pythonocc-demos (e.g. face recognition, STEP import) show how to inspect surfaces【60†L622-L630】【45†L352-L359】.  We can build on those examples.  

```mermaid
flowchart LR
    U(User) -->|Upload STEP| P[Parser (pythonocc/occwl)]
    P --> R[Rule-Based Checks]
    P --> M[ML Hint (BRepNet)]
    R --> A[Aggregate Issues]
    M --> A
    A --> UI[UI (Streamlit & PyVista)]
    UI --> U
```

*Diagram: SimReady processing pipeline. The user provides a STEP/B-Rep file; the backend parser (OCC) feeds both rule-check modules and (optionally) a BRepNet ML component. Results are aggregated and presented via a Streamlit/PyVista interface.*  

## Machine Learning (BRepNet) Role  
A secondary path uses ML to assist identification of complex features. Projects like **BRepNet** (AutodeskAI Lab) implement graph neural networks on B-Rep topology【7†L305-L313】. While beyond MVP scope, one could use such networks to highlight “hard” regions (e.g. many small features) or classify faces by type. For example, BRepNet was designed for part segmentation and recognition; we might train it on a labeled dataset (or use self-supervised learning【8†L257-L266】) to predict where manual fixes are needed. However, ML is supplementary: the core MVP relies on deterministic checks.  

## Rule-Based Checks and Severity Levels  
From the literature (e.g. FreeCAD FEM prep docs【20†L366-L373】【20†L387-L394】), we prioritize these checks:  
- **Critical:** Model is not a closed solid (open edges, gaps, non-manifold edges). Such issues block simulation.  
- **High:** Very thin walls/features that will cause poor mesh quality or failure.  
- **Medium:** Small geometric details (tiny fillets, holes, notches) that can be safely removed.  
- **Low:** Cosmesis or annotation features (text engraving, logos) that have negligible structural effect.  

For each flagged issue, the tool should suggest fixes. Example mappings:  

| **Issue Detected**        | **Severity** | **Suggested Action**                     |
|---------------------------|-------------:|------------------------------------------|
| Open gap/hole in surface  | Critical     | Fill gap or rebuild surface closure      |
| Non-manifold edge         | Critical     | Merge faces or remove extra edges        |
| Wall thickness < 0.1×size | High         | Thicken wall or add support elements     |
| Fillet radius < tolerance | Medium       | Increase radius or remove fillet         |
| Tiny hole (diam < thr)    | Medium       | Remove hole or enlarge diameter          |
| Decorative detail/logo    | Low          | Ignore or remove (defeature)            |  

*Table: Example severity categories and fix suggestions. Thresholds depend on part size and FEA solver limits. Users should confirm before applying changes.*  

## MVP vs Production Tool Differences  
An **MVP demo** of SimReady would focus on core functionality: basic CLI or simple web UI, minimal error handling, and ad-hoc testing. It might be a single script showing that a STEP can be loaded and issues reported. For example, a barebones Streamlit app could take a file upload and print a text report. Packaging would be minimal (perhaps just a `requirements.txt`) and there may be no formal license or documentation.  

In contrast, a **robust product** requires:  
- **User Experience:** Polished UI (intuitive menus, progress indicators, 3D previews). Possibly a full web front-end or standalone app.  
- **Reliability:** Comprehensive unit/integration tests (e.g. pytest suite with CAD test cases【43†L271-L280】), continuous integration pipelines, and performance tuning to meet the 10–30s targets.  
- **Packaging:** Structured repository (see below) with `setup.py` or `pyproject.toml`, clear dependency management, and possible docker or pip packaging.  
- **Documentation & License:** User guides, developer docs, and an open-source license.  
- **Deployment:** Automated CI/CD (GitHub Actions), error logging, and maintainability (code reviews, issue tracking).  

Example: a mature Python project might follow the layout in [python_project_example]【43†L271-L280】: a `setup.py` for installation, a `tests/` folder, and use pytest.  

## Proposed Repo Layout & Implementation Checklist  
A suggested repository structure (in Markdown/tree style) might be:  

```
SimReady/                 
├─ simready/             # core package  
│   ├─ parser.py         # STEP/BREP loading (pythonocc/occwl)  
│   ├─ checks/           # modules for each rule-based check (gaps, manifold, thin, etc.)  
│   ├─ ml/               # optional ML models (BRepNet usage)  
│   └─ utils.py          # common utilities (geometry queries)  
├─ ui/                  
│   ├─ app.py            # Streamlit application frontend  
│   └─ viz.py            # Visualization helpers (PyVista)  
├─ tests/                
│   ├─ data/             # sample STEP/BREP test files (e.g. GrabCAD models)  
│   ├─ test_checks.py    # pytest scripts validating each rule-check  
│   └─ test_parser.py    # tests for importing models  
├─ .github/              
│   └─ workflows/        # CI configuration (e.g. pytest run)  
├─ docs/                 # Documentation (could use Sphinx)  
├─ setup.py or pyproject.toml  
├─ requirements.txt  
└─ README.md            
```  

Checklist:  
- [ ] **Parser Module:** Implement `parser.py` to read STEP/BREP, return `TopoDS_Shape`【60†L622-L630】【45†L352-L359】.  
- [ ] **Check Modules:** Write functions in `checks/` to detect each issue (using OCC topology explorers).  
- [ ] **Severity Scoring:** Define weights/rules to combine issues into overall severity rating.  
- [ ] **UI Layer:** Create a Streamlit app (`app.py`) that calls the parser and checks, and displays results (text summary plus 3D viewer via PyVista).  
- [ ] **ML Integration (optional):** Include model loading and inference using BRepNet to flag complex regions.  
- [ ] **Testing:** Add unit tests (pytest) for each rule and a small set of CAD samples【43†L271-L280】.  
- [ ] **CI/CD:** Configure GitHub Actions to run tests on push.  
- [ ] **Package Config:** Write `setup.py` or `pyproject.toml` for installation, include metadata and license.  
- [ ] **Documentation:** Document API and usage in `docs/`, at least a README describing workflow.  

See the [pythonocc-demos] examples for code patterns (e.g. face traversal, STEP import)【60†L622-L630】【45†L352-L359】. A minimal CI example is given in [python_project_example] (use `pip install -e .` then `pytest` as shown【43†L277-L284】).  

## Validation and Metrics  
We suggest benchmarking correctness via a labeled test set (e.g. a few dozen CAD models from GrabCAD or the GE Jet Engine Bracket dataset) where known issues are annotated. Metrics include **precision/recall** for each issue type (e.g. how often true gaps are detected vs false alarms). For instance, track the false-positive rate of the “thin-wall” check on thick-walled parts. Aim for high precision in the MVP (avoid false alarms) and then improve recall as needed. Standard metrics (precision, recall, F1-score) from ML literature can apply to the classification of each defect.  

Performance targets should be measured (e.g. time to analyze each test model). Optimize until simple parts run in ~<10s and medium parts in ~<30s on target hardware.  

## Severity-to-Action Mapping (Example)  
Finally, here is an example table mapping detected issue severity to user actions:

| **Symptom**              | **Severity** | **Action**                           |
|--------------------------|-------------:|--------------------------------------|
| Model not watertight     | Critical     | Repair geometry (stitch/close faces) |
| Overlapping faces/edges  | Critical     | Remove duplicates or Boolean fuse     |
| Thin wall (< threshold)  | High         | Thicken wall, or add support         |
| Small fillet (< thr)     | Medium       | Enlarge or remove fillet            |
| Tiny hole (< thr)        | Medium       | Remove hole or make larger          |
| Sharp small corner       | Low          | Optional: fillet or ignore           |

*Example mapping of issue severity to suggested fixes. Thresholds (thr) should be set empirically per part.*  

## References  
Key GitHub sources (as cited above): the official [pythonocc-core README]【10†L318-L324】, [occwl README]【12†L275-L282】, [BRepNet docs]【7†L305-L313】, [PyVista README]【29†L379-L388】, [Streamlit README]【31†L341-L347】, and FreeCAD’s FEM prep guide【20†L366-L373】【20†L387-L394】. Example code snippets are from the `pythonocc-demos` repository【60†L622-L630】【45†L352-L359】. More details on project structure are adapted from community examples【43†L277-L284】. 

