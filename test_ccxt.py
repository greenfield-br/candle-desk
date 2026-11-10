import datetime as dt
import json
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch
import market_data as app
import ccxt_adapter as adapter

DAY=adapter.DAY
START=int(dt.datetime(2020,1,1,tzinfo=dt.timezone.utc).timestamp()*1000)
def bar(offset,volume=10):return [START+offset*DAY,100,110,90,105,volume]
class NetworkError(Exception):pass

class FakeExchange:
    has={'fetchOHLCV':True}
    timeframes={'1d':'1d'}
    def __init__(self,pages):self.pages=list(pages);self.calls=[];self.config=None
    def load_markets(self,**kwargs):return {'BTC/USDT':{'symbol':'BTC/USDT','id':'BTCUSDT','spot':True}}
    def fetch_ohlcv(self,symbol,**kwargs):
        self.calls.append((symbol,kwargs))
        page=self.pages.pop(0)
        if isinstance(page,Exception):raise page
        return page

def module(exchange):
    def ctor(config):exchange.config=config;return exchange
    return types.SimpleNamespace(exchanges=['binance','kraken'],binance=ctor,kraken=ctor,NetworkError=NetworkError,__version__='test')

class CryptoTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.old_db=app.DB;self.old_root=app.ROOT
        app.ROOT=Path(self.tmp.name);app.DB=app.ROOT/'history.sqlite3'
    def tearDown(self):app.DB=self.old_db;app.ROOT=self.old_root;self.tmp.cleanup()
    def collect(self,ex,symbol='BTC/USDT',end='2020-01-05'):
        return adapter.collect('binance',symbol,'2020-01-01',end,app.ROOT/'raw',ccxt_module=module(ex))
    def test_short_pages_duplicates_exclusive_end_and_missing_volume(self):
        ex=FakeExchange([[bar(1),bar(0)], [bar(1),bar(2,None)], [bar(3),bar(4)]])
        pair,rows=self.collect(ex,'BTCUSDT')
        self.assertEqual(pair,'BTC/USDT');self.assertEqual(len(rows),4)
        self.assertIsNone(rows[2]['volume']);self.assertEqual(rows[0]['date'],'2020-01-01')
        self.assertEqual(ex.calls[1][1]['since'],START+2*DAY)
        self.assertTrue(ex.config['enableRateLimit']);self.assertEqual(len(list((app.ROOT/'raw').glob('*.ccxt.json'))),3)
    def test_stalled_pagination_raises(self):
        with self.assertRaisesRegex(ValueError,'stalled'):self.collect(FakeExchange([[bar(0)],[bar(0)]]))
    def test_network_retry(self):
        ex=FakeExchange([NetworkError('temporary'),[bar(0)],[]])
        with patch.object(adapter.time,'sleep') as sleep:
            _,rows=self.collect(ex)
        self.assertEqual(len(rows),1);sleep.assert_called_once_with(1)
    def test_reject_derivative_unknown_exchange_and_bad_session(self):
        ex=FakeExchange([])
        with self.assertRaisesRegex(ValueError,'Unknown CCXT'):adapter.collect('fake','BTC/USDT','2020-01-01','2020-01-02',app.ROOT,ccxt_module=module(ex))
        bad=bar(0);bad[0]+=3600000
        with self.assertRaisesRegex(ValueError,'UTC midnight'):self.collect(FakeExchange([[bad]]))
        ex.load_markets=lambda **kwargs:{'BTC/USDT':dict(symbol='BTC/USDT',spot=False)}
        with self.assertRaisesRegex(ValueError,'Only spot'):self.collect(ex)
    def test_failed_download_keeps_stored_history(self):
        sid,_=app.save('BTC/USDT','ccxt:binance',adapter.BASIS,[dict(date='2020-01-01',close=100)])
        with patch.object(adapter,'collect',side_effect=NetworkError('offline')):
            with self.assertRaises(NetworkError):app.download('ccxt','BTC/USDT','2020-01-01','2020-01-05')
        # These local queries remain usable with every provider inaccessible.
        with patch.object(app,'fetch',side_effect=AssertionError('remote access during local read')),patch.object(adapter,'collect',side_effect=AssertionError('remote access during local read')):
            self.assertEqual(app.catalog()[0]['bars'],1);self.assertEqual(app.bars(sid)[0]['close'],100)
    def test_routes_cli_legacy_alias_to_ccxt_and_keeps_venues_separate(self):
        rows=[dict(date='2020-01-01',open=100,high=110,low=90,close=105,volume=5)]
        with patch.object(adapter,'collect',return_value=('BTC/USDT',rows)) as collect:
            sid,_=app.download('binance','BTCUSDT','2020-01-01','2020-01-03')
            self.assertEqual(collect.call_args.args[0],'binance')
            app.download('ccxt','BTC/USDT','2020-01-01','2020-01-03',exchange='kraken')
        self.assertEqual(len(app.catalog()),2)
        self.assertEqual(app.bars(sid)[0]['volume'],5)
if __name__=='__main__':unittest.main()
