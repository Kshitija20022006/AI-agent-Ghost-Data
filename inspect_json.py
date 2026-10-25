
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
EVIDENCE_DIR = BASE_DIR / "data" / "evidence"

json_files = list(EVIDENCE_DIR.rglob("*.json"))

print("Total JSON files found:", len(json_files))

for file_path in json_files:
    print("\nFile:", file_path.name)

    try:
        with open(file_path, "r", encoding="utf-8") as file:
            data = json.load(file)

        print("Status: Valid JSON")

        if isinstance(data, dict):
            print("Top-level keys:", list(data.keys())[:10])
        elif isinstance(data, list):
            print("Number of items:", len(data))

    except Exception as error:
        print("Could not read file:", error)


# to test exact resource ID matching

import re

text = "Resource export_1842 linked to user_18"

if re.search(r"\bexport_1842\b", text):
    print("Exact resource ID found")
else:
    print("Resource ID not found")

# displays the file and matching text so you can inspect the evidence

import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
EVIDENCE_DIR = BASE_DIR / "data" / "evidence"

# Identifiers we want to investigate
search_terms = [
    "export_1842",
    "user_18",
    "ingrid.dahl@outlook.com"
]

json_files = list(EVIDENCE_DIR.rglob("*.json"))
total_matches = 0

for file_path in json_files:
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            data = json.load(file)

        content = json.dumps(data, ensure_ascii=False, indent=2)
        matching_lines = []

        for line_number, line in enumerate(content.splitlines(), start=1):
            for term in search_terms:
                pattern = (
                    r"(?<![A-Za-z0-9_@.+-])"
                    + re.escape(term)
                    + r"(?![A-Za-z0-9_@.+-])"
                )

                if re.search(pattern, line, re.IGNORECASE):
                    matching_lines.append(
                        (line_number, term, line.strip())
                    )

        if matching_lines:
            print(f"\nFILE: {file_path.name}")

            for line_number, term, line in matching_lines:
                print(f"Line {line_number} | {term}: {line}")
                total_matches += 1

    except (OSError, json.JSONDecodeError) as error:
        print(f"Could not inspect {file_path.name}: {error}")

print(f"\nTotal matching lines: {total_matches}")
