#!/usr/bin/env python3
"""
apply_pool_corrections.py — write the verification sheet's judgments back into
pool-manifest.json.

The HTML sheet (build_verification_html.py) exports pool-corrections.json:
[{id, verified, verified_label, tolerant, tolerant_alt_label}, ...]. Until now
that file was applied by hand; this script is that hand, made repeatable.

Rules, deliberately conservative:
  - only entries with verified == true are applied — the export carries a row
    for every item on the sheet, and an unjudged row must not overwrite
    anything;
  - an item already verified in the manifest is NOT overwritten unless
    --overwrite is passed: re-running an old export must not silently undo a
    newer judgment;
  - ids missing from the manifest abort loudly.

After applying, rerun the consumers of verified_label (build_queues.py for
intake, build_requests.py for routing) ONLY if their artefacts are not frozen
yet; MAIN's are (SS8.1), the repl arms' are not until SS12 records them.

Usage:
    python tests/scripts/apply_pool_corrections.py <pool-corrections.json> [--overwrite] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = REPO_ROOT / "tests" / "fixtures" / "w2-branching" / "support-intake" / "pool-manifest.json"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("corrections", type=Path)
    ap.add_argument("--overwrite", action="store_true",
                    help="let the export overwrite items the manifest already marks verified")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    corrections = json.loads(args.corrections.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    by_id = {i["id"]: i for i in manifest["items"]}

    applied = skipped_unjudged = skipped_verified = 0
    for row in corrections:
        if not row.get("verified"):
            skipped_unjudged += 1
            continue
        item = by_id.get(row["id"])
        if item is None:
            raise SystemExit(f"{row['id']}: not in pool-manifest.json")
        if item.get("verified") and not args.overwrite:
            skipped_verified += 1
            continue
        item["verified"] = True
        item["verified_label"] = row["verified_label"]
        item["tolerant"] = bool(row.get("tolerant"))
        item["tolerant_alt_label"] = row.get("tolerant_alt_label")
        applied += 1

    print(f"applied {applied}, unjudged {skipped_unjudged}, "
          f"already-verified untouched {skipped_verified}")
    if args.dry_run:
        print("dry run -- nothing written")
        return
    if applied:
        MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                            encoding="utf-8")
        print(f"written {MANIFEST.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
