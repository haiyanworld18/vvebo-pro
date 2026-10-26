"""Execute the original Date getter with its four receiver/selector changes.

Foundation objects and Swift value witnesses are mocked. The actual packaged
ARM64 retains the original Date bridging, Optional handling, ARC cleanup and
stack frame; no stored preference or receipt is modified by this getter.
"""

import argparse
import struct
import zipfile

from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
import unicorn.arm64_const as regs

BASE = 0x100000000
DATE_META, DATE_VWT = 0x300001100, 0x300001200
OPTIONAL_META, OPTIONAL_VWT = 0x300002100, 0x300002200
DATE_CLASS, DATE_OBJECT, KEY = 0x300003000, 0x300004000, 0x300005000
DEFAULTS, OUTPUT = 0x300006000, 0x300007000
STOP, COPY, TAG, CHK = 0x300010000, 0x300011000, 0x300011100, 0x300011200
GET_TAG, DESTROY = 0x300011300, 0x300011400
MODEL = 0x300008000
SP = 0x40000FFF0
FUTURE = 63113904000.0  # Model NSDate.distantFuture in Date reference-time units.
PAST = -31536000.0


def image(path):
    with zipfile.ZipFile(path) as archive:
        return archive.read("Payload/VVebo.app/VVebo")


def execute(binary, stored_date, refresh_state=False):
    uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
    uc.mem_map(BASE, 0x900000)
    uc.mem_write(BASE, binary)
    uc.mem_map(0x300000000, 0x20000)
    uc.mem_map(0x400000000, 0x10000)
    def qword(address, value):
        uc.mem_write(address, struct.pack("<Q", value))
    qword(DATE_META - 8, DATE_VWT)
    qword(DATE_VWT + 0x40, 8)
    qword(DATE_VWT + 0x20, COPY)
    qword(DATE_VWT + 0x38, TAG)
    qword(DATE_VWT + 0x30, GET_TAG)
    qword(DATE_VWT + 8, DESTROY)
    qword(OPTIONAL_META - 8, OPTIONAL_VWT)
    qword(OPTIONAL_VWT + 0x40, 16)
    qword(BASE + 0x64B928, CHK)
    qword(BASE + 0x6F7820, 0xFFFFFFFFFFFFFFFF)
    qword(BASE + 0x700288, DEFAULTS)
    qword(BASE + 0x6CFBF8, DATE_CLASS)
    preferences = bytes(range(64))
    uc.mem_write(DEFAULTS, preferences)
    uc.mem_write(OUTPUT, b"\xAA" * 16)
    selectors = {}
    for offset in (0x6CA5A0, 0x6CEC40):
        pointer = struct.unpack_from("<Q", binary, offset)[0] & 0xFFFFFFFFF
        selectors[pointer] = binary[pointer - BASE:].split(b"\0", 1)[0].decode()
        qword(BASE + offset, pointer)
    assert selectors.values() and "distantFuture" in selectors.values()
    uc.reg_write(regs.UC_ARM64_REG_SP, SP)
    uc.reg_write(regs.UC_ARM64_REG_LR, STOP)
    uc.reg_write(regs.UC_ARM64_REG_FP, 0xABCDEF)
    uc.reg_write(regs.UC_ARM64_REG_X8, OUTPUT)
    for index in range(19, 29):
        uc.reg_write(getattr(regs, "UC_ARM64_REG_X" + str(index)), 0xA000 + index)
    if refresh_state:
        uc.reg_write(regs.UC_ARM64_REG_X20, MODEL)
    messages, releases, bridges = [], [], []
    published = {}
    returned_date = [None]

    def ret(value=None):
        if value is not None:
            uc.reg_write(regs.UC_ARM64_REG_X0, value)
        uc.reg_write(regs.UC_ARM64_REG_PC, uc.reg_read(regs.UC_ARM64_REG_LR))

    def callback(uc, pc, size, _):
        x0, x1, x2, x3, x8 = (uc.reg_read(r) for r in
            (regs.UC_ARM64_REG_X0, regs.UC_ARM64_REG_X1,
             regs.UC_ARM64_REG_X2, regs.UC_ARM64_REG_X3, regs.UC_ARM64_REG_X8))
        if pc == BASE + 0x561B4C:
            ret(DATE_META)
        elif pc == BASE + 0x346CC:
            assert x0 == BASE + 0x6FD558
            ret(OPTIONAL_META)
        elif pc == CHK:
            ret()
        elif pc == BASE + 0x5634A8:
            text = x0.to_bytes(8, "little") + x1.to_bytes(8, "little")[:7]
            assert text[:10] == b"expireDate"
            ret(KEY)
        elif pc == BASE + 0x565578:
            selector = selectors[x1]
            messages.append(selector)
            if selector == "distantFuture":
                assert x0 == DATE_CLASS
                returned_date[0] = FUTURE
                ret(DATE_OBJECT)
            else:
                assert x0 == DEFAULTS and x2 == KEY
                returned_date[0] = stored_date
                ret(DATE_OBJECT if stored_date is not None else 0)
        elif pc == BASE + 0x5655FC:
            ret(x0)
        elif pc == BASE + 0x5655CC:
            releases.append(x0)
            ret(0)
        elif pc == BASE + 0x561B28:
            assert x0 == DATE_OBJECT and returned_date[0] is not None
            bridges.append(returned_date[0])
            uc.mem_write(x8, struct.pack("<d", returned_date[0]))
            ret()
        elif pc in (BASE + 0x561B04, BASE + 0x561B40):
            value = 800000000.0 if pc == BASE + 0x561B40 else (
                struct.unpack("<d", uc.reg_read(regs.UC_ARM64_REG_D0).to_bytes(8, "little"))[0] - 978307200.0)
            uc.mem_write(x8, struct.pack("<d", value))
            ret()
        elif pc == COPY:
            assert x2 == DATE_META
            uc.mem_write(x0, bytes(uc.mem_read(x1, 8)))
            ret(x0)
        elif pc == TAG:
            assert x1 in (0, 1) and x2 == 1 and x3 == DATE_META
            uc.mem_write(x0 + 8, bytes([x1]))
            ret()
        elif pc == GET_TAG:
            assert x1 == 1 and x2 == DATE_META
            ret(bytes(uc.mem_read(x0 + 8, 1))[0])
        elif pc == DESTROY:
            assert x1 == DATE_META
            ret()
        elif pc == BASE + 0x125D2C:
            assert (refresh_state or x1 == OUTPUT) and x2 == BASE + 0x6FD558
            uc.mem_write(x1, bytes(uc.mem_read(x0, 16)))
            ret(x1)
        elif pc == BASE + 0x56346C:
            left = struct.unpack("<d", uc.mem_read(x0, 8))[0]
            right = struct.unpack("<d", uc.mem_read(x1, 8))[0]
            ret(int(left < right))
        elif pc == BASE + 0x12635C:
            ret(0x300009000)
        elif pc == BASE + 0x565B18:
            ret(x0)
        elif pc == BASE + 0x5655D8:
            ret(x0)
        elif pc == BASE + 0x565C08:
            ret()
        elif pc == BASE + 0x562218:
            assert x1 == MODEL
            names = {BASE + 0x5A3FD0: "isPayed", BASE + 0x5A4018: "isExpired",
                     BASE + 0x5A4138: "isForeverPayed", BASE + 0x5A4060: "subtitle"}
            name = names[x2]
            published[name] = bytes(uc.mem_read(x0, 16)) if name == "subtitle" else bool(uc.mem_read(x0, 1)[0])
            ret()

    uc.hook_add(UC_HOOK_CODE, callback)
    uc.emu_start(BASE + (0x11902C if refresh_state else 0x119878), STOP, count=5000)
    assert uc.reg_read(regs.UC_ARM64_REG_PC) == STOP
    assert uc.reg_read(regs.UC_ARM64_REG_SP) == SP
    assert uc.reg_read(regs.UC_ARM64_REG_FP) == 0xABCDEF
    for index in range(19, 29):
        expected = MODEL if refresh_state and index == 20 else 0xA000 + index
        assert uc.reg_read(getattr(regs, "UC_ARM64_REG_X" + str(index))) == expected
    assert bytes(uc.mem_read(DEFAULTS, 64)) == preferences
    if refresh_state:
        assert published["isPayed"] is True
        assert published["isExpired"] is False
        assert published["isForeverPayed"] is True
        assert "subtitle" in published
        return published, messages
    output = bytes(uc.mem_read(OUTPUT, 16))
    tag = output[8]
    value = None if tag else struct.unpack_from("<d", output)[0]
    assert releases == ([KEY] if returned_date[0] is None else [KEY, DATE_OBJECT])
    assert bridges == ([] if returned_date[0] is None else [returned_date[0]])
    return value, messages


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline")
    parser.add_argument("candidate")
    args = parser.parse_args()
    before, after = image(args.baseline), image(args.candidate)
    for value in (None, PAST):
        old, _ = execute(before, value)
        new, messages = execute(after, value)
        assert old == value and new == FUTURE
        assert messages == ["distantFuture"]
        execute(after, value, refresh_state=True)
    assert FUTURE > 31536000000.0  # Beyond original app's permanent-Pro threshold.
    print("PASS: actual ARM64 getter uses NSDate.distantFuture with original bridging/cleanup; original state updater publishes paid=true, expired=false and forever=true for missing/expired local state. Stack/registers and modeled preferences remain intact.")
    print("LIMIT: Foundation/Swift witnesses are mocked; real Pro UI and each feature require device testing. No App Store receipt, subscription or cloud authority is created.")
