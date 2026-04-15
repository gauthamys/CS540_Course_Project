"""
Prepare RE Elicitation dataset.

One-time preprocessing step:
  1. Load NICE dataset, group requirements by project_id
  2. For each project, call Claude to synthesise a use_case_description
     from its list of requirements (reverse-mapping)
  3. Save to data/processed/re_elicitation_projects.jsonl

Each output record:
  {
    "project_id": str,
    "use_case_description": str,
    "ground_truth_requirements": [{"id", "text", "label", "nfr_subtype"}, ...]
  }

Usage (from project root):
    python scripts/prepare_re_elicitation.py [--max_projects N] [--data_dir PATH]
"""
import os
import sys
import json
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

from langchain_core.messages import SystemMessage, HumanMessage

from src.datasets.nice_loader import load_nice_by_project
from src.llm.client import get_llm
from src.llm.prompts.re_elicitation_prompts import (
    SYSTEM_USE_CASE_SYNTHESIS,
    format_use_case_synthesis_prompt,
)

OUTPUT_PATH = "data/processed/re_elicitation_projects.jsonl"


def synthesise_use_case(llm, project_id: str, requirements: list[dict]) -> str:
    """Call Claude to produce a use-case description from a project's requirements."""
    prompt = format_use_case_synthesis_prompt(project_id, requirements)
    response = llm.invoke(
        [SystemMessage(content=SYSTEM_USE_CASE_SYNTHESIS), HumanMessage(content=prompt)]
    )
    return response.content.strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max_projects", type=int, default=None,
                        help="Limit number of projects (useful for pilot runs)")
    parser.add_argument("--data_dir", type=str, default=None,
                        help="Override NICE_DATA_DIR")
    parser.add_argument("--min_reqs", type=int, default=4,
                        help="Skip projects with fewer than N requirements")
    args = parser.parse_args()

    print("=== Preparing RE Elicitation dataset ===")

    # Load NICE by project
    projects = load_nice_by_project(args.data_dir)
    print(f"  Loaded {len(projects)} projects from NICE dataset")

    # Filter small projects
    projects = {pid: reqs for pid, reqs in projects.items() if len(reqs) >= args.min_reqs}
    print(f"  {len(projects)} projects with >= {args.min_reqs} requirements")

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

    print(f"\n  Saved {len(records)} project records → {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
