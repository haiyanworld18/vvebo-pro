"""Execute the actual login routing code with mocked Foundation/Swift calls.

The old fresh-login route must enter cloud progress. The release must enter
the existing normal form, without changing stored preferences or login state.
This is not a full UIKit or on-device authentication test. Requires unicorn.
"""

import argparse
import struct
import zipfile

from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm64_const import (UC_ARM64_REG_X0, UC_ARM64_REG_X1,
    UC_ARM64_REG_X2, UC_ARM64_REG_X8, UC_ARM64_REG_X20, UC_ARM64_REG_X22,
    UC_ARM64_REG_SP, UC_ARM64_REG_PC, UC_ARM64_REG_LR)

BASE = 0x100000000
SELF, INPUT, DEFAULTS, KEY = 0x300001000, 0x300002000, 0x300003000, 0x300004000
SP = 0x40000FFF0
NORMAL, PROGRESS = BASE + 0x17D3E0, BASE + 0x17D414


def image(path):
    with zipfile.ZipFile(path) as archive:
        return archive.read("Payload/VVebo.app/VVebo")


def execute(binary, restored, active_account=False, existing_overlay=False):
    uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
    uc.mem_map(BASE, 0x900000)
    uc.mem_write(BASE, binary)
    uc.mem_map(0x300000000, 0x10000)
    uc.mem_map(0x400000000, 0x10000)
    # Model only the field offsets and globals used by this original code slice.
    uc.mem_write(BASE + 0x707768, struct.pack("<Q", 0x30))
    uc.mem_write(BASE + 0x6F7820, struct.pack("<Q", 0xFFFFFFFFFFFFFFFF))
    uc.mem_write(BASE + 0x700288, struct.pack("<Q", DEFAULTS))
    selector = struct.unpack_from("<Q", binary, 0x6CA4E0)[0] & 0xFFFFFFFFF
    selector_name = binary[selector - BASE:].split(b"\0", 1)[0]
    assert selector_name == b"getBoolForKey:"
    uc.mem_write(BASE + 0x6CA4E0, struct.pack("<Q", selector))
    model = bytearray(bytes(range(128)))
    struct.pack_into("<Q", model, 0x10, INPUT)
    struct.pack_into("<Q", model, 0x30, INPUT if existing_overlay else 0)
    uc.mem_write(SELF, bytes(model))
    uc.mem_write(DEFAULTS, struct.pack("<Q", int(restored)))
    uc.reg_write(UC_ARM64_REG_X20, SELF)
    uc.reg_write(UC_ARM64_REG_X22, 0x10)
    uc.reg_write(UC_ARM64_REG_X8, INPUT if active_account else 0)
    uc.reg_write(UC_ARM64_REG_SP, SP)
    events = []
    route = []

    def ret(value):
        uc.reg_write(UC_ARM64_REG_X0, value)
        uc.reg_write(UC_ARM64_REG_PC, uc.reg_read(UC_ARM64_REG_LR))

    def callback(uc, pc, size, _):
        if pc in (NORMAL, PROGRESS):
            route.append("normal_login" if pc == NORMAL else "cloud_progress")
            uc.emu_stop()
        elif pc == BASE + 0x5634A8:
            first = uc.reg_read(UC_ARM64_REG_X0).to_bytes(8, "little")
            second = uc.reg_read(UC_ARM64_REG_X1).to_bytes(8, "little")
            assert first + second[:7] == b"accountRestored"
            events.append("bridge_key")
            ret(KEY)
        elif pc == BASE + 0x565578:
            assert uc.reg_read(UC_ARM64_REG_X0) == DEFAULTS
            assert uc.reg_read(UC_ARM64_REG_X1) == selector
            assert uc.reg_read(UC_ARM64_REG_X2) == KEY
            events.append("read_preference")
            ret(int(restored))
        elif pc == BASE + 0x5655CC:
            assert uc.reg_read(UC_ARM64_REG_X0) == KEY
            events.append("release_key")
            ret(0)

    uc.hook_add(UC_HOOK_CODE, callback)
    uc.emu_start(BASE + 0x17D368, BASE + 0x17D42C, count=200)
    assert len(route) == 1
    assert uc.reg_read(UC_ARM64_REG_SP) == SP
    assert uc.reg_read(UC_ARM64_REG_X20) == SELF
    assert uc.reg_read(UC_ARM64_REG_X22) == 0x10
    assert bytes(uc.mem_read(SELF, 128)) == bytes(model)
    assert bytes(uc.mem_read(DEFAULTS, 8)) == struct.pack("<Q", int(restored))
    assert events == ([] if active_account or existing_overlay else
                      ["bridge_key", "read_preference", "release_key"])
    return route[0]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline")
    parser.add_argument("release_ipa")
    args = parser.parse_args()
    before, after = image(args.baseline), image(args.release_ipa)
    assert before[0x17D3DC:0x17D3E0] == bytes.fromhex("d3010036")
    assert after[0x17D3DC:0x17D3E0] == bytes.fromhex("1f2003d5")
    assert execute(before, False) == "cloud_progress"
    assert execute(after, False) == "normal_login"
    for binary in (before, after):
        assert execute(binary, True) == "normal_login"
        assert execute(binary, False, active_account=True) == "normal_login"
        assert execute(binary, False, existing_overlay=True) == "normal_login"
    print("PASS: actual ARM64 fresh-login route changes from cloud progress to normal login; restored/account/overlay routes are preserved; key cleanup, stack and modeled account/preference bytes remain intact.")
    print("LIMIT: Foundation/Swift calls are mocked; complete UIKit, authentication and device startup still require device confirmation.")
