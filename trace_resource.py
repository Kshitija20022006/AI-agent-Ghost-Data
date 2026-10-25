
from pathlib import Path
import pandas as pd

PROJECT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_DIR / "data"
EVIDENCE_DIR = DATA_DIR / "evidence"

resource_id = input("Enter resource ID (example: account_005): ").strip()

print(f"\n=== SEARCHING EVIDENCE FOR {resource_id} ===")

matches = 0

for path in sorted(EVIDENCE_DIR.rglob("*")):
    if not path.is_file() or path.suffix.lower() not in {
        ".txt", ".log", ".json", ".sql"
    }:
        continue

    try:
        lines = path.read_text(
            encoding="utf-8", errors="replace"
        ).splitlines()

        for line_number, line in enumerate(lines, start=1):
            if resource_id.lower() in line.lower():
                print(
                    f"\nFile: {path.relative_to(EVIDENCE_DIR)}"
                    f"\nLine: {line_number}"
                    f"\n{line[:700]}"
                )
                matches += 1

                if matches >= 30:
                    break

    except OSError as error:
        print(f"Could not read {path.name}: {error}")

    if matches >= 30:
        break

print(f"\nTotal matches displayed: {matches}")

print("\n=== RELATED SYSTEM ACTIVITY ===")
activity_file = DATA_DIR / "system_activity.csv"
activity = pd.read_csv(activity_file, dtype=str).fillna("")

related = activity[
    activity["resource_id"].str.contains(
        resource_id, case=False, regex=False
    )
]

if related.empty:
    print("No direct resource-ID matches in system_activity.csv.")
else:
    print(related.to_string(index=False, max_rows=30))

print("\nTrace complete.")
