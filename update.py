#!/usr/bin/env python3
"""Cron entrypoint. Acquires data only; never starts the plotting app."""
import argparse,datetime as dt,json,os,subprocess,sys,time
from pathlib import Path
from zoneinfo import ZoneInfo
import market_data as store
ROOT=Path(__file__).resolve().parent
CONFIG=ROOT/'update_symbols.json'
def settings():return json.loads((ROOT/'update_settings.json').read_text())

def exclusive_end(job,now=None):
    """Fetch the latest available daily observation, including the current day.

    Daily bar identity is its source session date. The database upserts that key:
    same date refreshes the stored candle; a different date appends a new one.
    Publication/fetch time is not a new daily-bar timestamp.
    """
    now=now or dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None:raise ValueError('Cutoff time must be timezone-aware')
    if job['provider']=='yahoo':
        zone=job.get('eod',{}).get('timezone','America/Sao_Paulo' if job['symbol'].endswith('.SA') else 'America/New_York')
    else:zone='UTC'
    return (now.astimezone(ZoneInfo(zone)).date()+dt.timedelta(days=1)).isoformat()

def atomic_json(path,value):
    tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(value,indent=2,default=str));os.replace(tmp,path)

def matching_series(job):
    source='ccxt:'+job.get('exchange','binance') if job['provider']=='ccxt' else job['provider']
    return [s for s in store.catalog() if s['symbol']==job['symbol'] and s['source']==source]

def beginning(job,full=False):
    series=matching_series(job)
    if full or not series:return job.get('start','1900-01-01')
    from session_update import beginning as incremental_start
    return incremental_start(job,series,job.get('start','1900-01-01'),full)

def worker(job,start,end):
    if job.get('unavailable'):return dict(status='unavailable',error=job['unavailable'])
    existing=matching_series(job)
    if job.get('retired_on') and existing:
        s=existing[0]
        return dict(status='retired',series_id=s['id'],first=s['first'],latest=s['last'],bars=s['bars'],local_symbol=s['symbol'],source=s['source'],note=job['notes'])
    try:
        from session_update import refresh
        result=refresh(job,start,end)
        if result['status']=='no_new_data':
            if existing:
                last=max(existing,key=lambda s:s['last'])
                result.update(series_id=last['id'],latest=last['last'],bars=last['bars'])
            return result
        sid=result['series_id']
    except Exception as e:
        if job['id']!='DXY':raise
        from dollar_index import refresh
        sid,n,errors=refresh(job.get('start','1999-01-01'),end)
        result=dict(status='fallback',series_id=sid,downloaded_rows=n,primary_error=str(e),component_errors=errors)
    if job['provider']=='ccxt':result.update(current_candle_policy='latest available price snapshot; provisional until UTC day closes',snapshot_at=dt.datetime.now(dt.timezone.utc).isoformat())
    series=next(s for s in store.catalog() if s['id']==sid)
    from data import check
    if not check(sid)[0]['valid']:raise ValueError('Stored series failed validation')
    lag=max(0,(dt.date.fromisoformat(end)-dt.timedelta(days=1)-dt.date.fromisoformat(series['last'])).days)
    result.update(local_symbol=series['symbol'],source=series['source'],first=series['first'],latest=series['last'],bars=series['bars'],lag_calendar_days=lag)
    if job.get('retired_on'):result['status']='retired'
    elif lag>job.get('max_lag_days',7):result['status']='stale'
    return result

def run_one(job,start,end,timeout):
    args=[sys.executable,str(Path(__file__).resolve()),'--worker',job['id'],'--start',start,'--end',end]
    try:
        p=subprocess.run(args,cwd=ROOT,text=True,capture_output=True,timeout=timeout)
        if p.returncode:raise RuntimeError((p.stderr or p.stdout or f'Worker exit {p.returncode}')[-2000:])
        result=json.loads(p.stdout.strip().splitlines()[-1])
        if p.stderr:result['provider_messages']=p.stderr[-2000:]
        return result
    except subprocess.TimeoutExpired:return dict(status='failed',error=f'Download exceeded {timeout}s; cached history retained')
    except Exception as e:return dict(status='failed',error=str(e))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--full',action='store_true',help='Refetch all available history; daily runs revisit pending and latest observations, then fetch missing dates')
    parser.add_argument('--only',nargs='+',help='Configured IDs, e.g. BTCUSDT WREPO DXY')
    parser.add_argument('--timeout',type=int,default=None,help='Hard timeout per instrument in seconds')
    parser.add_argument('--worker',help=argparse.SUPPRESS);parser.add_argument('--start',default='1900-01-01',help=argparse.SUPPRESS)
    parser.add_argument('--end',default=None,help='Explicit exclusive date; default includes the current source-session date')
    a=parser.parse_args();config=json.loads(CONFIG.read_text());jobs=config['instruments']
    if a.worker:
        job=next(j for j in jobs if j['id']==a.worker)
        try:print(json.dumps(worker(job,a.start,a.end or exclusive_end(job)),default=str))
        except Exception as e:print(json.dumps(dict(status='failed',error=f'{type(e).__name__}: {e}')))
        return
    if a.only:
        unknown=set(a.only)-{j['id'] for j in jobs}
        if unknown:parser.error('Unknown IDs: '+', '.join(sorted(unknown)))
        jobs=[j for j in jobs if j['id'] in a.only]
    import fcntl
    lock=(ROOT/'.update.lock').open('a')
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:print('Another update is running',file=sys.stderr);raise SystemExit(75)
    logdir=ROOT/'logs';logdir.mkdir(exist_ok=True)
    now=dt.datetime.now(dt.timezone.utc)
    # Refresh complete Yahoo histories monthly because splits may revise old prices.
    full=a.full or now.day==settings()['full_refresh_day_of_month']
    report=dict(started_at=now.isoformat(),explicit_exclusive_end=a.end,cutoff_policy='refetch pending/latest; backfill; same-session upsert; persistent final/provisional state',full_refresh=full,results=[])
    for job in jobs:
        end=a.end or exclusive_end(job)
        start=beginning(job,full)
        if start>=end:start=(dt.date.fromisoformat(end)-dt.timedelta(days=settings()['overlap_days'])).isoformat()
        started=time.monotonic()
        result=dict(id=job['id'],requested_symbol=job['symbol'],requested_start=start,requested_end_exclusive=end,notes=job.get('notes',''),**run_one(job,start,end,a.timeout or (settings()['dxy_fallback_timeout_seconds'] if job['id']=='DXY' else settings()['timeout_seconds_per_symbol'])))
        result['seconds']=round(time.monotonic()-started,2)
        report['results'].append(result)
        atomic_json(logdir/'latest_update.json',report)
        print(f"{job['id']}: {result['status']} | latest={result.get('latest','—')} | {result.get('error','')}",flush=True)
    if not a.only or any(j['provider']=='defillama' for j in jobs):
        try:
            from stablecoin_sum import rebuild
            sid,n=rebuild()
            series=next(s for s in store.catalog() if s['id']==sid)
            report['results'].append(dict(id='STABLECOIN_SUM',status='ok',series_id=sid,bars=series['bars'],latest=series['last'],local_symbol='STABLECOIN_SUM'))
        except Exception as e:
            report['results'].append(dict(id='STABLECOIN_SUM',status='failed',error=str(e)))
    report['finished_at']=dt.datetime.now(dt.timezone.utc).isoformat()
    report['problems']=sum(r['status'] in ('failed','stale','unavailable') for r in report['results'])
    atomic_json(logdir/'latest_update.json',report)
    status_path=logdir/'symbol_status.json'
    try:status=json.loads(status_path.read_text())
    except (FileNotFoundError,json.JSONDecodeError):status={}
    for result in report['results']:status[result['id']]={**result,'updated_at':report['finished_at']}
    allowed={j['id'] for j in config['instruments']}|{'STABLECOIN_SUM'}
    atomic_json(status_path,{k:v for k,v in status.items() if k in allowed})
    atomic_json(logdir/(now.strftime('%Y%m%dT%H%M%S')+'.json'),report)
    raise SystemExit(1 if report['problems'] else 0)
if __name__=='__main__':main()
