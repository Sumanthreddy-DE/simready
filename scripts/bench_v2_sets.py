"""Write the SP2 pre-registered concept-id sets (design: Pre-registered results)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from simready.bench.concepts import CONCEPTS_V1, CONCEPTS_V2, load_concepts, v2_reference_ids  # noqa: E402

OUT = ROOT / "docs" / "validation" / "bench_v2" / "sets"
v1 = load_concepts(CONCEPTS_V1)
v2 = load_concepts(CONCEPTS_V2)
v2_vocab = v2_reference_ids()
SETS = {
    "regression": sorted(c.concept_id for c in v1 if c.in_vocab),                       # result 1
    "design": sorted(c.concept_id for c in v1 if not c.in_vocab and c.concept_id in v2_vocab),  # result 2
    "heldout": sorted(c.concept_id for c in v2),                                          # result 2
    "dsl_vs_code": sorted(c.concept_id for c in v1 + v2 if c.concept_id in v2_vocab),    # result 3
    "c044_c045_c046": ["c044", "c045", "c046"],                                           # result 3, apart
}
EXPECTED = {"regression": 37, "design": 10, "heldout": 15, "dsl_vs_code": 62, "c044_c045_c046": 3}
assert {k: len(v) for k, v in SETS.items()} == EXPECTED, {k: len(v) for k, v in SETS.items()}
OUT.mkdir(parents=True, exist_ok=True)
for name, ids in SETS.items():
    (OUT / f"{name}.txt").write_text("\n".join(ids) + "\n", encoding="utf-8")
print({k: len(v) for k, v in SETS.items()})
