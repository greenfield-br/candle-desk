"""Sum selected, locally stored stablecoin market caps on common dates only."""
import json
from pathlib import Path
import market_data as store
def config():return json.loads(Path(__file__).with_name('stablecoin_config.json').read_text())
DEFAULT=tuple(config()['default_selection'])

def sum_rows(assets=None):
    cfg=config();assets=tuple(dict.fromkeys(cfg['default_selection'] if assets is None else assets))
    if not assets or any(a not in cfg['assets'] for a in assets):raise ValueError('Select USDT, USDC and/or OUSD (Open USD)')
    history={}
    for asset in assets:
        matches=[s for s in store.catalog() if s['symbol']==asset+'_MCAP' and s['source']=='defillama']
        if len(matches)!=1:raise ValueError(f'{asset}: local market-cap history missing or ambiguous')
        history[asset]={r['date']:r['close'] for r in store.bars(matches[0]['id'])}
    dates=sorted(set.intersection(*(set(history[a]) for a in assets)))
    if not dates:raise ValueError('Selected stablecoins have no common stored observation dates')
    return [dict(date=d,open=None,high=None,low=None,close=sum(history[a][d] for a in assets),volume=None) for d in dates]

def rebuild():
    cfg=config()
    return store.save(cfg['synthetic_symbol'],'derived:stablecoins','+'.join(cfg['default_selection'])+'; USD market cap; common dates only',sum_rows())
