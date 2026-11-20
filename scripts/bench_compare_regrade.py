"""Compare a run log with its regrade, attempt by attempt.

Compares ``passed``, ``partial``, ``failure_class``, ``fingerprint`` and each
check's status; any other field (for example ``features``, added in SP2) is
ignored. Used for the SP1 no-drift check (2026-11-20: 0 differences on both
official logs under checker 1e70789).

    python scripts/bench_compare_regrade.py ORIGINAL.jsonl.gz REGRADED.jsonl

Negative control: a log against itself must print ``differing 0``.
"""
import gzip
import json
import sys

FIELDS = ("passed", "partial", "failure_class", "fingerprint")


def load(path):
    op = gzip.open if path.endswith(".gz") else open
    with op(path, "rt", encoding="utf-8") as f:
        rows = [json.loads(line) for line in f]
    return rows[0], {r["attempt_id"]: r for r in rows[1:] if r.get("record") == "attempt"}


def statuses(r):
    rep = r.get("check_report") or {}
    return [(c.get("type"), c.get("status")) for c in rep.get("checks", [])]


def main(orig_path, new_path):
    h0, a = load(orig_path)
    h1, b = load(new_path)
    print(f"header checker {h0.get('checker_version')} -> {h1.get('checker_version')}; regrade_of={h1.get('regrade_of')}")
    assert set(a) == set(b), f"attempt ids differ: {len(a)} vs {len(b)}"
    diffs = 0
    graded = sum(1 for r in b.values() if r.get("checker_version") == h1.get("checker_version") and r.get("spec") is not None)
    for aid in sorted(a):
        x, y = a[aid], b[aid]
        d = {k: (x.get(k), y.get(k)) for k in FIELDS if x.get(k) != y.get(k)}
        if statuses(x) != statuses(y):
            d["check_statuses"] = (statuses(x), statuses(y))
        if d:
            diffs += 1
            print(aid, d)
    passed0 = sum(bool(r.get("passed")) for r in a.values() if r.get("in_vocab"))
    passed1 = sum(bool(r.get("passed")) for r in b.values() if r.get("in_vocab"))
    print(f"attempts {len(a)}, regraded-with-spec {graded}, differing {diffs}, in-vocab passed {passed0} -> {passed1}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
