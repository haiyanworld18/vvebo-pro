"""Run compiled ARM64 adapter against a small ObjC/UIKit model.

Checks scope, callback ABI/order, installation guards, idempotence and fallback.
UIKit rendering and Apple signing are not exercised. Requires unicorn.
"""
import argparse
import struct
from pathlib import Path
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm64_const import (UC_ARM64_REG_PC, UC_ARM64_REG_SP,
    UC_ARM64_REG_LR, UC_ARM64_REG_X0, UC_ARM64_REG_X1, UC_ARM64_REG_X2,
    UC_ARM64_REG_X8, UC_ARM64_REG_X19, UC_ARM64_REG_X20, UC_ARM64_REG_FP)

MODEL, STACK, STOP, LAYOUT, STYLE = 0x300000000, 0x400000000, 0x300010000, 0x300010100, 0x300010200


def parse(binary):
    sections, symbols, commands = {}, {}, []
    p = 32
    for _ in range(struct.unpack_from('<I', binary, 16)[0]):
        kind, size = struct.unpack_from('<II', binary, p)
        commands.append((p, kind, size))
        if kind == 2:
            so, count, strings, _ = struct.unpack_from('<4I', binary, p + 8)
        elif kind == 0xB:
            indirect = struct.unpack_from('<I', binary, p + 56)[0]
        elif kind == 0x19:
            for index in range(struct.unpack_from('<I', binary, p + 64)[0]):
                q = p + 72 + 80 * index
                name = binary[q:q + 16].split(b'\0', 1)[0].decode()
                address, length, offset = struct.unpack_from('<QQI', binary, q + 32)
                first, stride = struct.unpack_from('<II', binary, q + 68)
                sections[name] = (address, length, offset, first, stride)
        p += size
    names = []
    for index in range(count):
        n, _, _, _, address = struct.unpack_from('<IBBHQ', binary, so + 16 * index)
        name = binary[strings + n:].split(b'\0', 1)[0].decode()
        names.append(name)
        symbols[name] = address
    address, length, _, first, stride = sections['__stubs']
    stubs = {address + index * stride: names[struct.unpack_from('<I', binary,
             indirect + 4 * (first + index))[0]] for index in range(length // stride)}
    return commands, sections, symbols, stubs


class Model:
    def __init__(self, binary):
        self.binary = binary
        self.commands, self.sections, self.symbols, self.stubs = parse(binary)
        self.uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        self.uc.mem_map(0, 0x40000)
        self.uc.mem_map(MODEL, 0x20000)
        self.uc.mem_map(STACK, 0x10000)
        for p, kind, _ in self.commands:
            if kind == 0x19:
                va, _, off, size = struct.unpack_from('<4Q', binary, p + 24)
                self.uc.mem_write(va, binary[off:off + size])
        self.objects, self.classes, self.events, self.associations = {}, {}, [], {}
        self.main, self.reduced, self.os_version = True, False, 26
        self.bundle = 'com.johnil.vvebo'
        self.next_id = MODEL + 0x1000
        self.superclasses = {'UIGlassEffect': 'UIVisualEffect', 'UIBlurEffect': 'UIVisualEffect',
            'UIVibrancyEffect': 'UIVisualEffect', 'UIVisualEffectView': 'UIView',
            '_TtC5VVebo8BlurView': 'UIView', '_TtC5VVebo11BaseBarView': 'UIView',
            '_TtC5VVebo6Tabbar': '_TtC5VVebo11BaseBarView'}
        for name in ('UIGlassEffect', 'UIBlurEffect', 'UIVisualEffectView',
                     '_TtC5VVebo8BlurView', '_TtC5VVebo11BaseBarView', 'NSThread'):
            self.classes[name] = self.obj('Class', name=name)
        # Rebase selector references and bind the NSThread class import.
        va, length, off, _, _ = self.sections['__objc_selrefs']
        for index in range(0, length, 8):
            self.q(va + index, struct.unpack_from('<Q', binary, off + index)[0] & 0xFFFFFFFFF)
        va, length, off, _, _ = self.sections['__objc_classrefs']
        for index in range(0, length, 8):
            # All declared class references are resolved for installer tests too.
            raw = struct.unpack_from('<Q', binary, off + index)[0]
            p = next(p for p, kind, _ in self.commands if kind == 0x80000034)
            data = struct.unpack_from('<I', binary, p + 8)[0]
            header = struct.unpack_from('<7I', binary, data)
            word = struct.unpack_from('<I', binary, data + header[2] + (raw & 0xFFFFFF) * 4)[0]
            start = data + header[3] + (word >> 9)
            name = binary[start:].split(b'\0', 1)[0].decode().split('$_')[-1]
            if name not in self.classes:
                self.classes[name] = self.obj('Class', name=name)
            self.q(va + index, self.classes[name])
        for variable, name in (('_glassClass', 'UIGlassEffect'), ('_blurClass', 'UIBlurEffect'),
                ('_effectViewClass', 'UIVisualEffectView'), ('_blurViewClass', '_TtC5VVebo8BlurView'),
                ('_barClass', '_TtC5VVebo11BaseBarView')):
            self.q(self.symbols[variable], self.classes[name])
        self.q(self.symbols['_originalLayout'], LAYOUT)
        self.q(self.symbols['_originalStyle'], STYLE)
        self.uc.hook_add(UC_HOOK_CODE, self.hook)

    def obj(self, cls, **kwargs):
        self.next_id += 0x100
        self.objects[self.next_id] = {'class': cls, **kwargs}
        return self.next_id

    def q(self, address, value):
        self.uc.mem_write(address, struct.pack('<Q', value))

    def cstr(self, address):
        return bytes(self.uc.mem_read(address, 200)).split(b'\0', 1)[0].decode()

    def string(self, pointer):
        if pointer in self.objects:
            return self.objects[pointer]['text']
        # CFConstantString contains a chained pointer to UTF-8 at +16.
        start = struct.unpack('<Q', self.uc.mem_read(pointer + 16, 8))[0] & 0xFFFFFFFFF
        return self.cstr(start)

    def kind(self, obj, cls):
        target = self.objects[cls]['name']
        current = self.objects[obj]['class']
        while current:
            if current == target:
                return True
            current = self.superclasses.get(current)
        return False

    def ret(self, value=None):
        if value is not None:
            self.uc.reg_write(UC_ARM64_REG_X0, value)
        self.uc.reg_write(UC_ARM64_REG_PC, self.uc.reg_read(UC_ARM64_REG_LR))

    def hook(self, uc, pc, size, _):
        x0, x1, x2 = (uc.reg_read(reg) for reg in (UC_ARM64_REG_X0, UC_ARM64_REG_X1, UC_ARM64_REG_X2))
        if pc == STOP:
            uc.emu_stop()
            return
        if pc in (LAYOUT, STYLE):
            self.events.append(('original', pc, x0, x1, x2))
            if pc == STYLE:
                # Model original theme update resetting its blur material.
                self.objects[self.effect]['effect'] = self.blur
            self.ret()
            return
        name = self.stubs.get(pc)
        if name is None:
            return
        if name in ('_objc_retain', '_objc_retainAutoreleasedReturnValue', '_objc_autoreleaseReturnValue'):
            self.ret(x0)
        elif name == '_objc_release':
            self.ret()
        elif name == '_UIAccessibilityIsReduceTransparencyEnabled':
            self.ret(int(self.reduced))
        elif name == '_objc_getAssociatedObject':
            self.ret(self.associations.get((x0, x1), 0))
        elif name == '_objc_setAssociatedObject':
            self.associations[x0, x1] = x2
            self.ret()
        elif name == '_NSClassFromString':
            self.ret(self.classes.get(self.string(x0), 0))
        elif name == '_sel_registerName':
            self.ret(x0)
        elif name == '_class_getInstanceMethod':
            self.ret(self.obj('Method', selector=x1, owner=x0))
        elif name == '_method_getImplementation':
            self.ret(LAYOUT if self.cstr(self.objects[x0]['selector']) == 'layoutSubviews' else STYLE)
        elif name == '_method_getTypeEncoding':
            self.ret(MODEL + 0x800)
        elif name == '_class_replaceMethod':
            self.events.append(('replace', x0, self.cstr(x1), x2))
            self.ret(0)
        elif name == '_objc_msgSend':
            sel = self.cstr(x1)
            if x0 == 0:
                self.ret(0)
                return
            obj = self.objects[x0]
            if sel == 'isMainThread': value = int(self.main)
            elif sel == 'isKindOfClass:': value = int(self.kind(x0, x2))
            elif sel == 'respondsToSelector:': value = 1
            elif sel == 'superview': value = obj.get('parent', 0)
            elif sel in ('subviews', 'windows'): value = self.obj('NSArray', items=obj.get('children', []))
            elif sel == 'count': value = len(obj['items'])
            elif sel == 'objectAtIndex:': value = obj['items'][x2]
            elif sel == 'effect': value = obj['effect']
            elif sel == 'setEffect:':
                obj['effect'] = x2
                self.events.append(('setEffect', x0, x2))
                value = 0
            elif sel == 'effectWithStyle:':
                assert x0 == self.classes['UIGlassEffect'] and x2 == 0
                self.events.append(('factory',))
                value = self.obj('UIGlassEffect')
            elif sel == 'mainBundle': value = self.obj('NSBundle')
            elif sel == 'bundleIdentifier': value = self.obj('NSString', text=self.bundle)
            elif sel == 'isEqualToString:': value = int(self.string(x0) == self.string(x2))
            elif sel == 'processInfo': value = self.obj('NSProcessInfo')
            elif sel == 'operatingSystemVersion':
                uc.mem_write(uc.reg_read(UC_ARM64_REG_X8), struct.pack('<qqq', self.os_version, 0, 0))
                value = 0
            elif sel == 'sharedApplication': value = self.obj('UIApplication', children=[])
            else: raise AssertionError('Unexpected selector: ' + sel)
            self.ret(value)
        else:
            raise AssertionError('Unexpected import: ' + name)

    def setup_bar(self, inside=True, vibrancy=False):
        bar = self.obj('_TtC5VVebo6Tabbar' if inside else 'UIView')
        self.view = self.obj('_TtC5VVebo8BlurView', parent=bar)
        container = self.obj('UIView', parent=self.view)
        self.blur = self.obj('UIVibrancyEffect' if vibrancy else 'UIBlurEffect')
        self.effect = self.obj('UIVisualEffectView', parent=container, effect=self.blur)
        self.objects[self.view]['children'] = [container]
        self.objects[container]['children'] = [self.effect]

    def call(self, function, receiver=None):
        self.uc.reg_write(UC_ARM64_REG_SP, STACK + 0xFFF0)
        self.uc.reg_write(UC_ARM64_REG_LR, STOP)
        self.uc.reg_write(UC_ARM64_REG_X0, self.view if receiver is None else receiver)
        self.uc.reg_write(UC_ARM64_REG_X1, MODEL + 0x900)
        self.uc.reg_write(UC_ARM64_REG_X2, MODEL + 0xA00)
        self.uc.reg_write(UC_ARM64_REG_X19, 0xA019)
        self.uc.reg_write(UC_ARM64_REG_X20, 0xA020)
        self.uc.reg_write(UC_ARM64_REG_FP, 0xABCDE)
        self.uc.emu_start(self.symbols[function], STOP, count=100000)
        assert self.uc.reg_read(UC_ARM64_REG_SP) == STACK + 0xFFF0
        assert self.uc.reg_read(UC_ARM64_REG_X19) == 0xA019
        assert self.uc.reg_read(UC_ARM64_REG_X20) == 0xA020
        assert self.uc.reg_read(UC_ARM64_REG_FP) == 0xABCDE


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('framework', type=Path)
    binary = p.parse_args().framework.read_bytes()
    m = Model(binary); m.setup_bar(); m.call('_ApplyGlass')
    assert m.kind(m.objects[m.effect]['effect'], m.classes['UIGlassEffect'])
    m.call('_ApplyGlass')
    assert m.events.count(('factory',)) == 1, 'Repeated layout recreated the effect'
    m.reduced = True; m.call('_ApplyGlass')
    assert m.objects[m.effect]['effect'] == m.blur, 'Accessibility did not restore original blur'
    for inside, vibrancy, reduced, main_thread in ((False, False, False, True),
            (True, True, False, True), (True, False, True, True), (True, False, False, False)):
        m = Model(binary); m.setup_bar(inside, vibrancy); m.reduced = reduced; m.main = main_thread
        m.call('_ApplyGlass')
        assert m.objects[m.effect]['effect'] == m.blur and not m.events
    m = Model(binary); m.setup_bar(); m.call('_GlassLayout')
    assert m.events[0] == ('original', LAYOUT, m.view, MODEL + 0x900, MODEL + 0xA00)
    m.events.clear(); m.call('_GlassStyle')
    assert m.events[0][0:2] == ('original', STYLE) and m.events[1] == ('factory',)
    for version, bundle, missing, expected in ((15, 'com.johnil.vvebo', False, 0),
            (26, 'other.bundle', False, 0), (26, 'com.johnil.vvebo', True, 0),
            (26, 'com.johnil.vvebo', False, 2)):
        m = Model(binary); m.setup_bar(); m.os_version = version; m.bundle = bundle
        if missing: del m.classes['UIGlassEffect']
        m.call('_InstallGlass', receiver=0)
        assert len([e for e in m.events if e[0] == 'replace']) == expected
        m.call('_InstallGlass', receiver=0)
        assert len([e for e in m.events if e[0] == 'replace']) == expected
    print('PASS: compiled ARM64 adapter scope, nested blur, vibrancy exclusion, idempotence, accessibility restore, original callback ABI/order, installation guards and stack/register checks.')
    print('LIMIT: Foundation/UIKit/ObjC runtime are modeled; rendering, actual lifecycle and device stability remain unverified.')


if __name__ == '__main__': main()
