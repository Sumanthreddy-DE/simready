# BRepNet & UV-Net — Implementation Notes for SimReady

These notes extract only the parts relevant to building our B-Rep graph extractor and running BRepNet inference. Not a paper summary — an implementation reference.

**Papers:**
- Jayaraman et al., "BRepNet: A topological message passing system for solid models" (CVPR 2021)
- Jayaraman et al., "UV-Net: Learning from Boundary Representations" (CVPR 2021)

**Repos:**
- BRepNet: https://github.com/AutodeskAILab/BRepNet
- occwl: https://github.com/AutodeskAILab/occwl
- UV-Net: https://github.com/AutodeskAILab/UV-Net
- Fusion360 Gallery Dataset: https://github.com/AutodeskAILab/Fusion360GalleryDataset

**IMPORTANT:** Verify all details against the actual paper and repo code before implementing. These notes are based on architecture knowledge up to May 2025. The repos may have evolved.

---

## 1. The B-Rep Data Model

A B-Rep (Boundary Representation) solid is defined by its boundary surfaces. The topology has a hierarchy:

```
Solid
  └─ Shell (closed set of faces)
       └─ Face (bounded surface patch)
            └─ Loop/Wire (boundary of a face)
                 └─ Coedge (directed use of an edge within a loop)
                      └─ Edge (curve shared between faces)
                           └─ Vertex (point)
```

**For BRepNet, three entity types matter:**

| Entity | What it is | Count in typical bracket |
|--------|-----------|------------------------|
| **Face** | A bounded surface patch (plane, cylinder, cone, sphere, torus, bspline) | 20-100 |
| **Edge** | A curve shared between exactly 2 faces (in manifold solid) | 30-150 |
| **Coedge** | A directed use of an edge by a face. Each edge has 2 coedges. | 2x edge count |

**Why coedges?** An edge between Face A and Face B has two perspectives — "this edge as seen from Face A" and "this edge as seen from Face B." Coedges capture this directionality. It's the key insight that makes BRepNet topology-aware.

---

## 2. BRepNet Graph Structure

BRepNet constructs a graph where message passing flows through the B-Rep topology:

```
face ←→ coedge ←→ edge ←→ coedge ←→ face
```

**Adjacency representation:**

The model needs these adjacency mappings:
1. `face_to_coedges`: for each face, list of coedge indices belonging to it
2. `edge_to_coedges`: for each edge, the 2 coedge indices (one per adjacent face)
3. `coedge_to_face`: for each coedge, which face it belongs to
4. `coedge_to_edge`: for each coedge, which edge it uses
5. `coedge_to_mate`: for each coedge, the other coedge sharing the same edge (the "mate")

**How to build these from OCC:**

```python
# Pseudocode — verify against occwl/BRepNet repo

# 1. Enumerate all faces
faces = list(TopExp_Explorer(shape, TopAbs_FACE))

# 2. Enumerate all edges
edges = list(TopExp_Explorer(shape, TopAbs_EDGE))

# 3. Build edge-to-face map
edge_face_map = TopTools_IndexedDataMapOfShapeListOfShape()
topexp.MapShapesAndAncestors(shape, TopAbs_EDGE, TopAbs_FACE, edge_face_map)

# 4. For each edge with exactly 2 faces → create 2 coedges
# coedge_0: (edge_i, face_a) — edge as used by face_a
# coedge_1: (edge_i, face_b) — edge as used by face_b
# These are mates of each other

# 5. For each face → collect all coedges that reference it
# This gives face_to_coedges

# 6. Orientation: check if coedge direction matches edge direction
# In OCC: edge orientation within a wire/loop tells you this
```

**Note:** We already have `topexp.MapShapesAndAncestors` in `checks.py` for the non-manifold edge check. Same pattern, extended.

---

## 3. Input Features

### Face Features

| Feature | How to extract from OCC | Dimension |
|---------|------------------------|-----------|
| Surface type | `BRepAdaptor_Surface(face).GetType()` → enum (plane=0, cylinder=1, cone=2, sphere=3, torus=4, bspline=5, other=6) | 1 (int, one-hot encoded to 7) |
| Face area | `brepgprop.SurfaceProperties(face, props); props.Mass()` | 1 |
| Normal at centroid | Evaluate surface at UV midpoint, get normal vector | 3 (nx, ny, nz) |
| UV bounding box | `BRepTools.UVBounds(face)` → (umin, umax, vmin, vmax) | 4 |
| Face centroid | `props.CentreOfMass()` → (x, y, z) | 3 (optional) |

**Total face feature vector:** ~18 dims (after one-hot encoding surface type)

**BRepNet repo specifics:** Check `brepnet/data/` or `occwl/` for exact feature extraction code. The feature set may differ slightly between BRepNet and UV-Net.

### Edge Features

| Feature | How to extract from OCC | Dimension |
|---------|------------------------|-----------|
| Edge length | `BRepAdaptor_Curve(edge); GCPnts_AbscissaPoint.Length(curve)` or parameter range | 1 |
| Convexity | Dihedral angle between adjacent face normals at edge midpoint. Concave (<180), convex (>180), smooth (~180) | 1 (categorical: 3 classes) |
| Midpoint curvature | Evaluate curve curvature at midpoint | 1 |
| Edge midpoint | Evaluate curve at mid-parameter | 3 (optional) |

**Convexity calculation:**
```python
# Pseudocode
# For an edge shared by face_a and face_b:
# 1. Find midpoint of edge
# 2. Evaluate normal of face_a at closest point to edge midpoint
# 3. Evaluate normal of face_b at closest point to edge midpoint
# 4. Compute dihedral angle between normals
# 5. Classify: concave / convex / smooth based on angle
```

**Note:** This is similar to the sharp edges check we're adding. Reuse the dihedral angle computation.

### Coedge Features

| Feature | How to extract from OCC | Dimension |
|---------|------------------------|-----------|
| Orientation | Whether coedge direction matches edge natural direction. In OCC: `IsPartner()` or check `Orientation()` on the edge within the wire | 1 (binary) |
| Coedge index within face loop | Position of this coedge in the face's wire | 1 (optional) |

**Coedge features are minimal.** The coedge mainly carries structural/connectivity information, not geometric features.

---

## 4. Model Architecture (for inference)

**We don't need to reimplement the model — we load pre-trained weights.** But understanding the architecture helps debug issues.

**Kernel structure:**
- Each round of message passing: face embeddings → propagate through coedges → aggregate at edges → propagate back through coedges → update face embeddings
- Multiple rounds (typically 3-5) build up increasingly rich representations
- Final face embeddings: 128-dim vectors

**Output head (segmentation):**
- MLP on top of face embeddings
- Softmax over 24 face type classes
- For SimReady: we use the 128-dim embeddings (before the classification head) OR the softmax entropy

**Complexity score derivation:**
```python
# Option A: Softmax entropy (simple, interpretable)
softmax_scores = model.predict(graph)  # shape: (num_faces, 24)
entropy = -sum(p * log(p) for p in softmax_scores)  # per face
complexity = entropy / log(24)  # normalize to 0-1

# Option B: Embedding distance (more nuanced)
embeddings = model.get_embeddings(graph)  # shape: (num_faces, 128)
# Compute centroid of "simple" faces (planes, large cylinders)
# Distance from centroid = complexity
# Normalize to 0-1
```

**Option A recommended for Phase 2 demo.** Simpler, explainable, no reference dataset needed.

---

## 5. occwl Usage

occwl (OpenCASCADE Wrapper Library) provides a Python-friendly API over pythonocc, specifically designed for ML on B-Rep.

**Key classes (check repo for current API):**

```python
from occwl.solid import Solid
from occwl.face import Face
from occwl.edge import Edge

# Load STEP and wrap in occwl
solid = Solid.from_step(filepath)

# Iterate faces
for face in solid.faces():
    surface_type = face.surface_type()  # enum
    area = face.area()
    normal = face.normal_at_uv(u, v)
    
# Iterate edges
for edge in solid.edges():
    length = edge.length()
    
# Get adjacency
for face in solid.faces():
    for loop in face.loops():
        for coedge in loop.coedges():
            edge = coedge.edge()
            mate = coedge.mate()  # the other coedge sharing this edge
            partner_face = mate.face()
```

**If occwl doesn't install:**

Build minimal extractor using raw pythonocc:
```python
from OCC.Core.TopExp import TopExp_Explorer, topexp
from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_EDGE
from OCC.Core.BRepAdaptor import BRepAdaptor_Surface, BRepAdaptor_Curve
from OCC.Core.BRepGProp import brepgprop
from OCC.Core.GProp import GProp_GProps
from OCC.Core.TopTools import TopTools_IndexedDataMapOfShapeListOfShape

# We already use all of these in checks.py — extend, don't rewrite
```

**Estimated effort:**
- occwl path: 0.5-1 day (if it installs)
- Custom extractor path: 2-3 days (topology traversal + feature extraction + testing)

---

## 6. Fusion360 Gallery Dataset

**What it is:** ~8,000 CAD models from Autodesk Fusion360, with per-face segmentation labels (24 classes).

**Repo:** https://github.com/AutodeskAILab/Fusion360GalleryDataset

**What we need from it:**
1. STEP files for auto-labeling (run our rule engine → generate training labels)
2. Pre-processed B-Rep graphs if available (saves extraction time)
3. Face segmentation labels (for reference/comparison, not direct training)

**Subset strategy:**
- Start with 100-500 models
- Filter for bracket/mounting-like geometries if category labels exist
- The dataset has metadata — check for complexity/category fields

**Download considerations:**
- Full dataset is large (multiple GB)
- Check if there's a download script in the repo
- May need to use their API or S3 links
- Create `scripts/download_fusion360.py` for reproducibility

---

## 7. Implementation Checklist

Before writing any code, verify:

- [ ] **Check Python version compatibility** between BRepNet/occwl requirements and the simready conda environment. BRepNet and occwl are 2021 research repos that may require Python 3.7-3.9 and specific PyTorch versions. SimReady uses Python 3.10 via conda. Version conflicts may require a separate conda env for training, or pinning compatible package versions. This can block Tasks 2-3 if not resolved early.
- [ ] Read BRepNet paper sections 3 (Method) and 4 (Experiments)
- [ ] Read UV-Net paper section 3 (Method) — different but complementary approach
- [ ] Clone BRepNet repo, inspect `brepnet/data/` for exact input format
- [ ] Clone occwl repo, try `pip install` in simready conda env
- [ ] Check BRepNet pre-trained weight availability and download instructions
- [ ] Check Fusion360 Gallery download process and dataset structure
- [ ] Identify exact PyTorch version BRepNet requires (may need specific CUDA/CPU build)

After verification, implementation order:
1. Graph extractor (occwl or custom) — input format must match BRepNet exactly
2. BRepNet inference wrapper — load weights, run forward pass, extract embeddings
3. Complexity score derivation — softmax entropy (Option A)
4. Score fusion with rule engine — combined formula
5. Auto-label pipeline — batch process Fusion360 subset
6. Fine-tuning notebook — Colab-compatible

---

## 8. What to Watch Out For

**Graph size variation:** BRepNet expects padded/batched graphs. A bracket with 24 faces and a complex part with 200 faces need different handling. Check how the repo handles variable-size graphs.

**Feature normalization:** Face areas, edge lengths, etc. vary wildly between parts. BRepNet likely normalizes features relative to bounding box. Match the normalization scheme exactly.

**Coedge ordering:** The order of coedges in a face's loop matters for message passing. OCC wire traversal gives a specific ordering — preserve it.

**Non-manifold geometry:** BRepNet assumes manifold solids (each edge shared by exactly 2 faces). Our validator already catches non-manifold edges. If a shape has non-manifold edges, either skip ML scoring for that body or heal first.

**Surface type mapping:** OCC `GeomAbs_SurfaceType` enum values may not match BRepNet's expected encoding. Map explicitly:
```
OCC: GeomAbs_Plane=0, GeomAbs_Cylinder=1, GeomAbs_Cone=2, 
     GeomAbs_Sphere=3, GeomAbs_Torus=4, GeomAbs_BSplineSurface=...
BRepNet: verify mapping in their code
```

**Memory:** BRepNet in PyTorch on CPU is fine for inference on single parts. But batch processing 500 Fusion360 models for auto-labeling — watch memory. Process one at a time, save results, clear.
