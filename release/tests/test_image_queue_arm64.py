"""Execute the packaged shared-image-manager initialization with mocked ObjC.

Checks the queue QoS argument, fallback availability guard, initializer wiring
and balanced local cleanup. Does not measure network throughput or frame rate.
Requires unicorn.
"""

import argparse
import struct
import zipfile

from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm64_const import (UC_ARM64_REG_X0, UC_ARM64_REG_X1,
    UC_ARM64_REG_X2, UC_ARM64_REG_X3, UC_ARM64_REG_FP,
    UC_ARM64_REG_SP, UC_ARM64_REG_PC, UC_ARM64_REG_LR)

BASE = 0x100000000
BLOCK, CACHE_CLASS, CACHE = 0x300001000, 0x300002000, 0x300003000
QUEUE_CLASS, QUEUE = 0x300004000, 0x300005000
MANAGER_CLASS, MANAGER = 0x300006000, 0x300007000
STOP, SP = 0x400000000, 0x40000FFF0


def image(path):
    with zipfile.ZipFile(path) as archive:
        return archive.read("Payload/VVebo.app/VVebo")


def execute(binary, supports_qos):
    uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
    uc.mem_map(BASE, 0x900000)
    uc.mem_write(BASE, binary)
    uc.mem_map(0x300000000, 0x10000)
    uc.mem_map(STOP, 0x10000)
    uc.mem_write(BLOCK + 32, struct.pack("<Q", MANAGER_CLASS))
    uc.mem_write(BASE + 0x6CF5D8, struct.pack("<Q", CACHE_CLASS))
    uc.mem_write(BASE + 0x6CF4B0, struct.pack("<Q", QUEUE_CLASS))
    uc.mem_write(BASE + 0x722AC0, b"\0" * 8)
    selectors = {}
    for offset in (0x6CA0A8, 0x6C8E68, 0x6CA0B0):
        pointer = struct.unpack_from("<Q", binary, offset)[0] & 0xFFFFFFFFF
        selectors[pointer] = binary[pointer - BASE:].split(b"\0", 1)[0].decode()
        uc.mem_write(BASE + offset, struct.pack("<Q", pointer))
    assert set(selectors.values()) == {"sharedCache", "setQualityOfService:", "initWithCache:queue:"}
    uc.reg_write(UC_ARM64_REG_X0, BLOCK)
    uc.reg_write(UC_ARM64_REG_SP, SP)
    uc.reg_write(UC_ARM64_REG_FP, 0xABCDEF)
    uc.reg_write(UC_ARM64_REG_LR, STOP)
    qos = []
    releases = []
    initialized = []

    def ret(value):
        uc.reg_write(UC_ARM64_REG_X0, value)
        uc.reg_write(UC_ARM64_REG_PC, uc.reg_read(UC_ARM64_REG_LR))

    def callback(uc, pc, size, _):
        x0, x1, x2, x3 = (uc.reg_read(r) for r in
            (UC_ARM64_REG_X0, UC_ARM64_REG_X1, UC_ARM64_REG_X2, UC_ARM64_REG_X3))
        if pc == BASE + 0x565578:
            selector = selectors[x1]
            if selector == "sharedCache":
                assert x0 == CACHE_CLASS
                ret(CACHE)
            elif selector == "setQualityOfService:":
                assert x0 == QUEUE and supports_qos
                qos.append(x2)
                ret(0)
            elif selector == "initWithCache:queue:":
                assert (x0, x2, x3) == (MANAGER, CACHE, QUEUE)
                initialized.append(True)
                ret(MANAGER)
        elif pc == BASE + 0x5655A8:
            assert x0 == QUEUE_CLASS
            ret(QUEUE)
        elif pc == BASE + 0x5655B4:
            assert x0 == QUEUE and selectors[x1] == "setQualityOfService:"
            ret(int(supports_qos))
        elif pc == BASE + 0x565488:
            assert x0 == MANAGER_CLASS
            ret(MANAGER)
        elif pc == BASE + 0x5655FC:
            ret(x0)
        elif pc == BASE + 0x5655CC:
            releases.append(x0)
            ret(0)

    uc.hook_add(UC_HOOK_CODE, callback)
    uc.emu_start(BASE + 0x28970, STOP, count=300)
    assert uc.reg_read(UC_ARM64_REG_PC) == STOP
    assert uc.reg_read(UC_ARM64_REG_SP) == SP and uc.reg_read(UC_ARM64_REG_FP) == 0xABCDEF
    assert initialized == [True] and releases == [0, QUEUE, CACHE]
    assert struct.unpack("<Q", uc.mem_read(BASE + 0x722AC0, 8))[0] == MANAGER
    return qos


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline")
    parser.add_argument("candidate")
    args = parser.parse_args()
    before, after = image(args.baseline), image(args.candidate)
    assert before[0x289D0:0x289D4] == bytes.fromhex("22018052")
    assert after[0x289D0:0x289D4] == bytes.fromhex("22038052")
    assert execute(before, True) == [9]
    assert execute(after, True) == [25]
    assert execute(before, False) == execute(after, False) == []
    print("PASS: actual ARM64 image-manager initialization changes queue QoS from background(9) to user-initiated(25), keeps the availability guard/cache/queue wiring, balances cleanup and preserves stack/FP.")
    print("LIMIT: ObjC methods are mocked; no real latency, decoding, scroll smoothness or power usage was measured.")
