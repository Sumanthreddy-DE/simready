"""Child entry point for the build123d arm. argv: code_path out_step_path. Exit 0 = STEP written.

Resource limits are set here, before the answer runs, not through
subprocess preexec_fn: the parent calls run_code from runner worker threads,
where preexec_fn can deadlock the child before exec.
"""

import resource
import sys

_GIB = 1024 ** 3
LIMITS = {
    resource.RLIMIT_CPU: (60, 60),
    resource.RLIMIT_AS: (4 * _GIB, 4 * _GIB),
    resource.RLIMIT_FSIZE: (64 * 1024 ** 2, 64 * 1024 ** 2),
    resource.RLIMIT_CORE: (0, 0),
}


def main() -> int:
    for which, value in LIMITS.items():
        resource.setrlimit(which, value)
    code_path, out_path = sys.argv[1], sys.argv[2]
    with open(code_path, encoding="utf-8") as f:
        code = f.read()
    namespace = {"__name__": "answer"}
    try:
        exec(compile(code, "answer.py", "exec"), namespace)
    except BaseException as exc:  # noqa: BLE001 — every failure is the answer's
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 3
    part = namespace.get("part")
    if part is None:
        print("the code did not assign a solid to 'part'", file=sys.stderr)
        return 2
    import build123d

    if not isinstance(part, build123d.Shape):
        print(f"'part' is a {type(part).__name__}, not a build123d shape", file=sys.stderr)
        return 2
    try:
        ok = build123d.export_step(part, out_path)
    except BaseException as exc:  # noqa: BLE001
        print(f"STEP export failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 3
    return 0 if ok is not False else 3


if __name__ == "__main__":
    raise SystemExit(main())
