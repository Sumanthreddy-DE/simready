import hashlib
import json
import math
from pathlib import Path

import pytest

def _large_graph_result_worker(queue):
    graph = {
        "node_features": [
            {"face_index": index, "payload": str(index) * 1000}
            for index in range(256)
        ]
    }
    queue.put({"kind": "ok", "graph": graph})


from scripts.inspect_real_clean import (
    inspect_open_topology,
    inspect_self_intersection,
    inspect_sliver_class,
    inspect_one,
    inspect_one_in_subprocess,
    iter_step_files,
    run_spawn_worker,
    main,
    source_sha256,
)


def test_iter_step_files_deduplicates_case_insensitive_step_paths(tmp_path):
    (tmp_path / "a.STEP").write_bytes(b"a")
    (tmp_path / "b.stp").write_bytes(b"b")
    (tmp_path / "c.Step").write_bytes(b"c")
    (tmp_path / "not-step.txt").write_bytes(b"no")

    paths = list(iter_step_files(tmp_path))

    assert [path.name for path in paths] == ["a.STEP", "b.stp", "c.Step"]
    assert source_sha256(paths[0]) == hashlib.sha256(b"a").hexdigest()


def test_smoke_box_has_explicit_completed_absence_evidence():
    record = inspect_one(Path("tests/data/smoke_box.step"), "a" * 64)

    assert record["status"] == "ok"
    assert record["source_sha256"] == "a" * 64
    assert record["face_count"] == 6
    assert record["graph_extraction"]["status"] == "ok"
    assert record["inspection"] == {
        "open_shell": "absent",
        "sliver_face": "absent",
        "self_intersection": "absent",
    }
    assert record["boundary_edge_count"] == 0
    assert record["nonmanifold_edge_count"] == 0
    assert record["solid_count"] == 1
    assert record["evaluated_solid_count"] == 1
    assert record["completion"] == {
        "OpenBoundaries": True,
        "PotentialGaps": True,
        "SelfIntersection": True,
        "ThinSolid": True,
    }


def test_six_face_zero_solid_shell_is_open_even_when_topology_has_no_boundary():
    from OCC.Core.TopoDS import TopoDS_Shell, topods
    from simready.parser import parse_geometry
    from simready.validator import validate_step_file

    validation = validate_step_file("tests/data/smoke_box.step")
    shell = TopoDS_Shell()
    from OCC.Core.BRep import BRep_Builder

    builder = BRep_Builder()
    builder.MakeShell(shell)
    for _index, face in __import__("simready.occ_utils", fromlist=["iter_faces"]).iter_faces(validation.shape):
        builder.Add(shell, face)
    summary = parse_geometry(shell)
    assert (summary.face_count, summary.solid_count) == (6, 0)

    evidence = inspect_open_topology(shell, summary)

    assert evidence["result"] == "present"
    assert evidence["completion"] == {"OpenBoundaries": True, "PotentialGaps": True}
    assert evidence["open_edge_count"] == 0
    assert any(finding["check"] == "OpenBoundaries" for finding in evidence["findings"])


def test_brep_valid_solid_with_extra_face_is_nonmanifold_and_closed_box_is_control():
    from OCC.Core.BRep import BRep_Builder
    from OCC.Core.BRepCheck import BRepCheck_Analyzer
    from OCC.Core.TopoDS import TopoDS_Compound
    from simready.occ_utils import iter_faces
    from simready.parser import parse_geometry
    from simready.validator import validate_step_file

    validation = validate_step_file("tests/data/smoke_box.step")
    solid = validation.shape
    closed = inspect_open_topology(solid, parse_geometry(solid))
    assert closed["result"] == "absent"
    assert closed["boundary_edge_count"] == 0
    assert closed["nonmanifold_edge_count"] == 0

    compound = TopoDS_Compound()
    builder = BRep_Builder()
    builder.MakeCompound(compound)
    builder.Add(compound, solid)
    builder.Add(compound, iter_faces(solid)[0][1])
    assert BRepCheck_Analyzer(compound).IsValid()

    evidence = inspect_open_topology(compound, parse_geometry(compound))

    assert evidence["result"] == "present"
    assert evidence["boundary_edge_count"] == 0
    assert evidence["nonmanifold_edge_count"] == 4
    assert evidence["findings"] == [] or all(f["check"] == "OpenBoundaries" for f in evidence["findings"])
    assert any("non-manifold" in finding["detail"] for finding in evidence["findings"])


def test_open_topology_unavailable_or_error_is_unknown(monkeypatch):
    monkeypatch.setattr("scripts.inspect_real_clean._build_open_topology", lambda _shape: (_ for _ in ()).throw(RuntimeError("map failed")))
    from simready.parser import parse_geometry
    from simready.validator import validate_step_file

    evidence = inspect_open_topology(object(), parse_geometry(validate_step_file("tests/data/smoke_box.step").shape))

    assert evidence["result"] == "unknown"
    assert evidence["completion"] == {"OpenBoundaries": False, "PotentialGaps": False}
    assert evidence["findings"] == []
    assert "map failed" in evidence["error"]


def test_open_topology_incomplete_gap_check_cannot_prove_absent(monkeypatch):
    monkeypatch.setattr(
        "scripts.inspect_real_clean._build_open_topology",
        lambda _shape: (0, 0, [{"check": "OpenBoundaries", "detail": "none"}]),
    )
    monkeypatch.setattr("scripts.inspect_real_clean._find_potential_gaps", lambda _shape: (_ for _ in ()).throw(RuntimeError("gaps failed")))
    from simready.parser import parse_geometry
    from simready.validator import validate_step_file

    evidence = inspect_open_topology(object(), parse_geometry(validate_step_file("tests/data/smoke_box.step").shape))

    assert evidence["result"] == "unknown"
    assert evidence["completion"] == {"OpenBoundaries": True, "PotentialGaps": False}
    assert "gaps failed" in evidence["error"]


def test_self_intersection_unavailable_or_error_is_unknown(monkeypatch):
    monkeypatch.setattr("scripts.inspect_real_clean.BOPAlgo_ArgumentAnalyzer", None)

    evidence = inspect_self_intersection(object(), 6)

    assert evidence["result"] == "unknown"
    assert evidence["completion"] == {"SelfIntersection": False}
    assert evidence["findings"] == []
    assert "unavailable" in evidence["error"]


def test_self_intersection_analyzer_error_does_not_look_absent(monkeypatch):
    class BrokenAnalyzer:
        def __init__(self):
            raise RuntimeError("analyzer unavailable")

    monkeypatch.setattr("scripts.inspect_real_clean.BOPAlgo_ArgumentAnalyzer", BrokenAnalyzer)
    monkeypatch.setattr("scripts.inspect_real_clean._count_freeform_faces", lambda _shape: 0)

    evidence = inspect_self_intersection(object(), 6)

    assert evidence["result"] == "unknown"
    assert evidence["completion"] == {"SelfIntersection": False}
    assert "analyzer unavailable" in evidence["error"]


def test_sliver_class_detects_generator_shape_and_absent_on_normal_box():
    from scripts.generate_degraded_steps import make_sliver_face
    from simready.parser import parse_geometry
    from simready.validator import validate_step_file

    box = validate_step_file("tests/data/smoke_box.step").shape
    negative = inspect_sliver_class(box, parse_geometry(box))
    assert negative["result"] == "absent"
    assert negative["completed"] is True
    assert negative["solid_count"] == 1
    assert negative["evaluated_solid_count"] == 1
    assert negative["evidence_scope"] == "class_specific_thin_solid_not_general_sliver_certificate"
    assert negative["findings"] == []

    sliver = make_sliver_face(box)
    positive = inspect_sliver_class(sliver, parse_geometry(sliver))
    assert positive["result"] == "present"
    assert positive["completed"] is True
    assert [finding["check"] for finding in positive["findings"]] == ["ThinSolid"]


@pytest.mark.parametrize("failure", ["bbox_failed", "void", "degenerate", "missing_traversal"])
def test_sliver_class_is_unknown_when_any_declared_solid_is_not_evaluated(monkeypatch, failure):
    import sys
    import types
    from types import SimpleNamespace

    class FakeBox:
        def IsVoid(self):
            return failure == "void"

        def Get(self):
            return (0, 0, 0, 1, 1, 1) if failure == "degenerate" else (0, 0, 0, 2, 2, 2)

    class BrokenBrepBndLib:
        @staticmethod
        def Add(_solid, _box):
            if failure == "bbox_failed":
                raise RuntimeError("bbox failed")

    bnd_module = types.ModuleType("OCC.Core.Bnd")
    bnd_module.Bnd_Box = FakeBox
    bndlib_module = types.ModuleType("OCC.Core.BRepBndLib")
    bndlib_module.brepbndlib = BrokenBrepBndLib
    monkeypatch.setitem(sys.modules, "OCC.Core.Bnd", bnd_module)
    monkeypatch.setitem(sys.modules, "OCC.Core.BRepBndLib", bndlib_module)
    if failure == "missing_traversal":
        class EmptyExplorer:
            def __init__(self, *_args):
                pass

            def More(self):
                return False

        monkeypatch.setattr("simready.checks.TopExp_Explorer", EmptyExplorer)

    evidence = inspect_sliver_class(object(), SimpleNamespace(solid_count=1))

    assert evidence["result"] == "unknown"
    assert evidence["completed"] is False
    assert evidence["completion"]["ThinSolid"] is False
    assert evidence["solid_count"] == 1
    assert evidence["evaluated_solid_count"] == 0
    assert evidence["errors"]


def test_sliver_class_reports_successful_count_when_a_later_solid_fails(monkeypatch):
    import sys
    import types
    from types import SimpleNamespace

    class FakeBox:
        def IsVoid(self):
            return False

        def Get(self):
            return (0, 0, 0, 2, 2, 2)

    class PartiallyBrokenBrepBndLib:
        calls = 0

        @classmethod
        def Add(cls, _solid, _box):
            cls.calls += 1
            if cls.calls == 2:
                raise RuntimeError("second bbox failed")

    class TwoSolidExplorer:
        def __init__(self, *_args):
            self.remaining = 2

        def More(self):
            return self.remaining > 0

        def Current(self):
            return object()

        def Next(self):
            self.remaining -= 1

    bnd_module = types.ModuleType("OCC.Core.Bnd")
    bnd_module.Bnd_Box = FakeBox
    bndlib_module = types.ModuleType("OCC.Core.BRepBndLib")
    bndlib_module.brepbndlib = PartiallyBrokenBrepBndLib
    monkeypatch.setitem(sys.modules, "OCC.Core.Bnd", bnd_module)
    monkeypatch.setitem(sys.modules, "OCC.Core.BRepBndLib", bndlib_module)
    import OCC.Core.TopExp
    monkeypatch.setattr(OCC.Core.TopExp, "TopExp_Explorer", TwoSolidExplorer)
    monkeypatch.setattr("scripts.inspect_real_clean._thin_solid_solid_count", lambda _shape: 2)

    evidence = inspect_sliver_class(object(), SimpleNamespace(solid_count=2))

    assert evidence["result"] == "unknown"
    assert evidence["solid_count"] == 2
    assert evidence["evaluated_solid_count"] == 1
    assert "second bbox failed" in evidence["error"]


def test_sliver_class_exception_is_unknown_not_completed(monkeypatch):
    monkeypatch.setattr("scripts.inspect_real_clean._thin_solid_solid_count", lambda *_args: (_ for _ in ()).throw(RuntimeError("bbox failed")))

    from types import SimpleNamespace

    evidence = inspect_sliver_class(object(), SimpleNamespace(solid_count=1))

    assert evidence["result"] == "unknown"
    assert evidence["completed"] is False
    assert evidence["findings"] == []
    assert "bbox failed" in evidence["error"]


def test_thin_solid_error_does_not_report_completed(monkeypatch):
    monkeypatch.setattr("scripts.inspect_real_clean._thin_solid_solid_count", lambda *_args: (_ for _ in ()).throw(RuntimeError("bbox failed")))

    record = inspect_one(Path("tests/data/smoke_box.step"), "a" * 64)

    assert record["completion"]["ThinSolid"] is False
    assert record["inspection"]["sliver_face"] == "unknown"
    assert any("ThinSolid" in error and "bbox failed" in error for error in record["errors"])


def test_inspection_cli_writes_evidence_not_training_manifest(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    source = input_dir / "Reviewed Part.STEP"
    source.write_bytes(Path("tests/data/smoke_box.step").read_bytes())
    output = tmp_path / "evidence" / "inspection.json"

    assert main(["--input", str(input_dir), "--output", str(output)]) == 0

    evidence = json.loads(output.read_text(encoding="utf-8"))
    assert evidence["schema_version"] == "real_clean_inspection_v1"
    assert "experiment" not in evidence
    assert "parts" not in evidence
    assert len(evidence["records"]) == 1
    record = evidence["records"][0]
    assert record["source_id"] == "Reviewed Part"
    assert record["source_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert record["inspection"]["sliver_face"] == "absent"
    assert evidence["sliver_evidence"] == "class_specific_thin_solid_not_general_sliver_certificate"
    assert record["completion"]["OpenBoundaries"] is True
    assert record["completion"]["SelfIntersection"] is True
    assert not (output.parent / "manifest.json").exists()


@pytest.mark.parametrize("timeout", [0, -1, math.nan, math.inf, -math.inf, "bad", None])
def test_inspection_rejects_nonpositive_nonfinite_or_invalid_timeout(timeout):
    with pytest.raises(ValueError, match="timeout"):
        inspect_one_in_subprocess(Path("unused.step"), timeout_s=timeout)


@pytest.mark.parametrize("timeout", [0, -1, math.nan, math.inf, -math.inf])
def test_inspection_cli_rejects_invalid_timeout_before_reading_input(tmp_path, timeout):
    with pytest.raises(SystemExit) as error:
        main(["--input", str(tmp_path / "absent"), "--output", str(tmp_path / "out.json"), "--timeout", str(timeout)])
    assert error.value.code == 2


def test_inspection_timeout_is_explicit_and_all_results_unknown(tmp_path, monkeypatch):
    class FakeProcess:
        def __init__(self):
            self.exitcode = None
            self.terminated = False

        def start(self):
            return None

        def join(self, _timeout):
            self.exitcode = -15 if self.terminated else None

        def is_alive(self):
            return not self.terminated

        def terminate(self):
            self.terminated = True

        def kill(self):
            self.terminated = True

    process = FakeProcess()

    class FakeQueue:
        def __init__(self):
            self.closed = False
            self.feeder_joined = False

        def close(self):
            self.closed = True

        def join_thread(self):
            self.feeder_joined = True

    queue = FakeQueue()

    class FakeContext:
        def Queue(self):
            return queue

        def Process(self, **_kwargs):
            return process

    monkeypatch.setattr("scripts.inspect_real_clean.mp.get_context", lambda _name: FakeContext())
    step = tmp_path / "part.step"
    step.write_bytes(b"step")

    record = inspect_one_in_subprocess(step, timeout_s=0.01)

    assert record["status"] == "timeout"
    assert record["process"]["terminated"] is True
    assert set(record["inspection"].values()) == {"unknown"}
    assert set(record["completion"].values()) == {False}
    assert any("0.01" in error for error in record["errors"])
    assert queue.closed and queue.feeder_joined


def test_spawn_worker_receives_large_graph_before_joining_child():
    outcome = run_spawn_worker(_large_graph_result_worker, (), timeout_s=10)

    assert outcome["kind"] == "result"
    assert outcome["process"] == {"exit_code": 0, "terminated": False}
    assert outcome["payload"]["graph"]["node_features"][255]["face_index"] == 255


def test_spawn_worker_cleans_queue_after_success(monkeypatch):
    class FakeProcess:
        exitcode = 0

        def start(self):
            return None

        def join(self, _timeout):
            return None

        def is_alive(self):
            return False

    class FakeQueue:
        def __init__(self):
            self.closed = False
            self.feeder_joined = False

        def get(self, timeout):
            return {"answer": 42}

        def close(self):
            self.closed = True

        def join_thread(self):
            self.feeder_joined = True

    queue = FakeQueue()

    class FakeContext:
        def Queue(self):
            return queue

        def Process(self, **_kwargs):
            return FakeProcess()

    monkeypatch.setattr("scripts.inspect_real_clean.mp.get_context", lambda _name: FakeContext())

    outcome = run_spawn_worker(lambda: None, (), 1)

    assert outcome == {"kind": "result", "payload": {"answer": 42}, "process": {"exit_code": 0, "terminated": False}}
    assert queue.closed and queue.feeder_joined


def test_spawn_worker_preserves_queue_read_error(monkeypatch):
    class FakeProcess:
        exitcode = 0

        def start(self):
            return None

        def join(self, _timeout):
            return None

        def is_alive(self):
            return False

    class FakeQueue:
        def get(self, timeout):
            raise TimeoutError("queue read timed out")

        def close(self):
            return None

        def join_thread(self):
            return None

    class FakeContext:
        def Queue(self):
            return FakeQueue()

        def Process(self, **_kwargs):
            return FakeProcess()

    monkeypatch.setattr("scripts.inspect_real_clean.mp.get_context", lambda _name: FakeContext())

    outcome = run_spawn_worker(lambda: None, (), 1)

    assert outcome["kind"] == "process_error"
    assert "no_result_from_worker" in outcome["error"]
    assert "queue read timed out" in outcome["error"]


def test_inspection_reports_process_error_when_child_survives_terminate_and_kill(tmp_path, monkeypatch):
    class FakeProcess:
        exitcode = None

        def start(self):
            return None

        def join(self, _timeout):
            return None

        def is_alive(self):
            return True

        def terminate(self):
            return None

        def kill(self):
            return None

    class FakeQueue:
        def __init__(self):
            self.closed = False
            self.feeder_joined = False

        def close(self):
            self.closed = True

        def join_thread(self):
            self.feeder_joined = True

    queue = FakeQueue()

    class FakeContext:
        def Queue(self):
            return queue

        def Process(self, **_kwargs):
            return FakeProcess()

    monkeypatch.setattr("scripts.inspect_real_clean.mp.get_context", lambda _name: FakeContext())
    step = tmp_path / "part.step"
    step.write_bytes(b"step")

    record = inspect_one_in_subprocess(step, timeout_s=1)

    assert record["status"] == "process_error"
    assert record["process"]["alive_after_kill"] is True
    assert any("remains alive" in error for error in record["errors"])
    assert queue.closed and queue.feeder_joined
