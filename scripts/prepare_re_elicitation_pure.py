"""
Prepare RE Elicitation dataset from PURE.

One-time preprocessing step:
  1. Load PURE XML dataset, group requirements by project (document)
  2. Filter projects with fewer than --min_reqs requirements
  3. Call Claude to synthesise a use_case_description for each project
  4. Save to data/processed/re_elicitation_projects_pure.jsonl

Each output record:
  {
    "project_id": str,
    "use_case_description": str,
    "ground_truth_requirements": [{"id", "text", "label", "nfr_subtype"}, ...]
  }

Usage (from project root):
    python scripts/prepare_re_elicitation_pure.py
    python scripts/prepare_re_elicitation_pure.py --max_projects 20 --min_reqs 5
"""
import os
import sys
import json
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

from langchain_core.messages import SystemMessage, HumanMessage

from src.datasets.pure_loader import load_pure_by_project
from src.llm.client import get_llm
from src.llm.prompts.re_elicitation_prompts import (
    SYSTEM_USE_CASE_SYNTHESIS,
    format_use_case_synthesis_prompt,
)

OUTPUT_PATH = "data/processed/re_elicitation_projects_pure.jsonl"
MAX_REQS_FOR_SYNTHESIS = 40  # Cap sent to Claude to stay within token limits


def synthesise_use_case(llm, project_id: str, requirements: list[dict]) -> str:
    # Sample evenly across the list if it's too long, to preserve diversity
    reqs = requirements
    if len(reqs) > MAX_REQS_FOR_SYNTHESIS:
        step = len(reqs) // MAX_REQS_FOR_SYNTHESIS
        reqs = reqs[::step][:MAX_REQS_FOR_SYNTHESIS]
    prompt = format_use_case_synthesis_prompt(project_id, reqs)
    response = llm.invoke(
        [SystemMessage(content=SYSTEM_USE_CASE_SYNTHESIS), HumanMessage(content=prompt)]
    )
    return response.content.strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max_projects", type=int, default=None)
    parser.add_argument("--data_dir", type=str, default=None,
                        help="Override PURE_DATA_DIR")
    parser.add_argument("--min_reqs", type=int, default=5,
                        help="Skip projects with fewer than N requirements (default 5)")
    args = parser.parse_args()

    print("=== Preparing RE Elicitation dataset (PURE) ===")

    projects = load_pure_by_project(args.data_dir)
    print(f"  Loaded {len(projects)} documents from PURE dataset")

    projects = {pid: reqs for pid, reqs in projects.items() if len(reqs) >= args.min_reqs}
    print(f"  {len(projects)} documents with >= {args.min_reqs} requirements")

    if args.max_projects:
        project_ids = list(projects.keys())[: args.max_projects]
        projects = {pid: projects[pid] for pid in project_ids}
        print(f"  Limited to {len(projects)} projects (--max_projects)")

    llm = get_llm()
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    records = []
    for i, (project_id, reqs) in enumerate(projects.items(), 1):
        print(f"  [{i:3d}/{len(projects)}] {project_id} ({len(reqs)} reqs) ...", end=" ", flush=True)
        try:
            use_case = synthesise_use_case(llm, project_id, reqs)
            record = {
                "project_id": project_id,
                "use_case_description": use_case,
                "ground_truth_requirements": [
                    {
                        "id": r["id"],
                        "text": r["text"],
                        "label": r["label"],
                        "nfr_subtype": r.get("nfr_subtype"),
                    }
                    for r in reqs
                ],
            }
            records.append(record)
            print("OK")
        except Exception as e:
            print(f"SKIP ({e})")

    with open(OUTPUT_PATH, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")

    print(f"\n  Saved {len(records)} project records -> {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
