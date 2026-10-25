
from pathlib import Path
import re
import pandas as pd

# ==================================================
# 1. PROJECT PATHS
# ==================================================

PROJECT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_DIR / "data"
EVIDENCE_DIR = DATA_DIR / "evidence"

# ==================================================
# 2. HELPER FUNCTIONS
# ==================================================

def clean_value(value):
    """Convert a value to clean text."""
    if pd.isna(value):
        return ""
    return str(value).strip()


def normalize_path(path):
    """Normalize a file path for comparison."""
    return str(path).replace("\\", "/").strip().lower()


def contains_identifier(identifier, text):
    """
    Match complete identifiers.

    user_43 matches user_43.
    user_43 does not match user_437.
    user_18 does not match user_180 or user_189.

    For email addresses and IDs, punctuation is preserved.
    """

    identifier = clean_value(identifier)
    text = str(text)

    if not identifier:
        return False

    pattern = (
        r"(?<![A-Za-z0-9_])"
        + re.escape(identifier)
        + r"(?![A-Za-z0-9_])"
    )

    return re.search(
        pattern,
        text,
        flags=re.IGNORECASE
    ) is not None


def find_identifier_position(identifier, text):
    """Return the first position of an exact identifier."""

    identifier = clean_value(identifier)

    if not identifier:
        return None

    pattern = (
        r"(?<![A-Za-z0-9_])"
        + re.escape(identifier)
        + r"(?![A-Za-z0-9_])"
    )

    match = re.search(
        pattern,
        str(text),
        flags=re.IGNORECASE
    )

    if match:
        return match.start()

    return None


def get_temporal_relation(event_time, audit_at):
    """
    Compare timestamps when both are available.

    This is a time comparison only. It does not establish
    that an event proves deletion or continued data existence.
    """

    event_time = clean_value(event_time)
    audit_at = clean_value(audit_at)

    if not event_time or not audit_at:
        return "UNKNOWN"

    event = pd.to_datetime(
        event_time,
        utc=True,
        errors="coerce"
    )

    audit = pd.to_datetime(
        audit_at,
        utc=True,
        errors="coerce"
    )

    if pd.isna(event) or pd.isna(audit):
        return "UNKNOWN"

    if event <= audit:
        return "BEFORE_OR_AT_AUDIT"

    return "AFTER_AUDIT"


# ==================================================
# 3. READ INPUT CSV FILES
# ==================================================

print("Reading input CSV files...")

required_files = [
    DATA_DIR / "deletion_requests.csv",
    DATA_DIR / "sample_deletion_requests.csv",
    DATA_DIR / "user_identities.csv",
    DATA_DIR / "system_activity.csv",
    DATA_DIR / "user_audit_log.csv",
]

for file_path in required_files:
    if not file_path.exists():
        raise FileNotFoundError(
            f"Required file not found: {file_path}"
        )

main_requests = pd.read_csv(
    DATA_DIR / "deletion_requests.csv",
    dtype=str
).fillna("")

sample_requests = pd.read_csv(
    DATA_DIR / "sample_deletion_requests.csv",
    dtype=str
).fillna("")

requests = pd.concat(
    [main_requests, sample_requests],
    ignore_index=True
)

requests["case_id"] = requests["case_id"].map(clean_value)

# Keep the main request when a case ID occurs in both files.
requests = requests.drop_duplicates(
    subset=["case_id"],
    keep="first"
).reset_index(drop=True)

identities = pd.read_csv(
    DATA_DIR / "user_identities.csv",
    dtype=str
).fillna("")

activities = pd.read_csv(
    DATA_DIR / "system_activity.csv",
    dtype=str
).fillna("")

audit_log = pd.read_csv(
    DATA_DIR / "user_audit_log.csv",
    dtype=str
).fillna("")

print("Main requests:", len(main_requests))
print("Sample requests:", len(sample_requests))
print("Unique requests indexed:", len(requests))

# ==================================================
# 4. READ EVIDENCE FILES
# ==================================================

print("\nReading evidence files...")

if not EVIDENCE_DIR.exists():
    raise FileNotFoundError(
        f"Evidence folder not found: {EVIDENCE_DIR}"
    )

evidence_paths = sorted(
    path for path in EVIDENCE_DIR.rglob("*")
    if path.is_file()
)

evidence_contents = []

for path in evidence_paths:
    try:
        content = path.read_text(
            encoding="utf-8",
            errors="ignore"
        )

        evidence_contents.append({
            "relative_path": str(
                path.relative_to(DATA_DIR)
            ).replace("\\", "/"),
            "content": content
        })

    except OSError as error:
        print(
            f"[WARNING] Cannot read {path}: {error}"
        )

print("Evidence files readable:", len(evidence_contents))

# ==================================================
# 5. LOAD EVIDENCE FILE MANIFEST
# ==================================================

manifest_path = DATA_DIR / "evidence_files.csv"
file_id_by_path = {}

if manifest_path.exists():
    manifest = pd.read_csv(
        manifest_path,
        dtype=str
    ).fillna("")

    for _, row in manifest.iterrows():
        file_id = clean_value(row.get("file_id", ""))
        file_path = clean_value(row.get("file_path", ""))

        if file_id and file_path:
            file_id_by_path[
                normalize_path(file_path)
            ] = file_id

# ==================================================
# 6. INDEX IDENTITIES BY EMAIL
# ==================================================

identity_by_email = {}

for _, identity in identities.iterrows():

    email = clean_value(
        identity.get("email", "")
    ).lower()

    if email:
        identity_by_email.setdefault(
            email, []
        ).append(identity)

# ==================================================
# 7. PREPARE OUTPUT RESULTS
# ==================================================

identity_results = []
evidence_results = []

# ==================================================
# 8. PROCESS EACH DELETION REQUEST
# ==================================================

print("\nSearching for identity and evidence matches...")

for request_number, (_, request) in enumerate(
    requests.iterrows(),
    start=1
):

    case_id = clean_value(
        request.get("case_id", "")
    )

    request_email = clean_value(
        request.get("email", "")
    ).lower()

    audit_at = clean_value(
        request.get("audit_at", "")
    )

    matched_identities = identity_by_email.get(
        request_email, []
    )

    # --------------------------------------------------
    # 8A. EXACT EMAIL IDENTITY MATCH
    # --------------------------------------------------

    for identity in matched_identities:

        user_id = clean_value(
            identity.get("user_id", "")
        )

        identity_name = clean_value(
            identity.get("name", "")
        )

        identity_results.append({
            "case_id": case_id,
            "request_email": request_email,
            "user_id": user_id,
            "identity_name": identity_name,
            "identity_match_type": "EXACT_EMAIL"
        })

        # Store identifiers belonging to this identity.
        identifiers = {}

        base_identifiers = {
            "request_email": request_email,
            "user_id": user_id,
            "name": identity_name,
            "phone": clean_value(
                identity.get("phone", "")
            ),
            "email_hash": clean_value(
                identity.get("email_hash", "")
            )
        }

        for label, value in base_identifiers.items():
            if value:
                identifiers[label] = value

        # --------------------------------------------------
        # 8B. HISTORICAL IDENTIFIERS FROM AUDIT LOG
        # --------------------------------------------------

        if (
            user_id
            and "user_id" in audit_log.columns
        ):

            user_audits = audit_log[
                audit_log["user_id"].map(clean_value)
                == user_id
            ]

            for _, audit in user_audits.iterrows():

                audit_id = clean_value(
                    audit.get("audit_id", "")
                )

                for field in ["old_value", "new_value"]:

                    value = clean_value(
                        audit.get(field, "")
                    )

                    if not value:
                        continue

                    # Only add historical values that look
                    # like email addresses or exact user IDs.
                    if (
                        "@" in value
                        or value.lower() == user_id.lower()
                    ):
                        identifiers[
                            f"audit_{audit_id}_{field}"
                        ] = value

        # --------------------------------------------------
        # 8C. FIND RELATED SYSTEM ACTIVITIES
        # --------------------------------------------------

        related_activities = []

        for _, activity in activities.iterrows():

            searchable = " ".join([
                clean_value(activity.get("details", "")),
                clean_value(activity.get("resource_id", "")),
                clean_value(activity.get("source_system", "")),
                clean_value(activity.get("target_system", ""))
            ])

            matched_terms = [
                value
                for value in identifiers.values()
                if len(value) >= 5
                and contains_identifier(value, searchable)
            ]

            if not matched_terms:
                continue

            related_activities.append(activity)

            event_time = clean_value(
                activity.get("event_time", "")
            )

            evidence_results.append({
                "case_id": case_id,
                "audit_at": audit_at,
                "match_type": "SYSTEM_ACTIVITY",
                "evidence_path": "",
                "file_id": "",
                "matched_identifier": matched_terms[0],
                "activity_id": clean_value(
                    activity.get("activity_id", "")
                ),
                "resource_id": clean_value(
                    activity.get("resource_id", "")
                ),
                "event_time": event_time,
                "event_type": clean_value(
                    activity.get("event_type", "")
                ),
                "reported_result": clean_value(
                    activity.get("reported_result", "")
                ),
                "temporal_relation": get_temporal_relation(
                    event_time,
                    audit_at
                ),
                "snippet": clean_value(
                    activity.get("details", "")
                )[:500]
            })

        # --------------------------------------------------
        # 8D. ADD RESOURCES FROM RELATED ACTIVITIES
        # --------------------------------------------------

        for activity in related_activities:

            resource_id = clean_value(
                activity.get("resource_id", "")
            )

            if resource_id:
                identifiers[
                    f"resource_{resource_id}"
                ] = resource_id

        # --------------------------------------------------
        # 8E. SEARCH EVIDENCE FILES
        # --------------------------------------------------

        for evidence in evidence_contents:

            content = evidence["content"]
            relative_path = evidence["relative_path"]

            for label, identifier in identifiers.items():

                if len(identifier) < 5:
                    continue

                position = find_identifier_position(
                    identifier,
                    content
                )

                if position is None:
                    continue

                start = max(
                    0,
                    position - 150
                )

                end = min(
                    len(content),
                    position + len(identifier) + 250
                )

                snippet = content[start:end]
                snippet = (
                    snippet.replace("\n", " ")
                    .replace("\r", " ")
                )

                file_id = file_id_by_path.get(
                    normalize_path(relative_path),
                    ""
                )

                evidence_results.append({
                    "case_id": case_id,
                    "audit_at": audit_at,
                    "match_type": "EVIDENCE_FILE",
                    "evidence_path": relative_path,
                    "file_id": file_id,
                    "matched_identifier": identifier,
                    "activity_id": "",
                    "resource_id": (
                        identifier
                        if label.startswith("resource_")
                        else ""
                    ),
                    "event_time": "",
                    "event_type": "",
                    "reported_result": "",
                    "temporal_relation": "UNKNOWN",
                    "snippet": snippet[:500]
                })

                # One match per identifier per file.
                break

    if request_number % 50 == 0:
        print(
            f"Processed {request_number} "
            f"of {len(requests)} requests..."
        )

# ==================================================
# 9. BUILD DATAFRAMES
# ==================================================

identity_columns = [
    "case_id",
    "request_email",
    "user_id",
    "identity_name",
    "identity_match_type"
]

evidence_columns = [
    "case_id",
    "audit_at",
    "match_type",
    "evidence_path",
    "file_id",
    "matched_identifier",
    "activity_id",
    "resource_id",
    "event_time",
    "event_type",
    "reported_result",
    "temporal_relation",
    "snippet"
]

identity_df = pd.DataFrame(
    identity_results,
    columns=identity_columns
)

evidence_df = pd.DataFrame(
    evidence_results,
    columns=evidence_columns
)

# ==================================================
# 10. SAVE REPORTS
# ==================================================

identity_output = DATA_DIR / "identity_matches.csv"
evidence_output = DATA_DIR / "evidence_matches.csv"

identity_df.to_csv(
    identity_output,
    index=False
)

evidence_df.to_csv(
    evidence_output,
    index=False
)

# ==================================================
# 11. PRINT SUMMARY
# ==================================================

print("\n" + "=" * 60)
print("EVIDENCE INDEX SUMMARY")
print("=" * 60)

print("Main requests:", len(main_requests))
print("Sample requests:", len(sample_requests))
print("Unique requests indexed:", len(requests))

print(
    "Requests with exact identity matches:",
    identity_df["case_id"].nunique()
)

print("Identity matches:", len(identity_df))
print("Evidence/activity matches:", len(evidence_df))

if not evidence_df.empty:

    print("\nMatch types:")
    print(
        evidence_df["match_type"]
        .value_counts()
        .to_string()
    )

    print("\nCases with the most matches:")
    print(
        evidence_df.groupby("case_id")
        .size()
        .sort_values(ascending=False)
        .head(10)
        .to_string()
    )

    print("\nTemporal relation summary:")
    print(
        evidence_df["temporal_relation"]
        .value_counts()
        .to_string()
    )

print("\nReports saved:")
print(identity_output)
print(evidence_output)

print("\nIMPORTANT:")
print("1. A match is a lead, not proof of deletion.")
print("2. Verify the customer and resource carefully.")
print("3. Check evidence timestamps against audit_at.")
print("4. A reported SUCCESS is not independent proof.")
print("5. This script does not create final output.csv.")

print("\nIndexing finished.")
