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

### Quick Start (5 minutes)

**Prerequisites:**
- Python 3.11+
- Ollama installed (for local LLM, optional)

**Step 1: Clone & Setup Environment**

```bash
# Windows (PowerShell)
python -m venv .venv
.\.venv\Scripts\activate

# macOS/Linux (bash)
python3 -m venv .venv
source .venv/bin/activate
```

**Step 2: Install Dependencies**

```bash
pip install -r requirements.txt
```

**Step 3: Configure LLM**

```bash
# Copy template
cp .env.example .env

# Choose your LLM:
# Option A: Use LOCAL Mistral Nemo (FREE, requires Ollama)
#   - Install Ollama: https://ollama.ai
#   - Run: ollama pull mistral-nemo
#   - Run: ollama serve
#   - Set in .env: USE_LOCAL_LLM=true

# Option B: Use Claude API (requires API key)
#   - Get key from: https://console.anthropic.com/account/keys
#   - Set in .env: USE_LOCAL_LLM=false
#   - Set: ANTHROPIC_API_KEY=sk-ant-...
```

**Step 4: Download Datasets** (optional, for full experiments)

```bash
python scripts/prepare_datasets.py
```

> Note: RE datasets (NICE, SecReq) require manual download. See [MISSING_DATASETS.md](MISSING_DATASETS.md).

---

### Detailed Setup

#### 1. Prerequisites

- **Python 3.11 or 3.12** (3.14 not yet supported)
- **Git** (for cloning repo)
- **Ollama** (optional, for free local LLM): https://ollama.ai

#### 2. Clone Repository

```bash
git clone <repository-url>
cd CS540_Course_Project
```

#### 3. Create Virtual Environment

```bash
# Windows (PowerShell)
python -m venv .venv
.\.venv\Scripts\activate

# macOS/Linux (bash)
python3 -m venv .venv
source .venv/bin/activate
```

#### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

**What's installed:**
- **LangChain + LangGraph** — Agent orchestration
- **Anthropic SDK** — Claude API
- **LangChain Community** — Local model support (Ollama)
- **EvalPlus** — Code evaluation
- **Sentence Transformers** — RE evaluation
- **Datasets, Pandas, scikit-learn** — Data processing

#### 5. Setup LLM Configuration

Copy the template:
```bash
cp .env.example .env
```

Edit `.env` and choose **ONE** of these options:

**Option A: Local Ollama (Recommended for cost-free experimentation)**

```bash
# .env
USE_LOCAL_LLM=true
LOCAL_MODEL_ID=mistral-nemo
OLLAMA_BASE_URL=http://localhost:11434
```

Then install & run Ollama:
```bash
# Download from https://ollama.ai
# Pull the model:
ollama pull mistral-nemo

# In a separate terminal, start the server:
ollama serve
```

**Option B: Claude API (Better quality, costs $)**

```bash
# .env
USE_LOCAL_LLM=false
ANTHROPIC_API_KEY=sk-ant-v0-...
```

Get your API key: https://console.anthropic.com/account/keys

#### 6. Download Datasets (Optional)

For full experiments, prepare datasets:

```bash
python scripts/prepare_datasets.py
```

**Note:** 
- **EvalPlus** (HumanEval+) downloads automatically
- **NICE & SecReq** require manual download (see [MISSING_DATASETS.md](MISSING_DATASETS.md))

---

## Running the Pilots

### Basic Usage

```bash
# Activate virtual environment first
.venv/bin/python scripts/run_pilot_single.py     # Single-agent baseline
.venv/bin/python scripts/run_pilot_multi.py      # Multi-agent system
.venv/bin/python scripts/evaluate_pilot.py --auto # Evaluate and compare
```

Outputs are written to `outputs/single_agent/` and `outputs/multi_agent/`.

### Switching Between LLMs at Runtime

You can override the LLM **without editing `.env`**:

**Windows (PowerShell):**
```powershell
# Use Ollama (cheap, free)
$env:USE_LOCAL_LLM="true"; python scripts/run_pilot_single.py

# Use Claude (better quality, costs $)
$env:USE_LOCAL_LLM="false"; python scripts/run_pilot_single.py
```

**macOS/Linux (bash):**
```bash
# Use Ollama
USE_LOCAL_LLM=true python scripts/run_pilot_single.py

# Use Claude
USE_LOCAL_LLM=false python scripts/run_pilot_single.py
```

**Pro tip:** Test with Ollama first to iterate cheaply, then run final experiments with Claude.

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
