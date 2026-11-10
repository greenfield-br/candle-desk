#!/usr/bin/env python3
"""Stages 1–2: acquire, check and normalize EOD history. No web UI required."""
import argparse
import csv
import datetime as dt
import json
import market_data as store

def check(series_id=None):
    result=[]
    for series in store.catalog():
        if series_id is not None and series['id']!=series_id:continue
        rows=store.bars(series['id']);errors=[];dates=set();previous=None
        for row in rows:
            try:store.normalize(row)
            except (ValueError,TypeError,KeyError) as e:errors.append(str(e))
            date=row['date']
            if date in dates:errors.append(f'{date}: duplicate')
            if previous and date<=previous:errors.append(f'{date}: not increasing')
            dates.add(date);previous=date
        result.append(dict(**series,ohlc_bars=sum(r['open'] is not None for r in rows),
                           close_only_bars=sum(r['open'] is None for r in rows),
                           missing_volume_bars=sum(r['volume'] is None for r in rows),valid=not errors,errors=errors))
    if series_id is not None and not result:raise ValueError('Unknown local series')
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='action',required=True)
    sub.add_parser('sources',help='Provider inventory and verification status')
    sub.add_parser('list',help='Locally stored series')
    verify=sub.add_parser('check',help='Validate stored normalized history');verify.add_argument('--id',type=int)
    dl=sub.add_parser('download');dl.add_argument('provider',choices=['ccxt','binance','yahoo','fred','defillama','stooq']);dl.add_argument('symbol');dl.add_argument('--exchange',default='binance');dl.add_argument('--start',default='1900-01-01');dl.add_argument('--end',default=dt.datetime.now(dt.timezone.utc).date().isoformat())
    imp=sub.add_parser('import');imp.add_argument('file');imp.add_argument('--symbol',required=True);imp.add_argument('--source',required=True);imp.add_argument('--basis',required=True)
    a=p.parse_args()
    if a.action=='sources':result=json.loads((store.ROOT/'sources.json').read_text())
    elif a.action=='list':
        from plot_data import catalog
        result=catalog()
    elif a.action=='check':
        result=check(a.id)
        print(json.dumps(result,indent=2))
        if any(not r['valid'] for r in result):raise SystemExit(1)
        return
    elif a.action=='download':
        sid,n=store.download(a.provider,a.symbol,a.start,a.end,exchange=a.exchange)
        result=dict(series_id=sid,imported=n,check=check(sid))
    else:
        with open(a.file,encoding='utf-8-sig',newline='') as f:sid,n=store.save(a.symbol,a.source,a.basis,list(csv.DictReader(f)))
        result=dict(series_id=sid,imported=n,check=check(sid))
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
