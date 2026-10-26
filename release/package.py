"""Shared release packaging/verification utilities; Python standard library only."""

import copy
import hashlib
import json
from pathlib import Path, PurePosixPath
import plistlib
import zipfile

from signing import require, signature_slots, verify_seal

APP = "Payload/VVebo.app/"
MAIN = APP + "VVebo"
INFO = APP + "Info.plist"
RESOURCES = APP + "_CodeSignature/CodeResources"
FRAMEWORK = APP + "Frameworks/VVProfile15.framework/VVProfile15"
TEST_KEYS = ("VVProfile15Build", "VVProfile17Compatibility", "VVProfile17DisplayCompatibility")


def config():
    return json.loads(Path(__file__).with_name("config.json").read_text())


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def read_ipa(path):
    with zipfile.ZipFile(path) as archive:
        require(archive.testzip() is None, "IPA CRC failure")
        entries = archive.infolist()
        require(len({entry.filename for entry in entries}) == len(entries), "Duplicate ZIP paths")
        for entry in entries:
            name = PurePosixPath(entry.filename)
            require(not name.is_absolute() and ".." not in name.parts, "Unsafe ZIP path")
        return {entry.filename: archive.read(entry) for entry in entries}, entries


def load_baseline(path, settings):
    require(sha256(Path(path).read_bytes()) == settings["baseline_sha256"],
            "Use the exact public, unsigned G baseline; re-signed IPAs are not accepted")
    files, entries = read_ipa(path)
    info = plistlib.loads(files[INFO])
    require(info["CFBundleIdentifier"] == settings["bundle_id"], "Wrong application")
    require(info["CFBundleVersion"] == "4.1707", "Wrong baseline build")
    require(sha256(files[FRAMEWORK]) == settings["profile_framework_sha256"],
            "Unexpected profile framework")
    verify_seal(files[MAIN], files[INFO], files[RESOURCES], settings["bundle_id"])
    return files, entries


def release_info(baseline_info, settings):
    info = plistlib.loads(baseline_info)
    for key in TEST_KEYS:
        info.pop(key, None)
    info["CFBundleDisplayName"] = settings["display_name"]
    info["CFBundleVersion"] = settings["build"]
    info["VVeboCompatibilityVersion"] = settings["version"]
    return plistlib.dumps(info, fmt=plistlib.FMT_BINARY, sort_keys=False)


def apply_runtime_patches(binary, settings):
    """Apply bounded, expected-byte-checked instruction substitutions from G."""
    path = settings.get("runtime_patches_file")
    patches = json.loads((Path(__file__).parent / path).read_text())["patches"] if path else []
    limit, _ = signature_slots(binary)
    output = bytearray(binary)
    touched = set()
    for patch in patches:
        offset = int(patch["file_offset"], 0)
        before, after = bytes.fromhex(patch["before"]), bytes.fromhex(patch["after"])
        require(offset % 4 == 0 and len(before) == len(after) == 4, "Expected one ARM64 instruction")
        require(0 <= offset and offset + 4 <= limit, "Patch exceeds executable prefix")
        positions = set(range(offset, offset + 4))
        require(not touched.intersection(positions), "Overlapping patches")
        require(binary[offset:offset + 4] == before, "Unexpected original instruction")
        output[offset:offset + 4] = after
        touched.update(positions)
    return bytes(output), tuple(sorted(touched))


def release_resources(baseline_resources, info):
    resources = plistlib.loads(baseline_resources)
    prior = resources["files"]["Info.plist"]
    digest = hashlib.sha1(info).digest()
    if isinstance(prior, dict):
        prior = dict(prior)
        prior["hash"] = digest
    else:
        prior = digest
    resources["files"]["Info.plist"] = prior
    return plistlib.dumps(resources, fmt=plistlib.FMT_XML, sort_keys=True)


def write_ipa(path, files, entries):
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for entry in entries:
            metadata = copy.copy(entry)
            metadata.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(metadata, files[entry.filename], compresslevel=9)
