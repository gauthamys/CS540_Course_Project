"""
Tracks LLM call counts and token usage across a run.

Usage:
    tracker = CostTracker(system="single_agent", dataset="nice")
    tracker.record(llm_calls=1, total_tokens=450)
    ...
    summary = tracker.summary()
    tracker.save("outputs/single_agent/nice_cost.json")
"""
import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime


@dataclass
class CostTracker:
    system: str
    dataset: str
    _records: list[dict] = field(default_factory=list, repr=False)
    started_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def record(self, llm_calls: int, total_tokens: int, task_id: str = "") -> None:
        self._records.append(
            {"task_id": task_id, "llm_calls": llm_calls, "total_tokens": total_tokens}
        )

    def summary(self) -> dict:
        if not self._records:
            return {
                "system": self.system,
                "dataset": self.dataset,
                "n_tasks": 0,
                "total_llm_calls": 0,
                "total_tokens": 0,
                "avg_llm_calls": 0.0,
                "avg_tokens": 0.0,
            }
        n = len(self._records)
        total_calls = sum(r["llm_calls"] for r in self._records)
        total_tokens = sum(r["total_tokens"] for r in self._records)
        return {
            "system": self.system,
            "dataset": self.dataset,
            "n_tasks": n,
            "total_llm_calls": total_calls,
            "total_tokens": total_tokens,
            "avg_llm_calls": total_calls / n,
            "avg_tokens": total_tokens / n,
        }

    def save(self, path: str) -> None:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        data = {
            "system": self.system,
            "dataset": self.dataset,
            "started_at": self.started_at,
            "finished_at": datetime.utcnow().isoformat(),
            "summary": self.summary(),
            "per_task": self._records,
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        print(f"Cost tracker saved → {path}")
