
from pathlib import Path
from collections import Counter

PROJECT_DIR = Path(__file__).resolve().parent.parent
EVIDENCE_DIR = PROJECT_DIR / "data" / "evidence"

files = [p for p in EVIDENCE_DIR.rglob("*") if p.is_file()]

print("Total evidence files:", len(files))

print("\n=== FILE TYPES ===")
counts = Counter(p.suffix.lower() or "(no extension)" for p in files)

for extension, count in sorted(counts.items()):
    print(f"{extension}: {count}")

print("\n=== TEXT EVIDENCE PREVIEW ===")

text_extensions = {".txt", ".log", ".json", ".sql", ".md", ".csv"}

shown = 0

for path in sorted(files):
    if path.suffix.lower() not in text_extensions:
        continue

    try:
        content = path.read_text(encoding="utf-8", errors="replace")
        print(f"\n--- {path.relative_to(EVIDENCE_DIR)} ---")
        print(content[:1200])
        shown += 1

        if shown >= 5:
            break

    except OSError as error:
        print("Could not read:", path.name, error)

print("\nPreview complete.")
