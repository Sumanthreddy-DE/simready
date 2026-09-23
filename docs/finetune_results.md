# Fine-Tune Eval Results

**Model:** Qwen2.5-3B-Instruct + QLoRA (r=16, alpha=32, q/k/v/o/gate/up/down proj)  
**Base for comparison:** Qwen2.5-3B-Instruct q8_0 GGUF — served through the *same* local
llama-server stack as the LoRA column, so the comparison isolates the fine-tune  
**Paid-model reference:** meta/llama-3.3-70b-instruct (trace generator)  
**Fine-tune data:** 951 train / 39 val synthetic tool-call traces (Llama-70B teacher runs through the real agent loop, `scripts/synth_tool_traces.py`) + 50 gold traces (Day 12, held out)  
**Eval script:** `scripts/eval_finetune.py`

---

## How to read this file

Each `## Run:` block below is appended by `eval_finetune.py` after a model run.
Fill the **Gap Analysis** sections manually after comparing runs.

Run the eval (recipe as of 2026-07-20 — GGUF + local llama-server; the agent loop and
OCC tools run locally, only token generation is served):
```powershell
# One-time setup:
#  1. Notebook section 9b exports the merged LoRA as q8_0 GGUF to MyDrive/simready/
#     — download it (~3.2 GB) to weights/gguf/ (gitignored).
#  2. Base column: download qwen2.5-3b-instruct-q8_0.gguf from
#     https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF to the same folder.
#  3. llama-server: prebuilt Windows zip from https://github.com/ggml-org/llama.cpp/releases
#     (llama-*-bin-win-*-x64.zip, no install). --jinja uses the GGUF's embedded chat
#     template, which is what makes Qwen tool-calling work.

# Terminal 1 — serve (swap the -m path for base vs LoRA):
llama-server -m weights/gguf/<model>.gguf --jinja -c 8192 --port 8080

# Terminal 2 — eval (sr env):
$env:PYTHONPATH = "C:\Users\suman\Desktop\Docs\Job\Projects\Mech\SimReady"
$env:OPENAI_BASE_URL = "http://localhost:8080/v1"
$env:OPENAI_API_KEY = "local"
C:\mm\sr\python.exe scripts/eval_finetune.py --dataset gold --model-tag "Qwen2.5-3B-LoRA-q8"
C:\mm\sr\python.exe scripts/eval_finetune.py --dataset gold --model-tag "Qwen2.5-3B-base-q8"   # after swapping -m

# Paid reference model (baseline ceiling, NIM):
C:\mm\sr\python.exe scripts/eval_finetune.py --model-tag "Llama-70B-ref" --model meta/llama-3.3-70b-instruct
```
Caveats: q8_0 quantization deviates slightly from the fp16 training result — acceptable
because both columns go through the identical quant + server; CPU generation is slow
(expect roughly 1–2 h for the 50-trace gold set per column — leave it running).

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

## Training run (recovered 2026-09-23 from `checkpoint-180/trainer_state.json`)

Colab, Unsloth, base `unsloth/qwen2.5-3b-instruct-unsloth-bnb-4bit`, LoRA r=16 / alpha=32 /
dropout 0, all attn + MLP projections. 3 epochs, 180 steps, batch 2. Final adapter ==
checkpoint-180 adapter (byte-identical). Local copy: `weights/qlora/` (gitignored).

| Step | Epoch | Train loss | Val loss |
|---|---|---|---|
| 50 | 0.84 | 0.697 | — |
| 100 | 1.67 | 0.160 | — |
| 150 | 2.50 | 0.107 | — |
| 180 | 3.00 | — | 0.150 |

Caveats: `eval_steps=200 > max_steps=180`, so val loss exists only at the end: no val
curve, no overfitting check. Low loss on teacher-generated traces means the student imitates
the teacher's format; it says nothing about tool-use quality. That is the gold-set eval below.

## Summary comparison table
*(Llama-70B ref = gold n=50, 2026-05-24. Base/LoRA columns filled after Day 17/18.)*

| Metric | Llama-70B (ref) | Qwen2.5-3B (base) | Qwen2.5-3B+LoRA |
|---|---|---|---|
| Tool-call exact (gold) | 0.760 | — | — |
| Tool-call exact (val) | — | — | — |
| Tool-call partial (gold) | 0.920 | — | — |
| Tool order correct | 0.780 | — | — |
| Verdict format (gold) | 0.780 | — | — |
| Issues+Fixes sections | 0.780 | — | — |
| Theme hit rate (gold) | 0.678 | — | — |

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


## Run: Llama-70B-ref-full  —  2026-05-24 07:49 UTC

| Metric | Gold (50) | Val (-) |
|---|---|---|
| Tool-call exact match | 0.760 | — |
| Tool-call partial match | 0.920 | — |
| Tool order correct | 0.780 | — |
| Verdict format present | 0.780 | — |
| Issues+Fixes sections | 0.780 | — |
| Theme hit rate (gold only) | 0.678 | — |
