# Project Call Graph

How files call each other, organized by dependency layer (top → bottom).

---

## Dependency Layers

### Layer 7 — Scripts (entry points)
`scripts/run_*.py`, `scripts/prepare_*.py`, `scripts/evaluate_*.py`

Each script is a standalone entry point. Run scripts instantiate either a single-agent or build a LangGraph, then iterate over a dataset and write JSONL results.

```
run_bigcodebench.py       →  codegen_graph.build_codegen_graph()   (multi)
                          →  CodeGenAgent                           (single)
run_re_elicitation.py     →  re_elicitation_graph / REElicitationAgent
prepare_re_elicitation.py →  nice_loader + get_llm()
evaluate_re_elicitation.py → re_elicitation_metrics
```

---

### Layer 6 — Graphs
`src/systems/multi_agent/codegen_graph.py`, `re_elicitation_graph.py`, `re_elicitation_graph_v2.py`

Wire nodes together into a `StateGraph`. Each graph file imports all the nodes it uses, sets entry point, adds edges and conditional routes, and exposes `build_*_graph()` + `make_initial_state()`.

```
codegen_graph.py  →  nodes/planner, extractor, critic, coder, test_runner
                  →  schemas/graph_state.CodeGenGraphState
```

---

### Layer 5 — Multi-Agent Nodes
`src/systems/multi_agent/nodes/*.py`

One file per role. Each node reads from state dict, calls `get_structured_llm()`, and returns a partial state dict.

```
planner.py         →  client.get_structured_llm()  +  codegen_prompts.SYSTEM_CODEGEN
extractor.py       →  client.get_structured_llm()  +  re_elicitation_prompts
critic.py          →  client.get_llm()             +  prompts
coder.py           →  client.get_structured_llm()  +  codegen_prompts  +  schemas/codegen_schema.CodeSolution
test_runner.py     →  evaluation/codegen_metrics.run_single_test  +  schemas/codegen_schema.TestRunResult
re_sme_node.py     →  client.get_structured_llm()  +  re_elicitation_prompts
re_combiner_node.py → sentence_transformers (no LLM call)
```

---

### Layer 4 — Single-Agent Systems
`src/systems/single_agent/re_elicitation_agent.py`, `codegen_agent.py`

Simple wrappers: one `invoke()` call per task. Import the same prompts and schemas as the multi-agent nodes (fairness control).

```
codegen_agent.py         →  client.get_structured_llm()  +  codegen_prompts  +  schemas/codegen_schema
re_elicitation_agent.py  →  client.get_structured_llm()  +  re_elicitation_prompts  +  schemas/re_elicitation_schema
```

---

### Layer 3 — Evaluation & Datasets
`src/evaluation/`, `src/datasets/`

```
codegen_metrics.py        →  (stdlib only: subprocess, tempfile)
re_elicitation_metrics.py →  sentence_transformers
cost_tracker.py           →  (stdlib only)

nice_loader.py            →  (stdlib + pandas)
pure_loader.py            →  (stdlib + lxml/xml)
evalplus_loader.py        →  evalplus library
```

---

### Layer 2 — LLM Hub
`src/llm/client.py`

The single point of contact for all LLM calls. **14+ files import it.** Exposes:
- `get_llm()` — raw `ChatAnthropic` instance
- `get_structured_llm(schema)` — LLM with Pydantic-typed output
- `check_budget(llm_calls, total_tokens)` — raises `BudgetExceededError` if limits exceeded

```
client.py  →  langchain_anthropic.ChatAnthropic  (external only)
```

`src/llm/prompts/` — `codegen_prompts.py`, `re_elicitation_prompts.py` are pure string constants, imported by both single-agent and multi-agent nodes. No other project imports.

---

### Layer 1 — Schemas & Utils (leaf modules)
`src/schemas/codegen_schema.py`, `re_elicitation_schema.py`, `graph_state.py` — Pydantic models and TypedDicts. Imported by ~15 files but import nothing from the project.

`src/utils/json_utils.py` — `strip_markdown_fences()` used by `test_runner.py` and agents.

---

## Key Structural Rules

| Rule | Where it's enforced |
|---|---|
| All LLM calls go through `client.py` | Every node/agent imports `get_structured_llm` |
| Single and multi-agent share identical prompts | Both import from `src/llm/prompts/` |
| Budget is enforced at every node | Each node calls `check_budget()` before LLM call |
| Token/call counts accumulate across nodes | `Annotated[int, operator.add]` in `graph_state.py` |
| Context availability is logged | `context_trace` list in `CodeGenGraphState`, accumulated same way |

---

## Most-Imported Files

| File | Imported by |
|---|---|
| `src/llm/client.py` | All 10+ nodes, both single-agent classes, prepare scripts |
| `src/schemas/codegen_schema.py` | `coder.py`, `test_runner.py`, `codegen_agent.py`, run scripts |
| `src/schemas/graph_state.py` | All graph files |
| `src/llm/prompts/codegen_prompts.py` | `planner.py`, `coder.py`, `codegen_agent.py` |
| `src/evaluation/codegen_metrics.py` | `test_runner.py`, run scripts |
