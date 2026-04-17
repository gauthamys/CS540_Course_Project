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

## Quick Start: Run with Ollama (Free, Local) — 10 minutes

**Goal:** Run the code generation system with Mistral Nemo on your machine (no API costs).

### Prerequisites
- **Python 3.11+** (check with `python --version`)
- **Ollama** (download from https://ollama.ai)
- **Git** (for cloning)

### Step 1: Download & Setup Ollama (First Time Only)

```bash
# 1. Download Ollama from https://ollama.ai
# 2. Install it
# 3. In a NEW terminal, start the Ollama server:
ollama serve
```

This will start Ollama on `http://localhost:11434`. Keep this terminal running.

### Step 2: Pull Mistral Nemo Model (First Time Only)

Open a **different terminal** and run:

```bash
ollama pull mistral-nemo
```

This downloads the 12B parameter Mistral Nemo model (~7 GB). Takes ~5 minutes on a good connection.

### Step 3: Clone & Setup Python Environment

```bash
# Clone the repository
git clone https://github.com/gauthamys/CS540_Course_Project.git
cd CS540_Course_Project

# Create virtual environment
python -m venv .venv

# Activate it
# Windows (PowerShell):
.\.venv\Scripts\activate
# OR Windows (Git Bash):
source .venv/Scripts/activate
# OR macOS/Linux (bash):
source .venv/bin/activate
```

### Step 4: Install Dependencies

```bash
pip install -r requirements.txt
```

Takes ~2 minutes. Installs:
- LangChain + LangGraph (orchestration)
- Pydantic (structured outputs)
- EvalPlus (code evaluation)
- Anthropic SDK (for Claude fallback option)

### Step 5: Configure .env File

```bash
# Copy the example config
cp .env.example .env

# Edit .env and verify these settings:
# USE_LOCAL_LLM=true
# LOCAL_MODEL_ID=mistral-nemo
# OLLAMA_BASE_URL=http://localhost:11434
```

**File should look like:**
```ini
USE_LOCAL_LLM=true
LOCAL_MODEL_ID=mistral-nemo
OLLAMA_BASE_URL=http://localhost:11434
MAX_LLM_CALLS_PER_TASK=10
MAX_TOKENS_PER_TASK=8000
MAX_REPAIR_ITERATIONS=3
RANDOM_SEED=42
```

### Step 6: Run the System!

```bash
# Make sure Ollama server is still running in another terminal!

# Run single-agent system on 10 test problems
python scripts/run_pilot_single.py

# Or run multi-agent system
python scripts/run_pilot_multi.py
```

**Expected output:**
```
=== Single-Agent Pilot Run ===
[CodeGen] Running single-agent on 10 problems...
  HumanEval/61 -> PASS
  HumanEval/104 -> PASS
  HumanEval/105 -> FAIL
  ...
  pass@1: 9/10
```

Results are saved to `outputs/single_agent/`

---

## Detailed Setup Instructions

## Detailed Setup Instructions

### System Requirements

| Component | Requirement | Why |
|-----------|-------------|-----|
| Python | 3.11+ | Uses modern type hints + asyncio features |
| RAM | 8GB minimum | For Ollama + processing |
| Disk | 10GB+ free | Ollama model (~7GB) + outputs |
| OS | Windows/macOS/Linux | All supported |

### For Ollama (Recommended - FREE)

**Hardware:**
- GPU: Optional but recommended (CUDA/Metal speeds up inference 5-10x)
- CPU: Works but slower (takes ~30-60s per task vs ~5-10s with GPU)

**Installation:**
1. Download Ollama: https://ollama.ai
2. Install and run
3. Model downloads automatically when first needed

### For Claude API (Alternative - PAID)

Cost: ~$0.003 per 1K input tokens, ~$0.015 per 1K output tokens

1. Get API key: https://console.anthropic.com/account/keys
2. Keep it in `.env`: `ANTHROPIC_API_KEY=sk-ant-...`

---

### Advanced: Environment Configuration

**All .env options:**

```ini
# ============================================================================
# LLM Selection
# ============================================================================
USE_LOCAL_LLM=true              # true = Ollama, false = Claude API
LOCAL_MODEL_ID=mistral-nemo    # Model to use with Ollama
OLLAMA_BASE_URL=http://localhost:11434  # Ollama server address
ANTHROPIC_API_KEY=sk-ant-...   # Claude API key (if USE_LOCAL_LLM=false)

# ============================================================================
# Constraints (prevents runaway loops)
# ============================================================================
MAX_LLM_CALLS_PER_TASK=10      # Max LLM calls per problem
MAX_TOKENS_PER_TASK=8000       # Max tokens per problem
MAX_REPAIR_ITERATIONS=3        # Max code repair attempts

# ============================================================================
# Other
# ============================================================================
RANDOM_SEED=42                 # For reproducible dataset splits
```

---

### Troubleshooting

**Problem:** `Connection refused` to Ollama
```
Solution: Make sure Ollama server is running in another terminal
          Run: ollama serve
```

**Problem:** `Model not found: mistral-nemo`
```
Solution: Pull the model first
          Run: ollama pull mistral-nemo
          (First time takes ~5 minutes)
```

**Problem:** `ANTHROPIC_API_KEY is not set`
```
Solution: If using Claude, set the key in .env:
          ANTHROPIC_API_KEY=sk-ant-v0-...
          OR switch to Ollama: USE_LOCAL_LLM=true
```

**Problem:** Out of memory / very slow
```
Solution 1: Use a smaller Ollama model
            ollama pull mistral:7b  # 7B instead of 12B
            
Solution 2: Free up RAM on your machine
            Close other applications
            
Solution 3: Use Claude API (faster, better quality)
            Set: USE_LOCAL_LLM=false
```

**Problem:** Windows encoding error (→ character)
```
Solution: Already fixed in latest version
          Update repo: git pull
```

---

### Download Datasets (Optional)

For full experiments with RE (Requirements Engineering) datasets:

```bash
# Download EvalPlus (code generation - automatic)
python scripts/prepare_datasets.py

# For NICE & SecReq datasets (manual):
# See MISSING_DATASETS.md
```

For **pilot experiments** (10 test samples): Already included, no download needed.

---

---

## Running Different Systems

| Script | What it does | Duration | LLM | Output |
|--------|-------------|----------|-----|--------|
| `run_pilot_single.py` | Single-agent on 10 test problems | ~1-2 min | Ollama/Claude | `outputs/single_agent/` |
| `run_pilot_multi.py` | Multi-agent V1 on 10 problems | ~5-10 min | Ollama/Claude | `outputs/multi_agent/` |
| `run_pilot_multi_v2.py` | Multi-agent V2 on 10 problems | ~5-10 min | Ollama/Claude | `outputs/multi_agent_v2/` |
| `run_full.py` | Full dataset (all 164 problems) | ~30 min | Ollama/Claude | `outputs/single_agent/` |

**Quick test:** `python scripts/run_pilot_single.py` (~1 min)
**Full comparison:** `python scripts/run_pilot_multi.py` + `run_pilot_single.py` (~15 min)

### Example: Run with Both Ollama and Claude

Compare results side-by-side:

```bash
# Run with Ollama (local, free)
python scripts/run_pilot_single.py
# Outputs: outputs/single_agent/codegen_solutions_pilot_20260416_103022.jsonl

# Switch to Claude in .env, then:
python scripts/run_pilot_single.py
# Outputs: outputs/single_agent/codegen_solutions_pilot_20260416_103145.jsonl

# Both files coexist - never overwritten!
ls -lt outputs/single_agent/*.jsonl
```

---

## Understanding Outputs

### File Structure

```
outputs/
├── single_agent/
│   ├── codegen_solutions_pilot_[timestamp].jsonl    ← Generated code solutions
│   ├── codegen_tests_pilot_[timestamp].jsonl        ← Test results (PASS/FAIL)
│   └── codegen_cost_[timestamp].json                ← LLM cost tracking
└── multi_agent/
    ├── codegen_solutions_pilot_[timestamp].jsonl
    ├── codegen_tests_pilot_[timestamp].jsonl
    └── codegen_cost_[timestamp].json
```

### Sample Output (CodeGen Solution)

```json
{
  "task_id": "HumanEval/61",
  "code": "def correct_bracketing(brackets: str) -> bool:\n    stack = []\n    for b in brackets:\n        if b == '(': stack.append(')')\n        elif not stack or b != stack.pop(): return False\n    return not stack",
  "explanation": "Uses a stack to track unmatched opening brackets..."
}
```

### Sample Output (Test Result)

```json
{
  "task_id": "HumanEval/61",
  "passed": true,
  "num_passed": 1,
  "num_total": 1,
  "error_output": null,
  "attempt_number": 1
}
```

### Sample Output (Cost Summary)

```json
{
  "system": "single_agent",
  "dataset": "codegen",
  "summary": {
    "n_tasks": 10,
    "total_llm_calls": 10,
    "total_tokens": 2642,
    "avg_llm_calls": 1.0,
    "avg_tokens": 264.2
  }
}
```

---

## Quick Commands Reference

```bash
# Activate environment (do this first every session!)
.venv\Scripts\activate           # Windows PowerShell
source .venv/bin/activate         # macOS/Linux or Git Bash

# Run systems
python scripts/run_pilot_single.py         # Quick test (~1 min)
python scripts/run_pilot_multi.py          # Multi-agent comparison (~10 min)
python scripts/run_full.py                 # Full dataset (~30 min)

# View results
cat outputs/single_agent/codegen_solutions_pilot_*.jsonl
cat outputs/single_agent/codegen_cost_*.json | python -m json.tool

# Switch LLMs (without editing .env)
USE_LOCAL_LLM=true python scripts/run_pilot_single.py    # Use Ollama
USE_LOCAL_LLM=false python scripts/run_pilot_single.py   # Use Claude
```

---

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
