# Workspace and local artifact map

**Canonical everyday workspace:** `C:\Users\suman\Desktop\Docs\Job\Projects\Mech\SimReady`  
**Last verified:** 2026-10-24  
**Scope:** local/generated assets needed to understand or reproduce SimReady experiments. Public setup and results remain in `README.md` and `docs/validation/`.

Large local assets are intentionally Git-ignored. Their presence here does not make a fresh clone reproducible by itself; use the linked recipes and do not publish private files.

## Model assets

| Task | Canonical local path | Git status | Provenance / identity | Recovery |
|---|---|---|---|---|
| BRepSAGE inference | `weights/brepnet.pt` plus adjacent JSON metrics | Tracked exceptions to `weights/*` | Small committed checkpoint and records | See `docs/impl/brepnet-implementation-notes.md` |
| Copilot chat QLoRA | `weights/qlora/` | Ignored | Qwen2.5-3B chat tool-call SFT; includes adapter, checkpoint-180, original ZIPs and traces | `docs/finetune_results.md`; not interchangeable with the GenCAD vision adapter |
| GenCAD vision QLoRA | `weights/gencad_qwen25vl3b_qlora/` | Ignored | Base `unsloth/Qwen2.5-VL-3B-Instruct-bnb-4bit`, LoRA r=16/alpha=16; copied 2026-10-24 from `SimReady-gencad/qwen_lora_adapter/qwen_lora_adapter/` | `notebooks/gencad_train_qwen.ipynb`; adapter SHA-256 below |

GenCAD adapter weights SHA-256:

```text
69d11308e63b77a65f2dc384a15b5fde5a7eb00f2e3321b297f62566513956e9
```

All seven extracted adapter files matched the original ZIP byte-for-byte on 2026-10-24. The ZIP remains at `SimReady-gencad/qwen_lora_adapter-20261007T064434Z-1-001.zip`; archiving it is not approved or completed.

## GenCAD evaluation caches

Canonical directory: `data/gencad/` (ignored). These paths are consumed by `scripts/gencad_common.py`.

| Path | Purpose / provenance | SHA-256 | Recovery |
|---|---|---|---|
| `gt_hundred.json` | 100 `hundred_subset` reference programs selected from the GenCAD-Code test split | `0588e037a6f29cbf84d2329f7e413b507fdd257963bc367e584b489dd1db9246` | `C:/mm/sr/python.exe scripts/gencad_reference.py` |
| `test-00000-of-00001.parquet` | Source test split downloaded from `CADCODER/GenCAD-Code` | `9eeadbf7da1022dc16a071de1e7512449c076e1aa22a8ffa7295d73527d6c9c5` | Downloaded automatically by `gencad_reference.py` from `TEST_PARQUET_URL` |
| `mecagent_metrics/best_iou.py` | MecAgent metric source used unchanged for published scoring | `0c4b6d2334d74d029ca93444feb1d50fb745a268c3b9fda9dbb14d7bae40e19e` | Retrieve from `MECAGENT_METRIC_URL`; record a fresh hash if upstream changes |
| `scaled_generated_steps/`, `reference_steps/`, `scaled_reference_steps/` | Generated checker-bridge intermediates | Regenerable; the copied source's `scaled_generated_steps/` was empty | `docs/validation/gencad_eval.md` gives script order; checker scales largest bbox side to 100 mm |

Published raw generations, scores, per-row analyses and 88 original-scale STEPs are tracked under `docs/validation/gencad/`; that directory is canonical over duplicate downloads.

## Other local inputs and evidence

| Path | Contents / disposition |
|---|---|
| `data/labels*/`, `data/parametric*/` | Versioned synthetic graphs/labels and generation inputs. Keep v1/v2 distinct; they support different historical records. |
| `tests/data/grabcad/`, `tests/data/real_eval/` | Local real-CAD inputs, not redistributed through Git. |
| `data/gen_eval/` | Raw generation evaluation records missing from a fresh clone. Evidence, not disposable cache. |
| `data/fea_docs/`, `data/fea_docs_index.json` | Full local FEA corpus/index. `data/fea_docs_index_seed.json` is the committed minimal fallback. |
| `Archive/gencad-colab-download-2026-10-07/` | Original GenCAD result download, already indexed. Do not duplicate or repack it. |
| `.superpowers/sdd/progress.md` | SP1 local resume ledger: paused at Task 2 review. |
| `.local/` | Private tooling notes and D Lab probe records; ignored and never published. Copied from the GenCAD worktree on 2026-10-24 with all four source files retained. |
| `.env`, `.claude/`, `docs/jobs/` | Private configuration/material. Not copied or inspected for this consolidation. |

## Workspace state and later gates

- `sp1-bench` remains paused and recoverable; do not merge it merely to simplify folders.
- `SimReady-gencad` remains registered. Original source assets were retained after all 14 destination hashes matched (7 adapter + 3 GenCAD cache + 4 private notes).
- No archive moves, deletions or worktree retirement occurred on 2026-10-24. Each requires separate approval.
- Fresh-clone README/demo remediation remains open; local caches must not be used to conceal missing public instructions.
