"""Verify the performance metrics learning notebook by executing code cells."""

from __future__ import annotations

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = PROJECT_ROOT / "notebooks" / "08_performance_metrics_explained.ipynb"


def display(value=None, *args, **kwargs):
    """Small stand-in for Jupyter display during script verification."""
    if value is not None:
        print(value)


def main() -> None:
    notebook = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    namespace = {
        "__name__": "__notebook_verification__",
        "display": display,
    }

    code_cell_count = 0
    for index, cell in enumerate(notebook["cells"], start=1):
        if cell.get("cell_type") != "code":
            continue
        code_cell_count += 1
        source = "".join(cell.get("source", []))
        try:
            exec(compile(source, f"{NOTEBOOK_PATH.name}#cell-{index}", "exec"), namespace)
        except Exception as exc:  # pragma: no cover - verification script diagnostics
            raise RuntimeError(f"Notebook code cell {index} failed") from exc

    summary = namespace.get("summary")
    comparison = namespace.get("comparison")
    if summary is None or comparison is None:
        raise RuntimeError("Notebook did not create expected summary/comparison tables")

    print(f"Executed {code_cell_count} code cells successfully.")
    print("Summary columns:", list(summary.columns))
    print("Comparison rows:", list(comparison.index))


if __name__ == "__main__":
    main()
