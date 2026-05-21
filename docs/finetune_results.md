# Fine-Tune Eval Results

**Model:** Qwen2.5-3B-Instruct + QLoRA (r=16, alpha=32, all-linear)  
**Base for comparison:** Qwen2.5-3B-Instruct (unquantized, via API)  
**Paid-model reference:** meta/llama-3.3-70b-instruct (trace generator)  
**Fine-tune data:** ~5 000 synthetic tool-call traces (Day 15) + 50 gold traces (Day 12, held out)  
**Eval script:** `scripts/eval_finetune.py`

---

## How to read this file

Each `## Run:` block below is appended by `eval_finetune.py` after a model run.
Fill the **Gap Analysis** sections manually after comparing runs.

Run the eval:
```powershell
# Paid reference model (baseline ceiling)
$env:PYTHONPATH = "C:\Users\suman\Desktop\Docs\Job\Projects\Mech\SimReady"
C:\mm\sr\python.exe scripts/eval_finetune.py --model-tag "Llama-70B-ref" --model meta/llama-3.3-70b-instruct

# Base 3B (floor — what fine-tuning improves from)
# Run in Colab after Day 17, or via NIM if 3B is available on NIM
# python scripts/eval_finetune.py --model-tag "Qwen2.5-3B-base" --model ...

# Fine-tuned LoRA 3B (the target)
# Run in Colab Day 20 via local backend once adapter is saved
# python scripts/eval_finetune.py --model-tag "Qwen2.5-3B-LoRA" --backend local --adapter ...
```

---

## Metric definitions

| Metric | Definition |
|---|---|
| **tool_call_exact** | Model called exactly the expected set of tools (no extra, no missing) |
| **tool_call_partial** | Model called at least all expected tools (extra tools OK) |
| **tool_order_ok** | Tools appear in expected relative order (analyze_geometry before suggest_fixes) |
| **format_ok** | Output contains "Verdict:" header |
| **sections_ok** | Output contains both "Issues:" and "Fixes:" sections |
| **theme_hit_rate** | Fraction of expected answer themes found in output (gold traces only) |

---

## Summary comparison table
*(fill in after running all three model tags)*

| Metric | Llama-70B (ref) | Qwen2.5-3B (base) | Qwen2.5-3B+LoRA |
|---|---|---|---|
| Tool-call exact (gold) | — | — | — |
| Tool-call exact (val) | — | — | — |
| Tool-call partial (gold) | — | — | — |
| Tool order correct | — | — | — |
| Verdict format (gold) | — | — | — |
| Issues+Fixes sections | — | — | — |
| Theme hit rate (gold) | — | — | — |

---

## Gap Analysis

*(Fill in after eval runs are complete)*

### Where LoRA matches the paid model
- [ ] TBD after Day 18

### Where LoRA still falls short
- [ ] TBD after Day 18

### Failure mode taxonomy

Categorize failures found during eval into these buckets (add examples):

| # | Failure mode | Description | Example trace ID | Count |
|---|---|---|---|---|
| 1 | Missing tool call | Model answers without calling any tool | — | — |
| 2 | Wrong tool order | suggest_fixes called before analyze_geometry | — | — |
| 3 | Extra spurious tools | Model calls lookup_standard when not needed | — | — |
| 4 | Format drift | No Verdict/Issues/Fixes structure in output | — | — |
| 5 | Hallucinated numbers | Invents score or face count not from tool output | — | — |
| 6 | Incomplete answer | Tool calls correct but final text truncated/empty | — | — |
| 7 | Path confusion | Wrong step_path passed to analyze_geometry | — | — |
| 8 | Standards miss | lookup_standard skipped when explicitly expected | — | — |

### Lessons for next iteration
- [ ] More data needed? (if tool_call_exact < 0.70 on base 3B even after LoRA)
- [ ] Bigger base? (3B → 7B if recall gap persists)
- [ ] Different tool schema? (simplify arg names if path_confusion failure mode is high)
- [ ] More gold traces? (if theme_hit_rate < 0.60)
- [ ] Longer training? (check if val loss still declining at epoch 3)

---

## Individual run results

*(appended automatically by eval_finetune.py)*


## Run: Llama-70B-ref  —  2026-05-21 07:39 UTC

| Metric | Gold (16) | Val (-) |
|---|---|---|
| Tool-call exact match | 0.812 | — |
| Tool-call partial match | 0.812 | — |
| Tool order correct | 0.875 | — |
| Verdict format present | 0.938 | — |
| Issues+Fixes sections | 0.938 | — |
| Theme hit rate (gold only) | 0.769 | — |
