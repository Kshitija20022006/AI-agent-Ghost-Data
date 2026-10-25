
import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

files_to_check = [
    "deletion_requests.csv",
    "deletion_rules.csv",
    "user_identities.csv",
    "user_audit_log.csv",
    "system_activity.csv",
    "evidence_files.csv",
    "sample_deletion_requests.csv",
    "sample_output.csv",
]

for filename in files_to_check:
    path = DATA_DIR / filename

    print("\n" + "=" * 65)
    print("FILE:", filename)

    if not path.exists():
        print("NOT FOUND:", path)
        continue

    try:
        df = pd.read_csv(path)

        print("Rows:", len(df))
        print("Columns:", list(df.columns))

        # Show a few example rows, without dumping the entire file
        print(df.head(3).to_string(index=False))

    except Exception as error:
        print("Could not read file:", error)
