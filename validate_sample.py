
import json
import pandas as pd
from collections import Counter
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

sample_path = DATA_DIR / "sample_output.csv"
rules_path = DATA_DIR / "deletion_rules.csv"

# Check that the required files exist
for path in [sample_path, rules_path]:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

# Load sample output and deletion rules
sample = pd.read_csv(sample_path)
rules = pd.read_csv(rules_path)

print("=" * 60)
print("SAMPLE OUTPUT VALIDATION")
print("=" * 60)

# Check output columns
expected_columns = [
    "case_id",
    "deletion_status",
    "steps_json"
]

print("Correct columns:", list(sample.columns) == expected_columns)
print("Total sample cases:", len(sample))
print("Duplicate case IDs:", sample["case_id"].duplicated().sum())

# Count statuses
print("\nSTATUS COUNTS:")
print(sample["deletion_status"].value_counts().to_string())

valid_statuses = {
    "COMPLETE",
    "INCOMPLETE",
    "NOT_APPLICABLE"
}

invalid_statuses = set(sample["deletion_status"].dropna()) - valid_statuses
print("\nInvalid statuses:", invalid_statuses)

# Check every steps_json value
operation_counts = Counter()
phase_counts = Counter()
invalid_json = []
invalid_steps = []
empty_steps = 0

for _, row in sample.iterrows():
    case_id = row["case_id"]

    try:
        steps = json.loads(row["steps_json"])
    except (json.JSONDecodeError, TypeError):
        invalid_json.append(case_id)
        continue

    if not isinstance(steps, list):
        invalid_steps.append(case_id)
        continue

    if not steps:
        empty_steps += 1

    for step in steps:
        if not isinstance(step, dict):
            invalid_steps.append(case_id)
            continue

        operation_counts[step.get("operation", "MISSING")] += 1
        phase_counts[step.get("phase", "MISSING")] += 1

print("\nSTEP VALIDATION:")
print("Invalid JSON cases:", invalid_json)
print("Invalid step structures:", invalid_steps)
print("Cases with empty steps:", empty_steps)

print("\nOPERATION COUNTS:")
for operation, count in sorted(operation_counts.items()):
    print(f"{operation}: {count}")

print("\nPHASE COUNTS:")
for phase, count in sorted(phase_counts.items()):
    print(f"{phase}: {count}")

# Display all supplied deletion rules
print("\n" + "=" * 60)
print("DELETION RULES")
print("=" * 60)

print(rules.to_string(index=False))

print("\nValidation finished.")
