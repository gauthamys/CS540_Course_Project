# Quick Start: Understanding the Code

## The Two Pipelines at a Glance

### Pipeline 1: RE Elicitation (YOUR FOCUS)

```
┌──────────────────────────────────────────────────────────────────┐
│                   RE ELICITATION PIPELINE                        │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  INPUT: "An e-commerce platform where users..."                │
│           ↓                                                      │
│  SINGLE AGENT:  1 LLM call → 50 requirements                   │
│           ↓                                                      │
│  MULTI V1:      Planner → Extractor → Critic (loop allowed)   │
│           ↓                                                      │
│  MULTI V2:      Planner → SME → Extractor → Critic            │
│           ↓                                                      │
│  OUTPUT: { req_id, text, type(FR/NFR), nfr_subtype, rationale }│
│                                                                  │
│  EVALUATION: Coverage, Precision, Semantic F1                  │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### Pipeline 2: Code Generation

```
┌──────────────────────────────────────────────────────────────────┐
│                   CODE GENERATION PIPELINE                       │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  INPUT: "Write function that returns sum of even numbers"      │
│           ↓                                                      │
│  SINGLE AGENT:  1 LLM call → Python code                       │
│           ↓                                                      │
│  MULTI V1:      Planner → Extractor → Critic → Coder → Test   │
│           ↓                                                      │
│  MULTI V2:      V1 + Test Critic node for scoring              │
│           ↓                                                      │
│  OUTPUT: Working Python code (or error message)                 │
│                                                                  │
│  EVALUATION: pass@1 (does code pass tests?)                     │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## One Script = One Task

| What to run | Command | Output location |
|---|---|---|
| **RE Pilot** | `python scripts/run_re_elicitation.py --system single --dataset pure --pilot` | `outputs/re_elicitation_pure/single_agent/` |
| **RE Full** | `python scripts/run_re_elicitation.py --system single --dataset pure` | same |
| **RE Eval** | `python scripts/evaluate_re_elicitation.py --dataset pure` | `outputs/re_elicitation_pure/evaluation_*.json` |
| **CodeGen** | `python scripts/run_codegen_single_agent.py` | `outputs/single_agent/` |
| **CodeGen Eval** | `python scripts/evaluate_codegen.py` | (printed to console) |

---

## Where to Make Changes

### To improve RE elicitation prompts:

```
src/llm/prompts/re_elicitation_prompts.py

def format_elicitation_prompt(use_case: str) -> str:
    # THIS IS WHAT THE LLM READS
    # Change this to improve what gets asked
```

### To improve RE elicitation schema (what LLM outputs):

```
src/schemas/re_elicitation_schema.py

class GeneratedRequirement(BaseModel):
    req_id: str
    text: str
    type: Literal["FR", "NFR"]
    # ADD/REMOVE FIELDS HERE
```

### To improve single agent logic:

```
src/systems/single_agent/re_elicitation_agent.py

def elicit(self, project_id, use_case_description):
    # CHANGE THIS TO IMPROVE BEHAVIOR
    # Currently: 1 LLM call, return requirements
```

### To change multi-agent workflow:

```
src/systems/multi_agent/re_elicitation_graph_v2.py

def build_re_elicitation_graph_v2():
    # Add/remove nodes
    # Change routing (when to loop back, when to approve)
    # Change connections
```

### To add a new node:

```
src/systems/multi_agent/nodes/re_elicitation/my_new_node.py

def my_new_node(state: dict) -> dict:
    """Takes state dict, returns updated state dict."""
    # Your logic here
    return { "field": value, "llm_calls": 1, "total_tokens": X }
```

Then import in graph and add to pipeline.

---

## State Flow (What Moves Between Nodes)

### Single Agent
```python
state = {
    "project_id": "proj_042",
    "use_case_description": "An e-commerce platform..."
}
    ↓ (1 LLM call)
state = {
    "generated_requirements": [...],
    "llm_calls": 1,
    "total_tokens": 842
}
```

### Multi-Agent V1
```python
state = {
    "project_id": "proj_042",
    "use_case_description": "An e-commerce platform..."
}
    ↓ (Planner)
state = {
    "plan": "Consider security, scalability..."
    "llm_calls": 1
}
    ↓ (Extractor)
state = {
    "generated_requirements": [...],
    "llm_calls": 2
}
    ↓ (Critic)
state = {
    "approved": true/false,
    "feedback": "Missing NFRs..." (if rejected)
    "llm_calls": 3
}
    ↓ (Loop or END)
```

---

## File Naming Convention

**Scripts:**
- `prepare_*.py` - Data prep
- `run_*.py` - Run a system
- `evaluate_*.py` - Compute metrics

**Output files:**
- `results_<MODEL>_<TIMESTAMP>.jsonl` - Raw LLM outputs
- `evaluation_<TIMESTAMP>.json` - Computed metrics

**Example:**
```
results_claude_2026-04-21_05-14.jsonl      ← Claude, April 21, 5:14 AM
results_mistral-nemo_2026-04-21_05-15.jsonl ← Mistral Nemo, April 21, 5:15 AM
```

---

## Configuration

All in `.env`:

```ini
# Which LLM to use
USE_LOCAL_LLM=false                    # false = Claude, true = Ollama
ANTHROPIC_API_KEY=sk-ant-...           # If USE_LOCAL_LLM=false
LOCAL_MODEL_ID=mistral-nemo            # If USE_LOCAL_LLM=true
OLLAMA_BASE_URL=http://localhost:11434

# Limits (prevent runaway loops)
MAX_LLM_CALLS_PER_TASK=10
MAX_TOKENS_PER_TASK=8000
RE_SIM_THRESHOLD=0.6                   # For evaluation (cosine sim cutoff)

# Reproducibility
RANDOM_SEED=42
```

---

## Common Workflows

### Debug a single project

```bash
# Run RE elicitation with verbose output
python -c "
from src.systems.single_agent.re_elicitation_agent import REElicitationAgent
agent = REElicitationAgent()
reqs, usage = agent.elicit('test_project', 'This is my use case...')
print(f'Generated {len(reqs)} requirements')
for req in reqs[:3]:
    print(f'  - {req[\"text\"][:60]}...')
"
```

### Compare two models

```bash
# Run with Claude
USE_LOCAL_LLM=false python scripts/run_re_elicitation.py --system single --dataset pure --pilot

# Run with Ollama
USE_LOCAL_LLM=true python scripts/run_re_elicitation.py --system single --dataset pure --pilot

# Evaluate both (should pick up latest results auto)
python scripts/evaluate_re_elicitation.py --dataset pure
```

### Test a new prompt

```bash
# 1. Edit the prompt file
vim src/llm/prompts/re_elicitation_prompts.py

# 2. Run pilot
python scripts/run_re_elicitation.py --system single --dataset pure --pilot

# 3. Check results
cat outputs/re_elicitation_pure/single_agent/results_*.jsonl | head -1 | python -m json.tool

# 4. Evaluate
python scripts/evaluate_re_elicitation.py --dataset pure
```

### Add a new NFR subtype

```python
# 1. Edit schema
# src/schemas/re_elicitation_schema.py
nfr_subtype: Optional[Literal[
    "performance",
    "security",
    "usability",
    "reliability",
    "maintainability",
    "portability",
    "availability",
    "my_new_type"  # ← ADD HERE
]] = None

# 2. Update prompt to mention it
# src/llm/prompts/re_elicitation_prompts.py
SYSTEM_RE_ELICITATION = (
    "...
    nfr_subtype options: performance, security, ..., my_new_type
    ..."
)

# 3. Run & test
python scripts/run_re_elicitation.py --system single --dataset pure --pilot
python scripts/evaluate_re_elicitation.py --dataset pure
```

---

## Metrics Explained

### RE Elicitation Metrics

**Coverage (Recall):** Of all ground-truth requirements, what % did the LLM generate?
- Example: 10 GT reqs, LLM covered 8 → coverage = 0.80

**Precision:** Of all generated reqs, what % actually matched something in GT?
- Example: LLM generated 50, only 30 matched → precision = 0.60

**Semantic F1:** Harmonic mean of coverage and precision
- Formula: `2 * coverage * precision / (coverage + precision)`
- Balanced score: can't game by outputting 200 reqs or 2 reqs

**FR Coverage / NFR Coverage:** Same as coverage, but split by requirement type

### Code Generation Metrics

**pass@1:** Percentage of problems solved correctly on first try
- Example: 10 problems, 7 pass → pass@1 = 0.70

**Tests passed/failed:** Per-problem test results

---

## Important Constraints

All protected by `check_budget()`:

```python
from src.llm.client import check_budget

# In any node:
check_budget(llm_calls, total_tokens)
# Raises BudgetExceededError if limits exceeded
```

This prevents infinite loops where Critic keeps rejecting.

---

## Next Steps: Your Contribution

1. **Read:** Review `PROJECT_STRUCTURE.md` fully
2. **Explore:** Walk through one end-to-end run:
   ```bash
   python scripts/run_re_elicitation.py --system single --dataset pure --pilot
   cat outputs/re_elicitation_pure/single_agent/results_*.jsonl | python -m json.tool | head -50
   python scripts/evaluate_re_elicitation.py --dataset pure
   ```
3. **Identify:** What do you want to improve? (prompts, schema, nodes, routing?)
4. **Modify:** Make your change in the right file
5. **Test:** Run pilot, check output
6. **Evaluate:** See metrics improve (or debug why they didn't)
7. **Commit:** Create a PR with your improvements
