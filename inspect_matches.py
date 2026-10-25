
from pathlib import Path
import pandas as pd

PROJECT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_DIR / "data"

matches = pd.read_csv(
    DATA_DIR / "evidence_matches.csv",
    dtype=str
).fillna("")

sample = pd.read_csv(
    DATA_DIR / "sample_output.csv",
    dtype=str
).fillna("")

requests = pd.read_csv(
    DATA_DIR / "deletion_requests.csv",
    dtype=str
).fillna("")

print("=" * 60)
print("1. SAMPLE OUTPUT EXAMPLES")
print("=" * 60)

for _, row in sample.head(5).iterrows():
    print("\nCase:", row["case_id"])
    print("Status:", row["deletion_status"])
    print("Steps:", row["steps_json"])

print("\n" + "=" * 60)
print("2. EVIDENCE MATCHES FOR SAMPLE CASES")
print("=" * 60)

sample_ids = set(sample["case_id"])

sample_matches = matches[
    matches["case_id"].isin(sample_ids)
]

print("Sample cases with evidence matches:",
      sample_matches["case_id"].nunique())
print("Total sample evidence matches:", len(sample_matches))

for case_id in sorted(sample_ids)[:5]:
    rows = sample_matches[sample_matches["case_id"] == case_id]

    print("\nCase:", case_id)
    if rows.empty:
        print("No indexed evidence matches.")
    else:
        for _, row in rows.head(5).iterrows():
            print(
                "Type:", row["match_type"],
                "| Resource:", row["resource_id"],
                "| Activity:", row["activity_id"],
                "| File:", row["evidence_path"]
            )
            print("Snippet:", row["snippet"][:250])

print("\n" + "=" * 60)
print("3. UNMATCHED REQUESTS")
print("=" * 60)

matched_ids = set(matches["case_id"])
all_ids = set(requests["case_id"])

# Identity matches are a separate report.
identities = pd.read_csv(
    DATA_DIR / "identity_matches.csv",
    dtype=str
).fillna("")

identity_ids = set(identities["case_id"])

unmatched = requests[
    ~requests["case_id"].isin(identity_ids)
]

print("Requests without exact identity match:", len(unmatched))
print(unmatched[["case_id", "email", "reported_status"]]
      .head(15).to_string(index=False))

print("\nInspection complete.")
