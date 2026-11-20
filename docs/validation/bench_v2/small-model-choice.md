# SP2 small open model: survey and pick

**Status:** picked and served (user approved install + download 2026-11-20)
**Last verified:** 2026-11-20
**Feeds:** SP2 design E3; closes the survey half of `sp3-entry-gate` (SP1 spec D5 "Open")

## Requirements

1. About 3–4B instruct model, so it can be served on the VPS CPU (6 cores, 11 GB RAM,
   about 7 GB free; no GPU).
2. Unsloth GRPO support, for SP3.
3. An official or Unsloth GGUF.
4. A chat template with tool calling that `llama-server --jinja` accepts. Verified for the pick
   only (smoke below).

## Candidates

| Model | GRPO (Unsloth) | GGUF Q4_K_M | Notes |
|---|---|---|---|
| **Qwen3-4B-Instruct-2507** | Qwen3 (4B) Advanced GRPO LoRA notebook | `unsloth/Qwen3-4B-Instruct-2507-GGUF`, 2.50 GB | Non-thinking variant: no reasoning tokens, which matters on CPU. Qwen tool-call template. |
| Ministral-3-3B-Instruct-2512 | Ministral-3B-Instruct GRPO notebook | `unsloth/Ministral-3-3B-Instruct-2512-GGUF`, 2.15 GB | Native function calling; smallest. |
| Qwen3.5-4B | Qwen3.5 (4B) Vision GRPO notebook | `unsloth/Qwen3.5-4B-GGUF`, 2.74 GB | Thinking/non-thinking toggle; the GRPO notebook is the vision one. |
| Llama 3.2 3B Instruct | Llama 3.2 (3B) Advanced GRPO LoRA (Kaggle) | Unsloth GGUF | Older (2024); weaker tool calling. |
| Phi-4-mini-instruct (3.8B) | not confirmed in the notebook list | `unsloth/Phi-4-mini-instruct-GGUF` | GRPO support not confirmed. |

GGUF sizes are from the Hugging Face API, read 2026-11-20.

## Pick

**Qwen3-4B-Instruct-2507, Q4_K_M (2.50 GB).**
- It has a text GRPO notebook, the path SP3 needs.
- It is non-thinking, so CPU time goes to the answer and not to reasoning tokens.
- It is the most common base in published Unsloth GRPO examples.

**Fallback:** Ministral-3-3B-Instruct-2512, if the Qwen tool calls do not parse under
`llama-server --jinja` at smoke time.

**Server:** llama.cpp release `b12562` (2026-11-20), CPU build
`llama-b12562-bin-ubuntu-x64.tar.gz`, 23 MB.

## Smoke and timing (2026-11-20, VPS CPU, 6 threads, one worker)

- Server: `llama-server` b12562, `--jinja -c 8192`, alias `qwen3-4b-instruct-2507`. It started with
  `n_slots = 4` sharing one 8192-token KV cache, so the timing runs used `--workers 1`.
- `python -m simready.bench smoke`: the configured id is listed; one `build_part` tool call parsed
  (`finish_reason: tool_calls`, 99 completion tokens, 44.4 s).
- Ten `concepts_v1` prompts, k = 1, per arm. These are smoke runs, not results:

| Arm | Wall for 10 calls | Median s/call | Max s/call | Passed |
|---|---|---|---|---|
| dsl-v1 | 495 s | 30.7 | 113.4 | 0/10 |
| dsl-v2 | 548 s | 50.3 | 91.4 | 1/10 |
| build123d | 647 s | 61.9 | 86.9 | 0/10 |

- Projected single-shot matrix for this model, at the mean wall time per call: 975 calls per arm
  (750 on `concepts_v1`, 225 on `concepts_v2`). dsl-v1 is 13.4 h, dsl-v2 14.8 h and build123d
  17.5 h, so **45.8 h** in total, before repair runs.

## Sources

- Unsloth notebooks: https://unsloth.ai/docs/get-started/unsloth-notebooks
- Unsloth model catalog: https://unsloth.ai/docs/get-started/unsloth-model-catalog
- Ministral 3 guide: https://unsloth.ai/docs/models/tutorials/ministral-3
- Qwen3.5 guide: https://unsloth.ai/docs/models/qwen3.5
- https://huggingface.co/unsloth/Qwen3-4B-Instruct-2507-GGUF
- https://huggingface.co/unsloth/Phi-4-mini-instruct-GGUF
- llama.cpp releases: https://github.com/ggml-org/llama.cpp/releases/tag/b12562
