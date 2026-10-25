
from pathlib import Path
import json
import subprocess
import sys
import importlib

import pandas as pd


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_DIR / "src"
DATA_DIR = PROJECT_DIR / "data"
OUTPUT_FILE = DATA_DIR / "output.csv"

EXPECTED_COLUMNS = [
    "case_id",
    "deletion_status",
    "steps_json",
]

VALID_STATUSES = {
    "COMPLETE",
    "INCOMPLETE",
    "NOT_APPLICABLE",
}


# ============================================================
# INPUT VALIDATION
# ============================================================

def validate_inputs():
    required_files = [
        "deletion_requests.csv",
        "deletion_rules.csv",
        "user_identities.csv",
        "user_audit_log.csv",
        "system_activity.csv",
        "sample_deletion_requests.csv",
        "sample_output.csv",
    ]

    missing = [
        filename
        for filename in required_files
        if not (DATA_DIR / filename).is_file()
    ]

    if missing:
        raise FileNotFoundError(
            "Missing required input files:\n"
            + "\n".join(missing)
        )

    requests = pd.read_csv(
        DATA_DIR / "deletion_requests.csv",
        dtype=str,
    ).fillna("")

    if "case_id" not in requests.columns:
        raise ValueError(
            "deletion_requests.csv must contain case_id."
        )

    if requests["case_id"].duplicated().any():
        raise ValueError(
            "Duplicate case IDs found in deletion_requests.csv."
        )

    print("Input files: OK", flush=True)
    print(f"Main requests: {len(requests)}", flush=True)

    return requests


# ============================================================
# SAMPLE VALIDATION
# ============================================================

def validate_sample():
    requests_path = DATA_DIR / "sample_deletion_requests.csv"
    sample_path = DATA_DIR / "sample_output.csv"

    requests = pd.read_csv(
        requests_path,
        dtype=str,
    ).fillna("")

    sample = pd.read_csv(
        sample_path,
        dtype=str,
    ).fillna("")

    if list(sample.columns) != EXPECTED_COLUMNS:
        raise ValueError(
            f"Expected sample columns {EXPECTED_COLUMNS}; "
            f"received {list(sample.columns)}."
        )

    if "case_id" not in requests.columns:
        raise ValueError(
            "Sample requests must contain case_id."
        )

    if requests["case_id"].duplicated().any():
        raise ValueError(
            "Duplicate case IDs in sample requests."
        )

    if sample["case_id"].duplicated().any():
        raise ValueError(
            "Duplicate case IDs in sample output."
        )

    if set(requests["case_id"]) != set(sample["case_id"]):
        raise ValueError(
            "Sample request IDs do not match sample output IDs."
        )

    invalid = set(sample["deletion_status"]) - VALID_STATUSES

    if invalid:
        raise ValueError(
            f"Invalid sample statuses: {invalid}"
        )

    for case_id, value in zip(
        sample["case_id"],
        sample["steps_json"],
    ):
        try:
            steps = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Invalid sample JSON for case {case_id}"
            ) from exc

        if not isinstance(steps, list):
            raise ValueError(
                f"steps_json must be a list for case {case_id}"
            )

    print("\nSample structure: OK", flush=True)
    print(f"Sample cases: {len(sample)}", flush=True)
    print("Sample status counts:", flush=True)
    print(
        sample["deletion_status"].value_counts().to_string(),
        flush=True,
    )


# ============================================================
# REBUILD EVIDENCE INDEX
# ============================================================

def rebuild_evidence_index():
    script = SRC_DIR / "build_evidence_index.py"

    if not script.is_file():
        raise FileNotFoundError(
            f"Evidence index builder not found: {script}"
        )

    print("\n" + "=" * 55, flush=True)
    print("STEP 1: BUILD EVIDENCE INDEX", flush=True)
    print("=" * 55, flush=True)

    # Stream progress directly to the terminal.
    subprocess.run(
        [sys.executable, "-u", str(script)],
        cwd=str(PROJECT_DIR),
        check=True,
    )

    required_outputs = [
        DATA_DIR / "identity_matches.csv",
        DATA_DIR / "evidence_matches.csv",
    ]

    missing = [
        str(path)
        for path in required_outputs
        if not path.is_file()
    ]

    if missing:
        raise FileNotFoundError(
            "Evidence builder did not create:\n"
            + "\n".join(missing)
        )

    print(
        "\nEvidence index rebuilt successfully.",
        flush=True,
    )


# ============================================================
# RUN AUDIT AGENT
# ============================================================

def run_audit_agent():
    print("\n" + "=" * 55, flush=True)
    print("STEP 2: RUN DELETION AUDIT", flush=True)
    print("=" * 55, flush=True)

    if str(SRC_DIR) not in sys.path:
        sys.path.insert(0, str(SRC_DIR))

    importlib.invalidate_caches()

    try:
        import audit_agent
    except ImportError as exc:
        raise ImportError(
            "Could not import src/audit_agent.py. "
            "Check the file name and Python errors."
        ) from exc

    audit_main = getattr(audit_agent, "main", None)

    if not callable(audit_main):
        raise RuntimeError(
            "src/audit_agent.py must expose a callable main(). "
            "Its current interface needs to be checked."
        )

    audit_main()

    if not OUTPUT_FILE.is_file():
        raise FileNotFoundError(
            "The audit agent finished without creating "
            f"{OUTPUT_FILE}"
        )


# ============================================================
# VALIDATE FINAL OUTPUT
# ============================================================

def validate_output(requests):
    print("\n" + "=" * 55, flush=True)
    print("STEP 3: VALIDATE OUTPUT", flush=True)
    print("=" * 55, flush=True)

    output = pd.read_csv(
        OUTPUT_FILE,
        dtype=str,
        keep_default_na=False,
    )

    if list(output.columns) != EXPECTED_COLUMNS:
        raise ValueError(
            f"Expected output columns {EXPECTED_COLUMNS}; "
            f"received {list(output.columns)}."
        )

    if len(output) != len(requests):
        raise ValueError(
            f"Expected {len(requests)} rows; "
            f"received {len(output)}."
        )

    if output["case_id"].duplicated().any():
        raise ValueError(
            "Output contains duplicate case IDs."
        )

    expected_ids = set(requests["case_id"])
    actual_ids = set(output["case_id"])

    if expected_ids != actual_ids:
        raise ValueError(
            "Output case IDs differ from deletion request IDs. "
            f"Missing: {sorted(expected_ids - actual_ids)[:10]}; "
            f"unexpected: {sorted(actual_ids - expected_ids)[:10]}."
        )

    invalid = set(output["deletion_status"]) - VALID_STATUSES

    if invalid:
        raise ValueError(
            f"Invalid deletion statuses: {invalid}"
        )

    for row in output.to_dict(orient="records"):
        case_id = row["case_id"]

        try:
            steps = json.loads(row["steps_json"])
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Invalid steps_json for case {case_id}"
            ) from exc

        if not isinstance(steps, list):
            raise ValueError(
                f"steps_json must be a list for case {case_id}"
            )

        previous_number = 0

        for step in steps:
            if not isinstance(step, dict):
                raise ValueError(
                    f"Each remediation step must be an object "
                    f"for case {case_id}."
                )

            number = step.get("step_no")

            if (
                not isinstance(number, int)
                or isinstance(number, bool)
                or number <= previous_number
            ):
                raise ValueError(
                    f"Remediation steps must have increasing "
                    f"integer step_no values for case {case_id}."
                )

            previous_number = number

    print("Output schema: OK", flush=True)
    print(f"Total rows: {len(output)}", flush=True)
    print(
        f"Unique case IDs: {output['case_id'].nunique()}",
        flush=True,
    )
    print("JSON validation: OK", flush=True)
    print("Status counts:", flush=True)
    print(
        output["deletion_status"].value_counts().to_string(),
        flush=True,
    )
    print(f"\nOutput saved to: {OUTPUT_FILE}", flush=True)


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 55, flush=True)
    print("GHOST DATA - DELETION AUDIT AGENT", flush=True)
    print("=" * 55, flush=True)

    requests = validate_inputs()
    validate_sample()

    rebuild_evidence_index()
    run_audit_agent()
    validate_output(requests)

    print("\n" + "=" * 55, flush=True)
    print("PIPELINE FINISHED SUCCESSFULLY", flush=True)
    print("=" * 55, flush=True)
    print(
        "Structural validation passed. "
        "Case-level policy correctness still requires verification.",
        flush=True,
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nPipeline interrupted by user.", flush=True)
        sys.exit(130)
    except Exception as exc:
        print(
            f"\nPIPELINE FAILED: {exc}",
            file=sys.stderr,
            flush=True,
        )
        sys.exit(1)
