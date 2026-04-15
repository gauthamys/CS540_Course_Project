"""
Generate comparison plots from full run outputs.

Usage (from project root):
    python scripts/plot_results.py

Saves figures to outputs/figures/
"""
import os
import sys
import json
import glob

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FIG_DIR = "outputs/figures"
os.makedirs(FIG_DIR, exist_ok=True)

SYSTEMS = {
    "single_agent":   {"label": "Single-Agent",    "color": "#4e79a7"},
    "multi_agent":    {"label": "Multi-Agent V1",   "color": "#f28e2b"},
    "multi_agent_v2": {"label": "Multi-Agent V2\n(+Test Critic)", "color": "#59a14f"},
}

STYLE = {
    "font.family": "sans-serif",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.3,
    "figure.dpi": 150,
}
plt.rcParams.update(STYLE)


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_jsonl(path: str) -> list[dict]:
    if not path or not os.path.exists(path):
        return []
    records = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def latest(pattern: str) -> str:
    files = sorted(glob.glob(pattern))
    return files[-1] if files else ""


def load_system_data(system: str) -> dict:
    tests_path = latest(f"outputs/{system}/full_codegen_tests_*.jsonl")
    cost_path  = latest(f"outputs/{system}/full_codegen_cost_*.json")

    tests = load_jsonl(tests_path)
    cost  = json.load(open(cost_path)) if cost_path and os.path.exists(cost_path) else {}
    summary = cost.get("summary", {})

    task_results = {r.get("task_id", f"task_{i}"): r for i, r in enumerate(tests)}

    return {
        "tests": tests,
        "task_results": task_results,
        "pass_at_1": sum(1 for r in tests if r.get("passed", False)) / len(tests) if tests else 0,
        "avg_llm_calls": summary.get("avg_llm_calls", 0),
        "avg_tokens": summary.get("avg_tokens", 0),
        "total_tokens": summary.get("total_tokens", 0),
        "per_task": cost.get("per_task", {}),
    }


# ── Plot 1: pass@1 bar chart ──────────────────────────────────────────────────

def plot_pass_at_1(data: dict) -> None:
    fig, ax = plt.subplots(figsize=(7, 4))
    systems = list(data.keys())
    labels  = [SYSTEMS[s]["label"] for s in systems]
    colors  = [SYSTEMS[s]["color"] for s in systems]
    values  = [data[s]["pass_at_1"] * 100 for s in systems]

    bars = ax.bar(labels, values, color=colors, width=0.5, zorder=3)
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                f"{val:.1f}%", ha="center", va="bottom", fontsize=11, fontweight="bold")

    ax.set_ylim(0, 115)
    ax.set_ylabel("pass@1 (%)", fontsize=12)
    ax.set_title("Code Generation — pass@1 (HumanEval+, 164 problems)", fontsize=13, pad=12)
    plt.tight_layout()
    path = f"{FIG_DIR}/pass_at_1.png"
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {path}")


# ── Plot 2: avg LLM calls bar chart ──────────────────────────────────────────

def plot_llm_calls(data: dict) -> None:
    fig, ax = plt.subplots(figsize=(7, 4))
    systems = list(data.keys())
    labels  = [SYSTEMS[s]["label"] for s in systems]
    colors  = [SYSTEMS[s]["color"] for s in systems]
    values  = [data[s]["avg_llm_calls"] for s in systems]

    bars = ax.bar(labels, values, color=colors, width=0.5, zorder=3)
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.05,
                f"{val:.1f}", ha="center", va="bottom", fontsize=11, fontweight="bold")

    ax.set_ylabel("Avg LLM calls per task", fontsize=12)
    ax.set_title("Orchestration Cost — Average LLM Calls per Task", fontsize=13, pad=12)
    plt.tight_layout()
    path = f"{FIG_DIR}/avg_llm_calls.png"
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {path}")


# ── Plot 3: avg tokens bar chart ──────────────────────────────────────────────

def plot_avg_tokens(data: dict) -> None:
    fig, ax = plt.subplots(figsize=(7, 4))
    systems = list(data.keys())
    labels  = [SYSTEMS[s]["label"] for s in systems]
    colors  = [SYSTEMS[s]["color"] for s in systems]
    values  = [data[s]["avg_tokens"] for s in systems]

    bars = ax.bar(labels, values, color=colors, width=0.5, zorder=3)
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 10,
                f"{val:.0f}", ha="center", va="bottom", fontsize=11, fontweight="bold")

    ax.set_ylabel("Avg tokens per task", fontsize=12)
    ax.set_title("Orchestration Cost — Average Tokens per Task", fontsize=13, pad=12)
    plt.tight_layout()
    path = f"{FIG_DIR}/avg_tokens.png"
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {path}")


# ── Plot 4: pass@1 vs cost scatter ────────────────────────────────────────────

def plot_pass_vs_cost(data: dict) -> None:
    fig, ax = plt.subplots(figsize=(6, 5))
    for system, d in data.items():
        ax.scatter(d["avg_tokens"], d["pass_at_1"] * 100,
                   color=SYSTEMS[system]["color"], s=180, zorder=5,
                   label=SYSTEMS[system]["label"], edgecolors="white", linewidths=1.5)
        ax.annotate(SYSTEMS[system]["label"],
                    (d["avg_tokens"], d["pass_at_1"] * 100),
                    textcoords="offset points", xytext=(8, 4), fontsize=9)

    ax.set_xlabel("Avg tokens per task (cost proxy)", fontsize=12)
    ax.set_ylabel("pass@1 (%)", fontsize=12)
    ax.set_title("Quality vs Cost Trade-off", fontsize=13, pad=12)
    plt.tight_layout()
    path = f"{FIG_DIR}/pass_vs_cost.png"
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {path}")


# ── Plot 5: per-task pass heatmap (pass/fail grid) ────────────────────────────

def plot_per_task_heatmap(data: dict) -> None:
    all_ids = sorted(
        set().union(*[set(d["task_results"].keys()) for d in data.values()]),
        key=lambda x: int(x.split("/")[-1]) if "/" in x else 0
    )
    systems = list(data.keys())

    matrix = np.zeros((len(systems), len(all_ids)))
    for i, system in enumerate(systems):
        for j, tid in enumerate(all_ids):
            r = data[system]["task_results"].get(tid, {})
            matrix[i, j] = 1 if r.get("passed", False) else 0

    fig, ax = plt.subplots(figsize=(18, 2.5))
    cmap = matplotlib.colors.ListedColormap(["#e74c3c", "#2ecc71"])
    ax.imshow(matrix, aspect="auto", cmap=cmap, vmin=0, vmax=1, interpolation="none")

    ax.set_yticks(range(len(systems)))
    ax.set_yticklabels([SYSTEMS[s]["label"] for s in systems], fontsize=9)
    ax.set_xticks(range(0, len(all_ids), 10))
    ax.set_xticklabels([all_ids[i].split("/")[-1] for i in range(0, len(all_ids), 10)], fontsize=7)
    ax.set_xlabel("HumanEval Problem ID", fontsize=10)
    ax.set_title("Per-Task Pass (green) / Fail (red) — All 164 Problems", fontsize=12, pad=10)

    pass_patch = mpatches.Patch(color="#2ecc71", label="Pass")
    fail_patch = mpatches.Patch(color="#e74c3c", label="Fail")
    ax.legend(handles=[pass_patch, fail_patch], loc="upper right", fontsize=8)

    plt.tight_layout()
    path = f"{FIG_DIR}/per_task_heatmap.png"
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {path}")


# ── Plot 6: token distribution per-task (box plot) ───────────────────────────

def plot_token_distribution(data: dict) -> None:
    fig, ax = plt.subplots(figsize=(7, 5))
    plot_data, labels, colors = [], [], []

    for system, d in data.items():
        tokens = [v.get("total_tokens", 0) for v in d["per_task"]]
        if tokens:
            plot_data.append(tokens)
            labels.append(SYSTEMS[system]["label"])
            colors.append(SYSTEMS[system]["color"])

    if not plot_data:
        plt.close(fig)
        return

    bp = ax.boxplot(plot_data, labels=labels, patch_artist=True, notch=False,
                    medianprops={"color": "black", "linewidth": 2})
    for patch, color in zip(bp["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)

    ax.set_ylabel("Tokens per task", fontsize=12)
    ax.set_title("Token Usage Distribution per Task", fontsize=13, pad=12)
    plt.tight_layout()
    path = f"{FIG_DIR}/token_distribution.png"
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {path}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=== Generating plots ===")

    data = {}
    for system in SYSTEMS:
        d = load_system_data(system)
        if d["tests"]:
            data[system] = d
            print(f"  Loaded {system}: {len(d['tests'])} results, pass@1={d['pass_at_1']:.3f}, avg_calls={d['avg_llm_calls']:.1f}")
        else:
            print(f"  SKIP {system}: no full run output found")

    if not data:
        print("No data found. Run scripts/run_full.py first.")
        return

    plot_pass_at_1(data)
    plot_llm_calls(data)
    plot_avg_tokens(data)
    plot_pass_vs_cost(data)
    plot_per_task_heatmap(data)
    plot_token_distribution(data)

    print(f"\n  All figures saved to {FIG_DIR}/")


if __name__ == "__main__":
    main()
