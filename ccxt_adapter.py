"""Paginated, public spot EOD history through CCXT. No trading credentials."""
import datetime as dt
import hashlib
import json
import time
from pathlib import Path

DAY = 86_400_000
BASIS = 'spot UTC daily; base-asset volume'


def collect(exchange_id, symbol, start, end, archive_dir, *, ccxt_module=None, include_current=False, allow_empty=False):
    if ccxt_module is None:
        try:
            import ccxt as ccxt_module
        except ImportError as exc:
            raise ValueError('Install CCXT: python -m pip install -r requirements.txt') from exc
    if exchange_id not in ccxt_module.exchanges:
        raise ValueError(f'Unknown CCXT exchange: {exchange_id}')
    # Never request keys or enable trading; explicit spot markets only.
    settings_path=Path(__file__).with_name('ccxt_settings.json')
    settings=json.loads(settings_path.read_text()).get(exchange_id,{}) if settings_path.exists() else {}
    cfg={'enableRateLimit':True,'timeout':15000,'options':{'defaultType':'spot','fetchMarkets':{'types':['spot']}}}
    exchange=getattr(ccxt_module,exchange_id)(cfg)
    if hasattr(exchange,'session'):exchange.session.trust_env=settings.get('trust_environment_proxy',True)
    if not exchange.has.get('fetchOHLCV'):
        raise ValueError(f'{exchange_id} does not support OHLCV')
    archive = Path(archive_dir)
    archive.mkdir(parents=True, exist_ok=True)

    def call(fn, *args, **kwargs):
        for attempt in range(3):
            try:
                return fn(*args, **kwargs)
            except ccxt_module.NetworkError:
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)

    market_params={'symbol':symbol.replace('/','').upper()} if exchange_id=='binance' else {}
    markets = call(exchange.load_markets,params=market_params)
    if not markets:raise ValueError(f'{exchange_id} returned no usable market definitions; pair verification unavailable, local history retained')
    candidate = symbol.strip().upper()
    if candidate not in markets:
        matches = [m['symbol'] for m in markets.values()
                   if m.get('spot') and m.get('id', '').upper() == candidate]
        if len(matches) != 1:
            raise ValueError(f'Unknown/ambiguous spot pair on {exchange_id}: {symbol}. Use the unified BASE/QUOTE format.')
        candidate = matches[0]
    market = markets[candidate]
    if not market.get('spot'):
        raise ValueError('Only spot pairs are supported; derivatives must use separate series')
    if exchange.timeframes and '1d' not in exchange.timeframes:
        raise ValueError(f'{exchange_id} does not support daily candles')
    stamp = lambda day: int(dt.datetime.combine(dt.date.fromisoformat(day), dt.time(), dt.timezone.utc).timestamp() * 1000)
    since = max(0, stamp(start))
    today = stamp(dt.datetime.now(dt.timezone.utc).date().isoformat())
    until = min(stamp(end), today + DAY if include_current else today)
    if since >= until:
        raise ValueError('No eligible UTC days in the requested range')
    first = since
    rows = {}
    for _ in range(10000):
        batch = call(exchange.fetch_ohlcv, candidate, timeframe='1d', since=since, limit=1000)
        payload = dict(exchange=exchange_id, symbol=candidate, timeframe='1d',
                       requested_since=since, retrieved_at=dt.datetime.now(dt.timezone.utc).isoformat(),
                       ccxt_version=getattr(ccxt_module, '__version__', 'unknown'), ohlcv=batch)
        raw = json.dumps(payload, allow_nan=False).encode()
        (archive / (hashlib.sha256(raw).hexdigest() + '.ccxt.json')).write_bytes(raw)
        if not batch:
            break
        timestamps = []
        for candle in batch:
            if len(candle) < 6:
                raise ValueError('Incomplete CCXT OHLCV row')
            ms = candle[0]
            if not isinstance(ms, (float, int)) or not float(ms).is_integer() or ms % DAY:
                raise ValueError('Expected daily candles opening at UTC midnight; refusing to relabel a different session')
            timestamps.append(int(ms))
            if first <= ms < until:
                rows[int(ms)] = dict(date=dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).date().isoformat(),
                                    open=candle[1], high=candle[2], low=candle[3], close=candle[4], volume=candle[5])
        last = max(timestamps)
        if last < since:
            raise ValueError(f'{exchange_id} pagination stalled; existing history preserved')
        since = last + DAY
        if since >= until:
            break
        # A short page need not be the last page. Continue until empty/end.
    else:
        raise ValueError('Pagination safety limit reached; narrow the requested range')
    if not rows and not allow_empty:
        raise ValueError(f'No eligible daily history returned by {exchange_id} for {candidate}')
    return candidate, [rows[k] for k in sorted(rows)]
