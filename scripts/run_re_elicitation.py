"""
Run all three RE Elicitation systems on the prepared project dataset.

Usage (from project root):
    python scripts/run_re_elicitation.py [--system single|multi|v2|all] [--pilot] [--max_projects N]

Outputs go to:
    outputs/re_elicitation/single_agent/results_<TIMESTAMP>.jsonl
    outputs/re_elicitation/multi_agent_v1/results_<TIMESTAMP>.jsonl
    outputs/re_elicitation/multi_agent_v2_sme/results_<TIMESTAMP>.jsonl

Each output line:
  {
    "project_id": str,
    "system": str,
    "generated_requirements": [...],
    "llm_calls": int,
    "total_tokens": int,
    "ground_truth_requirements": [...]
  }
"""
import os
import sys
import json
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

TIMESTAMP = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
DATA_PATH = "data/processed/re_elicitation_projects.jsonl"
PILOT_N = 5


def load_jsonl(path: str) -> list[dict]:
    records = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def write_jsonl(records: list[dict], path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    print(f"  Saved {len(records)} records → {path}")


# ── System 1: Single-Agent ─────────────────────────────────────────────────────

def run_single(projects: list[dict]) -> None:
    from src.systems.single_agent.re_elicitation_agent import REElicitationAgent

    out_path = f"outputs/re_elicitation/single_agent/results_{TIMESTAMP}.jsonl"
    print(f"\n[single_agent] Running on {len(projects)} projects...")

    agent = REElicitationAgent()
    results = []

    for i, proj in enumerate(projects, 1):
        pid = proj["project_id"]
        use_case = proj["use_case_description"]
        print(f"  [{i:3d}/{len(projects)}] {pid} ...", end=" ", flush=True)
        try:
            reqs, usage = agent.elicit(pid, use_case)
            result = {
                "project_id": pid,
                "system": "single_agent",
                "generated_requirements": reqs,
                "llm_calls": usage["llm_calls"],
                "total_tokens": usage["total_tokens"],
                "ground_truth_requirements": proj["ground_truth_requirements"],
            }
            results.append(result)
            print(f"OK ({len(reqs)} reqs, {usage['llm_calls']} calls)")
        except Exception as e:
            print(f"FAIL ({e})")
            results.append({
                "project_id": pid,
                "system": "single_agent",
                "generated_requirements": [],
                "llm_calls": 0,
                "total_tokens": 0,
                "ground_truth_requirements": proj["ground_truth_requirements"],
            })

    write_jsonl(results, out_path)
    avg_reqs = sum(len(r["generated_requirements"]) for r in results) / max(len(results), 1)
    print(f"  avg reqs/project: {avg_reqs:.1f}")


# ── System 2: Multi-Agent V1 ───────────────────────────────────────────────────

def run_multi(projects: list[dict]) -> None:
    from src.systems.multi_agent.re_elicitation_graph import (
        build_re_elicitation_graph,
        make_initial_state,
    )

    out_path = f"outputs/re_elicitation/multi_agent_v1/results_{TIMESTAMP}.jsonl"
    print(f"\n[multi_agent_v1] Running on {len(projects)} projects...")

    graph = build_re_elicitation_graph()
    results = []

    for i, proj in enumerate(projects, 1):
        pid = proj["project_id"]
        use_case = proj["use_case_description"]
        print(f"  [{i:3d}/{len(projects)}] {pid} ...", end=" ", flush=True)
        try:
            state = make_initial_state(pid, use_case)
            result_state = graph.invoke(state)
            reqs = result_state.get("final_requirements", [])
            result = {
                "project_id": pid,
                "system": "multi_agent_v1",
                "generated_requirements": reqs,
                "llm_calls": result_state.get("llm_calls", 0),
                "total_tokens": result_state.get("total_tokens", 0),
                "ground_truth_requirements": proj["ground_truth_requirements"],
            }
            results.append(result)
            print(f"OK ({len(reqs)} reqs, {result_state.get('llm_calls', 0)} calls)")
        except Exception as e:
            print(f"FAIL ({e})")
            results.append({
                "project_id": pid,
                "system": "multi_agent_v1",
                "generated_requirements": [],
                "llm_calls": 0,
                "total_tokens": 0,
                "ground_truth_requirements": proj["ground_truth_requirements"],
            })

    write_jsonl(results, out_path)
    avg_reqs = sum(len(r["generated_requirements"]) for r in results) / max(len(results), 1)
    print(f"  avg reqs/project: {avg_reqs:.1f}")


# ── System 3: Multi-Agent V2 + SME ────────────────────────────────────────────

def run_v2(projects: list[dict]) -> None:
    from src.systems.multi_agent.re_elicitation_graph_v2 import (
        build_re_elicitation_graph_v2,
        make_initial_state,
    )

    out_path = f"outputs/re_elicitation/multi_agent_v2_sme/results_{TIMESTAMP}.jsonl"
    print(f"\n[multi_agent_v2_sme] Running on {len(projects)} projects...")

    graph = build_re_elicitation_graph_v2()
    results = []

    for i, proj in enumerate(projects, 1):
        pid = proj["project_id"]
        use_case = proj["use_case_description"]
        print(f"  [{i:3d}/{len(projects)}] {pid} ...", end=" ", flush=True)
        try:
            state = make_initial_state(pid, use_case)
            result_state = graph.invoke(state)
            reqs = result_state.get("final_requirements", [])
            sme_count = sum(1 for r in reqs if r.get("source") == "sme")
            result = {
                "project_id": pid,
                "system": "multi_agent_v2_sme",
                "generated_requirements": reqs,
                "llm_calls": result_state.get("llm_calls", 0),
                "total_tokens": result_state.get("total_tokens", 0),
                "domain": result_state.get("domain", ""),
                "sme_subject": result_state.get("sme_subject", ""),
                "ground_truth_requirements": proj["ground_truth_requirements"],
            }
            results.append(result)
            print(f"OK ({len(reqs)} reqs [{sme_count} SME], {result_state.get('llm_calls', 0)} calls)")
        except Exception as e:
            print(f"FAIL ({e})")
            results.append({
                "project_id": pid,
                "system": "multi_agent_v2_sme",
                "generated_requirements": [],
                "llm_calls": 0,
                "total_tokens": 0,
                "ground_truth_requirements": proj["ground_truth_requirements"],
            })

    write_jsonl(results, out_path)
    avg_reqs = sum(len(r["generated_requirements"]) for r in results) / max(len(results), 1)
    print(f"  avg reqs/project: {avg_reqs:.1f}")


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--system", choices=["single", "multi", "v2", "all"], default="all")
    parser.add_argument("--pilot", action="store_true",
                        help=f"Run on first {PILOT_N} projects only")
    parser.add_argument("--max_projects", type=int, default=None)
    args = parser.parse_args()

    if not os.path.exists(DATA_PATH):
        print(f"ERROR: {DATA_PATH} not found. Run scripts/prepare_re_elicitation.py first.")
        sys.exit(1)

    projects = load_jsonl(DATA_PATH)
    limit = PILOT_N if args.pilot else args.max_projects
    if limit:
        projects = projects[:limit]

    print(f"=== RE Elicitation Run — {len(projects)} projects ===")

    if args.system in ("single", "all"):
        run_single(projects)
    if args.system in ("multi", "all"):
        run_multi(projects)
    if args.system in ("v2", "all"):
        run_v2(projects)

    print("\n=== Done ===")


if __name__ == "__main__":
    main()
