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
    UC_ARM64_REG_X8, UC_ARM64_REG_X19, UC_ARM64_REG_X20, UC_ARM64_REG_FP,
    UC_ARM64_REG_D0, UC_ARM64_REG_D1, UC_ARM64_REG_D2, UC_ARM64_REG_D3,
    UC_ARM64_REG_X3)

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
            'UIVibrancyEffect': 'UIVisualEffect', 'UIVisualEffectView': 'UIView', 'UILabel': 'UIView',
            '_TtC5VVebo8BlurView': 'UIView', '_TtC5VVebo11BaseBarView': 'UIView',
            '_TtC5VVebo6Tabbar': '_TtC5VVebo11BaseBarView'}
        for name in ('UIGlassEffect', 'UIBlurEffect', 'UIVisualEffectView',
                     '_TtC5VVebo8BlurView', '_TtC5VVebo11BaseBarView', 'NSThread',
                     'UIView', 'UICornerConfiguration', '_TtC5VVebo10BlurButton', 'UILabel', 'UIColor'):
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
                ('_barClass', '_TtC5VVebo11BaseBarView'), ('_plainViewClass', 'UIView'),
                ('_cornerClass', 'UICornerConfiguration'), ('_blurButtonClass', '_TtC5VVebo10BlurButton')):
            self.q(self.symbols[variable], self.classes[name])
        self.q(self.symbols['_originalLayout'], LAYOUT)
        self.q(self.symbols['_originalStyle'], STYLE)
        status_address = self.symbols['_statusReason']
        self.q(status_address, struct.unpack('<Q', self.uc.mem_read(status_address, 8))[0] & 0xFFFFFFFFF)
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
        flags = struct.unpack('<Q', self.uc.mem_read(pointer + 8, 8))[0]
        if flags & 0x10:
            length = struct.unpack('<Q', self.uc.mem_read(pointer + 24, 8))[0]
            return bytes(self.uc.mem_read(start, length * 2)).decode('utf-16-le')
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
        elif name == '_objc_storeStrong':
            self.q(x0, x1)
            self.ret()
        elif name == '_objc_alloc':
            self.ret(self.obj(self.objects[x0]['name']))
        elif name == '_dispatch_time':
            self.ret(x1)
        elif name == '_dispatch_after_f':
            self.events.append(('scheduled', x0, uc.reg_read(UC_ARM64_REG_X3)))
            self.ret()
        elif name == '_object_getClass':
            if not x0:
                self.ret(0)
            else:
                cls = self.objects[x0]['class']
                if cls not in self.classes: self.classes[cls] = self.obj('Class', name=cls)
                self.ret(self.classes[cls])
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
            elif sel == 'subviews': value = self.obj('NSArray', items=list(obj.get('children', [])))
            elif sel == 'windows': value = self.obj('NSArray', items=getattr(self, 'windows', []))
            elif sel == 'count': value = len(obj['items'])
            elif sel == 'objectAtIndex:': value = obj['items'][x2]
            elif sel == 'effect': value = obj['effect']
            elif sel == 'isUserInteractionEnabled': value = int(obj.get('interactive', True))
            elif sel == 'backgroundColor': value = obj.get('background', 0)
            elif sel == 'isHidden': value = int(obj.get('hidden', False))
            elif sel == 'setHidden:':
                obj['hidden'] = bool(x2)
                self.events.append(('setHidden', x0, bool(x2)))
                value = 0
            elif sel == 'numberWithBool:': value = self.obj('NSNumber', boolean=bool(x2))
            elif sel == 'boolValue': value = int(obj['boolean'])
            elif sel == 'capsuleConfiguration': value = self.obj('UICornerConfiguration')
            elif sel == 'cornerConfiguration': value = obj.get('corner', 0)
            elif sel == 'setCornerConfiguration:':
                obj['corner'] = x2
                value = 0
            elif sel == 'frame':
                for reg, number in zip((UC_ARM64_REG_D0, UC_ARM64_REG_D1, UC_ARM64_REG_D2, UC_ARM64_REG_D3), obj.get('frame', (0., 0., 300., 60.))):
                    uc.reg_write(reg, struct.unpack('<Q', struct.pack('<d', number))[0])
                value = 0
            elif sel == 'setFrame:':
                obj['frame'] = tuple(struct.unpack('<d', uc.reg_read(reg).to_bytes(8, 'little'))[0] for reg in
                    (UC_ARM64_REG_D0, UC_ARM64_REG_D1, UC_ARM64_REG_D2, UC_ARM64_REG_D3))
                value = 0
            elif sel == 'bounds':
                for reg, number in zip((UC_ARM64_REG_D0, UC_ARM64_REG_D1, UC_ARM64_REG_D2, UC_ARM64_REG_D3), (0., 0., 390., 844.)):
                    uc.reg_write(reg, struct.unpack('<Q', struct.pack('<d', number))[0])
                value = 0
            elif sel == 'initWithFrame:':
                obj['frame'] = tuple(struct.unpack('<d', uc.reg_read(reg).to_bytes(8, 'little'))[0] for reg in
                    (UC_ARM64_REG_D0, UC_ARM64_REG_D1, UC_ARM64_REG_D2, UC_ARM64_REG_D3))
                value = x0
            elif sel == 'stringWithFormat:':
                fmt = self.string(x2)
                arg = struct.unpack('<Q', uc.mem_read(uc.reg_read(UC_ARM64_REG_SP), 8))[0]
                text = fmt.replace('%lu', str(arg)) if '%lu' in fmt else fmt.replace('%@', self.string(arg))
                value = self.obj('NSString', text=text)
            elif sel == 'colorWithRed:green:blue:alpha:':
                components = tuple(struct.unpack('<d', uc.reg_read(reg).to_bytes(8, 'little'))[0] for reg in
                    (UC_ARM64_REG_D0, UC_ARM64_REG_D1, UC_ARM64_REG_D2, UC_ARM64_REG_D3))
                assert components[3] == 1.0
                value = self.obj('UIColor', rgba=components)
            elif sel in ('secondarySystemBackgroundColor', 'labelColor'): value = self.obj('UIColor')
            elif sel.startswith('set') and sel in ('setText:', 'setNumberOfLines:', 'setTextAlignment:', 'setUserInteractionEnabled:', 'setBackgroundColor:', 'setTextColor:', 'setAutoresizingMask:'):
                obj[sel] = x2
                value = 0
            elif sel == 'addSubview:':
                obj.setdefault('children', []).append(x2)
                self.objects[x2]['parent'] = x0
                self.events.append(('addSubview', x0, x2))
                value = 0
            elif sel == 'insertSubview:atIndex:':
                assert uc.reg_read(UC_ARM64_REG_X3) == 0
                obj.setdefault('children', []).insert(0, x2)
                self.objects[x2]['parent'] = x0
                self.events.append(('insertSubview', x0, x2))
                value = 0
            elif sel == 'removeFromSuperview':
                parent = obj.get('parent')
                if parent: self.objects[parent]['children'].remove(x0)
                obj['parent'] = 0
                self.events.append(('removeFromSuperview', x0))
                value = 0
            elif sel == 'setEffect:':
                obj['effect'] = x2
                self.events.append(('setEffect', x0, x2))
                value = 0
            elif sel == 'effectWithStyle:':
                assert obj['name'] in ('UIGlassEffect', 'UIBlurEffect') and x2 == 1
                self.events.append(('factory', obj['name']))
                value = self.obj(obj['name'])
            elif sel == 'initWithEffect:':
                obj['effect'] = x2
                value = x0
            elif sel == 'contentView':
                if 'content' not in obj: obj['content'] = self.obj('UIView', parent=x0)
                value = obj['content']
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
        self.bar = bar
        self.view = self.obj('_TtC5VVebo8BlurView', parent=bar)
        container = self.obj('UIView', parent=self.view)
        self.container = container
        self.blur = self.obj('UIVibrancyEffect' if vibrancy else 'UIBlurEffect')
        self.effect = self.obj('UIVisualEffectView', parent=container, effect=self.blur)
        self.objects[self.view]['children'] = [container]
        self.objects[bar]['children'] = [self.view]
        self.objects[container]['children'] = [self.effect]

    def add_plate(self, **overrides):
        plate = self.obj('UIView', parent=self.container, interactive=False, background=self.obj('UIColor'))
        self.objects[plate].update(overrides)
        self.objects[self.container]['children'].append(plate)
        return plate

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
    m = Model(binary); m.setup_bar(); plate = m.add_plate()
    content = m.add_plate(children=[m.obj('UILabel')]); interactive = m.add_plate(interactive=True)
    initially_hidden = m.add_plate(hidden=True)
    m.call('_ApplyGlass')
    fresh = [p for p in m.objects[m.container]['children'] if p != m.effect and m.objects[p]['class'] == 'UIVisualEffectView']
    assert len(fresh) == 1; fresh = fresh[0]
    assert m.objects[m.container]['children'][0] == fresh
    assert m.kind(m.objects[fresh]['effect'], m.classes['UIGlassEffect'])
    assert m.objects[m.effect]['effect'] == m.blur, 'Old blur object was modified'
    assert m.objects[m.effect]['hidden'] and m.objects[fresh]['frame'] == (0., 0., 300., 60.)
    assert m.objects[fresh]['setUserInteractionEnabled:'] == 0 and m.objects[fresh]['corner']
    assert m.objects[plate]['hidden'] and m.objects[initially_hidden]['hidden']
    assert not m.objects[content].get('hidden') and not m.objects[interactive].get('hidden')
    m.objects[m.effect]['frame'] = (1., 2., 320., 70.); m.call('_ApplyGlass')
    assert m.objects[fresh]['frame'] == (1., 2., 320., 70.)
    assert m.events.count(('factory', 'UIGlassEffect')) == 1
    m.reduced = True; m.call('_ApplyGlass')
    assert fresh not in m.objects[m.container]['children'] and not m.objects[m.effect]['hidden']
    assert not m.objects[plate]['hidden'] and m.objects[initially_hidden]['hidden']
    for inside, vibrancy, reduced, main_thread in ((False, False, False, True),
            (True, True, False, True), (True, False, True, True), (True, False, False, False)):
        m = Model(binary); m.setup_bar(inside, vibrancy); m.reduced = reduced; m.main = main_thread
        m.call('_ApplyGlass')
        assert m.objects[m.effect]['effect'] == m.blur and not m.events
    m = Model(binary); m.setup_bar(); m.objects[m.view]['parent'] = m.obj('_TtC5VVebo10BlurButton', parent=m.objects[m.view]['parent'])
    m.call('_ApplyGlass'); assert not m.events
    m = Model(binary); m.setup_bar(); m.call('_GlassLayout')
    assert m.events[0] == ('original', LAYOUT, m.view, MODEL + 0x900, MODEL + 0xA00)
    m.events.clear(); m.call('_GlassStyle')
    assert m.events[0][0:2] == ('original', STYLE)
    assert not any(e[0] == 'factory' for e in m.events), 'Theme update duplicated the new background'
    for version, bundle, missing, expected in ((15, 'com.johnil.vvebo', False, 0),
            (26, 'other.bundle', False, 0), (26, 'com.johnil.vvebo', True, 0),
            (26, 'com.johnil.vvebo', False, 2)):
        m = Model(binary); m.setup_bar(); m.os_version = version; m.bundle = bundle
        if missing: del m.classes['UIGlassEffect']
        m.call('_InstallGlass', receiver=0)
        assert len([e for e in m.events if e[0] == 'replace']) == expected
        m.call('_InstallGlass', receiver=0)
        assert len([e for e in m.events if e[0] == 'replace']) == expected
    m = Model(binary); m.setup_bar(); m.add_plate()
    window = m.obj('UIView', children=[m.bar]); m.objects[m.bar]['parent'] = window; m.windows = [window]
    m.call('_InstallGlass', receiver=0); m.call('_ShowStatus', receiver=0)
    assert len(m.objects[window]['children']) == 3, 'Expected original UI, status label, comparison card'
    status = m.objects[window]['children'][1]; card = m.objects[window]['children'][2]
    assert '已新建' in m.string(m.objects[status]['setText:'])
    assert m.objects[card]['frame'] == (16., 174., 358., 158.)
    samples = [m.objects[p] for p in m.objects[card]['children'] if m.objects[p]['class'] == 'UIVisualEffectView']
    assert len(samples) == 2
    assert [m.objects[o['effect']]['class'] for o in samples] == ['UIBlurEffect', 'UIGlassEffect']
    stripes = [m.objects[p] for p in m.objects[card]['children'] if m.objects[p]['class'] == 'UIView']
    assert len(stripes) == 8
    colors = [m.objects[o['setBackgroundColor:']]['rgba'] for o in stripes]
    assert colors[:4] == colors[4:], 'Comparison backgrounds are not identical'
    assert all(o['setUserInteractionEnabled:'] == 0 for o in samples)
    scheduled = [e for e in m.events if e[0] == 'scheduled']; assert len(scheduled) == 1 and scheduled[0][1] == 12000000000
    m.call('_HideStatus', receiver=0); assert m.objects[window]['children'] == [m.bar]
    print('PASS: actual ARM64 fresh surface creation, original blur/visibility preservation, stacking, geometry refresh, scope exclusions, reversible color plates, transparency fallback, installation guards, original callbacks, native comparison card and timed cleanup.')
    print('LIMIT: Foundation/UIKit/ObjC runtime are modeled; rendering, actual lifecycle and device stability remain unverified.')


if __name__ == '__main__': main()
