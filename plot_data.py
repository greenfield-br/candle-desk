"""Read-only plot catalog: exactly the requested instruments and stablecoin sums."""
import json
import market_data as store
from stablecoin_sum import sum_rows,config

def catalog():
    jobs=json.loads((store.ROOT/'update_symbols.json').read_text())['instruments']
    out=[]
    for s in store.catalog():
        matches=[j for j in jobs if j['symbol']==s['symbol'] and ('ccxt:'+j.get('exchange','binance') if j['provider']=='ccxt' else j['provider'])==s['source']]
        if matches:s=dict(s,display_symbol=matches[0]['id'],chart_type=matches[0].get('chart_type','candles' if matches[0]['provider'] in ('yahoo','ccxt') else 'line'))
        elif s['symbol'] in ('DXY_RECON_6','DXY_PROXY4') and s['source']=='derived:fred-fx':s=dict(s,display_symbol='DXY (reconstructed)' if s['symbol']=='DXY_RECON_6' else 'DXY (four-currency proxy)',chart_type='line')
        else:continue
        out.append(s)
    try:rows=sum_rows()
    except ValueError:rows=[]
    out.insert(0,dict(id=-1,chart_type='line',symbol=config()['synthetic_symbol'],display_symbol='+'.join(config()['default_selection'])+' market cap',source='local sum',basis='Selected stablecoins; USD market cap; common dates only',bars=len(rows),first=rows[0]['date'] if rows else None,last=rows[-1]['date'] if rows else None,volume_bars=0))
    return out

def bars(sid,assets=None):
    if sid==-1:return sum_rows(assets)
    if not any(s['id']==sid for s in catalog()):raise ValueError('Not a requested plot symbol')
    return store.bars(sid)
