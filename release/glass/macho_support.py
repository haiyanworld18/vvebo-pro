import struct,hashlib
def commands(b):
 p=32
 for _ in range(struct.unpack_from('<I',b,16)[0]):
  c,s=struct.unpack_from('<II',b,p);yield p,c,s;p+=s

def add_command(b,cmd):
 n,size=struct.unpack_from('<II',b,16);end=32+size
 assert not any(b[end:end+len(cmd)]),'No empty Mach-O header space'
 b[end:end+len(cmd)]=cmd;struct.pack_into('<II',b,16,n+1,size+len(cmd))

def blobs(b):
 for p,c,s in commands(b):
  if c!=0x1d:continue
  off,size=struct.unpack_from('<II',b,p+8)
  magic,length,n=struct.unpack_from('>III',b,off)
  assert magic==0xfade0cc0
  result={}
  for i in range(n):
   slot,rel=struct.unpack_from('>II',b,off+12+i*8)
   length=struct.unpack_from('>I',b,off+rel+4)[0]
   result[slot]=bytes(b[off+rel:off+rel+length])
  return result
 return {}

def sign(binary,identifier,info=None,resources=None):
 b=bytearray(binary);old=blobs(b);kept={k:v for k,v in old.items() if k in [5,7]}
 entry=next(((p,c,s) for p,c,s in commands(b) if c==0x1d),None)
 if entry:
  p=entry[0];start,size=struct.unpack_from('<II',b,p+8)
  assert start+size==len(b),'Signature is not final data'
  b=b[:start]
 else:
  add_command(b,struct.pack('<4I',0x1d,16,0,0));p=next(p for p,c,s in commands(b) if c==0x1d)
 limit=(len(b)+15)&~15;b.extend(b'\0'*(limit-len(b)))
 special={}
 if info is not None:special[1]=info
 if resources is not None:special[3]=resources
 special.update(kept)
 ns=max(special,default=0);nc=(limit+4095)//4096
 ident=identifier.encode()+b'\0';hashoff=88+len(ident)+ns*32;cdlen=hashoff+nc*32
 # SuperBlob: CodeDirectory + optional XML and DER entitlements, no CMS signature.
 payloads={0:None,**kept};count=len(payloads)
 total=12+8*count+cdlen+sum(map(len,kept.values()))
 struct.pack_into('<II',b,p+8,limit,total)
 textsize=0
 for q,c,s in commands(b):
  if c==0x19:
   name=bytes(b[q+8:q+24]).split(b'\0')[0]
   vm,vs,fo,fs=struct.unpack_from('<4Q',b,q+24)
   if name==b'__TEXT':textsize=fs
   if name==b'__LINKEDIT':
    end=limit+total;newfs=end-fo;newvs=(newfs+16383)&~16383
    struct.pack_into('<Q',b,q+32,newvs);struct.pack_into('<Q',b,q+48,newfs)
 flags=2;execflags=1 if struct.unpack_from('<I',b,12)[0]==2 else 0
 header=struct.pack('>9I4B4I4Q',0xfade0c02,cdlen,0x20400,flags,hashoff,88,ns,nc,limit,32,2,0,12,0,0,0,0,0,0,textsize,execflags)
 hashes=b''.join(hashlib.sha256(special[i]).digest() if i in special else b'\0'*32 for i in range(ns,0,-1))
 pages=b''.join(hashlib.sha256(b[i*4096:min(limit,(i+1)*4096)]).digest() for i in range(nc))
 cd=header+ident+hashes+pages;assert len(cd)==cdlen
 payloads[0]=cd;offset=12+8*count;index=b'';body=b''
 for slot,blob in payloads.items():
  index+=struct.pack('>II',slot,offset);body+=blob;offset+=len(blob)
 sig=struct.pack('>III',0xfade0cc0,total,count)+index+body
 assert len(sig)==total
 b.extend(sig)
 return bytes(b),hashlib.sha256(cd).digest()[:20]
