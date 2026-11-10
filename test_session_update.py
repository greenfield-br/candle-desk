import datetime as dt
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import market_data as store
import session_update as u
UTC=dt.timezone.utc
JOB=dict(id='BTCUSDT',symbol='BTC/USDT',provider='ccxt',exchange='binance')
class Incremental(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.old=store.DB;store.DB=Path(self.tmp.name)/'history.sqlite3'
 def tearDown(self):store.DB=self.old;self.tmp.cleanup()
 def refresh(self,rows,now):
  with patch.object(store,'download',return_value=('BTC/USDT','ccxt:binance','test',rows)):
   return u.refresh(JOB,'2026-10-01','2026-10-26',now)
 def test_snapshot_finalization_and_upsert(self):
  r=self.refresh([dict(date='2026-10-23',open=1,high=3,low=1,close=2)],dt.datetime(2026,10,23,22,tzinfo=UTC));sid=r['series_id']
  self.assertEqual(u.pending(sid),['2026-10-23'])
  self.refresh([dict(date='2026-10-23',open=1,high=4,low=1,close=3)],dt.datetime(2026,10,24,1,tzinfo=UTC))
  self.assertEqual(u.pending(sid),[]);self.assertEqual(len(store.bars(sid)),1);self.assertEqual(store.bars(sid)[0]['close'],3)
 def test_empty_retains_pending_even_after_new_day(self):
  r=self.refresh([dict(date='2026-10-23',close=2)],dt.datetime(2026,10,23,22,tzinfo=UTC));sid=r['series_id']
  self.assertEqual(self.refresh([],dt.datetime(2026,10,24,tzinfo=UTC))['status'],'no_new_data')
  self.refresh([dict(date='2026-10-24',close=3)],dt.datetime(2026,10,24,1,tzinfo=UTC))
  self.assertEqual(u.beginning(JOB,store.catalog(),'2017-01-01'),'2026-10-23')
  self.assertEqual(u.pending(sid),['2026-10-23','2026-10-24'])
 def test_sessions_holiday_and_early_close(self):
  job=dict(id='SPY',symbol='SPY',provider='yahoo')
  self.assertEqual(u.state(job,'2026-11-27',dt.datetime(2026,11,27,17,tzinfo=UTC)),'provisional')
  self.assertEqual(u.state(job,'2026-11-27',dt.datetime(2026,11,27,19,tzinfo=UTC)),'final')
  self.assertEqual(u.state(job,'2026-11-26',dt.datetime(2026,11,27,tzinfo=UTC)),'provisional')
 def test_published_series(self):
  self.assertEqual(u.state(dict(provider='fred'),'2026-10-23',dt.datetime(2026,10,23,tzinfo=UTC)),'published')
 def test_invalid_batch_atomic(self):
  with self.assertRaises(ValueError):self.refresh([dict(date='2026-10-23',close=1),dict(date='2026-10-24',close=None)],dt.datetime(2026,10,24,tzinfo=UTC))
  self.assertEqual(store.catalog(),[])
if __name__=='__main__':unittest.main()
