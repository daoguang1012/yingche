"""Opt-in loopback-only bridge for the bundled browser extension."""
import base64,json,secrets,threading,time,socket
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path

def run(model,config):
    from face_worker import FaceProcessor,decode_image
    values=json.loads(Path(config).read_text(encoding='utf-8'))
    extension=values['extensionId'];port=int(values.get('port',18766))
    allowed='chrome-extension://'+extension
    processor=FaceProcessor(model);gate=threading.Lock();token=secrets.token_urlsafe(32)
    class Handler(BaseHTTPRequestHandler):
        protocol_version='HTTP/1.1'
        def log_message(self,*args):pass
        def reply(self,status,value):
            payload=json.dumps(value,separators=(',',':')).encode()
            self.send_response(status)
            origin=self.headers.get('Origin')
            if origin==allowed:self.send_header('Access-Control-Allow-Origin',allowed)
            self.send_header('Access-Control-Allow-Headers','Content-Type, Authorization, X-Yingche-Extension')
            self.send_header('Access-Control-Allow-Methods','POST, OPTIONS')
            self.send_header('Access-Control-Allow-Private-Network','true')
            self.send_header('Cache-Control','no-store')
            self.send_header('Content-Type','application/json; charset=utf-8')
            self.send_header('Content-Length',str(len(payload)))
            self.send_header('Connection','close');self.end_headers()
            try:self.wfile.write(payload)
            except (BrokenPipeError,ConnectionResetError):pass
            self.close_connection=True
        def trusted(self):
            return self.client_address[0]=='127.0.0.1' and self.headers.get('Host')=='127.0.0.1:'+str(port) and self.headers.get('Origin') in (None,allowed)
        def do_OPTIONS(self):
            if not self.trusted() or self.headers.get('Origin')!=allowed:return self.reply(403,{'error':'Origin rejected'})
            self.reply(200,{'ok':True})
        def do_POST(self):
            if not self.trusted():return self.reply(403,{'error':'Origin rejected'})
            if self.headers.get('X-Yingche-Extension')!=extension:return self.reply(403,{'error':'Extension rejected'})
            if self.headers.get('Content-Type','').split(';')[0]!='application/json':return self.reply(415,{'error':'JSON required'})
            if self.path!='/session' and self.headers.get('Authorization')!='Bearer '+token:return self.reply(401,{'error':'Session expired'})
            try:length=int(self.headers.get('Content-Length','0'))
            except ValueError:return self.reply(400,{'error':'Invalid body length'})
            if length<2 or length>6_000_000:return self.reply(413,{'error':'Request too large'})
            self.connection.settimeout(15)
            try:
                body=self.rfile.read(length)
                if len(body)!=length:raise ValueError('Incomplete body')
                req=json.loads(body)
                if not isinstance(req,dict):raise ValueError('Object required')
            except Exception as exc:return self.reply(400,{'error':str(exc)})
            if self.path=='/session':return self.reply(200,{'ok':True,'token':token,'version':'0.4.1','sourceReady':processor.source_ready})
            if self.path not in ('/analyze','/source','/clear-source'):return self.reply(404,{'error':'Not found'})
            acquired=gate.acquire(timeout=15) if self.path in ('/source','/clear-source') else gate.acquire(blocking=False)
            if not acquired:return self.reply(429,{'error':'本地引擎正忙，请稍后重试'})
            try:
                if self.path=='/source':
                    if not isinstance(req.get('png'),str):raise ValueError('请先选择源照片')
                    value=processor.set_source(decode_image({'png':req['png']}))
                elif self.path=='/clear-source':value=processor.process({'action':'clear-source'})
                else:
                    # Do not accept paths or actions from web-facing frame requests.
                    safe={k:req[k] for k in ['id','generation','streamId','pts','sampleTime','width','height','rgba','jpeg','paused','swapEnabled','swapTarget','swapFeather'] if k in req}
                    if ('rgba' in safe)==('jpeg' in safe):raise ValueError('Exactly one analysis image required')
                    if 'jpeg' in safe:
                        if not isinstance(safe['jpeg'],str):raise ValueError('Invalid JPEG frame')
                        safe['png']=safe.pop('jpeg')
                    value=processor.process(safe)
                self.reply(200,value)
            except Exception as exc:self.reply(422,{'error':str(exc)})
            finally:gate.release()
    class LocalServer(ThreadingHTTPServer):
        allow_reuse_address=False
        def server_bind(self):
            if hasattr(socket,'SO_EXCLUSIVEADDRUSE'):
                self.socket.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
            super().server_bind()
    server=LocalServer(('127.0.0.1',port),Handler);server.daemon_threads=True
    print(json.dumps({'bridgeReady':True,'port':port}),flush=True)
    try:server.serve_forever(poll_interval=.25)
    finally:server.server_close();processor.close()
