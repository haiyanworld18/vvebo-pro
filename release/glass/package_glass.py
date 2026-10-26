"""Build a separate glass candidate from the exact G IPA, without text patches.

Requires a compiled VVGlass binary. Does not change the stable builder config.
"""
import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import struct
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from package import APP, MAIN, INFO, RESOURCES, load_baseline, release_info, sha256, write_ipa
from signing import commands, refresh_seal, require, signature_slots, verify_seal
from macho_support import sign

VERSION = '1.1.0-glass.4'
NAME = 'VVebo-3.3.31-Glass-D.ipa'
IDENTIFIER = 'com.vvebo.compat.VVGlass'
REL = 'Frameworks/VVGlass.framework/'
PATH = APP + REL
BASELINE = '543f3c816da02bbef4ec6757058381114674e1abc0e3143ed7d87f47f472167c'
PROFILE = '75dfac48fb9bcb6f63b9148d300a2061d4e0424c958059834151f909e3fac0e3'
LOAD_PATH = '@executable_path/Frameworks/VVGlass.framework/VVGlass'


def settings():
    return dict(version=VERSION, build='4.1904', display_name='VVebo 玻璃D',
                bundle_id='com.johnil.vvebo', app_version='3.3.31',
                baseline_sha256=BASELINE, profile_framework_sha256=PROFILE)


def command(binary):
    # Only use the existing zero-filled header padding. Never relocate text.
    old_count, old_size = struct.unpack_from('<II', binary, 16)
    end = 32 + old_size
    path = LOAD_PATH.encode() + b'\0'
    length = (24 + len(path) + 7) & ~7
    load = struct.pack('<6I', 0x80000018, length, 24, 2, 0x10000, 0x10000) + path
    load += b'\0' * (length - len(load))
    text = None
    for p, kind, _ in commands(binary):
        if kind != 0x19: continue
        for index in range(struct.unpack_from('<I', binary, p + 64)[0]):
            q = p + 72 + index * 80
            if binary[q:q + 16].split(b'\0', 1)[0] == b'__text':
                text = struct.unpack_from('<I', binary, q + 48)[0]
    require(text is not None and end + length <= text, 'No safe header padding')
    require(not any(binary[end:end + length]), 'Header padding is occupied')
    result = bytearray(binary)
    struct.pack_into('<II', result, 16, old_count + 1, old_size + length)
    result[end:end + length] = load
    return bytes(result), tuple(range(16, 24)) + tuple(range(end, end + length))


def verify(baseline, target):
    original, _ = load_baseline(baseline, settings())
    with zipfile.ZipFile(target) as archive:
        require(archive.testzip() is None, 'Bad ZIP CRC')
        require(len(set(archive.namelist())) == len(archive.namelist()), 'Duplicate files')
        files = {entry: archive.read(entry) for entry in archive.namelist()}
    added = {PATH + 'VVGlass', PATH + 'Info.plist', PATH + '_CodeSignature/CodeResources'}
    require(set(files) == set(original) | added, 'Unexpected new files')
    require({n for n in original if original[n] != files[n]} == {MAIN, INFO, RESOURCES},
            'Unplanned baseline changes')
    info = plistlib.loads(files[INFO])
    expected_info = plistlib.loads(release_info(original[INFO], settings()))
    expected_info['VVeboGlassExperiment'] = 'fresh-native-backgrounds-d'
    require(info == expected_info, 'Unplanned Info settings')
    require(not info.get('VVeboLocalProEnabled'), 'Paid flag must not be present')
    expected, offsets = command(original[MAIN])
    require(files[MAIN] == refresh_seal(expected, files[INFO], files[RESOURCES], offsets),
            'Main differs beyond load/SDK declarations and seal')
    # Explicitly validate entire text, not only selected disassembled functions.
    for p, kind, _ in commands(original[MAIN]):
        if kind != 0x19: continue
        for index in range(struct.unpack_from('<I', original[MAIN], p + 64)[0]):
            q = p + 72 + index * 80
            if original[MAIN][q:q + 16].split(b'\0', 1)[0] == b'__text':
                length, offset = struct.unpack_from('<QI', original[MAIN], q + 40)
                require(files[MAIN][offset:offset + length] == original[MAIN][offset:offset + length],
                        'Original executable text changed')
    _, main_slots = verify_seal(files[MAIN], files[INFO], files[RESOURCES], 'com.johnil.vvebo')
    _, old_slots = signature_slots(original[MAIN])
    require({k: v[1] for k, v in main_slots.items() if k in (5, 7)} ==
            {k: v[1] for k, v in old_slots.items() if k in (5, 7)}, 'Entitlements changed')
    _, glass_slots = verify_seal(files[PATH + 'VVGlass'], files[PATH + 'Info.plist'],
                       files[PATH + '_CodeSignature/CodeResources'], IDENTIFIER)
    for executable, sdk, label in ((files[MAIN], 0x120000, 'G main'),
                                   (files[PATH + 'VVGlass'], 0x1A0000, 'new glass module')):
        versions = [p for p, kind, _ in commands(executable) if kind == 0x32]
        require(len(versions) == 1 and struct.unpack_from('<III', executable, versions[0] + 8)
                == (2, 0xE0000, sdk), 'Unexpected SDK/minimum declaration: ' + label)
    cdhash = hashlib.sha256(glass_slots[0][1]).digest()[:20]
    resources = plistlib.loads(files[RESOURCES])
    for rel, seal in resources['files'].items():
        if APP + rel not in files: continue
        digest = seal['hash'] if isinstance(seal, dict) else seal
        require(digest == hashlib.sha1(files[APP + rel]).digest(), 'Bad resource: ' + rel)
    require(resources['files2'][REL.rstrip('/')]['cdhash'] == cdhash, 'Nested seal mismatch')
    require(sha256(files[APP + 'Frameworks/VVProfile15.framework/VVProfile15']) == PROFILE,
            'Homepage framework changed')
    return dict(version=VERSION, artifact=NAME, build=info['CFBundleVersion'],
                bytes=Path(target).stat().st_size, sha256=sha256(Path(target).read_bytes()),
                checks=dict(main_text_identical_to_g=True, main_header_only_adds_weak_glass_load=True,
                            main_sdk18_preserved_and_only_new_module_declares_sdk26=True,
                            original_entitlements_preserved=True, network_framework_identical=True,
                            original_frameworks_and_assets_identical=True, code_and_resource_seals_valid=True,
                            no_membership_or_image_priority_patches=True),
                limits=['Native effect rendering and stability require device testing',
                        'Glass only applies to existing BlurView backgrounds inside BaseBarView',
                        'Main SDK compatibility declaration remains G SDK 18; no C compatibility flags',
                        'Fresh native backgrounds and temporary comparison card require real rendering confirmation',
                        'iCloud remains disabled'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reproduce-failed-experiment', action='store_true',
                        help='Historical research only; D did not produce the requested Liquid Glass effect')
    parser.add_argument('baseline', type=Path)
    parser.add_argument('framework', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if not args.reproduce_failed_experiment:
        parser.error('Glass experiments did not achieve the requested on-device Liquid Glass effect. '
                     'Do not distribute as a working adaptation. Historical reproduction requires '
                     '--reproduce-failed-experiment.')
    files, entries = load_baseline(args.baseline, settings())
    framework_info = plistlib.dumps(dict(CFBundleIdentifier=IDENTIFIER, CFBundleName='VVGlass',
        CFBundleExecutable='VVGlass', CFBundlePackageType='FMWK', CFBundleVersion='1',
        CFBundleShortVersionString='1.0', MinimumOSVersion='14.0', CFBundleSupportedPlatforms=['iPhoneOS']),
        fmt=plistlib.FMT_BINARY, sort_keys=True)
    framework_resources = plistlib.dumps(dict(files={'Info.plist': hashlib.sha1(framework_info).digest()},
        files2={}, rules={'^.*': True}, rules2={'^.*': True, '^Info\\.plist$': {'omit': True, 'weight': 10}}),
        fmt=plistlib.FMT_XML, sort_keys=True)
    framework, cdhash = sign(args.framework.read_bytes(), IDENTIFIER, framework_info, framework_resources)
    info = plistlib.loads(release_info(files[INFO], settings()))
    info['VVeboGlassExperiment'] = 'fresh-native-backgrounds-d'
    files[INFO] = plistlib.dumps(info, fmt=plistlib.FMT_BINARY, sort_keys=False)
    new_files = {PATH + 'VVGlass': framework, PATH + 'Info.plist': framework_info,
                 PATH + '_CodeSignature/CodeResources': framework_resources}
    resources = plistlib.loads(files[RESOURCES])
    old_info = resources['files']['Info.plist']
    digest = hashlib.sha1(files[INFO]).digest()
    if isinstance(old_info, dict):
        old_info = dict(old_info); old_info['hash'] = digest
    else: old_info = digest
    resources['files']['Info.plist'] = old_info
    for name, data in new_files.items():
        resources['files'][name[len(APP):]] = hashlib.sha1(data).digest()
    resources['files2'][REL.rstrip('/')] = {'cdhash': cdhash, 'requirement': 'cdhash H"' + cdhash.hex() + '"'}
    files[RESOURCES] = plistlib.dumps(resources, fmt=plistlib.FMT_XML, sort_keys=True)
    binary, offsets = command(files[MAIN])
    files[MAIN] = refresh_seal(binary, files[INFO], files[RESOURCES], offsets)
    files.update(new_files)
    for name in new_files:
        entry = zipfile.ZipInfo(name, (2026, 10, 26, 0, 0, 0))
        entry.create_system = 3
        entry.external_attr = ((0o100755 if name.endswith('/VVGlass') else 0o100644) << 16)
        entries.append(entry)
    args.output.mkdir(parents=True, exist_ok=True)
    target = args.output / NAME
    write_ipa(target, files, entries)
    report = verify(args.baseline, target)
    report_path = args.output / 'VVebo-Glass-D-verification.json'
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == '__main__': main()
