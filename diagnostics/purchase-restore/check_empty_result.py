"""Check original empty-restore routing without contacting StoreKit or granting anything."""
import zipfile,struct,sys
from unicorn import Uc,UC_ARCH_ARM64,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm64_const import *
BASE=0x100000000;RESULTS=0x300001000;ERRORS=0x300002000;CTX=0x300003000;SP=0x40000fff0
with zipfile.ZipFile(sys.argv[1]) as z:b=z.read('Payload/VVebo.app/VVebo')
for restored,failed in [(0,0),(0,1),(1,0)]:
 u=Uc(UC_ARCH_ARM64,UC_MODE_ARM);u.mem_map(BASE,0x900000);u.mem_write(BASE,b);u.mem_map(0x300000000,0x10000);u.mem_map(0x400000000,0x10000)
 u.mem_write(RESULTS,struct.pack('<QQQQ',0,0,restored,restored));u.mem_write(ERRORS,struct.pack('<QQQQ',0,0,failed,failed));u.mem_write(CTX,bytes(range(64)))
 for r,v in [(UC_ARM64_REG_X0,RESULTS),(UC_ARM64_REG_X1,ERRORS),(UC_ARM64_REG_X2,CTX),(UC_ARM64_REG_X3,0x1234),(UC_ARM64_REG_X4,0x5678),(UC_ARM64_REG_SP,SP)]:u.reg_write(r,v)
 route=[]
 def hook(u,pc,size,data):
  if pc in [BASE+0x11ab80,BASE+0x11acd8]:route.append('continue_receipt' if pc==BASE+0x11ab80 else 'no_purchase_record');u.emu_stop()
 u.hook_add(UC_HOOK_CODE,hook);u.emu_start(BASE+0x11ab50,BASE+0x11ad90,count=40)
 assert route==(['continue_receipt'] if restored else ['no_purchase_record'])
 assert bytes(u.mem_read(CTX,64))==bytes(range(64))
 print('Restored entries',restored,'failed entries',failed,'=>',route[0])
print('PASS: an empty restored list selects the same no-record branch even with a modeled nonempty failure list. This does not establish actual StoreKit results, original purchase type, or failure reason.')
