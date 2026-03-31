# Future Work & Known Limitations

---

## Current Limitations

### 1. Datasets — Requirements Engineering

The RE evaluation is blocked on two datasets that could not be automatically obtained:

- **NICE (ICSE 2025)**: The re-labeled PROMISE NFR dataset is not publicly hosted. Must be requested from the paper authors. See [MISSING_DATASETS.md](MISSING_DATASETS.md) for instructions.
- **SecReq**: The HuggingFace dataset `infsci2402/SecReq` no longer exists on the Hub and the original source is not publicly mirrored. Must be obtained directly from the paper authors.

Until these are available, the RE pipeline cannot be evaluated.

---

### 2. Datasets — Code Generation (Project-Level)

The current codegen pipeline is **function-level only** — one input description produces one Python function, evaluated by running a test file. Three project-level benchmarks were investigated and found to be architecturally incompatible:

#### CodeProjectEval ([whisperzqh/ProjectGen](https://github.com/whisperzqh/ProjectGen))
- 18 real-world Python repositories (Flask, TinyDB, PyJWT, etc.)
- Input: PRD + UML + architecture design docs
- Output: entire multi-file Python project (~12 files, ~2,400 LOC per project)
- Evaluation: pytest suite run in an isolated venv per repo + SketchBLEU structural similarity
- **Incompatibility**: `CodeSolution` schema holds a single code string; evaluation requires per-repo environment setup and a full pytest suite

#### DevBench — open-compass ([open-compass/DevBench](https://github.com/open-compass/DevBench))
- 22 repositories across Python, C/C++, Java, JavaScript
- 5 sequential task stages: Software Design → Environment Setup → Implementation → Acceptance Testing → Unit Testing
- Evaluation: pytest/GTest/JUnit/Jest pass rate + coverage + LLM-as-judge for design stages
- **Incompatibility**: Multi-stage pipeline with Docker/venv isolation per repo; some stages require LLM-as-judge rather than execution-based evaluation

#### ProjectEval ([RyanLoil/ProjectEval](https://github.com/RyanLoil/ProjectEval))
- 20 projects: 16 Django web apps, 3 console apps, 1 batch processing app
- Input: natural language prompt / structured checklist / code skeleton (3 difficulty levels)
- Output: complete Django project (10–15 files) + parameter values (HTML element IDs, URLs)
- Evaluation: live Selenium WebDriver tests against a running Django server
- **Incompatibility**: Requires Chrome/Firefox + WebDriver + live server management; a unique "parameter alignment" step where the model must introspect its own code to supply test parameters; only 20 total projects (too few for reliable statistical comparison)

---

### 3. Python 3.14 Compatibility

`pip install -e ".[dev]"` fails on Python 3.14 due to `setuptools.backends.legacy` not being importable. Packages must be installed individually. Additionally, `langchain-core` emits a warning that Pydantic V1 compatibility is broken on Python 3.14. The project should be pinned to **Python 3.11 or 3.12** for full compatibility.

---

### 4. Single-Agent RE Has No Retry

The single-agent RE baseline makes one LLM call with no retry on incorrect classification (only on malformed JSON). The multi-agent system can loop up to `MAX_LLM_CALLS_PER_TASK` times. This asymmetry means some performance difference may be attributable to the number of LLM calls rather than the orchestration structure itself. A fairer baseline would allow the single-agent RE system up to the same call budget.

---

### 5. Test Execution Granularity

`run_single_test` in `codegen_metrics.py` runs the entire test file as one subprocess and returns a single `passed: bool`. It does not count individual test cases — `num_passed` and `num_total` are both set to 0 or 1. This means partial credit (e.g., 8/10 tests passing) is invisible in the metrics. EvalPlus's native evaluator provides per-test granularity and should be used for the full evaluation run.

---

## Future Work

### A. Integrate alvinwmtan's DevBench (Near-Term, Low Effort)

**DevBench** ([alvinwmtan/dev-bench](https://github.com/alvinwmtan/dev-bench)) is a code *completion* benchmark — not project-level generation — and is directly compatible with the existing pipeline:

- 1,800 instances across Python, JavaScript, TypeScript, Java, C++, C#
- Schema fields: `prefix`, `golden_completion`, `suffix`, `language`, `category`, `assertions`
- Evaluation: Pass@1 (n=5), executable assertions (drop-in replacement for `test_code`)
- License: CC BY 4.0

**Integration effort:** ~100 lines — a new loader in `src/datasets/devbench_loader.py`, a new prompt template that injects `prefix + suffix` as context, and a new pilot script. The existing `run_single_test` subprocess runner works unchanged.

---

### B. Project-Level CodeGen Pipeline (Medium-Term, High Effort)

To support CodeProjectEval or DevBench (open-compass), the following components would need to be built:

1. **`ProjectSolution` schema** — list of `{file, path, code}` instead of a single string
2. **`ProjectCoderNode`** — LLM generates multiple files as structured JSON
3. **`ProjectSetupNode`** — installs `requirements.txt`, runs migrations, per-project venv isolation
4. **`ProjectTestRunnerNode`** — runs pytest suite per repo, parses JSON coverage reports
5. **New LangGraph graph** — `planner → file_generator → setup → test_runner → repair`

Estimated effort: 2–3 days. Recommended dataset: **CodeProjectEval** (Python-only, Apache-2.0, cleaner config schema than DevBench).

---

### C. ProjectEval Pipeline (Long-Term, High Infrastructure Cost)

Full support for ProjectEval would additionally require:

1. **`ParameterAlignmentNode`** — second LLM call that reads generated code and returns HTML element IDs, URLs, etc. required by Selenium tests
2. **`SeleniumTestRunnerNode`** — manages Django server lifecycle (`manage.py runserver`), Chrome/Firefox WebDriver, port allocation, and test execution via `func_timeout`
3. **Headless browser setup** — Chrome + chromedriver or Firefox + geckodriver in CI

Given only 20 projects total, statistical power for single vs multi-agent comparison is limited. This is best suited as a qualitative case study rather than a quantitative benchmark.

---

### D. Ablation Studies

The current design compares the full multi-agent system against the single-agent baseline. An ablation study isolating individual components would strengthen the paper:

| Ablation | Remove | Measures |
|---|---|---|
| No Planner | Skip planner node, feed raw input to extractor/coder | Value of decomposition |
| No Critic | Skip critic node entirely | Value of intermediate verification |
| No Repair Loop | Set `MAX_REPAIR_ITERATIONS=0` | Value of test-driven repair |
| No Test Critic (V2) | Use V1 graph instead of V2 | Value of test augmentation |

---

### E. Multi-Model Comparison

All experiments currently use `claude-sonnet-4-6` for both systems. A future direction is to compare across model families (GPT-4o, Gemini, open-source models) to test whether orchestration benefits are model-agnostic or depend on the underlying model's instruction-following capability.
