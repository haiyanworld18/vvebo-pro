"""Validate and refresh an existing ad-hoc seal for explicitly declared changes.

This does not produce a trusted Apple signature. The user must re-sign the IPA.
Only the known G baseline is accepted by the release builder.
"""

import hashlib
import struct


def require(condition, message):
    if not condition:
        raise ValueError(message)


def commands(binary):
    require(binary[:4] == b"\xcf\xfa\xed\xfe", "Expected arm64 Mach-O")
    count, size = struct.unpack_from("<II", binary, 16)
    end = 32 + size
    require(end <= len(binary), "Truncated load commands")
    position = 32
    for _ in range(count):
        require(position + 8 <= end, "Truncated load command")
        kind, length = struct.unpack_from("<II", binary, position)
        require(length >= 8 and length % 8 == 0, "Invalid load command")
        require(position + length <= end, "Load command exceeds header")
        yield position, kind, length
        position += length
    require(position == end, "Inconsistent load command count")


def signature_slots(binary):
    entries = [p for p, kind, _ in commands(binary) if kind == 0x1D]
    require(len(entries) == 1, "Expected one code signature")
    offset, size = struct.unpack_from("<II", binary, entries[0] + 8)
    require(offset + size == len(binary), "Signature must be final data")
    magic, length, count = struct.unpack_from(">III", binary, offset)
    require(magic == 0xFADE0CC0 and length == size, "Invalid SuperBlob")
    require(12 + count * 8 <= size, "Truncated signature index")
    slots = {}
    for index in range(count):
        kind, relative = struct.unpack_from(">II", binary, offset + 12 + index * 8)
        require(kind not in slots, "Duplicate signature slot")
        require(12 + count * 8 <= relative <= size - 8, "Invalid signature offset")
        start = offset + relative
        blob_length = struct.unpack_from(">I", binary, start + 4)[0]
        require(8 <= blob_length <= size - relative, "Invalid signature blob")
        slots[kind] = (start, bytes(binary[start:start + blob_length]))
    require(0 in slots, "Missing CodeDirectory")
    return offset, slots


def verify_seal(binary, info, resources, identifier):
    limit, slots = signature_slots(binary)
    cd = slots[0][1]
    require(len(cd) >= 88, "Truncated CodeDirectory")
    magic, length, version, flags, hashes, ident, specials, pages, code_limit = (
        struct.unpack_from(">9I", cd)
    )
    require(magic == 0xFADE0C02 and length == len(cd), "Invalid CodeDirectory")
    require(version == 0x20400 and flags & 2, "Expected baseline ad-hoc seal")
    require(65536 not in slots, "Cannot refresh a CMS-signed package")
    require(cd[36:40] == bytes([32, 2, 0, 12]), "Expected SHA256/4KB pages")
    require(code_limit == limit, "Code limit mismatch")
    require(pages == (limit + 4095) // 4096, "Code page count mismatch")
    require(hashes + pages * 32 == len(cd), "Code hash table mismatch")
    require(ident >= 88 and hashes - specials * 32 > ident, "Invalid directory layout")
    require(cd[ident:].split(b"\0", 1)[0] == identifier.encode(), "Identifier mismatch")
    for page in range(pages):
        actual = hashlib.sha256(binary[page * 4096:min(limit, (page + 1) * 4096)]).digest()
        require(cd[hashes + page * 32:hashes + (page + 1) * 32] == actual,
                f"Code page hash mismatch: {page}")
    expected = {1: info, 3: resources}
    expected.update({kind: data for kind, (_, data) in slots.items() if kind in (5, 7)})
    for kind, data in expected.items():
        require(kind <= specials, f"Missing special slot: {kind}")
        require(cd[hashes - kind * 32:hashes - (kind - 1) * 32] == hashlib.sha256(data).digest(),
                f"Special slot hash mismatch: {kind}")
    return limit, slots


def refresh_seal(binary, info, resources, patched_offsets=()):
    """Refresh bundle hashes and only pages touched by whitelisted patches."""
    limit, slots = signature_slots(binary)
    start, cd = slots[0]
    hashes = struct.unpack_from(">I", cd, 16)[0]
    output = bytearray(binary)
    for kind, data in ((1, info), (3, resources)):
        position = start + hashes - kind * 32
        output[position:position + 32] = hashlib.sha256(data).digest()
    for offset in patched_offsets:
        require(0 <= offset < limit, "Patch offset exceeds signed code")
    for page in sorted({offset // 4096 for offset in patched_offsets}):
        position = start + hashes + page * 32
        output[position:position + 32] = hashlib.sha256(
            binary[page * 4096:min(limit, (page + 1) * 4096)]).digest()
    return bytes(output)
