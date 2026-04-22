"""
Prepare RE Elicitation dataset.

Reads an existing projects JSONL (which has ground_truth_requirements),
calls Claude to synthesise a rich BRD document from each project's requirements,
and writes updated records with a `brd_document` field.

Each output record:
  {
    "project_id": str,
    "brd_document": str,
    "ground_truth_requirements": [{"id", "text", "label", "nfr_subtype"}, ...]
  }

Usage (from project root):
    python scripts/prepare_re_elicitation.py [--dataset nice|pure] [--max_projects N]
"""
import os
import sys
import json
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

from langchain_core.messages import SystemMessage, HumanMessage

from src.llm.client import get_llm
from src.llm.prompts.re_elicitation_prompts import (
    SYSTEM_BRD_SYNTHESIS,
    format_brd_synthesis_prompt,
)

DATA_PATHS = {
    "nice": (
        "data/processed/re_elicitation_projects_old.jsonl",
        "data/processed/re_elicitation_projects.jsonl",
    ),
    "pure": (
        "data/processed/re_elicitation_projects_pure.jsonl",
        "data/processed/re_elicitation_projects_pure.jsonl",
    ),
}


def load_jsonl(path: str) -> list[dict]:
    records = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def synthesise_brd(llm, project_id: str, requirements: list[dict]) -> str:
    """Call Claude to produce a structured BRD from a project's requirements."""
    prompt = format_brd_synthesis_prompt(project_id, requirements)
    response = llm.invoke(
        [SystemMessage(content=SYSTEM_BRD_SYNTHESIS), HumanMessage(content=prompt)]
    )
    return response.content.strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", choices=["nice", "pure"], default="nice",
                        help="Which dataset to prepare (default: nice)")
    parser.add_argument("--max_projects", type=int, default=None,
                        help="Limit number of projects (useful for pilot runs)")
    args = parser.parse_args()

    INPUT_PATH, OUTPUT_PATH = DATA_PATHS[args.dataset]
    print(f"=== Preparing RE Elicitation dataset [{args.dataset.upper()}] (BRD synthesis) ===")

    if not os.path.exists(INPUT_PATH):
        print(f"ERROR: {INPUT_PATH} not found.")
        sys.exit(1)

    existing = load_jsonl(INPUT_PATH)
    print(f"  Loaded {len(existing)} projects from {INPUT_PATH}")

    projects = existing
    if args.max_projects:
        projects = projects[: args.max_projects]
        print(f"  Limited to {len(projects)} projects (--max_projects)")

    llm = get_llm()

    records = []
    for i, proj in enumerate(projects, 1):
        project_id = proj["project_id"]
        reqs = proj["ground_truth_requirements"]
        print(f"  [{i:3d}/{len(projects)}] {project_id} ({len(reqs)} reqs) ...", end=" ", flush=True)
        try:
            brd = synthesise_brd(llm, project_id, reqs)
            records.append({
                "project_id": project_id,
                "brd_document": brd,
                "ground_truth_requirements": reqs,
            })
            print("OK")
        except Exception as e:
            print(f"SKIP ({e})")
            # Keep the old record unchanged so we don't lose ground truth
            records.append(proj)

    with open(OUTPUT_PATH, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")

    print(f"\n  Saved {len(records)} project records -> {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
