
import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

case_id = "case_33"

requests = pd.read_csv(DATA_DIR / "deletion_requests.csv", dtype=str).fillna("")
identities = pd.read_csv(DATA_DIR / "user_identities.csv", dtype=str).fillna("")
activities = pd.read_csv(DATA_DIR / "system_activity.csv", dtype=str).fillna("")
audits = pd.read_csv(DATA_DIR / "user_audit_log.csv", dtype=str).fillna("")

request = requests[requests["case_id"] == case_id]

if request.empty:
    print("Case not found:", case_id)
    raise SystemExit

email = request.iloc[0]["email"]
audit_at = request.iloc[0]["audit_at"]

identity = identities[
    identities["email"].str.lower() == email.lower()
]

print("CASE:", case_id)
print("Email:", email)
print("Audit date:", audit_at)

if identity.empty:
    print("\nNo exact identity match found.")
    raise SystemExit

user = identity.iloc[0]
user_id = user["user_id"]

print("User ID:", user_id)
print("Name:", user["name"])

print("\n--- USER AUDIT LOG ---")
audit_matches = audits[
    (audits["user_id"] == user_id)
]

if audit_matches.empty:
    print("No audit rows for this user.")
else:
    print(audit_matches.to_string(index=False))

print("\n--- SYSTEM ACTIVITY ---")
terms = [
    email.lower(),
    user_id.lower(),
    user["email_hash"].lower()
]

mask = activities.apply(
    lambda row: any(
        term and term in " ".join(row.astype(str)).lower()
        for term in terms
    ),
    axis=1
)

activity_matches = activities[mask]

if activity_matches.empty:
    print("No activity rows matched the identifiers.")
else:
    print(activity_matches.to_string(index=False))

print("\nRemember: a match is a clue, not automatic proof.")
