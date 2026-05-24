# Serving the fine-tuned copilot (day 20)

How to run the QLoRA-fine-tuned Qwen2.5-3B behind an OpenAI-compatible endpoint
so the **existing** agent, eval script, and Streamlit UI use it unchanged.

> **Design note.** `CopilotAgent` and `scripts/eval_finetune.py` are 100%
> `base_url`-driven (env `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `OPENAI_MODEL`).
> We deliberately do **not** ship an in-process transformers backend. Instead we
> serve the model with vLLM's OpenAI server and point `OPENAI_BASE_URL` at it.
> Zero new agent code; the fine-tuned model drops in behind the same interface
> as GPT-4o / NIM. See `docs/exec-plans/path-c-4week.md` day 20 for the rationale.

---

## Why this works without changing the agent

The fine-tune data (`scripts/prep_finetune_dataset.py`) formats tool calls as
Qwen2.5's native Hermes blocks:

```
<tool_call>
{"name": "analyze_geometry", "arguments": {"step_path": "..."}}
</tool_call>
```

vLLM's `--tool-call-parser hermes` converts those text blocks back into the
OpenAI structured `tool_calls` field that the agent loop reads
(`msg.tool_calls`). So the round-trip is:

```
agent sends OpenAI messages
  → vLLM applies Qwen2.5 chat template → <tool_call> text
  → model emits <tool_call> text
  → hermes parser → OpenAI tool_calls
  → agent dispatches the tool   (unchanged)
```

---

## Prerequisites

- A CUDA GPU. **This will not run on the Windows CPU dev box** — use the Colab
  T4 that trained the adapter, or any GPU host. (An in-process 3B on CPU would
  be unusably slow too, so a GPU is required either way.)
- `pip install vllm` (Linux/CUDA). On Colab it's `!pip install vllm`.
- The LoRA adapter from day 17 at `MyDrive/simready/lora_adapter/` (download or
  mount it; below it's `$ADAPTER`).

---

## Serve base + LoRA together (one command)

vLLM exposes the base model **and** the adapter as two model names from a
single server, so you can run eval run 2 (base) and run 3 (LoRA) against the
same endpoint:

```bash
export ADAPTER=/path/to/lora_adapter

vllm serve Qwen/Qwen2.5-3B-Instruct \
  --enable-auto-tool-choice \
  --tool-call-parser hermes \
  --enable-lora \
  --lora-modules simready=$ADAPTER \
  --max-model-len 2048 \
  --port 8000
```

Model names now available at `http://localhost:8000/v1`:

| Model name (`OPENAI_MODEL`) | What it is |
|---|---|
| `Qwen/Qwen2.5-3B-Instruct` | base 3B (eval **run 2**) |
| `simready`                 | base + LoRA adapter (eval **run 3**, live demo) |

`--max-model-len 2048` matches the notebook's `MAX_SEQ_LEN`; the dataset was
capped to 2048-token traces in `prep_finetune_dataset.py --max-tokens 2048`.

---

## Recommended eval topology: remote GPU serves, local box evals

`eval_finetune.py` drives the **real** SimReady pipeline (pythonocc on STEP
files). The Windows dev box already has pythonocc + every STEP fixture
(including the gitignored grabcad files that a fresh clone lacks — so it covers
more gold traces). So keep eval local and make only **inference** remote:

1. On the GPU host (Colab), serve as above, then expose port 8000:
   ```bash
   # Colab: cloudflared is the least-friction tunnel
   cloudflared tunnel --url http://localhost:8000
   # → prints https://<random>.trycloudflare.com
   ```
2. On the Windows dev box (sr env, has pythonocc + STEPs):
   ```powershell
   $env:PYTHONPATH = "C:\Users\suman\Desktop\Docs\Job\Projects\Mech\SimReady"
   $env:OPENAI_BASE_URL = "https://<random>.trycloudflare.com/v1"
   $env:OPENAI_API_KEY  = "EMPTY"   # vLLM ignores it; OpenAI client needs non-empty

   # Run 2 — base 3B
   python scripts/eval_finetune.py --dataset gold `
     --model "Qwen/Qwen2.5-3B-Instruct" --model-tag "base-3B"

   # Run 3 — LoRA 3B
   python scripts/eval_finetune.py --dataset gold `
     --model "simready" --model-tag "LoRA-3B"
   ```

Both runs append a timestamped table to `docs/finetune_results.md`, next to the
existing `Llama-70B-ref-full` reference-ceiling row.

> If the tunnel is rate-limited or flaky, reuse the NIM pacing flags:
> `--request-delay 1 --max-retries 6 --initial-backoff 4`.

(Alternative — everything in Colab — needs pythonocc-core installed there plus
the STEP fixtures uploaded. More friction; not recommended.)

---

## Live demo: point Streamlit at the fine-tuned model

The Streamlit sidebar has a **Backend** selector (`ui/copilot_app.py`):

- **Environment default** — uses `.env` (NIM / OpenAI / whatever).
- **Local fine-tuned (vLLM)** — base_url `http://localhost:8000/v1`, model
  `simready`. Use when vLLM is serving on the same host.
- **Custom** — paste the tunnel URL + model name to demo the Colab-served LoRA
  from your laptop.

No restart needed — the next chat turn rebuilds the agent against the selected
endpoint.

---

## Reading the numbers honestly

The day-24 reference ceiling (`Llama-70B-ref-full`, n=50) scored
`format_ok 0.780` — i.e. even a 70B model misses the `Verdict:` contract ~22% of
the time. **That is a prompt/regex brittleness, not a model-size problem.** When
the 3B base/LoRA `format_ok` looks low, compare against 0.78, not 1.0, before
concluding the fine-tune "failed on formatting." The honest story (narrative C,
`project_path-c-decisions.md`) is the data→QLoRA→eval *loop*, not 3B-beats-70B.
