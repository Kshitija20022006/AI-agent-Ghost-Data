

from pathlib import Path
import json
import re
import pandas as pd

PROJECT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_DIR / "data"
EVIDENCE_DIR = DATA_DIR / "evidence"
OUTPUT_PATH = DATA_DIR / "output.csv"

REQUIRED_FILES = [
    "deletion_requests.csv",
    "deletion_rules.csv",
    "user_identities.csv",
    "user_audit_log.csv",
    "system_activity.csv",
    "evidence_files.csv",
]

VALID_STATUSES = {"COMPLETE", "INCOMPLETE", "NOT_APPLICABLE"}
SUCCESS_VALUES = {"SUCCESS", "SUCCEEDED", "OK", "COMPLETED", "TRUE"}
FAILURE_VALUES = {"FAILED", "FAILURE", "ERROR", "PARTIAL"}
DELETE_EVENTS = {"DELETE_RECORD", "DELETE", "ERASE", "PURGE"}
REDACT_EVENTS = {"REDACT_RECORD", "REDACT", "REDACTION"}
ANONYMIZE_EVENTS = {"ANONYMIZE_RECORD", "ANONYMIZE", "ANONYMIZATION"}
RETAIN_EVENTS = {"RETAIN_RECORD", "RETAIN", "LEGAL_HOLD"}
RESTORE_EVENTS = {
    "SYNC_RECORD", "SYNC", "IMPORT", "RESTORE_BACKUP", "RESTORE",
    "INDEX_RECORD", "INDEX", "REFRESH_CACHE", "RECREATE_RECORD",
    "CREATE_EXPORT",
}


def read_csv(filename, required=True):
    path = DATA_DIR / filename
    if not path.exists():
        if required:
            raise FileNotFoundError(f"Missing required file: {path}")
        return pd.DataFrame()

    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except Exception as exc:
        raise RuntimeError(f"Unable to read {filename}: {exc}") from exc


def val(row, *names):
    """Return the first non-empty value from a row."""
    for name in names:
        if name in row.index:
            value = str(row[name]).strip()
            if value:
                return value
    return ""


def norm(value):
    return re.sub(r"[^A-Z0-9]+", "_", str(value).upper()).strip("_")


def exact_match(needle, haystack):
    needle = str(needle).strip()
    if len(needle) < 4:
        return False
    pattern = (
        r"(?<![A-Za-z0-9_])"
        + re.escape(needle)
        + r"(?![A-Za-z0-9_])"
    )
    return re.search(pattern, str(haystack), re.IGNORECASE) is not None


def build_identity_index(identities, audit_log):
    """
    Map known current and historical identifiers to stable user IDs.
    Only use fields actually present in the input files.
    """
    index = {}

    for _, row in identities.iterrows():
        user_id = val(row, "user_id", "customer_id", "account_id")
        if not user_id:
            continue

        for column in (
            "user_id", "customer_id", "account_id",
            "email", "old_email", "previous_email",
            "phone", "old_phone", "email_hash",
        ):
            identifier = val(row, column)
            if identifier:
                index.setdefault(identifier.casefold(), set()).add(user_id)

    for _, row in audit_log.iterrows():
        user_id = val(row, "user_id", "customer_id", "account_id")
        if not user_id:
            continue

        for column in (
            "old_value", "new_value", "old_email", "new_email",
            "email", "phone", "identifier",
        ):
            identifier = val(row, column)
            if identifier:
                index.setdefault(identifier.casefold(), set()).add(user_id)

    return index


def resolve_user_ids(request, identity_index, identities):
    user_id = val(request, "user_id", "customer_id", "account_id")
    email = val(request, "email", "email_address", "requested_email")
    users = set()

    if user_id:
        users.update(identity_index.get(user_id.casefold(), set()))
        users.add(user_id)

    if email:
        users.update(identity_index.get(email.casefold(), set()))

    # Exact email fallback, if that column exists.
    if email and "email" in identities.columns:
        matches = identities[
            identities["email"].str.casefold() == email.casefold()
        ]
        for _, row in matches.iterrows():
            matched_id = val(row, "user_id", "customer_id", "account_id")
            if matched_id:
                users.add(matched_id)

    return users


def make_identifier_set(request, user_ids, identities, audit_log):
    identifiers = set()

    for column in (
        "user_id", "customer_id", "account_id",
        "email", "email_address", "requested_email",
        "phone", "email_hash",
    ):
        value = val(request, column)
        if value:
            identifiers.add(value)

    for table in (identities, audit_log):
        if table.empty:
            continue

        id_column = next(
            (c for c in ("user_id", "customer_id", "account_id")
             if c in table.columns),
            None,
        )
        if id_column is None:
            continue

        selected = table[
            table[id_column].astype(str).str.casefold().isin(
                {u.casefold() for u in user_ids}
            )
        ]

        for _, row in selected.iterrows():
            for column in (
                "email", "old_email", "new_email",
                "previous_email", "phone", "old_phone",
                "email_hash", "old_value", "new_value",
                "identifier",
            ):
                value = val(row, column)
                if value:
                    identifiers.add(value)

    return identifiers


def row_text(row):
    return " ".join(str(value) for value in row.tolist())


def find_index_rows(table, case_id):
    if table.empty or "case_id" not in table.columns:
        return pd.DataFrame()

    return table[table["case_id"].astype(str) == str(case_id)]


def find_related_activity(activities, identifiers, user_ids):
    if activities.empty:
        return pd.DataFrame()

    matched = []
    for _, row in activities.iterrows():
        row_user = val(row, "user_id", "customer_id", "account_id")
        if row_user and row_user.casefold() in {
            item.casefold() for item in user_ids
        }:
            matched.append(row)
            continue

        searchable = row_text(row)
        if any(exact_match(identifier, searchable)
               for identifier in identifiers):
            matched.append(row)

    if not matched:
        return pd.DataFrame(columns=activities.columns)

    return pd.DataFrame(matched).drop_duplicates().reset_index(drop=True)


def build_rule_steps(rules):
    steps = []

    for _, rule in rules.iterrows():
        category = val(rule, "data_category", "category", "data_type")
        action = norm(val(rule, "required_action", "action", "disposition"))
        rule_id = val(rule, "rule_id", "policy_id", "id")
        condition = val(rule, "condition", "retention_condition", "notes")

        if not category or not action:
            continue

        if action in {"DELETE", "ERASE", "PURGE"}:
            operation = "VERIFY_RECORD_ABSENT"
        elif action in {"REDACT", "REDACTION"}:
            operation = "VERIFY_DIRECT_IDENTIFIERS_REDACTED"
        elif action in {"ANONYMIZE", "ANONYMIZATION"}:
            operation = "VERIFY_RECORD_ANONYMIZED"
        elif action in {"RETAIN", "LEGAL_HOLD", "PRESERVE"}:
            operation = "VERIFY_REQUIRED_RETENTION_AND_ACCESS_RESTRICTIONS"
        else:
            operation = "REVIEW_RETENTION_RULE"

        steps.append({
            "step_no": 0,
            "phase": "POLICY_CHECK",
            "system_id": category,
            "resource_id": "",
            "operation": operation,
            "state": "REQUIRES_VERIFICATION",
            "rule_id": rule_id,
            "condition": condition,
        })

    return steps


def event_to_step(row):
    event = norm(val(
        row, "event_type", "action", "activity_type",
        "operation", "event"
    ))
    result = norm(val(
        row, "result", "status", "outcome", "event_status"
    ))
    resource = val(row, "resource_id", "record_id", "object_id")
    system = val(
        row, "target_system", "system_id", "system",
        "source_system", "platform"
    ) or "unknown_system"
    event_id = val(row, "event_id", "activity_id", "id")

    success = result in SUCCESS_VALUES
    failed = result in FAILURE_VALUES

    if event in DELETE_EVENTS:
        operation = "VERIFY_RECORD_ABSENT"
        state = "DELETE_REPORTED_SUCCESS" if success else (
            "DELETE_FAILED_OR_UNCONFIRMED"
        )
    elif event in REDACT_EVENTS:
        operation = "VERIFY_DIRECT_IDENTIFIERS_REDACTED"
        state = "REDACTION_REPORTED_SUCCESS" if success else (
            "REDACTION_FAILED_OR_UNCONFIRMED"
        )
    elif event in ANONYMIZE_EVENTS:
        operation = "VERIFY_RECORD_ANONYMIZED"
        state = "ANONYMIZATION_REPORTED_SUCCESS" if success else (
            "ANONYMIZATION_FAILED_OR_UNCONFIRMED"
        )
    elif event in RETAIN_EVENTS:
        operation = "VERIFY_REQUIRED_RETENTION_AND_ACCESS_RESTRICTIONS"
        state = "RETENTION_REPORTED"
    elif event in RESTORE_EVENTS:
        operation = "INVESTIGATE_SYNC_IMPORT_INDEX_OR_RESTORE_PATH"
        state = "POTENTIAL_RECREATION_PATH"
    else:
        operation = "REVIEW_ACTIVITY_AND_VERIFY_DATA_STATE"
        state = "ACTION_FAILED" if failed else "REVIEW_REQUIRED"

    return {
        "step_no": 0,
        "phase": "REMEDIATION" if (
            failed or event in RESTORE_EVENTS or not success
        ) else "VERIFICATION",
        "system_id": system,
        "resource_id": resource,
        "operation": operation,
        "state": state,
        "evidence_id": event_id,
        "event_type": event,
        "event_time": val(
            row, "event_time", "timestamp", "created_at", "activity_time"
        ),
        "reported_result": result,
    }


def build_case(request, rules, identities, audit_log, activities,
               identity_matches, evidence_matches, identity_index):
    case_id = val(request, "case_id", "request_id")
    if not case_id:
        raise ValueError("A deletion request has no case_id/request_id.")

    # Respect explicit non-applicable cases only when the request clearly says so.
    applicability = norm(val(
        request, "applicability", "request_type",
        "deletion_type", "status"
    ))
    if applicability in {
        "NOT_APPLICABLE", "N_A", "NOT_APPLICABLE_REQUEST"
    }:
        return {
            "case_id": case_id,
            "deletion_status": "NOT_APPLICABLE",
            "steps_json": json.dumps([], separators=(",", ":")),
        }

    user_ids = resolve_user_ids(request, identity_index, identities)
    identifiers = make_identifier_set(
        request, user_ids, identities, audit_log
    )

    identity_rows = find_index_rows(identity_matches, case_id)
    evidence_rows = find_index_rows(evidence_matches, case_id)
    related_activity = find_related_activity(
        activities, identifiers, user_ids
    )

    steps = []
    seen = set()

    for _, row in related_activity.iterrows():
        step = event_to_step(row)
        key = (
            step["event_type"], step["system_id"], step["resource_id"],
            step["event_time"], step["reported_result"],
        )
        if key not in seen:
            seen.add(key)
            steps.append(step)

    # Keep index evidence visible as evidence to review; a filename alone
    # does not prove a deletion or retention action succeeded.
    for _, row in evidence_rows.iterrows():
        match_type = norm(val(row, "match_type", "source_type"))
        if match_type in {"SYSTEM_ACTIVITY", "ACTIVITY"}:
            continue

        steps.append({
            "step_no": 0,
            "phase": "EVIDENCE_REVIEW",
            "system_id": val(row, "system_id", "source_system", "evidence_path")
                         or "evidence_file",
            "resource_id": val(row, "resource_id", "record_id"),
            "operation": "INSPECT_EVIDENCE_AND_VERIFY_CURRENT_STATE",
            "state": "EVIDENCE_MATCH_REQUIRES_REVIEW",
            "evidence_id": val(row, "file_id", "evidence_id", "evidence_path"),
            "match_type": match_type,
        })

    if not user_ids:
        steps.insert(0, {
            "step_no": 0,
            "phase": "INVESTIGATION",
            "system_id": "identity_resolution",
            "resource_id": "",
            "operation": "RESOLVE_CURRENT_AND_HISTORICAL_IDENTIFIERS",
            "state": "IDENTITY_UNRESOLVED",
            "evidence_id": "",
        })

    if identity_rows.empty:
        steps.append({
            "step_no": 0,
            "phase": "INVESTIGATION",
            "system_id": "identity_index",
            "resource_id": "",
            "operation": "REVIEW_IDENTITY_MATCHES",
            "state": "NO_CASE_SPECIFIC_IDENTITY_INDEX_ROW",
            "evidence_id": "",
        })

    if not evidence_rows.empty:
        temporal_values = []
        for _, row in evidence_rows.iterrows():
            temporal = val(
                row, "temporal_relation", "time_relation", "relation_to_request"
            )
            if temporal:
                temporal_values.append(norm(temporal))
        if not temporal_values or all(
            "UNKNOWN" in item or "UNSURE" in item
            for item in temporal_values
        ):
            steps.append({
                "step_no": 0,
                "phase": "INVESTIGATION",
                "system_id": "evidence_timeline",
                "resource_id": "",
                "operation": "ESTABLISH_EVIDENCE_TIMELINE",
                "state": "TEMPORAL_RELATION_UNKNOWN",
                "evidence_id": "",
            })

    # Add policy tasks for categories with retention/deletion requirements.
    steps.extend(build_rule_steps(rules))

    # Always inspect sync/import/restore routes. They can reintroduce data
    # even when a deletion event is recorded as successful.
    steps.append({
        "step_no": 0,
        "phase": "REMEDIATION",
        "system_id": "sync_import_restore",
        "resource_id": "",
        "operation": "VERIFY_UPSTREAM_SYNC_IMPORT_REPLICA_AND_RESTORE_PATHS",
        "state": "REQUIRES_VERIFICATION",
        "evidence_id": "",
    })

    for number, step in enumerate(steps, start=1):
        step["step_no"] = number

    # Conservative classification: COMPLETE requires clear evidence for
    # all relevant policy obligations, not merely a successful delete event.
    all_events = [
        norm(val(row, "event_type", "action", "activity_type", "operation"))
        for _, row in related_activity.iterrows()
    ]
    all_results = [
        norm(val(row, "result", "status", "outcome", "event_status"))
        for _, row in related_activity.iterrows()
    ]

    has_successful_delete = any(
        event in DELETE_EVENTS and result in SUCCESS_VALUES
        for event, result in zip(all_events, all_results)
    )
    has_failed_action = any(
        result in FAILURE_VALUES for result in all_results
    )
    has_recreation_path = any(
        event in RESTORE_EVENTS for event in all_events
    )

    # No direct proof of every required category means INCOMPLETE.
    # Do not infer NOT_APPLICABLE from a missing identity match.
    if (
        user_ids
        and has_successful_delete
        and not has_failed_action
        and not has_recreation_path
        and not evidence_rows.empty
        and not identity_rows.empty
    ):
        # Evidence still needs to establish policy compliance and timeline.
        # This generic implementation cannot reliably prove that from unknown
        # schemas, so keep the status conservative unless a human verifies it.
        status = "INCOMPLETE"
    else:
        status = "INCOMPLETE"

    return {
        "case_id": case_id,
        "deletion_status": status,
        "steps_json": json.dumps(steps, ensure_ascii=False, separators=(",", ":")),
    }


def main():
    print("=" * 60)
    print("GHOST DATA DELETION AUDIT AGENT")
    print("=" * 60)

    data = {name.removesuffix(".csv"): read_csv(name)
            for name in REQUIRED_FILES}

    requests = data["deletion_requests"]
    rules = data["deletion_rules"]
    identities = data["user_identities"]
    audit_log = data["user_audit_log"]
    activities = data["system_activity"]

    identity_matches = read_csv("identity_matches.csv", required=False)
    evidence_matches = read_csv("evidence_matches.csv", required=False)

    case_column = "case_id" if "case_id" in requests.columns else "request_id"
    if case_column not in requests.columns:
        raise ValueError(
            "deletion_requests.csv must contain case_id or request_id."
        )

    requests = requests.copy()
    requests["case_id"] = requests[case_column].astype(str).str.strip()

    if requests["case_id"].eq("").any():
        raise ValueError("Found request rows with empty case IDs.")
    if requests["case_id"].duplicated().any():
        raise ValueError("deletion_requests.csv contains duplicate case IDs.")

    identity_index = build_identity_index(identities, audit_log)

    print(f"Deletion requests: {len(requests)}")
    print(f"Deletion rules: {len(rules)}")
    print(f"Identity records: {len(identities)}")
    print(f"Audit log records: {len(audit_log)}")
    print(f"System activity records: {len(activities)}")
    print(f"Identity index matches: {len(identity_matches)}")
    print(f"Evidence index matches: {len(evidence_matches)}")

    results = []
    for count, (_, request) in enumerate(requests.iterrows(), start=1):
        results.append(build_case(
            request, rules, identities, audit_log, activities,
            identity_matches, evidence_matches, identity_index
        ))
        if count % 50 == 0 or count == len(requests):
            print(f"Processed {count}/{len(requests)} requests")

    output = pd.DataFrame(
        results,
        columns=["case_id", "deletion_status", "steps_json"]
    )

    if output["case_id"].duplicated().any():
        raise ValueError("Output contains duplicate case IDs.")
    if set(output["case_id"]) != set(requests["case_id"]):
        raise ValueError("Output case IDs do not match request IDs.")
    if not output["deletion_status"].isin(VALID_STATUSES).all():
        raise ValueError("Output contains an invalid deletion status.")

    for serialized in output["steps_json"]:
        parsed = json.loads(serialized)
        if not isinstance(parsed, list):
            raise ValueError("steps_json must serialize a JSON list.")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(OUTPUT_PATH, index=False)

    print("\nOutput saved to:", OUTPUT_PATH)
    print("\nStatus counts:")
    print(output["deletion_status"].value_counts().to_string())
    print("\nOutput schema and JSON validation passed.")


if __name__ == "__main__":
    main()
