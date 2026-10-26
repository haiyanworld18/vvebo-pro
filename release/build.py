"""Build the maintenance release without recompiling the verified runtime."""

import argparse
import json
from pathlib import Path

from package import (MAIN, INFO, RESOURCES, config, load_baseline, release_info,
                     release_resources, sha256, write_ipa)
from signing import refresh_bundle_hashes
from verify import verify_release


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path, help="Exact public G IPA")
    parser.add_argument("output", type=Path, help="Output directory")
    args = parser.parse_args()
    settings = config()
    files, entries = load_baseline(args.baseline, settings)
    files[INFO] = release_info(files[INFO], settings)
    files[RESOURCES] = release_resources(files[RESOURCES], files[INFO])
    files[MAIN] = refresh_bundle_hashes(files[MAIN], files[INFO], files[RESOURCES])
    args.output.mkdir(parents=True, exist_ok=True)
    target = args.output / settings["artifact"]
    write_ipa(target, files, entries)
    report = verify_release(args.baseline, target)
    report.update({"artifact": target.name, "bytes": target.stat().st_size,
                   "sha256": sha256(target.read_bytes())})
    report_path = args.output / f"VVebo-Compat-{settings['version']}-verification.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
