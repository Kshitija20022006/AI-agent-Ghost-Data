
import json
import re
import pandas as pd
from pathlib import Path

# Locate the project and data folders
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
EVIDENCE_DIR = DATA_DIR / "evidence"

# Change this to investigate another case
CASE_ID = "case_33"

# Load the CSV files
requests = pd.read_csv(DATA_DIR / "deletion_requests.csv")
identities = pd.read_csv(DATA_DIR / "user_identities.csv")
activities = pd.read_csv(DATA_DIR / "system_activity.csv")

# Find the requested deletion case
case_rows = requests[requests["case_id"] == CASE_ID]

if case_rows.empty:
    raise ValueError(f"Case not found: {CASE_ID}")

case = case_rows.iloc[0]
email = str(case["email"]).strip()

print("=" * 60)
print("CASE:", CASE_ID)
print("EMAIL:", email)
print("REPORTED STATUS:", case["reported_status"])
print("AUDIT DATE:", case["audit_at"])

# Find the customer's identity using an exact email match
email_matches = identities[
    identities["email"].fillna("").str.strip().str.casefold()
    == email.casefold()
]

user_ids = set(email_matches["user_id"].dropna().astype(str))

if email_matches.empty:
    print("\nNo exact identity match found.")
else:
    print("\nMATCHING CUSTOMER IDENTITIES:")
    print(email_matches.to_string(index=False))

# Search activity records for this email or its user IDs
resource_ids = set()

for _, activity in activities.iterrows():
    details = str(activity.get("details", ""))
    resource_id = str(activity.get("resource_id", "")).strip()

    matched = email.casefold() in details.casefold()

    for user_id in user_ids:
        if re.search(
            r"(?<![A-Za-z0-9_])"
            + re.escape(user_id)
            + r"(?![A-Za-z0-9_])",
            details,
            flags=re.IGNORECASE
        ):
            matched = True

    if matched and resource_id and resource_id.lower() != "nan":
        resource_ids.add(resource_id)

print("\nRELATED RESOURCE IDS:")
for resource_id in sorted(resource_ids):
    print("-", resource_id)

# Search terms include the email, user IDs and linked resource IDs
search_terms = {email}
search_terms.update(user_ids)
search_terms.update(resource_ids)

# Also search for historical identifiers in the identity record
if not email_matches.empty:
    for column in ["name", "phone", "email_hash"]:
        if column in email_matches.columns:
            for value in email_matches[column].dropna().astype(str):
                value = value.strip()
                if value and value.lower() != "nan":
                    search_terms.add(value)

print("\nSEARCHING JSON EVIDENCE...")
total_hits = 0

for file_path in EVIDENCE_DIR.rglob("*.json"):
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            data = json.load(file)

        content = json.dumps(data, ensure_ascii=False, indent=2)

        for line_number, line in enumerate(content.splitlines(), start=1):
            for term in search_terms:
                pattern = (
                    r"(?<![A-Za-z0-9_@.+-])"
                    + re.escape(term)
                    + r"(?![A-Za-z0-9_@.+-])"
                )

                if re.search(pattern, line, re.IGNORECASE):
                    print(
                        f"\nFILE: {file_path.name}"
                        f"\nLINE: {line_number}"
                        f"\nMATCH: {term}"
                        f"\nCONTENT: {line.strip()}"
                    )
                    total_hits += 1
                    break

    except (OSError, json.JSONDecodeError) as error:
        print(f"\nCould not read {file_path.name}: {error}")

print("\n" + "=" * 60)
print("TOTAL MATCHING LINES:", total_hits)
print("Evidence search completed.")


print("Evidence folder:", EVIDENCE_DIR)
print("Evidence folder exists:", EVIDENCE_DIR.exists())

json_files = list(EVIDENCE_DIR.rglob("*.json"))

print("JSON files found:", len(json_files))

for file_path in json_files:
    print(file_path.name)


    #search_all_evidence.py


    
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
EVIDENCE_DIR = BASE_DIR / "data" / "evidence"

# Case 33 identifiers
search_terms = [
    "ingrid.dahl@outlook.com",
    "user_18",
    "export_1260",
    "export_1842",
    "0649eddaba37af918d82b64da379e6623d34cf290b2a26ecbe53bafc1484f8af"
]

# Search text-based evidence formats
extensions = {
    ".json", ".sql", ".log", ".txt", ".csv",
    ".xml", ".html", ".md", ".yaml", ".yml"
}

total_files = 0
total_matches = 0

print("Searching evidence folder:", EVIDENCE_DIR)

for file_path in EVIDENCE_DIR.rglob("*"):
    if not file_path.is_file():
        continue

    if file_path.suffix.lower() not in extensions:
        continue

    total_files += 1

    try:
        content = file_path.read_text(
            encoding="utf-8",
            errors="replace"
        )

        lines = content.splitlines()

        for line_number, line in enumerate(lines, start=1):
            matched_terms = []

            for term in search_terms:
                pattern = (
                    r"(?<![A-Za-z0-9_@.+-])"
                    + re.escape(term)
                    + r"(?![A-Za-z0-9_@.+-])"
                )

                if re.search(pattern, line, re.IGNORECASE):
                    matched_terms.append(term)

            if matched_terms:
                print("\nFile:", file_path.name)
                print("Line:", line_number)
                print("Matched:", ", ".join(matched_terms))
                print("Text:", line.strip()[:500])
                total_matches += 1

    except OSError as error:
        print("Could not read:", file_path.name, error)

print("\n========== SUMMARY ==========")
print("Files searched:", total_files)
print("Matching lines:", total_matches)
