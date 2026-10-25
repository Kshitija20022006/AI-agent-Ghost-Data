
from pathlib import Path
import json
import subprocess
import sys

import pandas as pd
import streamlit as st

# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------
PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = PROJECT_DIR / "data"
OUTPUT_FILE = DATA_DIR / "output.csv"

st.set_page_config(
    page_title="Ghost Data | Deletion Audit",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --------------------------------------------------
# STYLING
# --------------------------------------------------
st.markdown("""
<style>
    .stApp {
        background-color: #0b1020;
        color: #e7edf7;
    }
    [data-testid="stSidebar"] {
        background-color: #111a2e;
    }
    div[data-testid="stMetric"] {
        background: #151f35;
        border: 1px solid #283754;
        padding: 18px;
        border-radius: 12px;
    }
    div[data-testid="stMetric"] label {
        color: #a9bad4;
    }
    .hero {
        padding: 24px;
        border-radius: 16px;
        background: linear-gradient(120deg, #172541, #112d38);
        border: 1px solid #304b61;
        margin-bottom: 22px;
    }
    .hero h1 {
        margin: 0;
        color: #ffffff;
    }
    .hero p {
        color: #b8c8dc;
        margin-bottom: 0;
    }
    .small-note {
        color: #a9bad4;
        font-size: 0.9rem;
    }
</style>
""", unsafe_allow_html=True)


# --------------------------------------------------
# DATA LOADING
# --------------------------------------------------
@st.cache_data
def load_csv(path_string):
    path = Path(path_string)
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except Exception:
        return pd.DataFrame()


def load_data():
    requests = load_csv(str(DATA_DIR / "deletion_requests.csv"))
    output = load_csv(str(OUTPUT_FILE))
    identities = load_csv(str(DATA_DIR / "identity_matches.csv"))
    evidence = load_csv(str(DATA_DIR / "evidence_matches.csv"))
    rules = load_csv(str(DATA_DIR / "deletion_rules.csv"))
    activities = load_csv(str(DATA_DIR / "system_activity.csv"))
    return requests, output, identities, evidence, rules, activities


def find_case_column(df):
    for col in ("case_id", "request_id"):
        if col in df.columns:
            return col
    return None


def parse_steps(value):
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    except (TypeError, ValueError, json.JSONDecodeError):
        return []


def safe_filter(df, column, search):
    if column not in df.columns or not search:
        return df
    return df[df[column].astype(str).str.contains(
        search, case=False, na=False, regex=False
    )]


# --------------------------------------------------
# SIDEBAR
# --------------------------------------------------
with st.sidebar:
    st.markdown("## 🛡️ Ghost Data")
    st.caption("Deletion audit intelligence")
    st.divider()

    page = st.radio(
        "Navigation",
        [
            "Overview",
            "Case Explorer",
            "Evidence Explorer",
            "Retention Rules",
            "Pipeline & Export",
        ],
    )

    st.divider()
    st.caption("Northstar Shop · Hackathon prototype")


requests, output, identities, evidence, rules, activities = load_data()

if output.empty:
    st.error("No output.csv found. Run the audit pipeline to generate results.")
    if st.button("Run audit pipeline", type="primary"):
        pipeline = PROJECT_DIR / "src" / "generate_output.py"
        if not pipeline.exists():
            st.error(f"Pipeline script not found: {pipeline}")
        else:
            with st.spinner("Running deletion audit pipeline..."):
                result = subprocess.run(
                    [sys.executable, str(pipeline)],
                    cwd=str(PROJECT_DIR),
                    capture_output=True,
                    text=True,
                )
            if result.returncode == 0:
                st.success("Pipeline finished. Reloading results.")
                st.cache_data.clear()
                st.rerun()
            else:
                st.error("Pipeline failed. Review the log below.")
                st.code(result.stdout[-12000:] + "\n" + result.stderr[-6000:])
    st.stop()

if "case_id" not in output.columns:
    st.error("output.csv must contain a case_id column.")
    st.stop()

if "deletion_status" not in output.columns:
    st.error("output.csv must contain a deletion_status column.")
    st.stop()

output["case_id"] = output["case_id"].astype(str)
output["deletion_status"] = output["deletion_status"].str.upper().str.strip()

# Join original request details onto audit results.
request_key = find_case_column(requests)
if request_key:
    request_copy = requests.copy()
    request_copy[request_key] = request_copy[request_key].astype(str)
    if request_key != "case_id":
        request_copy = request_copy.rename(columns={request_key: "case_id"})

    duplicate_columns = [
        c for c in request_copy.columns
        if c in output.columns and c != "case_id"
    ]
    request_copy = request_copy.drop(columns=duplicate_columns, errors="ignore")
    cases = output.merge(request_copy, on="case_id", how="left")
else:
    cases = output.copy()

statuses = cases["deletion_status"]
total_cases = len(cases)
complete_count = int((statuses == "COMPLETE").sum())
incomplete_count = int((statuses == "INCOMPLETE").sum())
na_count = int((statuses == "NOT_APPLICABLE").sum())
other_count = total_cases - complete_count - incomplete_count - na_count


# --------------------------------------------------
# HEADER
# --------------------------------------------------
st.markdown("""
<div class="hero">
    <h1>🛡️ Ghost Data</h1>
    <p>Deletion Audit Intelligence · Detect residual personal data,
    evidence gaps, and data restoration risks.</p>
</div>
""", unsafe_allow_html=True)


# --------------------------------------------------
# OVERVIEW
# --------------------------------------------------
if page == "Overview":
    st.subheader("Audit overview")
    st.caption("Live summary of the latest output.csv generated by your pipeline.")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total requests", f"{total_cases:,}")
    c2.metric("Complete", f"{complete_count:,}")
    c3.metric("Incomplete", f"{incomplete_count:,}")
    c4.metric("Not applicable", f"{na_count:,}")

    if total_cases and incomplete_count == total_cases:
        st.warning(
            "All cases are currently classified INCOMPLETE. "
            "The output structure is valid, but this does not establish "
            "that the case-level classifications are correct."
        )

    st.divider()
    left, right = st.columns([1, 1])

    with left:
        st.markdown("### Status distribution")
        chart_data = pd.DataFrame({
            "Status": ["COMPLETE", "INCOMPLETE", "NOT_APPLICABLE", "OTHER"],
            "Cases": [
                complete_count, incomplete_count, na_count, other_count
            ],
        })
        chart_data = chart_data[chart_data["Cases"] > 0]
        if not chart_data.empty:
            st.bar_chart(chart_data.set_index("Status"))
        else:
            st.info("No cases to display.")

    with right:
        st.markdown("### Evidence index")
        e1, e2, e3 = st.columns(3)
        e1.metric("Identity matches", len(identities))
        e2.metric("Evidence matches", len(evidence))
        e3.metric("System activity rows", len(activities))

        st.markdown("### Data health")
        st.write(
            "Output rows match requests:",
            len(output) == len(requests) if not requests.empty else "Unknown",
        )
        st.write(
            "Unique case IDs:",
            not output["case_id"].duplicated().any(),
        )
        st.write(
            "Steps JSON column:",
            "steps_json" in output.columns,
        )

    st.divider()
    st.markdown("### Recent cases")
    st.dataframe(cases.head(10), use_container_width=True, hide_index=True)


# --------------------------------------------------
# CASE EXPLORER
# --------------------------------------------------
elif page == "Case Explorer":
    st.subheader("Case explorer")
    st.caption("Search a deletion request and inspect its audit trail.")

    search = st.text_input("Search case ID or identifier", placeholder="e.g. case_52")
    status_options = sorted(cases["deletion_status"].dropna().unique().tolist())
    selected_statuses = st.multiselect(
        "Filter by status",
        options=status_options,
        default=status_options,
    )

    filtered = cases[
        cases["deletion_status"].isin(selected_statuses)
    ].copy()

    if search:
        searchable_cols = [
            col for col in (
                "case_id", "email", "user_id", "customer_id",
                "request_id", "deletion_status"
            ) if col in filtered.columns
        ]
        if searchable_cols:
            mask = pd.Series(False, index=filtered.index)
            for col in searchable_cols:
                mask |= filtered[col].astype(str).str.contains(
                    search, case=False, na=False, regex=False
                )
            filtered = filtered[mask]

    st.write(f"Showing **{len(filtered)}** case(s).")
    display_columns = [
        c for c in (
            "case_id", "deletion_status", "email", "user_id",
            "request_date", "audit_at", "request_type"
        ) if c in filtered.columns
    ]
    if not display_columns:
        display_columns = ["case_id", "deletion_status"]

    st.dataframe(
        filtered[display_columns],
        use_container_width=True,
        hide_index=True,
    )

    if not filtered.empty:
        case_ids = filtered["case_id"].tolist()
        chosen_case = st.selectbox("Inspect case", case_ids)
        selected = filtered[filtered["case_id"] == chosen_case].iloc[0]

        st.divider()
        st.markdown(f"### Case: `{chosen_case}`")
        status = selected["deletion_status"]

        if status == "COMPLETE":
            st.success("Status: COMPLETE")
        elif status == "INCOMPLETE":
            st.warning("Status: INCOMPLETE — further verification is needed.")
        elif status == "NOT_APPLICABLE":
            st.info("Status: NOT APPLICABLE")
        else:
            st.error(f"Unexpected status: {status}")

        st.markdown("#### Request details")
        details = selected.drop(
            labels=["steps_json"], errors="ignore"
        ).to_dict()
        st.json(details)

        st.markdown("#### Ordered remediation steps")
        steps = parse_steps(selected.get("steps_json", ""))
        if steps:
            for step in steps:
                with st.expander(
                    f"Step {step.get('step_no', '?')}: "
                    f"{step.get('operation', 'Review evidence')}"
                ):
                    st.json(step)
        else:
            st.info("No remediation steps were recorded for this case.")


# --------------------------------------------------
# EVIDENCE EXPLORER
# --------------------------------------------------
elif page == "Evidence Explorer":
    st.subheader("Evidence explorer")
    st.caption(
        "Matches are investigation leads, not independent proof that data was deleted."
    )

    if evidence.empty:
        st.warning("evidence_matches.csv was not found or contains no rows.")
    else:
        ecase = find_case_column(evidence)
        query = st.text_input("Search evidence", placeholder="case ID, file name, system")
        filtered_evidence = evidence.copy()

        if query:
            mask = pd.Series(False, index=filtered_evidence.index)
            for col in filtered_evidence.columns:
                mask |= filtered_evidence[col].astype(str).str.contains(
                    query, case=False, na=False, regex=False
                )
            filtered_evidence = filtered_evidence[mask]

        if "match_type" in filtered_evidence.columns:
            types = sorted(filtered_evidence["match_type"].unique().tolist())
            selected_types = st.multiselect(
                "Match type", types, default=types
            )
            filtered_evidence = filtered_evidence[
                filtered_evidence["match_type"].isin(selected_types)
            ]

        st.write(f"Evidence matches: **{len(filtered_evidence)}**")
        st.dataframe(
            filtered_evidence,
            use_container_width=True,
            hide_index=True,
        )

    st.divider()
    st.markdown("### Identity matches")
    if identities.empty:
        st.info("identity_matches.csv was not found or contains no rows.")
    else:
        query_id = st.text_input("Search identity matches", key="identity_search")
        filtered_ids = identities.copy()
        if query_id:
            mask = pd.Series(False, index=filtered_ids.index)
            for col in filtered_ids.columns:
                mask |= filtered_ids[col].astype(str).str.contains(
                    query_id, case=False, na=False, regex=False
                )
            filtered_ids = filtered_ids[mask]
        st.dataframe(filtered_ids, use_container_width=True, hide_index=True)


# --------------------------------------------------
# RETENTION RULES
# --------------------------------------------------
elif page == "Retention Rules":
    st.subheader("Retention rules")
    st.caption(
        "Review the policies that determine what must be deleted, redacted, "
        "anonymized, or retained."
    )

    if rules.empty:
        st.warning("deletion_rules.csv was not found or contains no rows.")
    else:
        st.metric("Rules loaded", len(rules))
        st.dataframe(rules, use_container_width=True, hide_index=True)

    st.info(
        "A retention requirement is not a reason to retain all personal data. "
        "Keep only what the applicable rule requires, restrict access, and "
        "remove direct identifiers when required by policy."
    )


# --------------------------------------------------
# PIPELINE AND EXPORT
# --------------------------------------------------
elif page == "Pipeline & Export":
    st.subheader("Pipeline and export")
    st.write("Run the existing Python audit pipeline and refresh the dashboard.")

    if st.button("Run audit pipeline", type="primary"):
        pipeline = PROJECT_DIR / "src" / "generate_output.py"

        if not pipeline.exists():
            st.error(f"Could not find {pipeline}")
        else:
            with st.spinner("Running evidence indexing and audit..."):
                result = subprocess.run(
                    [sys.executable, str(pipeline)],
                    cwd=str(PROJECT_DIR),
                    capture_output=True,
                    text=True,
                )

            if result.returncode == 0:
                st.success("Pipeline completed. Reloading dashboard data.")
                st.cache_data.clear()
                st.rerun()
            else:
                st.error("Pipeline failed.")
                st.code(result.stdout[-12000:])
                st.code(result.stderr[-6000:])

    st.divider()
    st.markdown("### Download results")

    st.download_button(
        "Download audit output CSV",
        data=output.to_csv(index=False).encode("utf-8"),
        file_name="deletion_audit_output.csv",
        mime="text/csv",
    )

    if not evidence.empty:
        st.download_button(
            "Download evidence matches CSV",
            data=evidence.to_csv(index=False).encode("utf-8"),
            file_name="evidence_matches.csv",
            mime="text/csv",
        )

    if not identities.empty:
        st.download_button(
            "Download identity matches CSV",
            data=identities.to_csv(index=False).encode("utf-8"),
            file_name="identity_matches.csv",
            mime="text/csv",
        )

    st.divider()
    st.markdown("### Latest output validation")
    st.write("Rows:", len(output))
    st.write("Unique case IDs:", output["case_id"].nunique())
    st.write("Statuses:", sorted(output["deletion_status"].unique().tolist()))

    if "steps_json" in output.columns:
        valid_json = 0
        for item in output["steps_json"]:
            try:
                json.loads(item)
                valid_json += 1
            except (ValueError, TypeError):
                pass
        st.write(f"Valid steps_json rows: {valid_json}/{len(output)}")
