"""Bounded async result reuse: misses cannot extend a face beyond the original sample."""
import sys,time,threading,json
from pathlib import Path
import numpy as np
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'tools'))
from swap_engine import AsyncSwap
class Engine:
 def __init__(self):self.mode='good';self.calls=0;self.entered=threading.Event();self.release=threading.Event()
 def infer(self,image,faces,ids,selected):
  self.calls+=1
  if self.mode=='blocked':self.entered.set();assert self.release.wait(2)
  if self.mode=='error':raise RuntimeError('test failure')
  return [{'id':i} for i in ids if i in selected] if self.mode in ('good','blocked') else []
def wait(test):
 until=time.monotonic()+2
 while not test():
  if time.monotonic()>until:raise AssertionError('Async worker did not settle')
  time.sleep(.002)
engine=Engine();swap=AsyncSwap(engine);image=np.zeros((32,32,3),np.uint8);points=np.linspace(0,1,956).reshape(478,2)
checks=[]
def submit(n,stamp,ident=1):
 calls=engine.calls;swap.submit(image,[points],[ident],{'pts':n,'sampleTime':stamp,'swapTarget':'largest'});wait(lambda:engine.calls>calls and swap.running is None and swap.pending is None)
try:
 submit(1,1000);assert swap.result['patches'];engine.mode='miss';submit(2,1100)
 assert swap.result['reused'] and swap.result['sampleTime']==1000;checks.append('Brief miss keeps original timestamp')
 submit(3,1261);assert not swap.result['patches'];checks.append('Repeated misses cannot extend 260ms expiry')
 engine.mode='good';submit(4,1400);engine.mode='miss';submit(5,1450,2)
 assert not swap.result['patches'];checks.append('Different track never inherits old identity')
 engine.mode='good';submit(6,1600);engine.mode='error';submit(7,1650)
 assert swap.error and not swap.result['patches'];checks.append('Inference failure clears previous result')
 engine.mode='blocked';swap.submit(image,[points],[2],{'pts':8,'sampleTime':1800,'swapTarget':'largest'});assert engine.entered.wait(2)
 swap.reset();engine.release.set();wait(lambda:swap.running is None);assert swap.result is None;checks.append('Reset discards an in-flight completion')
 print(json.dumps({'passed':True,'checks':checks}));(root/'work/v041/async-bounds.json').write_text(json.dumps({'passed':True,'checks':checks},indent=2),encoding='utf-8')
finally:engine.release.set();swap.close();swap.thread.join(timeout=2)
