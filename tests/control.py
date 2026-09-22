import json,time
from pathlib import Path
root=Path(__file__).resolve().parents[1]
qa=root/'work/qa'
def state():
    try:return json.loads((qa/'state.json').read_text(encoding='utf-8'))
    except (OSError,ValueError):return {}
def wait(check,seconds=20):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        s=state()
        if check(s):return s
        time.sleep(.1)
    raise RuntimeError('State timeout: '+json.dumps(state(),ensure_ascii=False)[:1500])
def send(action,**values):
    ident=int(time.time()*1000)
    tmp=qa/'next.json'
    tmp.write_text(json.dumps({'id':ident,'action':action,**values}),encoding='utf-8')
    for attempt in range(50):
        try:
            tmp.replace(qa/'command.json');break
        except PermissionError:
            if attempt==49:raise
            time.sleep(.03)
    wait(lambda s:s.get('commandId',-1)>=ident)
    return ident
