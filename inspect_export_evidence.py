
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
EVIDENCE_DIR = BASE_DIR / "data" / "evidence"

identifiers = [
    "ingrid.dahl@outlook.com",
    "user_18",
    "export_1260",
    "export_1842",
    "0649eddaba37af918d82b64da379e6623d34cf290b2a26ecbe53bafc1484f8af"
]

def search_exact(obj, path="$"):
    matches = []

    if isinstance(obj, dict):
        for key, value in obj.items():
            current_path = f"{path}.{key}"

            if isinstance(value, (dict, list)):
                matches.extend(search_exact(value, current_path))
            else:
                text_value = str(value)

                for identifier in identifiers:
                    # Match complete identifier values, not partial IDs.
                    if text_value == identifier:
                        matches.append(
                            (current_path, identifier, text_value)
                        )

    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            matches.extend(
                search_exact(value, f"{path}[{index}]")
            )

    return matches


print("Searching for exact identifiers for case_33...\n")

total = 0

for file_path in sorted(EVIDENCE_DIR.rglob("*.json")):
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            data = json.load(file)

        matches = search_exact(data)

        if matches:
            print("=" * 65)
            print("FILE:", file_path.relative_to(EVIDENCE_DIR))
            for path, identifier, value in matches:
                print(f"Identifier: {identifier}")
                print(f"JSON path:  {path}")
                print(f"Exact value: {value}")
                print()
                total += 1

    except (OSError, json.JSONDecodeError) as error:
        print("Could not read:", file_path.name, error)

print("=" * 65)
print("Total exact matches:", total)
