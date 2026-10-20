"""Compare fixed real-video frames against the preserved 0.6.0 binary."""
import argparse, hashlib, json, os, subprocess, time
from pathlib import Path
import cv2
import numpy as np
import control

ROOT=Path(__file__).resolve().parents[1]
PRESETS={
    'natural':{'smooth':25,'detail':70,'white':10,'warm':0,'pink':0,'slim':0,'eyes':0,'chin':0,'nose':0,'lip':0,'blush':0,'sharp':8},
    'soft':{'smooth':45,'detail':60,'white':18,'warm':0,'pink':6,'slim':0,'eyes':0,'chin':0,'nose':0,'lip':0,'blush':0,'sharp':6},
}

def capture(exe, output, clip):
    output.mkdir(parents=True)
    control.qa=output/'qa';control.qa.mkdir()
    env=dict(os.environ)
    for key in ['APPDATA','LOCALAPPDATA']:
        path=output/key;path.mkdir();env[key]=str(path)
    log=(output/'player.log').open('w',encoding='utf-8')
    proc=subprocess.Popen([str(exe),'--control-dir',str(control.qa)],cwd=exe.parent.parent,
                          env=env,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
    images={}
    try:
        control.wait(lambda s:s.get('workerReady') and s.get('gpupixelReady'),40)
        control.send('load',path=str(clip));control.wait(lambda s:s.get('loaded'))
        control.send('pause',value=True);control.send('seek',seconds=35)
        control.wait(lambda s:abs(s.get('position',0)-35)<.02 and s.get('resultGeneration')==s.get('generation') and s.get('faces',0)>0,30)
        for name in ['original',*PRESETS]:
            control.send('enabled',value=name!='original')
            if name in PRESETS:control.send('beauty',values=PRESETS[name])
            # Allow the specified 180 ms parameter transition to reach its terminal frame.
            time.sleep(.65)
            path=output/(name+'.png');control.send('snapshot',path=str(path))
            image=cv2.imread(str(path));assert image is not None
            images[name]=image
        state=control.state()
        assert not state.get('syncActive',False) and state.get('audioDelayMs',0)==0
        control.send('quit');proc.wait(timeout=15);assert proc.returncode==0
    finally:
        if proc.poll() is None:
            try:control.send('quit');proc.wait(timeout=10)
            except Exception:proc.terminate();proc.wait(timeout=10)
        log.close()
    return images

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',type=Path,required=True)
    parser.add_argument('--candidate',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    args.output=args.output.resolve()
    args.output.mkdir(parents=True,exist_ok=False)
    assert hashlib.sha256(args.baseline.read_bytes()).hexdigest()=='ce8b04e2d0d2a96922e985c8b420987acf70a91a55248451e9de7b1480f8bff8'
    clip=ROOT/'work/v04/intel-fixtures/head-pose-face-detection-female.mp4'
    baseline=capture(args.baseline.resolve(),args.output/'baseline',clip)
    restored=capture(args.candidate.resolve(),args.output/'restored',clip)
    report={'passed':True,'clip':'Intel CC BY head-pose-face-detection-female.mp4','pts':35,'samples':{}}
    for name in baseline:
        assert baseline[name].shape==restored[name].shape
        delta=np.abs(baseline[name].astype(np.int16)-restored[name].astype(np.int16))
        report['samples'][name]={'meanAbsoluteDifference':float(delta.mean()),'maxDifference':int(delta.max()),'exact':bool(np.array_equal(baseline[name],restored[name]))}
        if delta.max()>1:report['passed']=False
    report['restoredNaturalChangedPixels']=int(np.count_nonzero(np.max(np.abs(restored['natural'].astype(np.int16)-restored['original'].astype(np.int16)),axis=2)>1))
    assert report['restoredNaturalChangedPixels']>100
    (args.output/'result.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2),flush=True)
    assert report['passed'], 'Investigate the difference before claiming exact restoration'

if __name__=='__main__':main()
