
from pathlib import Path
import pandas as pd
import json
import re

# Find the main project folder automatically
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
EVIDENCE_DIR = DATA_DIR / "evidence"

REQUESTS_FILE = DATA_DIR / "deletion_requests.csv"
IDENTITIES_FILE = DATA_DIR / "user_identities.csv"
AUDIT_FILE = DATA_DIR / "user_audit_log.csv"
ACTIVITY_FILE = DATA_DIR / "system_activity.csv"
MANIFEST_FILE = DATA_DIR / "evidence_files.csv"


def load_csv(path):
    """Load a CSV safely and clean its column names."""
    if not path.exists():
        print(f"[ERROR] File not found: {path}")
        return None

    try:
        df = pd.read_csv(path, dtype=str, keep_default_na=False,
                         encoding="utf-8-sig")
        df.columns = [
            str(column).strip().replace("\ufeff", "")
            for column in df.columns
        ]
        return df
    except Exception as error:
        print(f"[ERROR] Could not read {path.name}: {error}")
        return None


def clean(value):
    """Remove extra spaces and normalize text for comparisons."""
    return str(value).strip().casefold()


def find_column(df, column_name):
    """Find a column without being affected by capitalization."""
    for column in df.columns:
        if clean(column) == clean(column_name):
            return column
    return None


def print_section(title):
    print("\n" + "=" * 65)
    print(title)
    print("=" * 65)


def print_rows(title, df, limit=30):
    print_section(title)

    if df is None:
        print("Data unavailable.")
        return

    if df.empty:
        print("No matching records found.")
        return

    print(df.head(limit).to_string(index=False))

    if len(df) > limit:
        print(f"\nShowing {limit} of {len(df)} records.")


def search_evidence(search_terms):
    """Search text-based evidence files for relevant identifiers."""
    print_section("EVIDENCE FILE SEARCH")

    if not EVIDENCE_DIR.exists():
        print(f"Evidence folder not found: {EVIDENCE_DIR}")
        return

    terms = {
        clean(term)
        for term in search_terms
        if str(term).strip()
    }

    if not terms:
        print("No identifiers available to search.")
        return

    matches = 0

    for path in EVIDENCE_DIR.rglob("*"):
        if not path.is_file():
            continue

        # Images and PDFs require separate OCR/PDF processing.
        if path.suffix.lower() not in {".txt", ".log", ".sql", ".json", ".csv"}:
            continue

        try:
            content = path.read_text(
                encoding="utf-8",
                errors="ignore"
            )

            found_terms = []

            for term in terms:
                if not term:
                    continue

    # Match complete identifiers, not partial identifiers.
            pattern = (r"(?<![A-Za-z0-9_@.+-])"+ re.escape(term) + r"(?![A-Za-z0-9_@.+-])" )

            if re.search(pattern, content, flags=re.IGNORECASE):
                found_terms.append(term)

                
            if found_terms:
                matches += 1
                print(f"\nFile: {path.relative_to(DATA_DIR)}")
                print("Matching identifiers:", ", ".join(found_terms))

                # Print only relevant lines, not entire evidence files.
                for line_number, line in enumerate(content.splitlines(), 1):
                    if any(term in clean(line) for term in found_terms):
                        print(f"  Line {line_number}: {line[:300]}")

        except Exception as error:
            print(f"Could not inspect {path.name}: {error}")

    if matches == 0:
        print("No matching text evidence found.")


def main():
    print("GHOST DATA AUDIT - CUSTOMER CASE TRACE")
    print(f"Project folder: {BASE_DIR}")
    print(f"Data folder:    {DATA_DIR}")

    # Load all relevant files.
    requests = load_csv(REQUESTS_FILE)
    identities = load_csv(IDENTITIES_FILE)
    audit_log = load_csv(AUDIT_FILE)
    activities = load_csv(ACTIVITY_FILE)
    manifest = load_csv(MANIFEST_FILE)

    if requests is None:
        print("\nCheck that deletion_requests.csv is inside the data folder.")
        return

    case_column = find_column(requests, "case_id")

    if case_column is None:
        print("\n[ERROR] The CSV has no case_id column.")
        print("Actual columns:", requests.columns.tolist())
        return

    # Clean case IDs before searching.
    requests[case_column] = requests[case_column].astype(str).str.strip()

    print_section("DATASET CHECK")
    print("Deletion requests:", len(requests))
    print("CSV columns:", requests.columns.tolist())
    print("First 10 case IDs:", requests[case_column].head(10).tolist())

    case_id = input(
        "\nEnter the exact case ID shown above "
        "(example: case_05): "
    ).strip()

    if not case_id:
        print("No case ID entered.")
        return

    # First try exact match, ignoring capitalization and extra spaces.
    matches = requests[
        requests[case_column].map(clean) == clean(case_id)
    ]

    # If not found, show similar IDs rather than silently guessing.
    if matches.empty:
        print_section("CASE NOT FOUND")
        print(f"No exact match for: {case_id!r}")

        similar = requests[
            requests[case_column].map(clean).str.contains(
                re.escape(clean(case_id)), na=False
            )
        ]

        if not similar.empty:
            print("\nSimilar case IDs:")
            print(similar[[case_column]].head(20).to_string(index=False))
        else:
            print("\nAvailable case IDs:")
            print(requests[case_column].head(30).to_list())

        print("\nCheck that you entered an ID from this dataset.")
        return

    request = matches.iloc[0].to_dict()

    print_section("DELETION REQUEST")
    print(json.dumps(request, indent=2, ensure_ascii=False))

    # Get the customer's email from the deletion request.
    email = ""
    for key, value in request.items():
        if clean(key) == "email":
            email = str(value).strip()
            break

    search_terms = {case_id, email}

    # Find matching customer identities.
    if identities is not None:
        email_column = find_column(identities, "email")
        identity_matches = identities.iloc[0:0].copy()

        if email and email_column:
            identity_matches = identities[
                identities[email_column].map(clean) == clean(email)
            ]

        print_rows("MATCHING USER IDENTITIES", identity_matches)

        # Collect user IDs and other known identifiers.
        for _, row in identity_matches.iterrows():
            for field in ("user_id", "name", "email", "phone", "email_hash"):
                column = find_column(identities, field)
                if column:
                    value = str(row[column]).strip()
                    if value:
                        search_terms.add(value)

    # Search audit history using known customer identifiers.
    if audit_log is not None:
        audit_matches = audit_log.iloc[0:0].copy()

        user_id_column = find_column(audit_log, "user_id")
        if user_id_column and identities is not None:
            identity_user_column = find_column(identities, "user_id")
            if identity_user_column:
                user_ids = set(
                    identity_matches[identity_user_column].map(clean)
                )
                audit_matches = audit_log[
                    audit_log[user_id_column].map(clean).isin(user_ids)
                ]

        print_rows("USER AUDIT HISTORY", audit_matches)

        # Add values from matching audit records for evidence searching.
        for _, row in audit_matches.iterrows():
            for value in row.tolist():
                if value:
                    search_terms.add(str(value).strip())

    # Search system activities for customer identifiers.
    if activities is not None:
        activity_matches = activities.iloc[0:0].copy()

        # Match known identifiers against activity fields.
        activity_columns = [
            find_column(activities, field)
            for field in (
                "resource_id", "details", "source_system",
                "target_system", "event_type"
            )
        ]
        activity_columns = [c for c in activity_columns if c]

        for column in activity_columns:
            mask = activities[column].map(clean).isin(
                {clean(term) for term in search_terms if term}
            )

            # Also search inside details for identifiers embedded in text.
            if clean(column) == "details":
                for term in search_terms:
                    if term:
                        mask = mask | activities[column].map(clean).str.contains(
                            re.escape(clean(term)), na=False
                        )

            activity_matches = pd.concat(
                [activity_matches, activities[mask]]
            ).drop_duplicates()

        print_rows("MATCHING SYSTEM ACTIVITIES", activity_matches)

        for _, row in activity_matches.iterrows():
            resource_column = find_column(activities, "resource_id")
            if resource_column:
                resource = str(row[resource_column]).strip()
                if resource:
                    search_terms.add(resource)

    # Show evidence manifest entries relevant to the files present.
    if manifest is not None:
        print_section("EVIDENCE MANIFEST")
        print(f"Manifest entries: {len(manifest)}")

        path_column = find_column(manifest, "file_path")
        if path_column:
            print("Evidence files listed in manifest:", len(manifest))
            missing = []

            for relative_path in manifest[path_column]:
                if not relative_path:
                    continue

                path = EVIDENCE_DIR / relative_path.replace(
                    "evidence/", "", 1
                ).replace("/", "\\")

                # Also support normal forward-slash paths on Windows.
                path = EVIDENCE_DIR / Path(
                    relative_path.replace("evidence/", "", 1)
                )

                if not path.exists():
                    missing.append(relative_path)

            print("Manifest paths not found:", len(missing))
            for item in missing[:20]:
                print("  ", item)

    # Search local text evidence. This is a lead-finding aid,
    # not proof by itself that a deletion succeeded or failed.
    search_evidence(search_terms)

    print_section("IMPORTANT")
    print("This script traces a case and displays potential evidence.")
    print("It does NOT decide the final deletion status automatically.")
    print("Validate evidence timestamps, system state, retention rules,")
    print("and restore/synchronization risks before generating output.csv.")


if __name__ == "__main__":
    main()
