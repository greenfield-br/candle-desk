"""Official Binance spot archive backfill for delisted XMRUSDT."""
import concurrent.futures,csv,datetime as dt,hashlib,io,json,urllib.parse,urllib.request,xml.etree.ElementTree as ET,zipfile
from pathlib import Path

def collect(symbol,start,end,archive_dir):
    if symbol!='XMRUSDT':raise ValueError('This retired-market archive route is configured only for XMRUSDT')
    archive=Path(archive_dir);archive.mkdir(exist_ok=True)
    cached={}
    for p in archive.glob('*.source.json'):
        try:
            meta=json.loads(p.read_text());base=p.name.removesuffix('.source.json')
            for ext in ('.zip','.xml'):
                candidate=archive/(base+ext)
                if candidate.exists():cached[meta['url']]=candidate
        except (ValueError,KeyError,OSError):pass
    def fetch(url):
        if url in cached:return cached[url].read_bytes()
        with urllib.request.urlopen(url,timeout=25) as response:raw=response.read()
        digest=hashlib.sha256(raw).hexdigest();suffix='.zip' if raw.startswith(b'PK') else '.xml'
        (archive/(digest+suffix)).write_bytes(raw)
        (archive/(digest+'.source.json')).write_text(json.dumps(dict(url=url,downloaded_at=dt.datetime.now(dt.timezone.utc).isoformat())))
        return raw
    prefix=f'data/spot/monthly/klines/{symbol}/1d/'
    listing=fetch('https://s3-ap-northeast-1.amazonaws.com/data.binance.vision?'+urllib.parse.urlencode({'list-type':2,'prefix':prefix}))
    root=ET.fromstring(listing);ns={'s':'http://s3.amazonaws.com/doc/2006-03-01/'}
    if root.findtext('s:IsTruncated',namespaces=ns)=='true':raise ValueError('Archive listing truncated')
    keys=[e.text for e in root.findall('.//s:Key',ns) if e.text.endswith('.zip') and start[:7]<=e.text.rsplit('-',2)[-2]+'-'+e.text.rsplit('-',1)[-1][:2]<=end[:7]]
    # Month keys are YYYY-MM.zip; retain boundary months then filter exact dates.
    def parse(key):
        payload=fetch('https://data.binance.vision/'+key)
        with zipfile.ZipFile(io.BytesIO(payload)) as z:
            names=[n for n in z.namelist() if n.endswith('.csv')]
            if len(names)!=1:raise ValueError('Expected one CSV per Binance archive')
            parsed=[]
            for r in csv.reader(io.StringIO(z.read(names[0]).decode())):
                timestamp=int(r[0]);timestamp=timestamp/1_000_000 if timestamp>=10**15 else timestamp/1000
                day=dt.datetime.fromtimestamp(timestamp,dt.timezone.utc).date().isoformat()
                if start<=day<end:parsed.append(dict(date=day,open=r[1],high=r[2],low=r[3],close=r[4],volume=r[5]))
            return parsed
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:rows=[r for part in pool.map(parse,keys) for r in part]
    if not rows:raise ValueError('No archived XMRUSDT observations in requested range')
    return sorted(rows,key=lambda r:r['date'])
