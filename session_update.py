"""Incremental daily observations. Session dates remain source dates, never fetch dates."""
import datetime as dt
from functools import lru_cache
import market_data as store

@lru_cache(maxsize=8)
def calendar(name):
    import exchange_calendars as xc
    return xc.get_calendar(name)

def calendar_name(job):
    if 'calendar' in job:return job['calendar']
    if job['provider']!='yahoo':return None
    if job['symbol'].endswith('.SA'):return 'BVMF'
    # Futures and dollar index use conservative end-of-session confirmation:
    # next UTC day, rather than claiming that settlement is already published.
    if job['symbol'].endswith('=F') or job['id']=='DXY':return None
    return 'XNYS'

def state(job,date,now):
    if job['provider'] in ('fred','defillama'):return 'published'
    day=dt.date.fromisoformat(date)
    name=calendar_name(job)
    if day < now.date()-dt.timedelta(days=30):return 'final'
    if name:
        cal=calendar(name)
        if not cal.is_session(date):return 'provisional'
        return 'final' if cal.session_close(date).to_pydatetime()<=now else 'provisional'
    return 'final' if day<now.astimezone(dt.timezone.utc).date() else 'provisional'

def pending(sid):
    with store.connect() as db:
        return [r[0] for r in db.execute("SELECT date FROM bar_state WHERE series_id=? AND state='provisional' ORDER BY date",(sid,))]

def beginning(job,series,default,full=False):
    if full or not series:return default
    latest=max(s['last'] for s in series)
    # Revisit the last observation itself, not just dates after it. Pending bars
    # remain eligible even when newer bars have already been appended.
    dates=[latest]
    for s in series:dates.extend(pending(s['id']))
    return max(default,min(dates))

def refresh(job,start,end,now=None):
    now=now or dt.datetime.now(dt.timezone.utc)
    symbol,source,basis,rows=store.download(job['provider'],job['symbol'],start,end,
        exchange=job.get('exchange','binance'),include_current=True,persist=False)
    rows=[r for r in rows if start<=str(r['date'])[:10]<end]
    # Refuse future observations; overnight futures may carry tomorrow's
    # source session label, but no fabricated "today" row is added.
    rows=[r for r in rows if str(r['date'])[:10]<=now.astimezone(dt.timezone.utc).date().isoformat()]
    if not rows:return dict(status='no_new_data',downloaded_rows=0,note='Empty response; cached history and pending candle states retained')
    states={str(r['date'])[:10]:state(job,str(r['date'])[:10],now) for r in rows}
    sid,n=store.save(symbol,source,basis,rows,states=states)
    return dict(status='ok',series_id=sid,downloaded_rows=n,
                latest_state=states[max(states)],pending_dates=pending(sid))
