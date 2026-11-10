#!/usr/bin/env python3
"""Read-only daily plotting app. Run update.py separately or through cron."""
import argparse,csv,io,json
from urllib.parse import urlparse,parse_qs
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from market_data import ROOT,connect
import plot_data

class Handler(BaseHTTPRequestHandler):
    def reply(self,status,obj,mime='application/json'):
        raw=json.dumps(obj,allow_nan=False).encode() if mime=='application/json' else obj
        self.send_response(status);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    def do_GET(self):
        u=urlparse(self.path);q=parse_qs(u.query)
        try:
            if u.path=='/api/stablecoins':
                from stablecoin_sum import config
                return self.reply(200,config())
            if u.path=='/api/series':return self.reply(200,plot_data.catalog())
            if u.path in ('/api/bars','/api/export'):
                sid=int(q['id'][0]);assets=tuple(q['assets'][0].split(',')) if 'assets' in q else None
                rows=plot_data.bars(sid,assets)
                if u.path=='/api/bars':return self.reply(200,rows)
                out=io.StringIO();w=csv.DictWriter(out,fieldnames=['date','open','high','low','close','volume']);w.writeheader();w.writerows(rows)
                return self.reply(200,out.getvalue().encode(),'text/csv')
            assets={'/':('index.html','text/html'),'/app.js':('app.js','text/javascript'),'/style.css':('style.css','text/css')}
            if u.path in assets:
                filename,mime=assets[u.path];return self.reply(200,(ROOT/'static'/filename).read_bytes(),mime)
            return self.reply(404,{'error':'Not found'})
        except (ValueError,KeyError) as e:self.reply(400,{'error':str(e)})
    def do_POST(self):self.reply(405,{'error':'Plotting is read-only. Run update.py separately.'})

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',nargs='?',choices=['serve'],default='serve');p.add_argument('--port',type=int,default=8765);a=p.parse_args()
    connect().close();print(f'Candle Desk: http://127.0.0.1:{a.port}',flush=True)
    ThreadingHTTPServer(('127.0.0.1',a.port),Handler).serve_forever()
if __name__=='__main__':main()
