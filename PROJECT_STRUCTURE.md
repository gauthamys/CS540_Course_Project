# Project Structure & Contribution Guide

## Quick Overview

This project has **two independent pipelines**:

1. **RE Elicitation** — Given a use-case description, generate software requirements
2. **Code Generation** — Given a problem description, generate working code

Each pipeline has:
- **Single-agent** version (one LLM call per task)
- **Multi-agent V1** version (planner → extractor → critic pipeline)
- **Multi-agent V2** version (V1 + extra node, e.g., SME for RE, test-critic for codegen)

---

## Directory Structure

```
CS540_Project/
│
├── scripts/                                  # Entry points — one script per system
│   ├── 1_prepare/                           # Data preparation
│   │   ├── prepare_codegen_data.py          # Download EvalPlus/MBPP
│   │   ├── prepare_re_nice_dataset.py       # Prepare NICE → use_case + GT requirements
│   │   └── prepare_re_pure_dataset.py       # Prepare pure dataset
│   │
│   ├── 2_run/                               # Run systems
│   │   ├── run_re_elicitation.py            # RE: --system single|multi|v2 --dataset nice|pure --pilot
│   │   ├── run_codegen_single_agent.py      # CodeGen: single agent on pilot
│   │   ├── run_codegen_multi_agent_v1.py    # CodeGen: multi-agent V1 on pilot
│   │   ├── run_codegen_multi_agent_v2.py    # CodeGen: multi-agent V2 on pilot
│   │   ├── run_codegen_full_dataset.py      # CodeGen: full HumanEval+ dataset
│   │   └── run_codegen_mbpp.py              # CodeGen: MBPP dataset
│   │
│   ├── 3_evaluate/                          # Evaluation
│   │   ├── evaluate_re_elicitation.py       # Compute RE metrics (coverage, precision, F1)
│   │   └── evaluate_codegen.py              # Compute CodeGen metrics (pass@1)
│   │
│   └── 4_report/
│       └── plot_results.py
│
├── src/
│   ├── datasets/                            # Data loaders
│   │   ├── nice_loader.py                   # Load NICE requirement dataset
│   │   ├── pure_loader.py                   # Load pure (no LLM-synthesized) data
│   │   ├── evalplus_loader.py               # Load EvalPlus code generation problems
│   │   ├── secreq_loader.py                 # Load SecReq security requirements (optional)
│   │   └── splitter.py                      # Train/test split logic
│   │
│   ├── llm/
│   │   ├── client.py                        # LLM client (Claude or Ollama)
│   │   └── prompts/
│   │       ├── re_elicitation_prompts.py    # RE elicitation prompt templates
│   │       ├── codegen_prompts.py           # CodeGen prompt templates
│   │       └── re_prompts.py                # RE classification prompts (old pipeline)
│   │
│   ├── schemas/                             # Pydantic data models
│   │   ├── re_elicitation_schema.py         # RE: GeneratedRequirement, PlannerOutput, SMEAdvisory
│   │   ├── codegen_schema.py                # CodeGen: CodeSolution
│   │   ├── re_schema.py                     # RE classification: REPrediction (old)
│   │   └── graph_state.py                   # Multi-agent state shapes
│   │
│   ├── evaluation/
│   │   ├── re_elicitation_metrics.py        # RE metrics (coverage, precision, semantic F1)
│   │   ├── codegen_metrics.py               # CodeGen metrics (pass@1, test results)
│   │   ├── re_metrics.py                    # RE classification metrics (old)
│   │   └── cost_tracker.py                  # LLM token/cost tracking
│   │
│   ├── systems/
│   │   ├── single_agent/
│   │   │   ├── re_elicitation_agent.py      # RE: one LLM call → requirements
│   │   │   ├── codegen_agent.py             # CodeGen: one LLM call → code
│   │   │   └── re_agent.py                  # RE classification agent (old)
│   │   │
│   │   └── multi_agent/
│   │       ├── codegen_graph.py             # CodeGen V1: planner→extractor→critic→coder→test
│   │       ├── codegen_graph_v2.py          # CodeGen V2: + test_critic node
│   │       ├── re_elicitation_graph.py      # RE V1: planner→extractor→critic
│   │       ├── re_elicitation_graph_v2.py   # RE V2: + SME node
│   │       ├── re_graph.py                  # RE classification graph (old)
│   │       │
│   │       └── nodes/
│   │           ├── codegen/                 # CodeGen-only nodes
│   │           │   ├── planner.py           # Decompose problem
│   │           │   ├── extractor.py         # Write code outline
│   │           │   ├── critic.py            # Check code for issues
│   │           │   ├── coder.py             # Write final implementation
│   │           │   ├── test_runner.py       # Execute tests
│   │           │   └── test_critic.py       # Score improvements (V2 only)
│   │           │
│   │           ├── re_elicitation/         # RE elicitation-only nodes
│   │           │   ├── planner.py           # Analyze use case
│   │           │   ├── extractor.py         # Generate requirements
│   │           │   ├── critic.py            # Validate requirements
│   │           │   ├── sme.py               # Domain expert advisory (V2 only)
│   │           │   └── combiner.py          # Combine outputs (if needed)
│   │           │
│   │           └── re_classification/      # RE classification nodes (old)
│   │               ├── planner.py
│   │               ├── extractor.py
│   │               └── critic.py
│   │
│   └── utils/
│       ├── json_utils.py
│       └── seed.py
│
├── data/
│   ├── raw/                 # Downloaded datasets (not in repo)
│   └── processed/           # Train/test splits, samples
│       ├── re_elicitation_projects.jsonl          # NICE-based RE data
│       ├── re_elicitation_projects_pure.jsonl     # Pure RE data
│       ├── humaneval_plus.jsonl                   # EvalPlus codegen data
│       └── mbpp_plus.jsonl                        # MBPP codegen data
│
├── outputs/
│   ├── re_elicitation/
│   │   ├── single_agent/results_claude_*.jsonl
│   │   ├── multi_agent_v1/results_*.jsonl
│   │   ├── multi_agent_v2_sme/results_*.jsonl
│   │   └── evaluation_*.json
│   │
│   ├── re_elicitation_pure/
│   │   └── (same structure)
│   │
│   └── single_agent/, multi_agent/, multi_agent_v2/
│       └── (CodeGen results)
│
└── .env                     # Config: USE_LOCAL_LLM, ANTHROPIC_API_KEY, etc.
```

---

## Pipeline 1: RE Elicitation

### What it does
**Input:** A software system's use-case description (plain English)  
**Output:** A list of functional and non-functional requirements

### Example

**Input:**
```
"An e-commerce platform where users browse products, add items to cart, 
and complete purchases. Administrators can manage inventory and discounts."
```

**Output:**
```json
[
  { "req_id": "R001", "text": "Users shall browse products by category", "type": "FR", "nfr_subtype": null },
  { "req_id": "R002", "text": "System shall respond to searches in < 1 second", "type": "NFR", "nfr_subtype": "performance" },
  { "req_id": "R003", "text": "Payment data shall be encrypted per PCI-DSS", "type": "NFR", "nfr_subtype": "security" }
]
```

### Data Flow

```
data/processed/
  re_elicitation_projects_pure.jsonl    ← Input: { project_id, use_case_description, ground_truth_requirements }
         ↓
scripts/run_re_elicitation.py --system single --dataset pure
         ↓
src/systems/single_agent/re_elicitation_agent.py  ← Makes 1 LLM call
         ↓
src/llm/prompts/re_elicitation_prompts.py  ← Formats prompt
src/llm/client.py                          ← Calls Claude/Ollama
src/schemas/re_elicitation_schema.py       ← Validates output (Pydantic)
         ↓
outputs/re_elicitation_pure/single_agent/results_claude_*.jsonl
         ↓
scripts/evaluate_re_elicitation.py --dataset pure
         ↓
src/evaluation/re_elicitation_metrics.py   ← Computes: coverage, precision, F1
         ↓
outputs/re_elicitation_pure/evaluation_*.json
```

### For Single-Agent Contribution

If you want to **improve single-agent RE elicitation**, modify:

**1. The prompt** → `src/llm/prompts/re_elicitation_prompts.py`
```python
def format_elicitation_prompt(use_case: str) -> str:
    return f"""Given this use case:
{use_case}

Generate up to 50 requirements. Ensure at least 30% are NFR.
...
"""
```

**2. The schema** → `src/schemas/re_elicitation_schema.py`
```python
class GeneratedRequirement(BaseModel):
    req_id: str
    text: str
    type: Literal["FR", "NFR"]
    nfr_subtype: Optional[str] = None
    # Add new fields here if needed
```

**3. The agent logic** → `src/systems/single_agent/re_elicitation_agent.py`
```python
def elicit(self, project_id: str, use_case_description: str) -> tuple[list[dict], dict]:
    # 1. Format prompt
    # 2. Call LLM
    # 3. Return requirements + usage stats
```

**4. Run & evaluate:**
```bash
python scripts/run_re_elicitation.py --system single --dataset pure --pilot
python scripts/evaluate_re_elicitation.py --dataset pure
```

---

## Pipeline 2: Code Generation

### What it does
**Input:** A Python function specification  
**Output:** Working Python code that passes tests

### Example

**Input:**
```
Write a function that takes a list and returns the sum of even numbers.
```

**Output:**
```python
def sum_evens(nums):
    return sum(n for n in nums if n % 2 == 0)
```

### Data Flow

```
data/processed/
  humaneval_plus.jsonl       ← Input: { id, prompt, test_code, entry_point }
         ↓
scripts/run_codegen_single_agent.py
         ↓
src/systems/single_agent/codegen_agent.py  ← Makes 1-3 LLM calls
         ↓
src/llm/prompts/codegen_prompts.py    ← Formats prompt
src/llm/client.py                      ← Calls Claude/Ollama
src/schemas/codegen_schema.py          ← Validates output
         ↓
outputs/single_agent/codegen_solutions_pilot_*.jsonl
         ↓
Each solution is executed in subprocess (10s timeout)
         ↓
outputs/single_agent/codegen_tests_pilot_*.jsonl
         ↓
scripts/evaluate_codegen.py
         ↓
src/evaluation/codegen_metrics.py  ← Computes: pass@1, test results
         ↓
outputs/single_agent/codegen_cost_*.json
```

---

## Multi-Agent Pipelines

### RE Elicitation V1: Planner → Extractor → Critic

```
Input: use_case_description
   ↓
[Planner Node]  ← LLM analyzes use case, outputs strategy
   ↓ (plan)
[Extractor Node] ← LLM uses plan to generate requirements
   ↓ (requirements)
[Critic Node]   ← LLM validates, approves or rejects
   ↓
If approved → Output
If rejected + budget ok → Loop back to Extractor
```

Run with:
```bash
python scripts/run_re_elicitation.py --system multi --dataset pure
```

### RE Elicitation V2: + SME Node

```
Input: use_case_description
   ↓
[Planner] → identifies domain + lists expert role
   ↓
[SME Node] ← Domain expert LLM provides constraints, patterns, risks
   ↓ (advisory)
[Extractor] ← Uses SME guidance when generating requirements
   ↓
[Critic]
   ↓
Output
```

Run with:
```bash
python scripts/run_re_elicitation.py --system v2 --dataset pure
```

---

## How to Contribute

### Scenario 1: Improve Single-Agent RE Elicitation

**Goal:** Better prompts, better requirement coverage

**Files to modify:**
```
src/llm/prompts/re_elicitation_prompts.py        ← Change the prompt text
src/systems/single_agent/re_elicitation_agent.py ← Change retry logic, parsing
src/schemas/re_elicitation_schema.py             ← Add new fields if needed
```

**Test your changes:**
```bash
# Run pilot (5 projects)
python scripts/run_re_elicitation.py --system single --dataset pure --pilot

# Evaluate
python scripts/evaluate_re_elicitation.py --dataset pure

# Compare F1 score against baseline (currently ~0.34)
```

---

### Scenario 2: Improve Multi-Agent RE Elicitation V2

**Goal:** Better SME node advisory, better planner strategy

**Files to modify:**
```
src/systems/multi_agent/nodes/re_elicitation/planner.py  ← Change planning strategy
src/systems/multi_agent/nodes/re_elicitation/sme.py      ← Improve domain expert
src/systems/multi_agent/re_elicitation_graph_v2.py       ← Change routing logic
```

**Test:**
```bash
python scripts/run_re_elicitation.py --system v2 --dataset pure --pilot
python scripts/evaluate_re_elicitation.py --dataset pure
```

---

### Scenario 3: Add a New Node to Multi-Agent

**Goal:** Add a new processing step

**Steps:**

1. **Create the node file:**
```python
# src/systems/multi_agent/nodes/re_elicitation/my_node.py
def my_node(state: dict) -> dict:
    """Process state, return updated dict."""
    from src.llm.client import get_llm, check_budget
    
    llm_calls = state.get("llm_calls", 0)
    check_budget(llm_calls, ...)
    
    # Your logic here
    
    return { "new_field": value, "llm_calls": 1, "total_tokens": X }
```

2. **Import in the graph:**
```python
# src/systems/multi_agent/re_elicitation_graph_v2.py
from src.systems.multi_agent.nodes.re_elicitation.my_node import my_node

def build_re_elicitation_graph_v2():
    graph.add_node("my_node_name", my_node)
    graph.add_edge("previous_node", "my_node_name")
    # ...
```

3. **Test:**
```bash
python scripts/run_re_elicitation.py --system v2 --dataset pure --pilot
```

---

### Scenario 4: Switch LLMs

**Goal:** Compare Claude vs Ollama

**Change .env:**
```ini
USE_LOCAL_LLM=false
ANTHROPIC_API_KEY=sk-ant-...
```

Or temporarily:
```bash
USE_LOCAL_LLM=false python scripts/run_re_elicitation.py --system single --dataset pure --pilot
```

**Result:** Filenames automatically include model name:
```
results_claude_2026-04-21_05-14.jsonl
results_mistral-nemo_2026-04-21_05-15.jsonl
```

---

## Key Metrics & Baselines

### RE Elicitation (Pure Dataset, 15 projects)

| System | F1 Score | Coverage | Precision | Notes |
|--------|----------|----------|-----------|-------|
| Single Agent (Mistral) | 0.338 | 0.359 | 0.367 | ~20 reqs/project |
| Single Agent (Claude) | TBD | TBD | TBD | Should hit 50 req cap |
| Multi V1 (Mistral) | 0.325 | 0.329 | 0.375 | More expensive (3 LLM calls) |
| Multi V2+SME (Mistral) | 0.258 | 0.260 | 0.300 | SME adds overhead |

**Goal:** Get Claude single-agent baseline, then optimize from there.

### Code Generation (EvalPlus, 164 problems)

| System | Pass@1 | Notes |
|--------|--------|-------|
| Single Agent (Mistral) | ~0.65 | Fast |
| Multi V1 | ~0.75 | Better but 5× slower |
| Multi V2 | ~0.78 | Marginal improvement |

---

## Important: Budget Guards

Every LLM call is protected by:
```python
check_budget(llm_calls, total_tokens)
# Raises BudgetExceededError if:
#   - llm_calls >= MAX_LLM_CALLS_PER_TASK (default 10)
#   - total_tokens >= MAX_TOKENS_PER_TASK (default 8000)
```

Set in `.env` or code to prevent runaway loops.

---

## Quick Debugging

**"Import not found" error?**
```bash
# Verify the path matches the new structure
python -c "from src.systems.multi_agent.nodes.re_elicitation.planner import re_elicitation_planner_node"
```

**"LLM call budget exceeded"?**
```bash
# Increase budget in .env
MAX_LLM_CALLS_PER_TASK=20
MAX_TOKENS_PER_TASK=16000
```

**"ANTHROPIC_API_KEY is not set"?**
```bash
# Fill in .env
ANTHROPIC_API_KEY=sk-ant-v0-...
# OR use local Ollama
USE_LOCAL_LLM=true
LOCAL_MODEL_ID=mistral-nemo
```

**Results not being saved?**
```bash
# Check output dir was created
ls outputs/re_elicitation_pure/single_agent/
# If empty, run with --pilot first to debug
python scripts/run_re_elicitation.py --system single --dataset pure --pilot
```

