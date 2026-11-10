"""Explicitly labelled daily dollar-basket reconstructions from local FRED FX."""
import math
import market_data as store
WEIGHTS={'DEXUSEU':-.576,'DEXJPUS':.136,'DEXUSUK':-.119,'DEXCAUS':.091,'DEXSDUS':.042,'DEXSZUS':.036}
FOUR=('DEXUSEU','DEXJPUS','DEXUSUK','DEXSZUS')

def reconstruct(components, partial=False):
    names=FOUR if partial else tuple(WEIGHTS)
    if not all(components.get(name) for name in names):raise ValueError('Missing FX components')
    dates=sorted(set.intersection(*(set(components[name]) for name in names)))
    dates=[d for d in dates if all(math.isfinite(components[n][d]) and components[n][d]>0 for n in names)]
    if not dates:raise ValueError('No positive, common-date FX observations')
    total=sum(abs(WEIGHTS[n]) for n in names)
    def geometric(d):return math.exp(sum(WEIGHTS[n]*math.log(components[n][d]) for n in names)/(total if partial else 1))
    anchor=geometric(dates[0])
    return [dict(date=d,close=100*geometric(d)/anchor if partial else 50.14348112*geometric(d)) for d in dates]

def local_components():
    return {s['symbol']:{r['date']:r['close'] for r in store.bars(s['id'])}
            for s in store.catalog() if s['source']=='fred' and s['symbol'] in WEIGHTS}

def refresh(start,end):
    errors={}
    cached=local_components()
    # Fresh downloads include overlapping revisions. Rebuild derived series from full local histories.
    for name in WEIGHTS:
        try:
            beginning=start if name not in cached else max(start, sorted(cached[name])[-1][:4]+'-01-01')
            store.download('fred',name,beginning,end)
        except Exception as e:errors[name]=str(e)
    components=local_components()
    try:
        rows=reconstruct(components)
        name='DXY_RECON_6';basis='ICE six-currency weights; FRED noon FX; close-only reconstruction, not official DXY'
    except ValueError:
        rows=reconstruct(components,partial=True)
        name='DXY_PROXY4';basis='EUR JPY GBP CHF; 86.7% basket renormalized; base 100 at first common local date; NOT official DXY'
    sid,n=store.save(name,'derived:fred-fx',basis,rows)
    return sid,n,errors
