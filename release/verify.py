"""Verify release identity and exact equivalence of runtime bytes to G."""

import argparse
import hashlib
import plistlib
import struct
from pathlib import Path

from package import (APP, MAIN, INFO, RESOURCES, TEST_KEYS, config, load_baseline,
                     read_ipa, release_info, release_resources)
from signing import commands, refresh_bundle_hashes, require, verify_seal


def verify_release(baseline, target):
    settings = config()
    old, _ = load_baseline(baseline, settings)
    files, _ = read_ipa(target)
    require(set(files) == set(old), "IPA entries changed")
    changed = {name for name in files if files[name] != old[name]}
    require(changed == {MAIN, INFO, RESOURCES}, "Unexpected modified files")
    info = plistlib.loads(files[INFO])
    require(info["CFBundleIdentifier"] == settings["bundle_id"], "Bundle ID changed")
    require(info["CFBundleShortVersionString"] == settings["app_version"], "App version changed")
    require(not any(key in info for key in TEST_KEYS), "Test markers remain")
    require(files[INFO] == release_info(old[INFO], settings), "Unplanned application settings")
    require(files[RESOURCES] == release_resources(old[RESOURCES], files[INFO]),
            "Unplanned resource seal changes")
    old_limit, _ = verify_seal(old[MAIN], old[INFO], old[RESOURCES], settings["bundle_id"])
    limit, _ = verify_seal(files[MAIN], files[INFO], files[RESOURCES], settings["bundle_id"])
    require(limit == old_limit and files[MAIN][:limit] == old[MAIN][:limit],
            "Executable instructions or load commands differ from G")
    require(files[MAIN] == refresh_bundle_hashes(old[MAIN], files[INFO], files[RESOURCES]),
            "Signature changed beyond the two bundle metadata hashes")
    for name, value in plistlib.loads(files[RESOURCES])["files"].items():
        if APP + name in files:
            expected = value["hash"] if isinstance(value, dict) else value
            require(expected == hashlib.sha1(files[APP + name]).digest(),
                    f"Resource hash mismatch: {name}")
    sdk_commands = [p for p, kind, _ in commands(files[MAIN]) if kind == 0x32]
    require(len(sdk_commands) == 1, "Build-version command mismatch")
    platform, minimum, sdk = struct.unpack_from("<III", files[MAIN], sdk_commands[0] + 8)
    require((platform, minimum, sdk) == (2, 0xE0000, 0x120000), "G display declaration changed")
    return {"release": settings["version"], "app_version": settings["app_version"],
            "build": settings["build"], "display_name": settings["display_name"],
            "baseline": "User-confirmed G", "checks": {
                "exact_three_changed_files": True,
                "main_code_and_load_commands_identical_to_g": True,
                "all_frameworks_and_ui_assets_identical_to_g": True,
                "cloud_disable_patches_preserved": True,
                "display_sdk_declaration_preserved": True,
                "original_bundle_id_and_entitlements_preserved": True,
                "only_two_code_directory_hashes_refreshed": True,
                "all_resource_hashes_and_code_pages_valid": True,
                "test_metadata_removed": True},
            "device_evidence": "User confirmed E startup/profile functionality and G display; release package itself not independently device-tested",
            "limitations": ["iCloud sync remains disabled", "Apple-trusted re-signing is required",
                            "Original app source is unavailable; this release maintains compatibility patches"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("release_ipa", type=Path)
    args = parser.parse_args()
    import json
    print(json.dumps(verify_release(args.baseline, args.release_ipa), indent=2, ensure_ascii=False))
