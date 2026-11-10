#!/usr/bin/env python3
"""Independent EOD acquisition, normalization and local storage. Python 3.10+, stdlib server/storage; optional yfinance/CCXT."""
import argparse, csv, datetime as dt, io, json, math, sqlite3, sys, time, hashlib
from pathlib import Path
from urllib.parse import urlparse, parse_qs, urlencode
from urllib.request import Request, urlopen
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(__file__).resolve().parent
DB = ROOT / 'history.sqlite3'

def connect():
    db = sqlite3.connect(DB, timeout=30)
    db.row_factory = sqlite3.Row
    db.executescript('''CREATE TABLE IF NOT EXISTS series (
    id INTEGER PRIMARY KEY, symbol TEXT NOT NULL, source TEXT NOT NULL,
    basis TEXT NOT NULL, UNIQUE(symbol,source,basis));
    CREATE TABLE IF NOT EXISTS bars (
    series_id INTEGER, date TEXT, open REAL, high REAL, low REAL, close REAL NOT NULL,
    volume REAL, PRIMARY KEY(series_id,date));
    CREATE TABLE IF NOT EXISTS bar_state (
    series_id INTEGER, date TEXT, state TEXT NOT NULL, fetched_at TEXT NOT NULL,
    PRIMARY KEY(series_id,date));''')
    return db

def number(v):
    if v is None or str(v).strip().lower() in ('','nan','null','none','n/a'): return None
    n = float(v)
    if not math.isfinite(n): return None
    return n

def normalize(row):
    r = {str(k).strip().lower():v for k,v in row.items()}
    date = dt.date.fromisoformat(str(r['date'])[:10]).isoformat()
    c = number(r.get('close'))
    if c is None: raise ValueError(f'{date}: missing close')
    o,h,l = (number(r.get(k)) for k in ('open','high','low'))
    if any(x is not None for x in (o,h,l)) and not all(x is not None for x in (o,h,l)):
        raise ValueError(f'{date}: partial OHLC; supply all three or close only')
    if o is not None and (h < max(o,c,l) or l > min(o,c,h)):
        raise ValueError(f'{date}: invalid OHLC range')
    v = number(r.get('volume'))
    if v is not None and v < 0: raise ValueError(f'{date}: negative volume')
    return (date,o,h,l,c,v)

def save(symbol, source, basis, rows, states=None):
    symbol, source, basis = [x.strip() for x in (symbol,source,basis)]
    if not all((symbol,source,basis)): raise ValueError('Symbol, source and basis required')
    # Validate the entire batch before changing anything. No truncating history.
    clean = [normalize(r) for r in rows]
    if not clean: raise ValueError('No usable data returned; existing history preserved')
    with connect() as db:
        db.execute('INSERT OR IGNORE INTO series(symbol,source,basis) VALUES(?,?,?)',(symbol,source,basis))
        sid = db.execute('SELECT id FROM series WHERE symbol=? AND source=? AND basis=?',(symbol,source,basis)).fetchone()[0]
        db.executemany('''INSERT INTO bars VALUES(?,?,?,?,?,?,?)
        ON CONFLICT(series_id,date) DO UPDATE SET open=excluded.open,high=excluded.high,
        low=excluded.low,close=excluded.close,volume=COALESCE(excluded.volume,bars.volume)''',[(sid,*r) for r in clean])
        if states is not None:
            fetched=dt.datetime.now(dt.timezone.utc).isoformat()
            db.executemany("INSERT INTO bar_state VALUES(?,?,?,?) ON CONFLICT(series_id,date) DO UPDATE SET state=excluded.state,fetched_at=excluded.fetched_at",[(sid,r[0],states[r[0]],fetched) for r in clean])
    return sid, len(clean)

def fetch(url):
    with urlopen(Request(url, headers={'User-Agent':'CandleDesk/0.1'}),timeout=30) as r:
        raw = r.read()
        archive = ROOT / 'raw'
        archive.mkdir(exist_ok=True)
        digest = hashlib.sha256(raw).hexdigest()
        (archive / (digest + '.txt')).write_bytes(raw)
        with (archive / 'downloads.jsonl').open('a') as log:
            log.write(json.dumps(dict(url=url,sha256=digest,downloaded_at=dt.datetime.now(dt.timezone.utc).isoformat()))+'\n')
        return raw.decode('utf-8-sig')

def download(provider, symbol, start, end, exchange="binance", include_current=False, persist=True):
    def finish(symbol,source,basis,rows):
        rows=list(rows)
        if persist:return save(symbol,source,basis,rows)
        # Validate before any transaction. Empty responses are a normal no-op.
        for row in rows:normalize(row)
        return symbol,source,basis,rows
    # end is exclusive; today is omitted by default, so incomplete EOD bars stay out.
    startd, endd = dt.date.fromisoformat(start), dt.date.fromisoformat(end)
    if startd >= endd: raise ValueError('Start must precede exclusive end date')
    if provider == 'fred':
        payload = fetch('https://fred.stlouisfed.org/graph/fredgraph.csv?'+urlencode(dict(id=symbol,cosd=start,coed=(endd-dt.timedelta(days=1)).isoformat())))
        rows=[]
        for r in csv.DictReader(io.StringIO(payload)):
            date=r.get('observation_date') or r.get('DATE')
            val=r.get(symbol)
            if val in (None,'','.'): continue
            rows.append(dict(date=date,close=val))
        basis='weekly ending Wednesday; millions USD; no daily interpolation' if symbol=='WREPO' else 'daily observation; native series units; close-only'
        return finish(symbol,'fred',basis,rows)
    if provider == 'defillama':
        symbol = symbol.upper()
        asset_config=json.loads(Path(__file__).with_name('stablecoin_config.json').read_text())['assets']
        supported=('STABLECAP','STABLECAP_USD',*(a+'_MCAP' for a in asset_config))
        if symbol not in supported:raise ValueError('Unknown stablecoin; verified identity required in stablecoin_config.json')
        asset = None
        url = 'https://stablecoins.llama.fi/stablecoincharts/all'
        if symbol.endswith('_MCAP'):
            ticker = symbol.removesuffix('_MCAP')
            listed = json.loads(fetch('https://stablecoins.llama.fi/stablecoins?includePrices=true'))
            matches = [a for a in listed.get('peggedAssets', []) if a.get('symbol') == ticker and a.get('pegType') == 'peggedUSD']
            # Match the established provider asset ID as well as its symbol.
            expected=asset_config[ticker]
            matches=[a for a in matches if str(a.get('id'))==expected['id'] and (ticker!='OUSD' or (a.get('name')==expected['name'] and a.get('gecko_id')==expected['gecko_id']))]
            if len(matches) != 1:
                raise ValueError(f'{ticker}: stablecoin identity could not be verified')
            asset = matches[0]
            url += '?' + urlencode(dict(stablecoin=asset['id']))
        payload=json.loads(fetch(url))
        if not isinstance(payload,list): raise ValueError('Unexpected DefiLlama response')
        rows=[]
        for r in payload:
            date=dt.datetime.fromtimestamp(int(r['date']),dt.timezone.utc).date().isoformat()
            if not (start <= date < end): continue
            # Never add quantities of differently pegged currencies without USD conversion.
            values = r.get('totalCirculatingUSD')
            if symbol != 'STABLECAP_USD':
                if not isinstance(values,dict):
                    raise ValueError('DefiLlama response lacks USD-converted totals. Use STABLECAP_USD for USD-pegged supply or import a verified CSV.')
                value=sum(float(x) for x in values.values())
                basis='all tracked pegs; USD-valued provider totals; daily snapshot' if asset is None else f"{asset['symbol']} stablecoin id={asset['id']}; USD market cap; daily snapshot"
            else:
                values=r.get('totalCirculating',{})
                if 'peggedUSD' not in values: continue
                value=values['peggedUSD']
                basis='USD-pegged circulating supply at peg; not depeg-adjusted market cap'
            rows.append(dict(date=date,close=value))
        return finish(symbol,'defillama',basis if rows else 'daily snapshot',rows)
    if provider == 'yahoo':
        try: import yfinance as yf
        except ImportError: raise ValueError('Install downloader: python -m pip install -r requirements.txt')
        ticker = yf.Ticker(symbol)
        data = ticker.history(start=start,end=end,interval='1d',auto_adjust=False,actions=False)
        metadata = ticker.get_history_metadata() or {}
        if symbol.upper() == '^MOVE':
            name = str(metadata.get('shortName','')) + ' ' + str(metadata.get('longName',''))
            if 'move' not in name.lower() or not any(x in name.lower() for x in ('ice','bofa','volatility','merrill')):
                raise ValueError('MOVE identity not verified as ICE bond volatility index; refusing to store a possible wrong instrument. Import a verified CSV instead.')
        archive = ROOT / 'raw'; archive.mkdir(exist_ok=True)
        snapshot = data.to_csv().encode()
        digest = hashlib.sha256(snapshot).hexdigest()
        (archive/(digest+'.csv')).write_bytes(snapshot)
        (archive/(digest+'.json')).write_text(json.dumps(dict(symbol=symbol,metadata=metadata,downloaded_at=dt.datetime.now(dt.timezone.utc).isoformat()),default=str))
        rows = [];quality=[]
        for stamp,row in data.iterrows():
            r=dict(date=stamp.date().isoformat(),**{k.lower():row[k] for k in ['Open','High','Low','Close','Volume']})
            if not start <= r['date'] < end:continue
            if number(r['close']) is None:
                quality.append(dict(date=r['date'],issue='missing close',action='omit observation'));continue
            try:normalize(r)
            except ValueError as e:
                # Keep the genuine close when source OHLC is inconsistent; do not manufacture candle extrema.
                r.update(open=None,high=None,low=None)
                normalize(r)
                quality.append(dict(date=r['date'],issue=str(e),action='preserve close and volume; OHLC unavailable'))
            rows.append(r)
        if quality:(archive/(digest+'.quality.json')).write_text(json.dumps(quality,indent=2))
        return finish(symbol,'yahoo','provider OHLC; auto_adjust=False',rows)
    if provider == 'stooq':
        url = 'https://stooq.com/q/d/l/?'+urlencode(dict(s=symbol.lower(),i='d',d1=startd.strftime('%Y%m%d'),d2=(endd-dt.timedelta(days=1)).strftime('%Y%m%d')))
        return finish(symbol,'stooq','provider OHLC; adjustment policy unverified',list(csv.DictReader(io.StringIO(fetch(url)))))
    if provider=='binance_archive':
        from binance_archive import collect
        return finish(symbol,'binance_archive','Binance spot archive; UTC daily; base-asset volume',collect(symbol,start,end,ROOT/'raw'))
    if provider in ('ccxt', 'binance'):
        from ccxt_adapter import collect, BASIS
        exchange_id = 'binance' if provider == 'binance' else exchange
        pair, rows = collect(exchange_id, symbol, start, end, ROOT / 'raw', **({'include_current':True} if include_current else {}), **({'allow_empty':True} if not persist else {}))
        return finish(pair, 'ccxt:' + exchange_id, BASIS, rows)
    raise ValueError('Unknown provider')

def catalog():
    with connect() as db:
        return [dict(r) for r in db.execute('''SELECT s.*,COUNT(b.date) AS bars, MIN(date) AS first,MAX(date) AS last,
        COUNT(b.volume) AS volume_bars,
        (SELECT state FROM bar_state bs WHERE bs.series_id=s.id ORDER BY bs.date DESC LIMIT 1) AS latest_state FROM series s JOIN bars b ON s.id=b.series_id GROUP BY s.id ORDER BY s.symbol,s.source''')]

def bars(sid):
    with connect() as db:
        return [dict(r) for r in db.execute('SELECT date,open,high,low,close,volume FROM bars WHERE series_id=? ORDER BY date',(sid,))]

