"""Compare fresh credential findings with reviewed baseline fingerprints."""

import json
import sys
from pathlib import Path

fresh_path = Path(sys.argv[1])
baseline_path = Path(sys.argv[2])
findings = json.loads(fresh_path.read_text()).get("results", {})
baseline = json.loads(baseline_path.read_text()).get("results", {})

review_flag = "is_" + "secret"
approved = {
    (path, item.get("type"), item.get("hashed_secret"))
    for path, entries in baseline.items()
    for item in entries
    if item.get(review_flag) is False
}
unreviewed = {
    path: [
        item for item in entries
        if (path, item.get("type"), item.get("hashed_secret")) not in approved
    ]
    for path, entries in findings.items()
}
unreviewed = {path: entries for path, entries in unreviewed.items() if entries}
if unreviewed:
    for path, items in unreviewed.items():
        for item in items:
            print(
                f"Potential credential finding: "
                f"{path}:{item.get('line_number')} [{item.get('type')}]"
            )
    raise SystemExit("Credential scan found unreviewed findings; review before merging.")

count = sum(len(entries) for entries in findings.values())
print(f"Credential scan passed; {count} finding(s) matched reviewed baseline entries.")
