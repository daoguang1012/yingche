"""Generate the GUI-free DLC core from pinned, auditable upstream source.
DLC functions are copied verbatim, with explicit dependencies supplied below.
"""
import ast,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DLC=ROOT/'third_party/deep-live-cam/modules/processors/frame'
OUT=ROOT/'tools/dlc_core'
OUT.mkdir(exist_ok=True)
header='''# Derived from hacksider/Deep-Live-Cam, AGPL-3.0-or-later.
# Revision d759e31b11d9432afdfddce698c0f7c9a715e086.
# Selected upstream functions are unchanged; GUI imports and device selection are host-owned.
from typing import Any, Tuple, Optional
import cv2, numpy as np, threading, onnxruntime
Frame=np.ndarray
Face=Any
_HAS_TORCH_CUDA=False
_paste_cache={'soft_alpha':None,'alpha_size':0}
THREAD_SEMAPHORE=threading.Semaphore()
def run_inference(session,input_name,input_tensor):
    return session.run(None,{input_name:input_tensor})[0]
'''
def select(file,names):
 s=(DLC/file).read_text(encoding='utf-8');tree=ast.parse(s)
 selected={node.name:ast.get_source_segment(s,node) for node in tree.body if isinstance(node,(ast.FunctionDef,ast.ClassDef)) and node.name in names}
 assert set(selected)==set(names)
 return '\n\n'.join(selected[n] for n in names)+'\n'
(OUT/'__init__.py').write_text(header+select('face_swapper.py',['_get_soft_alpha','_fast_paste_back','apply_color_transfer'])+
 select('_onnx_enhancer.py',['preprocess_face','postprocess_face','_get_face_affine','enhance_face_onnx']),encoding='utf-8')
INS=ROOT/'third_party/insightface/insightface';dest=ROOT/'tools/insightface_runtime'
for p in ['','utils','model_zoo','app']:
 (dest/p).mkdir(parents=True,exist_ok=True);(dest/p/'__init__.py').write_text('# Selected InsightFace 0.7.3 ONNX runtime, upstream MIT.\n')
for p in ['utils/face_align.py','model_zoo/inswapper.py','model_zoo/arcface_onnx.py','model_zoo/retinaface.py','model_zoo/landmark.py','app/common.py']:
 shutil.copy2(INS/p,dest/p)
shutil.copy2(ROOT/'third_party/deep-live-cam/LICENSE',ROOT/'licenses/Deep-Live-Cam-AGPL-3.0.txt')
print('DLC core and InsightFace ONNX runtime generated')

p=dest/'utils/face_align.py'
s=p.read_text().replace('from skimage import transform as trans','from . import similarity_transform as trans')
p.write_text('# Modified: lightweight NumPy similarity transform.\n'+s,encoding='utf-8')
