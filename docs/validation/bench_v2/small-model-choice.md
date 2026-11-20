# SP2 small open model: survey and pick

**Status:** pick proposed, pending user approval of install + download
**Last verified:** 2026-11-20
**Feeds:** SP2 design E3; closes the survey half of `sp3-entry-gate` (SP1 spec D5 "Open")

## Requirements

1. About 3–4B instruct model, so it can be served on the VPS CPU (6 cores, 11 GB RAM,
   about 7 GB free; no GPU).
2. Unsloth GRPO support, for SP3.
3. An official or Unsloth GGUF.
4. A chat template with tool calling that `llama-server --jinja` accepts. The tool-calling part
   is **not yet verified** for any candidate: Task 10 Step 5 (smoke) checks it.

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

## Sources

- Unsloth notebooks: https://unsloth.ai/docs/get-started/unsloth-notebooks
- Unsloth model catalog: https://unsloth.ai/docs/get-started/unsloth-model-catalog
- Ministral 3 guide: https://unsloth.ai/docs/models/tutorials/ministral-3
- Qwen3.5 guide: https://unsloth.ai/docs/models/qwen3.5
- https://huggingface.co/unsloth/Qwen3-4B-Instruct-2507-GGUF
- https://huggingface.co/unsloth/Phi-4-mini-instruct-GGUF
- llama.cpp releases: https://github.com/ggml-org/llama.cpp/releases/tag/b12562
