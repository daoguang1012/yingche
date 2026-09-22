"""Build the actual upstream GPUPixel BeautyFaceFilter into the MV3 extension.
Local toolchain: tools/emsdk, emsdk install 6.0.10 && emsdk activate 6.0.10.
No system PATH or global SDK installation is required.
"""
from pathlib import Path
import subprocess,sys,json,hashlib,os
ROOT=Path(__file__).resolve().parents[1]
SDK=ROOT/'tools/emsdk'
GPU=ROOT/'third_party/gpupixel'
OUT=ROOT/'edge-extension/gpupixel.js'
parts=['core/gpupixel.cc','core/gpupixel_program.cc','core/gpupixel_framebuffer.cc',
       'core/gpupixel_framebuffer_factory.cc','source/source.cc','source/source_image.cc',
       'sink/sink.cc','utils/math_toolbox.cc','utils/util.cc']
sources=[GPU/'src'/p for p in parts]+sorted((GPU/'src/filter').glob('*.cc'))
sources += [ROOT/'src/web/gpupixel_web_context.cpp',ROOT/'src/web/gpupixel_web.cpp']
args=[str(SDK/'python/3.13.3_64bit/python.exe'),str(SDK/'upstream/emscripten/em++.py'),
      '-O3','-std=c++17','-fexceptions','-DNDEBUG',
      '-sMODULARIZE=1','-sEXPORT_NAME=GPUPixelModule','-sSINGLE_FILE=1',
      '-sSINGLE_FILE_BINARY_ENCODE=0','-sENVIRONMENT=web',
      '-sDYNAMIC_EXECUTION=0','-sALLOW_MEMORY_GROWTH=1',
      '-sMIN_WEBGL_VERSION=2','-sMAX_WEBGL_VERSION=2','-sFULL_ES2=1',
      '-sGL_PREINITIALIZED_CONTEXT=1','-sFORCE_FILESYSTEM=1',
      '-sEXPORTED_RUNTIME_METHODS=["GL","UTF8ToString"]','--no-entry']
for path in ['include','src','third_party/stb/include','third_party/ghc/include']:
    args+=['-I'+str(GPU/path)]
for name in ['lookup_gray.png','lookup_origin.png','lookup_skin.png','lookup_light.png']:
    args+=['--embed-file',str(GPU/'src/res'/name)+'@/gpupixel/res/'+name]
args += list(map(str,sources))+['-o',str(OUT)]
env=os.environ.copy();env['EM_CONFIG']=str(SDK/'.emscripten')
print('Compiling original GPUPixel sources:',len(sources),flush=True)
subprocess.run(args,cwd=ROOT,env=env,check=True)
# Emscripten's top-level var is exposed in the extension isolated world.
meta={'engine':'GPUPixel 1.3.0','upstream':'https://github.com/pixpark/gpupixel',
      'revision':'5415b738817553f339620b89ea755bdbfe44e166','compiler':'Emscripten 6.0.10',
      'sha256':hashlib.sha256(OUT.read_bytes()).hexdigest(),'bytes':OUT.stat().st_size,
      'sources':[str(p.relative_to(ROOT)).replace(chr(92),'/') for p in sources]}
(ROOT/'edge-extension/gpupixel-build.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf-8')
print(json.dumps(meta|{'sources':len(sources)}),flush=True)
