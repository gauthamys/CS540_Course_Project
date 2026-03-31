# CS540 Project — Multi-Agent Software Development Assistant

Compares **single-agent** vs **multi-agent (LangGraph)** LLMs on two software engineering tasks:

1. **Requirements Engineering (RE)** — classify requirements from NICE and SecReq datasets
2. **Code Generation** — solve HumanEval+ problems from EvalPlus

---

## Architecture

### Single-Agent Baseline

One LLM call (with up to 2 structured-output retries) per task. No inter-agent communication.

```
Input → [LLM] → Output
         ↑  |
         └──┘ (retry on parse/compile error, max 2x)
```

- **RE**: classifies a requirement as FR / NFR / NONE + NFR subtype in one shot
- **CodeGen**: generates code, compile-checks it, and sends errors back for repair if needed

### Multi-Agent System (LangGraph)

Two separate graphs sharing the same underlying LLM (`claude-sonnet-4-6`, `temperature=0`).

#### RE Graph

```
planner → extractor → critic
              ↑           |
              └─ revise ──┘  (if critic rejects + budget ok)
                          |
                       finalize → END
```

| Node | Role |
|------|------|
| **Planner** | Analyzes the sentence; outputs a 2–4 sentence classification strategy (no classification yet) |
| **Extractor** | Uses the plan to produce a structured `REPrediction` (FR / NFR / NONE + subtype + rationale) |
| **Critic** | Checks consistency and format; rejects → routes back to Extractor for revision |
| **Finalize** | Promotes `draft_prediction` → `final_prediction` and exits |

#### CodeGen Graph

```
planner → extractor → critic → coder → test_runner
                                  ↑          |
                                  └─ repair ─┘  (if tests fail + budget ok)
                                             |
                                           END
```

| Node | Role |
|------|------|
| **Planner** | Decomposes the problem into sub-goals and lists edge cases |
| **Extractor** | Produces a solution outline + initial draft code |
| **Critic** | Reviews draft code for obvious issues; feedback is passed to Coder (advisory only) |
| **Coder** | Writes the final implementation using the plan, critic feedback, and any prior test failures |
| **Test Runner** | Executes code in a subprocess (10s timeout); routes back to Coder for repair if tests fail |

#### Key Design Decisions

- **Budget guards** — every routing function enforces `MAX_LLM_CALLS_PER_TASK` (default 10) and `MAX_TOKENS_PER_TASK` (default 8000) to prevent runaway loops
- **Repair loop** (CodeGen only) — up to `MAX_REPAIR_ITERATIONS` (default 3) Coder → TestRunner cycles
- **Critic is advisory in CodeGen** — always routes to Coder regardless of approval; critique is context, not a gate
- **Shared prompts** — both systems use identical core prompt templates for a fair comparison
- **Reproducibility** — `temperature=0` throughout; `RANDOM_SEED=42` for dataset splits

---

## Project Structure

```
CS540_Project/
├── src/
│   ├── datasets/          # Loaders for NICE, SecReq, EvalPlus
│   ├── evaluation/        # RE metrics, codegen metrics, cost tracker
│   ├── llm/
│   │   ├── client.py      # Central LLM client (ChatAnthropic, budget checks)
│   │   └── prompts/       # RE and codegen prompt templates
│   ├── schemas/           # Pydantic schemas (REPrediction, CodeSolution, graph states)
│   ├── systems/
│   │   ├── single_agent/  # REAgent, CodeGenAgent
│   │   └── multi_agent/
│   │       ├── nodes/     # planner, extractor, critic, coder, test_runner
│   │       ├── re_graph.py
│   │       └── codegen_graph.py
│   └── utils/
├── scripts/
│   ├── prepare_datasets.py   # Download + split + sample pilot files
│   ├── run_pilot_single.py   # Run single-agent on all pilot sets
│   ├── run_pilot_multi.py    # Run multi-agent on all pilot sets
│   └── evaluate_pilot.py     # Compute and compare metrics
├── data/
│   ├── raw/               # Raw dataset files (see MISSING_DATASETS.md)
│   ├── processed/         # Train/test JSONL splits
│   └── pilots/            # 10-record pilot samples
├── outputs/
│   ├── single_agent/      # Predictions + cost summaries
│   └── multi_agent/
├── MISSING_DATASETS.md    # Instructions for obtaining NICE and SecReq
└── pyproject.toml
```

---

## Setup

### 1. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install anthropic "langchain>=0.2" "langchain-anthropic>=0.1" "langgraph>=0.1" \
    "pydantic>=2.0" "evalplus>=0.3" "datasets>=2.19" pandas scikit-learn \
    python-dotenv jsonlines tqdm jupyter ipykernel pytest pytest-asyncio
```

> `pip install -e ".[dev]"` is blocked on Python 3.14 due to a setuptools compatibility issue.

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env and fill in your ANTHROPIC_API_KEY
```

### 4. Obtain missing datasets

See [MISSING_DATASETS.md](MISSING_DATASETS.md) for instructions on downloading NICE and SecReq.
EvalPlus (HumanEval+) downloads automatically.

### 5. Prepare datasets

```bash
.venv/bin/python scripts/prepare_datasets.py
```

---

## Running the Pilots

```bash
# Single-agent baseline
.venv/bin/python scripts/run_pilot_single.py

# Multi-agent system
.venv/bin/python scripts/run_pilot_multi.py

# Evaluate and compare
.venv/bin/python scripts/evaluate_pilot.py --auto
```

Outputs are written to `outputs/single_agent/` and `outputs/multi_agent/`.

---

## Datasets

| Dataset | Task | Status |
|---------|------|--------|
| NICE (ICSE 2025) | RE classification (FR/NFR/NONE) | Manual download required |
| SecReq | RE security classification | Manual download required |
| EvalPlus HumanEval+ | Code generation | Auto-downloaded |

---

## Tech Stack

- **Python** 3.11+
- **LangChain** + **LangGraph** for agent orchestration
- **Anthropic** `claude-sonnet-4-6` as the underlying LLM
- **Pydantic v2** for structured outputs
- **scikit-learn** for RE metrics (F1, precision, recall)
- **EvalPlus** for code generation evaluation (pass@1)
- **JSONL** for all data storage
