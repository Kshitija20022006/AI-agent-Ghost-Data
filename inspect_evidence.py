
from pathlib import Path
import pandas as pd

PROJECT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_DIR / "data"
EVIDENCE_DIR = DATA_DIR / "evidence"

manifest = pd.read_csv(DATA_DIR / "evidence_files.csv")
activity = pd.read_csv(DATA_DIR / "system_activity.csv")
samples = pd.read_csv(DATA_DIR / "sample_output.csv")

print("\n=== EVIDENCE MANIFEST ===")
print(manifest.head(5).to_string(index=False))

print("\n=== EVIDENCE PATH CHECK ===")
found = 0
missing = 0

for _, row in manifest.iterrows():
    path = Path(str(row["file_path"]))
    if path.is_absolute():
        full_path = path
    else:
        full_path = DATA_DIR / path

    if full_path.exists():
        found += 1
    else:
        # Also check paths relative to the evidence folder
        alternative = EVIDENCE_DIR / path.name
        if alternative.exists():
            found += 1
        else:
            missing += 1
            print("Missing:", row["file_path"])

print(f"\nManifest files found: {found}")
print(f"Manifest files missing: {missing}")

print("\n=== ACTIVITY EVENT TYPES ===")
print(activity["event_type"].value_counts().to_string())

print("\n=== SAMPLE ANSWER STATUS COUNTS ===")
print(samples["deletion_status"].value_counts().to_string())
