# SimReady Design (STEP-to-Simulation-Readiness Checker)

## Executive Summary  
**SimReady** is a Python tool (MVP demo) for analyzing CAD B-Rep models (STEP files) and reporting whether they are “simulation-ready” for structural FEA. The tool will ingest a STEP file, perform rule-based checks (e.g. water-tightness, degenerate faces, thin features, intersections, duplicate geometry, etc.), and output a JSON report with severity-coded issues and (when possible) suggested fixes.  A minimal Streamlit/PyVista UI will visualize key issues on the model. Optionally, a B-Rep neural net (e.g. BRepNet) can be used as a secondary classifier to highlight suspect regions (e.g. thin walls) by learning from labeled CAD data【44†L305-L313】【24†L369-L377】. Performance goals are under ~10 s for simple parts and under 30 s for medium complexity, enabling near-interactive use.  We will validate against a curated dataset (e.g. GrabCAD models) and define clear metrics (issue detection rate, false positives, etc.) to measure correctness. The code will be open-source with clear license (likely MIT/Apache compatible), continuous integration/tests, and a straightforward GitHub repo layout.  

 

## “Simulation-Ready” Definition (Structural FEA)  
A **simulation-ready** CAD model typically means:  
- **Watertight Solid**: All parts are closed, manifold solids (no open edges/gaps), so a volumetric mesh can be generated. No intersecting or overlapping faces. Each body should be a single `TopoDS_Solid`. For example, using PythonOCC one can check `shape.IsNull()` after `reader.TransferRoots()` to detect unreadable or null geometry【39†L447-L455】【53†L1197-L1204】.  
- **Single Body (or clear assembly)**: Either a single solid or a well-defined assembly (no unintended “floating” faces). All parts should have volume; “shells” or `TopoDS_Shell` with zero thickness are invalid for solid FEA.  
- **No Degenerate/Zero-Area Faces**: Faces must have positive area. Degenerate faces (e.g. from bad STEP) should be flagged and removed.  
- **Minimum Feature Size**: No features (e.g. walls, holes) thinner than practical limits of the target mesh or FEA solver. For example, if two faces are parallel and extremely close, report a “thin region” (FEM tips require thickening).  
- **No Self-Intersection or Non-Manifolds**: The solid must be geometrically valid (OpenCASCADE’s global checking can detect some issues via `ws.Model().Check()`【39†L383-L392】).  
- **Consistent Orientation**: Face normals and shell orientations must be consistent (OCC ensures this on valid solids). Flipped faces can confuse FEA (flag if found).  
- **Simplicity for Meshing**: Fillets, chamfers, small unnecessary details may be optional checks (flag “minor” with suggestion to simplify). However MVP focus is geometric validity.

In summary, **Simulation-Ready** = *(Closed, non-self-intersecting solid, free of ill-shaped faces or tiny features, suitable for volumetric meshing)*.  We will encode this as explicit checks below.  

## Severity Taxonomy and Suggested Fixes  
We categorize issues by severity:  
- **Critical (Crash)**: File cannot be read, no valid solid extracted, or global geometry failure. *Fix:* Reject input, ask user to repair the STEP file externally.  
- **Major (Must-Fix)**: Non-manifold edges, open gaps, self-intersections, overlapping solids, duplicate faces, zero-volume geometry. *Fix:* Use OCC tools (e.g. sew/shape healing) or advise deletion of offending faces. Suggest using PythonOCC’s shape healing or a commercial tool if needed.  
- **Minor (Warning)**: Very small features (thin walls below tolerance), sliver faces, cosmetic defects (tiny edges), unresolved fillets/chamfers. *Fix:* Provide suggestions like “increase wall thickness to > X”, “merge sliver faces”, or “remove unused sketches.” These don’t block simulation but can cause poor mesh.  
- **Info (Note)**: Model ready or completed; suggestions for optimization (e.g. “fillet on edge 12 not needed for analysis”).  

For each issue, the report will include a human-readable *message*, severity, affected B-Rep entity ID (if applicable), and a *suggested fix*. E.g.:
```
{"type":"ThinWall","severity":"Major","face_id":23,
 "detail":"Wall thickness 0.2 mm < 1 mm threshold",
 "suggestion":"Consider thickening or removing this feature."}
```  

## Rule-Based Checks (Pseudo-code)  
We prioritize checks by impact: file validity first, then fundamental topology, then geometric quality:

1. **Load and Basic Check** (Critical)  
   ```python
   reader = STEPControl_Reader()
   status = reader.ReadFile(filepath)
   if status != IFSelect_RetDone:
       report.add_issue(type="LoadError", severity="Critical",
           message=f"STEP file read failed (status={status})")
   reader.TransferRoots()
   shape = reader.Shape()
   if shape.IsNull():
       report.add_issue(type="NullShape", severity="Critical",
           message="Transferred shape is null (invalid STEP)")
   ```
   *Based on yapCAD’s validator【39†L435-L443】【39†L447-L455】.* If critical, abort further checks.  

2. **Topology Check** (Major)  
   ```python
   topo = TopologyExplorer(shape)
   if topo.solids() is empty:
       report.add_issue(type="NoSolid", severity="Major",
           message="No solid bodies found in model")
   # Check for non-manifold or disconnected edges:
   if not TopologyUtils().IsSolid(shape):
       report.add_issue(type="NonManifold", severity="Major",
           message="Shape has non-manifold edges or open boundaries")
   ```
   (You can use OCC.Extend.TopologyUtils or check `face.Orientation()` consistency.)  

3. **Geometric Integrity** (Major)  
   - **Degenerate Faces/Edges**: Iterate all faces/edges via `TopologyExplorer`. If `face.Area() <= 0` or `edge.Length() == 0`, flag.  
   - **Intersection**: (Hard) Check if any pair of faces intersect improperly (OCC has `BRepAlgoAPI_Section` or global check; skip brute). If OCC’s global check flags intersections, report.  
   - **Duplicate/Overlapping Geometry**: If two faces are coincident (similar geometry) or two solids overlap, flag possible duplicate. 

4. **Feature Size Checks** (Major/Minor)  
   ```python
   for face in topo.faces():
       if is_parallel_to_another(face, other_face):
           thickness = distance_between(face, other_face)
           if thickness < THIN_THRESHOLD:
               report.add_issue(type="ThinRegion", severity="Major",
                   message=f"Region with thickness {thickness:.2f} mm < threshold",
                   suggestion="Increase wall thickness")
   # Example: use bounding-box or oriented distance to compute thickness.
   ```
   *(No direct code example found; would implement via geometric queries using OCC’s distance tools.)*  

5. **Small Features / Slivers** (Minor)  
   - Edges shorter than a tolerance (e.g. <0.01 mm).  
   - Faces with area below threshold (suspected tiny cutout or sliver).  
   - Zero-thickness shells (TopoDS_Shell not in a solid).  

6. **Orientation / Normals** (Minor)  
   Check for reversed faces: use `BRepCheck_Analyzer` or just pool all face normals and ensure consistency. 

7. **Additional Rules (Future)**  
   - Wall thickness uniformity, undercut detection for mold tools, etc.  
   - Assembly issues: part interferences (if assembly is allowed).  

   
## ML Integration (BRepNet or Similar)  
For an MVP, ML is optional but could be used to **highlight suspect regions**. For example, **BRepNet**【44†L305-L313】 can consume the B-Rep graph (faces, edges, coedges) and output per-face labels. We could train it on a dataset of CAD parts labeled “OK” vs “has thin wall” or “has small faces.” In practice, BRepNet’s strength is capturing topology via graph convolutions【44†L305-L313】.  We might integrate BRepNet by:  
- Precomputing OCC geometry features and topology (per face/edge) into the format BRepNet expects (see [44], `pipeline.quickstart` usage).  
- Loading a pre-trained BRepNet to *predict* quality issues on new parts. For MVP, we could simply run one forward pass: 
  ```python
  brep_model = load_brepnet_model(...)
  face_labels = brep_model.predict(shape_data)
  for face_id,label in face_labels:
      if label == "bad_region":
          report.add_issue(type="ML_Highlight", severity="Minor",
                           message="ML: Face likely problematic (thin/sliver)")
  ```
BRepNet’s main limitation is the need for a trained model and heavy inference (GPU recommended). For an MVP we might skip full training and instead run a *pre-packaged* BRepNet demonstration (the [AutodeskAILab/BRepNet](https://github.com/AutodeskAILab/BRepNet) repo shows setup and usage)【44†L305-L313】【44†L331-L338】. If not, we can treat ML hints as future work. Alternatively, a point-cloud approach (as in AAGNet) uses sampled points on faces【53†L1213-L1222】, but that’s more work. The report will note “ML-based suggestion” as low-priority feature.  

## Visualization / UI  
We will provide a simple web UI (Streamlit) embedding 3D visualization via PyVista. The [pyvista/streamlit-pyvista](https://github.com/pyvista/streamlit-pyvista) example shows how to display a PyVista `Plotter` in Streamlit using `ipywidgets` and `components.html`【24†L335-L343】【24†L369-L377】. For example:  
```python
import pyvista as pv
from pyvista.jupyter import pv_pythreejs
# ... in Streamlit app:
pv.start_xvfb()  # for headless plotting
p = pv.Plotter()
p.add_mesh(pv.wrap(occ_shape), color='tan')
# Mark a bad face (if any) in red:
p.add_mesh(bad_face_mesh, color='red')
components.html(embed_pyvista_plot(p), height=500)
```
This is similar to the code in [24] which loads an example mesh and renders it. We will adapt that to our STEP model (converted to triangular mesh for display).  The UI will allow uploading a STEP, showing the mesh, and overlaying highlights (e.g. red faces or arrows) for each issue【24†L369-L377】.  PyVista is chosen for its ease with meshes and Streamlit integration【24†L335-L343】【24†L369-L377】.  

## Validation Plan and Metrics  
- **Test Cases**: Collect a benchmark set of CAD models with known issues. We can use **GrabCAD** (open CAD models) as a source. For example, the [FlynnHHH/grabcad](https://github.com/FlynnHHH/grabcad) tool can scrape GrabCAD models programmatically【49†L248-L257】. We will grab a variety: simple solids (cube, cylinder), models with known thin walls (e.g. turbine blade geometries), assemblies, and corrupted examples.  
- **Metrics**: For each test model, record whether SimReady finds *all* known issues (true positives) and counts false positives. We can report recall/precision for each rule type. For MVP, at least ensure no critical issues are missed. Another metric: **processing time** vs. model size to meet our <10–30 s goal.  
- **Comparison**: Optionally compare to a commercial CAD check (if any trial) or ask a CAE engineer to rate. But at minimum, ensure consistency with user expectations (we will refine rules based on feedback).  
- **Regression Tests**: Include unit tests (in `tests/`) using PythonOCC on simple shapes (e.g. a box with a deliberate hole) to ensure checks trigger correctly.  

## GitHub Repo Layout and Licensing  
A suggested layout (following examples like OCCWL and BRepNet):  
```
SimReady/  
├── docs/             # Documentation (mkdocs or README)
├── src/simready/     # Source code: modules for parsing, checks, ML, etc.
│   ├── parser.py     # STEP reading (using pythonocc/occwl)
│   ├── checks.py     # Rule-check functions
│   ├── ml_utils.py   # BRepNet integration (optional)
│   ├── ui.py         # Streamlit UI components
│   └── ... 
├── examples/         # Sample STEP files and expected JSON outputs
├── tests/            # Unit tests (pytest)
├── environment.yml   # Conda environment (like BRepNet uses)
├── Dockerfile        # (optional) for reproducible environment
├── .github/workflows/CI.yml  # CI pipeline
├── LICENSE           # e.g. MIT or Apache 2.0
├── README.md         # Project overview and instructions
└── report_schema.json # (optional) JSON schema for output
```
We should choose a permissive license (e.g. MIT) so companies can reuse.  The `environment.yml` will pin OpenCASCADE/pythonocc versions (e.g. `pythonocc-core`) and PyVista, Streamlit, PyTorch (for BRepNet). For reference, OCCWL uses `conda install occwl`【6†L275-L281】, but we might install `pythonocc-core` directly.  

CI will run basic tests (geometry files in `tests/` checked). For example, running `pyocc-validate.py` (like yapCAD’s script【39†L435-L443】【39†L447-L455】) could be one test.  

## API and Report Format  
**CLI/API**: At minimum, a command-line entry point: 
```
simready analyze input.stp --output report.json
```
or a REST endpoint if extended. The output JSON schema (one example):  
```json
{
  "file": "example.step",
  "status": "NeedsCleaning", 
  "issues": [
    {"type":"NullShape","severity":"Critical","message":"Transferred shape is null"},
    {"type":"ThinRegion","severity":"Major","face_id":12,"detail":"Thickness 0.2 mm","suggestion":"Thicken wall"},
    {"type":"SliverFace","severity":"Minor","face_id":7,"detail":"Area 0.0001 mm^2","suggestion":"Remove tiny face"}
  ],
  "fixed_geometry": "fixed_geometry.step"
}
```
This schema (or similar) will be defined in `report_schema.json`.  If automatic fixes are implemented (e.g. removing degenerate faces), the tool can offer a corrected STEP for download.  For now MVP, outputting the JSON report and *optionally* a marked-up mesh (via the UI) suffices.

 

## Candidate Repositories (Comparison)  

| Category      | Repository (stars)                 | Key Points                                               |
|---------------|-------------------------------------|----------------------------------------------------------|
| **STEP Parsers**  | [tpaviot/pythonocc](https://github.com/tpaviot/pythonocc-core) (1700★)  | Official PythonOCC (bindings to OpenCASCADE). Demonstrated use of `STEPControl_Reader().ReadFile()` and `TransferRoots()` to load STEP【53†L1197-L1204】【39†L435-L443】. LGPL-3.0 license. Heavyweight but full-featured. |
|               | [AutodeskAILab/occwl](https://github.com/AutodeskAILab/occwl) (84★)      | High-level wrapper over pythonocc. Example: `Solid.make_box(10,10,10)`【6†L291-L300】. Simplifies common tasks, has viewer integration. Good for MVP. BSD-3-Clause license. |
|               | [CadQuery](https://github.com/CadQuery/cadquery) (1000★)                | Parametric CAD library on OCC. Can import/export STEP, but primary use is modeling. Could use `cadquery.importers.importStep()`. MIT-licensed. |
| **ML (B-Rep)**  | [AutodeskAILab/BRepNet](https://github.com/AutodeskAILab/BRepNet) (220★) | BRepNet implementation for face/edge classification【44†L305-L313】. Requires PyTorch/GPU. Provides scripts to convert STEP to graph data. License: CC BY-NC-SA 4.0 (non-commercial). |
|               | *No notable forks* (searched)      | (No major open forks; BRepNet is research code.)         |
|               | —Potential alt: MeshCNN, PointNet†| MeshCNN (on triangle meshes), PointNet (on point clouds). Not B-Rep native; would require conversion.|
| **Rule-Check Examples** | [rdevaul/yapCAD:pyocc-validate.py](https://github.com/rdevaul/yapCAD/blob/main/pyocc-validate.py) (24★) | Script that reads STEP and uses OCC global `model.Check()` to list entity failures【39†L375-L383】【39†L447-L455】. Example of STEP validation pipeline. |
|               | [whjdark/AAGNet](https://github.com/whjdark/AAGNet) (15★)        | Geometry ML pipeline. Shows reading STEP and extracting per-face point grids (using OCC)【53†L1197-L1204】. Not explicitly rule-checks but good example of STEP parsing and face sampling. |
|               | *No direct “check CAD” repos*     | (Most geometry-cleanup tools are commercial.)             |

‡CADQuery and alternative ML repos are **not strictly needed**, but are noted for comparison. 

## Prioritized Task List

| Task                                     | Description                                                 | Priority | Est. Effort |
|------------------------------------------|-------------------------------------------------------------|----------|-------------|
| *Core: STEP Parsing*                     | Load STEP file with OCC, handle errors (see step_reader)【53†L1197-L1204】. Validate basic shape existence. | High     | 1–2 days    |
| *Core: Topology Checks*                  | Use TopologyExplorer to detect no-solids, open shells, non-manifolds. | High     | 1–2 days    |
| *Core: Geometric Rules*                  | Implement checks for degenerate faces, duplicate faces, thin-walls, etc. (pseudo-code above). | High     | 3–4 days    |
| *Reporting Framework*                    | Define JSON schema, integrate rule results into report with severity and suggestions. | High     | 1–2 days    |
| *UI/Visualization*                       | Build Streamlit app and PyVista renderer, show 3D model and highlight issues【24†L369-L377】. | Medium   | 3–4 days    |
| *ML Integration*                         | (Optional) Hook up BRepNet to run inference on the model. Prepare step->graph pipeline. | Low      | 4–6 days    |
| *Validation Dataset*                     | Collect sample STEP models (use GrabCAD scraper【49†L248-L257】), curate test cases, write tests. | High     | 2–3 days    |
| *CI/Testing*                             | Set up GitHub Actions, unit tests for each rule (e.g. known shapes). | Medium   | 2 days      |
| *Documentation & Packaging*              | Write README, usage examples, prepare Conda env file.       | Medium   | 2 days      |

**Timeline (approx.):** A rough 2–3 week sprint. First week: core parsing and rule engine; second week: report output and simple UI; third week: polishing, tests, and optional ML. Tasks in *italics* are higher priority.  

## References  
- OCC Python example: loading STEP with `STEPControl_Reader` and `TransferRoots()` to get a solid【53†L1197-L1204】【28†L622-L630】.  
- OCC validation: yapCAD’s validator uses global shape checks and `shape.IsNull()` to detect invalid models【39†L435-L443】【39†L447-L455】.  
- OCC wrapper library (OCCWL) provides higher-level API (e.g. `Solid.make_box()`)【6†L291-L300】.  
- BRepNet paper and code: specialized for B-Rep graph learning【44†L305-L313】【44†L331-L338】.  
- Streamlit + PyVista embedding example: uses `pyvista.Plotter` with `convert_plotter` and `components.html`【24†L335-L343】【24†L369-L377】.  
- GrabCAD model scraping (FlynnHHH/grabcad) to build dataset【49†L248-L257】.  

## Questions for Follow-Up  
- **Scope & Use Case:** Are we targeting a specific FEA solver or workflow (e.g. integration with open-source meshers like Gmsh), or a general check? Should SimReady be a standalone CLI, web demo, or library?  
- **Definition Clarification:** What conventions or feature sizes are expected (e.g. what thickness threshold is “too thin” for your use-case)? Do you have examples of “simulation-ready” vs. “not-ready” models as ground truth?  
- **Data and Privacy:** Will we work with any proprietary CAD data, or only open models? Are there licensing constraints on models we test?  
- **MVP vs Production:** Beyond the demo, is there interest in extending SimReady to a full startup product? This may affect choices (e.g. using a commercial-grade GUI toolkit vs. Streamlit, or adding robust error handling).  
- **Validation:** How will “correctness” be measured? Are there specific success criteria (e.g. no FEA failures on cleaned models), and how will you judge false positives/negatives in our report?  

