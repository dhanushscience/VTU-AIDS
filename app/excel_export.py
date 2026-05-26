"""Export diary entries to Excel for download or bot legacy use."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

EXCEL_COLUMNS = [
    "Date",
    "Internship",
    "WorkSummary",
    "HoursWorked",
    "LearningOutcomes",
    "SkillsUsed",
    "ReferenceLinks",
    "BlockersRisks",
]


def entries_to_rows(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for e in entries:
        rows.append(
            {
                "Date": e.get("date", e.get("Date", "")),
                "Internship": e.get("internship", e.get("Internship", "")),
                "WorkSummary": e.get("description", e.get("WorkSummary", "")),
                "HoursWorked": e.get("hoursWorked", e.get("HoursWorked", "")),
                "LearningOutcomes": e.get(
                    "learningOutcomes", e.get("LearningOutcomes", "")
                ),
                "SkillsUsed": e.get("skillsUsed", e.get("SkillsUsed", "")),
                "ReferenceLinks": e.get("referenceLinks", e.get("ReferenceLinks", "")),
                "BlockersRisks": e.get("blockersRisks", e.get("BlockersRisks", "")),
            }
        )
    return rows


def write_entries_excel(entries: list[dict[str, Any]], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(entries_to_rows(entries), columns=EXCEL_COLUMNS)
    df.to_excel(path, sheet_name="Entries", index=False)
    return path
