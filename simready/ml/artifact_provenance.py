"""Deterministic hashes for the exact experiment artifacts."""

from __future__ import annotations

import hashlib
from pathlib import Path


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact_hashes(dataset_dir: Path, entries: list[dict]) -> dict[str, str]:
    hashes = {"manifest.json": file_sha256(dataset_dir / "manifest.json")}
    for entry in entries:
        stem = entry["stem"]
        for suffix in ("graph.json", "labels.json"):
            name = f"{stem}.{suffix}"
            hashes[name] = file_sha256(dataset_dir / name)
    return hashes


def verify_artifact_hashes(dataset_dir: Path, expected: dict[str, str]) -> None:
    for name, expected_hash in expected.items():
        actual = file_sha256(dataset_dir / name)
        if actual != expected_hash:
            raise ValueError(f"dataset provenance mismatch: {dataset_dir / name}")


def real_declared_artifacts(dataset_dir: Path) -> dict[str, str]:
    """Read prepared per-artifact seals without opening graph/label payloads."""
    import json

    entries = json.loads((dataset_dir / "manifest.json").read_text(encoding="utf-8"))
    hashes = {"manifest.json": file_sha256(dataset_dir / "manifest.json")}
    for entry in entries:
        for kind in ("graph", "labels"):
            seal = entry.get(f"{kind}_sha256")
            if not isinstance(seal, str) or len(seal) != 64:
                raise ValueError(f"prepared manifest missing {kind}_sha256 for {entry.get('source_id')}")
            hashes[f"{entry['stem']}.{kind}.json"] = seal
    return hashes


def real_source_provenance(dataset_dir: Path) -> dict[str, str]:
    """Map every prepared graph to the reviewed source STEP hash."""
    import json

    entries = json.loads((dataset_dir / "manifest.json").read_text(encoding="utf-8"))
    return {entry["source_id"]: entry["source_sha256"] for entry in entries}


def recorded_artifacts(dataset_dir: Path, source_ids: set[str] | None = None) -> dict[str, str]:
    """Hash all graph/label artifacts, or only the requested recorded subset."""
    import json

    entries = json.loads((dataset_dir / "manifest.json").read_text(encoding="utf-8"))
    samples = [entry for entry in entries if entry.get("status") == "ok"]
    if source_ids is not None:
        samples = [entry for entry in samples if entry.get("source_id", entry.get("stem")) in source_ids]
        if {entry.get("source_id", entry.get("stem")) for entry in samples} != source_ids:
            raise ValueError("recorded dataset IDs do not match the manifest")
    return artifact_hashes(dataset_dir, samples)
